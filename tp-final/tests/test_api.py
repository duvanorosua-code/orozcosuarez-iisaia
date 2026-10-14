from __future__ import annotations

import json
import math
from dataclasses import dataclass
from dataclasses import field

import pandas as pd
import pytest
import numpy as np
from fastapi.testclient import TestClient

import backend.api as api_module
from backend.api import DatasetSnapshot, create_app
from backend.api_schemas import ComparisonRequest


def make_data(length: int = 70) -> pd.DataFrame:
    closes = [100.0] * 30 + [120.0] * 20 + [120.0] * 8 + [90.0] * 12
    closes = closes[:length]
    index = pd.date_range("2025-01-02", periods=length, freq="B")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [price + 1 for price in closes],
            "Low": [price - 1 for price in closes],
            "Close": closes,
        },
        index=index,
    )


def make_summary_data() -> pd.DataFrame:
    index = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"])
    closes = [100.0, 110.0, 99.0, 108.0]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [value + 1 for value in closes],
            "Low": [value - 1 for value in closes],
            "Close": closes,
            "Volume": [1000, 1000, 1000, 1000],
            "Dividends": [0.0, 2.0, 0.0, 0.0],
            "Stock Splits": [0.0, 0.0, 2.0, 0.0],
        },
        index=index,
    )


@dataclass
class Provider:
    data: pd.DataFrame
    requested_ids: list[str] = field(default_factory=list)

    def __call__(self, dataset_id: str) -> DatasetSnapshot:
        self.requested_ids.append(dataset_id)
        if dataset_id != "synthetic-test":
            raise KeyError(dataset_id)
        return DatasetSnapshot(
            dataset_id=dataset_id,
            ticker="SYNTH",
            sha256="a" * 64,
            source="synthetic fixture",
            data=self.data.copy(deep=True),
        )


@pytest.fixture
def client():
    return TestClient(create_app(Provider(make_data())))


def payload(**overrides):
    request = {
        "dataset_id": "synthetic-test",
        "initial_capital": 1000,
        "evaluation_start": "2025-03-13",
        "evaluation_end": "2025-03-27",
        "transaction_cost_rate": 0.001,
        "short_window": 20,
        "long_window": 50,
    }
    request.update(overrides)
    return request


def test_comparison_returns_both_strategies_and_effective_configuration():
    provider = Provider(make_data())
    client = TestClient(create_app(provider))
    response = client.post("/api/v1/comparisons", json=payload())

    assert response.status_code == 200
    body = json.loads(response.content)
    assert body == response.json()
    assert provider.requested_ids == ["synthetic-test"]
    assert body["configuration"] == {
        "dataset_id": "synthetic-test",
        "initial_capital": 1000,
        "transaction_cost_rate": 0.001,
        "evaluation_start": "2025-03-13",
        "evaluation_end": "2025-03-27",
        "short_window": 20,
        "long_window": 50,
    }
    assert body["dataset"]["sha256"] == "a" * 64
    assert body["evaluation_dates"][0] == "2025-03-13"
    assert body["evaluation_dates"][-1] == "2025-03-27"
    assert body["buy_and_hold"]["equity_curve"]
    assert body["sma_crossover"]["equity_curve"]
    expected_metric_fields = {
        "cumulative_return",
        "annualized_return",
        "annualized_volatility",
        "maximum_drawdown",
        "valuation_intervals",
        "unavailable_reasons",
    }
    for strategy_name in ("buy_and_hold", "sma_crossover"):
        strategy = body[strategy_name]
        assert expected_metric_fields <= strategy["metrics"].keys()
        assert strategy["metrics"]["cumulative_return"] is not None
        assert strategy["metrics"]["maximum_drawdown"] is not None

    assert [point["date"] for point in body["buy_and_hold"]["equity_curve"]] == body[
        "evaluation_dates"
    ]
    assert [point["date"] for point in body["sma_crossover"]["equity_curve"]] == body[
        "evaluation_dates"
    ]
    assert body["buy_and_hold"]["executions"][0]["session"] == "2025-03-13"

    def assert_finite_json_values(value):
        if isinstance(value, dict):
            for item in value.values():
                assert_finite_json_values(item)
        elif isinstance(value, list):
            for item in value:
                assert_finite_json_values(item)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            assert math.isfinite(value)

    assert_finite_json_values(body)


