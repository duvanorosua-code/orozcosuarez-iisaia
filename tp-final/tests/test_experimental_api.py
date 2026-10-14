from __future__ import annotations

import json
import math

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api import DatasetSnapshot, create_app
from backend.api_schemas import ExperimentalComparisonRequest
from backend.synthetic_data import generate_synthetic_history


SCENARIOS = ("uptrend", "sideways", "high_volatility")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_synthetic_scenarios_are_valid_and_reproducible(scenario):
    first = generate_synthetic_history(scenario, session_count=12, warmup_sessions=50)
    second = generate_synthetic_history(scenario, session_count=12, warmup_sessions=50)

    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 62
    assert first.index.is_monotonic_increasing
    assert (first["Close"] > 0).all()
    assert (first["Dividends"] == 0).all()
    assert (first["Stock Splits"] == 0).all()


def test_synthetic_scenarios_have_distinct_price_paths():
    paths = [
        generate_synthetic_history(scenario, session_count=40, warmup_sessions=50)["Close"]
        for scenario in SCENARIOS
    ]

    assert not paths[0].equals(paths[1])
    assert not paths[0].equals(paths[2])
    assert not paths[1].equals(paths[2])


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_experimental_comparison_returns_finite_json_for_both_strategies(scenario):
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/experimental/comparisons",
        json={
            "scenario": scenario,
            "initial_capital": 100_000,
            "session_count": 80,
            "transaction_cost_rate": 0.001,
            "short_window": 5,
            "long_window": 20,
        },
    )

    assert response.status_code == 200, response.text
    body = json.loads(response.content)
    assert body == response.json()
    assert body["mode"] == "experimental"
    assert body["data_origin"] == "synthetic"
    assert body["scenario"] == scenario
    assert "datos sintéticos" in body["notice"]
    assert body["dataset"]["ticker"] == "SYNTHETIC"
    assert body["dataset"]["dataset_id"] == f"synthetic-{scenario}"
    assert len(body["dataset"]["sha256"]) == 64
    assert body["configuration"]["session_count"] == 80
    assert body["configuration"]["initial_capital"] == 100_000
    assert body["configuration"]["transaction_cost_rate"] == 0.001
    assert len(body["evaluation_dates"]) == 80

    for strategy_key in ("buy_and_hold", "sma_crossover"):
        result = body[strategy_key]
        assert [point["date"] for point in result["equity_curve"]] == body["evaluation_dates"]
        assert result["equity_curve"]
        assert result["executions"]
        assert all(execution["fee"] == pytest.approx(execution["notional"] * 0.001) for execution in result["executions"])
        assert set(result["metrics"]) >= {
            "cumulative_return", "annualized_return", "annualized_volatility",
            "maximum_drawdown", "valuation_intervals", "unavailable_reasons",
        }
        assert result["metrics"]["cumulative_return"] == pytest.approx(
            result["equity_curve"][-1]["equity"] / 100_000 - 1
        )
        # The metrics contract counts each evaluated Close as an interval
        # from initial capital, so N evaluated sessions produce N intervals.
        assert result["metrics"]["valuation_intervals"] == 80

    def assert_finite_json(value):
        if isinstance(value, dict):
            for item in value.values():
                assert_finite_json(item)
        elif isinstance(value, list):
            for item in value:
                assert_finite_json(item)
        elif isinstance(value, (float, int)) and not isinstance(value, bool):
            assert math.isfinite(value)

    assert_finite_json(body)


def test_experimental_comparison_is_reproducible():
    client = TestClient(create_app())
    request = {"scenario": "sideways", "session_count": 30, "short_window": 5, "long_window": 10}

    first = client.post("/api/v1/experimental/comparisons", json=request)
    second = client.post("/api/v1/experimental/comparisons", json=request)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_252_session_experimental_comparison_never_overspends(scenario):
    response = TestClient(create_app()).post(
        "/api/v1/experimental/comparisons",
        json={
            "scenario": scenario,
            "initial_capital": 1_000_000,
            "session_count": 252,
            "transaction_cost_rate": 0.001,
            "short_window": 20,
            "long_window": 50,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scenario"] == scenario
    assert body["configuration"]["initial_capital"] == 1_000_000
    assert body["configuration"]["session_count"] == 252
    assert body["configuration"]["transaction_cost_rate"] == 0.001
    assert body["configuration"]["short_window"] == 20
    assert body["configuration"]["long_window"] == 50

    for strategy_key in ("buy_and_hold", "sma_crossover"):
        available_cash = 1_000_000.0
        result = body[strategy_key]
        for execution in result["executions"]:
            assert execution["fee"] == pytest.approx(execution["notional"] * 0.001)
            if execution["side"] == "buy":
                available_cash -= execution["notional"] + execution["fee"]
            else:
                available_cash += execution["notional"] - execution["fee"]
            assert available_cash >= 0
        assert result["final_cash"] == pytest.approx(available_cash)


@pytest.mark.parametrize(
    "overrides",
    [
        {"scenario": "unknown"},
        {"initial_capital": 0},
        {"transaction_cost_rate": 1},
        {"session_count": 1},
        {"session_count": 2001},
        {"short_window": 20, "long_window": 20},
        {"long_window": 501},
        {"initial_capital": True},
    ],
)
def test_invalid_experimental_parameters_are_rejected(overrides):
    request = {
        "scenario": "uptrend", "initial_capital": 1000, "session_count": 20,
        "transaction_cost_rate": 0.001, "short_window": 5, "long_window": 10,
    }
    request.update(overrides)

    response = TestClient(create_app()).post("/api/v1/experimental/comparisons", json=request)

    assert response.status_code == 422
    assert "buy_and_hold" not in response.json()


@pytest.mark.parametrize("field", ["initial_capital", "transaction_cost_rate"])
def test_experimental_schema_rejects_nonfinite_numbers(field):
    request = {
        "scenario": "uptrend", "initial_capital": 1000, "session_count": 20,
        "transaction_cost_rate": 0.001, "short_window": 5, "long_window": 10,
    }
    request[field] = float("inf")

    with pytest.raises(ValueError, match="finite|Input should be a finite number"):
        ExperimentalComparisonRequest(**request)


def test_historical_comparison_still_blocks_unprocessed_dividends():
    index = pd.bdate_range("2025-01-02", periods=70)
    close = [100.0] * 70
    data = pd.DataFrame(
        {
            "Open": close, "High": [101.0] * 70, "Low": [99.0] * 70,
            "Close": close, "Dividends": [0.0] * 70, "Stock Splits": [0.0] * 70,
        },
        index=index,
    )
    data.iloc[60, data.columns.get_loc("Dividends")] = 0.25

    def provider(dataset_id: str) -> DatasetSnapshot:
        if dataset_id != "spy-2020-2025":
            raise KeyError(dataset_id)
        return DatasetSnapshot(dataset_id, "SPY", "a" * 64, "synthetic test fixture", data.copy())

    response = TestClient(create_app(provider)).post(
        "/api/v1/comparisons",
        json={
            "dataset_id": "spy-2020-2025", "initial_capital": 1000,
            "evaluation_start": "2025-03-27", "evaluation_end": "2025-04-09",
            "transaction_cost_rate": 0.001, "short_window": 5, "long_window": 50,
        },
    )

    assert response.status_code == 409
    assert "does not process and reconcile corporate actions" in response.json()["detail"]
    assert "buy_and_hold" not in response.json()