@pytest.mark.parametrize(
    "overrides",
    [
        {"initial_capital": 0},
        {"initial_capital": True},
        {"transaction_cost_rate": 1},
        {"transaction_cost_rate": False},
        {"short_window": 50, "long_window": 50},
        {"short_window": 2.5},
        {"evaluation_start": "not-a-date"},
        {"unknown_path": "C:/private/data.csv"},
    ],
)
def test_invalid_parameters_are_rejected_without_result(client, overrides):
    response = client.post("/api/v1/comparisons", json=payload(**overrides))

    assert response.status_code == 422
    assert "buy_and_hold" not in response.json()
    assert "sma_crossover" not in response.json()


def test_comparison_request_rejects_infinite_initial_capital():
    with pytest.raises(ValueError, match="finite|Input should be a finite number"):
        ComparisonRequest(
            dataset_id="synthetic-test",
            initial_capital=float("inf"),
            evaluation_start="2025-03-13",
        )


def test_cors_preflight_allows_only_the_local_frontend_origin(client):
    allowed = client.options(
        "/api/v1/comparisons",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    rejected = client.options(
        "/api/v1/comparisons",
        headers={
            "Origin": "http://localhost:5501",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5500"
    assert "access-control-allow-origin" not in rejected.headers


def test_cors_preflight_allows_summary_get_from_local_frontend(client):
    response = client.options(
        "/api/v1/datasets/synthetic-test/summary",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "accept",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5500"


def test_summary_returns_descriptive_close_statistics_without_running_strategies(monkeypatch):
    original = make_summary_data()
    provider = Provider(original.copy(deep=True))
    client = TestClient(create_app(provider))
    monkeypatch.setattr(
        api_module, "compare_strategies",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("strategy engine called")),
    )

    response = client.get("/api/v1/datasets/synthetic-test/summary")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert b"NaN" not in response.content and b"Infinity" not in response.content
    body = response.json()
    returns = pd.Series([0.1, -0.1, 108 / 99 - 1])
    assert body["dataset_id"] == "synthetic-test"
    assert body["ticker"] == "SYNTH"
    assert body["sha256"] == "a" * 64
    assert body["session_count"] == 4
    assert body["first_date"] == "2025-01-02"
    assert body["last_date"] == "2025-01-07"
    assert body["initial_close"] == 100
    assert body["final_close"] == 108
    assert body["price_change"] == pytest.approx(0.08)
    assert body["annualized_volatility"] == pytest.approx(returns.std(ddof=1) * np.sqrt(252))
    assert body["maximum_drawdown"] == pytest.approx(-0.1)
    assert body["dividend_events"] == 1
    assert body["split_events"] == 1
    assert body["price_basis"] == "Close"
    assert body["includes_distributions"] is False
    assert body["is_strategy_result"] is False
    assert "no representa rentabilidad total" in body["interpretation"]
    assert provider.requested_ids == ["synthetic-test"]
    pd.testing.assert_frame_equal(provider.data, original)


def test_summary_unknown_dataset_is_not_found():
    client = TestClient(create_app(Provider(make_summary_data())))

    response = client.get("/api/v1/datasets/missing-dataset/summary")

    assert response.status_code == 404


@pytest.mark.parametrize("invalid_close", [0.0, float("nan"), float("inf")])
def test_summary_rejects_invalid_prices(invalid_close):
    data = make_summary_data()
    data.iloc[1, data.columns.get_loc("Close")] = invalid_close
    # Preserve OHLC consistency so this specifically tests price validation.
    data.iloc[1, data.columns.get_loc("Open")] = invalid_close
    data.iloc[1, data.columns.get_loc("High")] = invalid_close
    data.iloc[1, data.columns.get_loc("Low")] = invalid_close
    client = TestClient(create_app(Provider(data)))

    response = client.get("/api/v1/datasets/synthetic-test/summary")

    assert response.status_code == 422
    assert "summary" not in response.json()


def test_summary_requires_enough_observations_for_sample_volatility():
    client = TestClient(create_app(Provider(make_summary_data().iloc[:2])))

    response = client.get("/api/v1/datasets/synthetic-test/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["price_change"] is not None
    assert body["maximum_drawdown"] is not None
    assert body["annualized_volatility"] is None
    assert "annualized_volatility" in body["unavailable_reasons"]


def test_unknown_dataset_is_not_found(client):
    response = client.post(
        "/api/v1/comparisons", json=payload(dataset_id="missing-dataset")
    )

    assert response.status_code == 404
    assert "buy_and_hold" not in response.json()


def test_insufficient_warmup_and_out_of_range_dates_are_rejected(client):
    too_early = client.post(
        "/api/v1/comparisons",
        json=payload(evaluation_start="2025-01-16", evaluation_end=None),
    )
    outside = client.post(
        "/api/v1/comparisons",
        json=payload(evaluation_start="2025-05-01", evaluation_end=None),
    )

    assert too_early.status_code == 422
    assert "warmup" in too_early.json()["detail"]
    assert outside.status_code == 422
    for response in (too_early, outside):
        assert "buy_and_hold" not in response.json()
        assert "sma_crossover" not in response.json()


def test_invalid_ohlc_is_rejected_without_result():
    data = make_data()
    data.loc[data.index[55], "Low"] = 500
    client = TestClient(create_app(Provider(data)))

    response = client.post("/api/v1/comparisons", json=payload())

    assert response.status_code == 422
    assert "OHLC relationships" in response.json()["detail"]
    assert "buy_and_hold" not in response.json()


@pytest.mark.parametrize(
    ("column", "event_value"), [("Dividends", 0.25), ("Stock Splits", 2.0)]
)
def test_unprocessed_corporate_actions_are_blocked(column, event_value):
    data = make_data()
    data[column] = 0.0
    data.loc[data.index[55], column] = event_value
    client = TestClient(create_app(Provider(data)))

    response = client.post("/api/v1/comparisons", json=payload())

    assert response.status_code == 409
    assert "does not process and reconcile corporate actions" in response.json()["detail"]
    assert "buy_and_hold" not in response.json()
    assert "sma_crossover" not in response.json()


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), -1, True, "bad"])
@pytest.mark.parametrize("column", ["Dividends", "Stock Splits"])
def test_invalid_corporate_action_values_are_rejected(column, value):
    data = make_data()
    data[column] = [0.0] * len(data)
    # Use object dtype so malformed source values reach the strategy validator.
    data[column] = data[column].astype(object)
    data.iloc[55, data.columns.get_loc(column)] = value
    client = TestClient(create_app(Provider(data)))

    response = client.post("/api/v1/comparisons", json=payload())

    assert response.status_code == 422
    assert "buy_and_hold" not in response.json()
    assert "sma_crossover" not in response.json()


def test_response_is_strict_json_with_iso_dates_and_no_nonfinite_values(client):
    response = client.post("/api/v1/comparisons", json=payload())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert b"NaN" not in response.content
    assert b"Infinity" not in response.content
    body = response.json()
    for point in body["sma_crossover"]["equity_curve"]:
        assert isinstance(point["date"], str)
        assert len(point["date"]) == 10
    assert [point["date"] for point in body["buy_and_hold"]["equity_curve"]] == body[
        "evaluation_dates"
    ]
    assert [point["date"] for point in body["sma_crossover"]["equity_curve"]] == body[
        "evaluation_dates"
    ]
