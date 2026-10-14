from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api import DatasetSnapshot, _load_registered_dataset_files, create_app
from backend.dataset_catalog import DATASET_CATALOG


def make_spy_fixture() -> pd.DataFrame:
    index = pd.bdate_range("2025-01-02", periods=70)
    closes = [100.0 + position * 0.1 for position in range(70)]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [value + 1 for value in closes],
            "Low": [value - 1 for value in closes],
            "Close": closes,
            "Volume": [1000] * 70,
            "Dividends": [0.0] * 70,
            "Stock Splits": [0.0] * 70,
        },
        index=index,
    )


def make_qqq_fixture() -> pd.DataFrame:
    index = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    closes = [100.0, 110.0, 99.0, 108.0]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [value + 1 for value in closes],
            "Low": [value - 1 for value in closes],
            "Close": closes,
            "Volume": [1000] * 4,
            "Dividends": [0.0, 0.0, 0.5, 0.0],
            "Stock Splits": [0.0] * 4,
        },
        index=index,
    )


class CatalogProvider:
    def __init__(self):
        self.data = make_spy_fixture()
        self.qqq_data = make_qqq_fixture()
        self.calls: list[str] = []
        self.sha256 = hashlib.sha256(b"synthetic injected SPY snapshot").hexdigest()

    def __call__(self, dataset_id: str) -> DatasetSnapshot:
        self.calls.append(dataset_id)
        fixtures = {
            "spy-2020-2025": ("SPY", self.data),
            "qqq-2020-2025": ("QQQ", self.qqq_data),
        }
        if dataset_id not in fixtures:
            raise KeyError(dataset_id)
        ticker, data = fixtures[dataset_id]
        return DatasetSnapshot(
            dataset_id=dataset_id,
            ticker=ticker,
            sha256=hashlib.sha256(f"synthetic injected {ticker} snapshot".encode()).hexdigest(),
            source="synthetic test fixture",
            data=data.copy(deep=True),
        )


def test_catalog_lists_five_assets_with_consistent_states_and_capabilities():
    provider = CatalogProvider()
    response = TestClient(create_app(provider)).get("/api/v1/datasets")

    assert response.status_code == 200
    items = response.json()["datasets"]
    assert [item["ticker"] for item in items] == ["SPY", "QQQ", "IWM", "TLT", "GLD"]
    spy, qqq, *pending = items
    assert [item["name"] for item in items] == [
        "SPDR S&P 500 ETF Trust",
        "Invesco QQQ Trust",
        "iShares Russell 2000 ETF",
        "iShares 20+ Year Treasury Bond ETF",
        "SPDR Gold Shares",
    ]
    assert [item["asset_type"] for item in items] == [
        "equity_etf", "equity_etf", "equity_etf", "fixed_income_etf", "commodity_etf"
    ]
    assert [item["exposure"] for item in items] == [
        "Acciones estadounidenses de gran capitalización; índice S&P 500.",
        "Acciones de grandes empresas no financieras del Nasdaq-100.",
        "Acciones estadounidenses de pequeña capitalización del Russell 2000.",
        "Bonos del Tesoro de Estados Unidos con vencimientos superiores a 20 años.",
        "Exposición al precio del oro físico, menos gastos del fondo.",
    ]
    assert all(item["currency"] == "USD" for item in items)
    assert spy["dataset_id"] == "spy-2020-2025"
    assert spy["validation_status"] == "descriptive_only"
    assert spy["capabilities"] == {
        "descriptive_analysis": True,
        "historical_simulation": False,
    }
    assert "descriptivo disponible" in spy["validation_note"]
    assert "bloqueada" in spy["validation_note"]
    assert spy["available_start"] == "2025-01-02"
    assert spy["available_end"] == "2025-04-09"
    assert spy["sha256"] == provider.sha256
    assert qqq["dataset_id"] == "qqq-2020-2025"
    assert qqq["validation_status"] == "descriptive_only"
    assert qqq["capabilities"] == {
        "descriptive_analysis": True,
        "historical_simulation": False,
    }
    assert qqq["available_start"] == "2024-01-02"
    assert qqq["available_end"] == "2024-01-05"
    assert qqq["sha256"] is not None
    assert all(item["validation_status"] == "pending_validation" for item in pending)
    assert all(item["capabilities"] == {"descriptive_analysis": False, "historical_simulation": False} for item in pending)
    assert all(item["available_start"] is None and item["available_end"] is None for item in pending)
    assert all(item["sha256"] is None for item in pending)
    assert all("No hay datos históricos validados registrados" in item["validation_note"] for item in pending)
    assert provider.calls == ["spy-2020-2025", "qqq-2020-2025"]


def test_catalog_metadata_endpoint_and_pending_dataset_isolation():
    provider = CatalogProvider()
    client = TestClient(create_app(provider))

    spy = client.get("/api/v1/datasets/spy-2020-2025")
    qqq = client.get("/api/v1/datasets/qqq-2020-2025")

    assert spy.status_code == qqq.status_code == 200
    assert spy.json()["ticker"] == "SPY"
    assert spy.json()["sha256"] == provider.sha256
    assert qqq.json()["ticker"] == "QQQ"
    assert qqq.json()["sha256"] is not None
    assert qqq.json()["available_start"] == "2024-01-02"
    assert qqq.json()["validation_status"] == "descriptive_only"

    for response in (spy, qqq):
        serialized = json.dumps(response.json())
        assert "path" not in serialized.lower()
        assert "data/raw" not in serialized.lower()
        assert "c:\\" not in serialized.lower()


def test_unknown_catalog_id_is_not_found():
    client = TestClient(create_app(CatalogProvider()))

    assert client.get("/api/v1/datasets/missing").status_code == 404
    assert client.get("/api/v1/datasets/missing/summary").status_code == 404


def test_spy_summary_is_available_and_descriptive_only():
    provider = CatalogProvider()
    client = TestClient(create_app(provider))

    response = client.get("/api/v1/datasets/spy-2020-2025/summary")

    assert response.status_code == 200
    assert response.json()["dataset_id"] == "spy-2020-2025"
    assert response.json()["session_count"] == 70
    assert response.json()["includes_distributions"] is False
    assert response.json()["is_strategy_result"] is False


def test_pending_datasets_reject_summary_and_historical_comparison():
    provider = CatalogProvider()
    client = TestClient(create_app(provider))

    summary = client.get("/api/v1/datasets/iwm-pending/summary")
    comparison = client.post(
        "/api/v1/comparisons",
        json={
            "dataset_id": "iwm-pending",
            "initial_capital": 1000,
            "evaluation_start": "2025-03-27",
            "short_window": 5,
            "long_window": 50,
        },
    )

    assert summary.status_code == 409
    assert "pending validation" in summary.json()["detail"]
    assert comparison.status_code == 409
    assert "pending validation" in comparison.json()["detail"]
    assert provider.calls == []


def test_qqq_summary_uses_only_qqq_fixture_and_keeps_simulation_blocked():
    provider = CatalogProvider()
    client = TestClient(create_app(provider))

    response = client.get("/api/v1/datasets/qqq-2020-2025/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["dataset_id"] == "qqq-2020-2025"
    assert body["ticker"] == "QQQ"
    assert body["name"] == "Invesco QQQ Trust"
    assert body["session_count"] == 4
    assert body["first_date"] == "2024-01-02"
    assert body["last_date"] == "2024-01-05"
    assert body["initial_close"] == 100
    assert body["final_close"] == 108
    assert body["price_change"] == pytest.approx(0.08)
    qqq_returns = pd.Series([0.1, -0.1, 108 / 99 - 1])
    assert body["annualized_volatility"] == pytest.approx(qqq_returns.std(ddof=1) * 252**0.5)
    assert body["maximum_drawdown"] == pytest.approx(-0.1)
    assert body["dividend_events"] == 1
    assert body["split_events"] == 0
    assert body["includes_distributions"] is False
    assert body["is_strategy_result"] is False

    comparison = client.post(
        "/api/v1/comparisons",
        json={
            "dataset_id": "qqq-2020-2025",
            "initial_capital": 1000,
            "evaluation_start": "2024-01-05",
            "short_window": 2,
            "long_window": 3,
        },
    )
    assert comparison.status_code == 409
    assert "historical simulation is not enabled" in comparison.json()["detail"]


def test_qqq_summary_adjusts_requested_dates_to_available_sessions():
    client = TestClient(create_app(CatalogProvider()))

    response = client.get(
        "/api/v1/datasets/qqq-2020-2025/summary",
        params={"start_date": "2024-01-04", "end_date": "2024-01-07"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_start"] == "2024-01-04"
    assert body["requested_end"] == "2024-01-07"
    assert body["first_date"] == "2024-01-04"
    assert body["last_date"] == "2024-01-05"
    assert body["session_count"] == 2
    assert "inclusivo" in body["period_note"]
    assert "fecha final ajustada a 2024-01-05" in body["period_note"]
    assert body["annualized_volatility"] is None
    assert "annualized_volatility" in body["unavailable_reasons"]


def test_qqq_missing_or_invalid_local_artifacts_do_not_enable_descriptive_analysis(tmp_path: Path):
    qqq = next(item for item in DATASET_CATALOG if item.ticker == "QQQ")
    with pytest.raises(FileNotFoundError):
        _load_registered_dataset_files(qqq, Path("missing-test-directory"))

    data = make_qqq_fixture()
    data.index.name = "Date"
    csv_bytes = data.to_csv(index=True, index_label="Date").encode("utf-8")
    expected_hash = hashlib.sha256(csv_bytes).hexdigest()
    test_definition = replace(qqq, expected_sha256=expected_hash)
    csv_path = tmp_path / qqq.csv_filename
    metadata_path = tmp_path / qqq.metadata_filename
    csv_path.write_bytes(csv_bytes)
    metadata_path.write_text(json.dumps({
        "ticker": "QQQ", "start": "2020-01-01", "end": "2025-01-01",
        "csv_file": qqq.csv_filename, "sha256": expected_hash,
        "source": "synthetic test fixture",
    }), encoding="utf-8")
    loaded = _load_registered_dataset_files(test_definition, tmp_path)
    assert loaded.ticker == "QQQ"
    with pytest.raises(ValueError, match="registered SHA-256"):
        _load_registered_dataset_files(replace(test_definition, expected_sha256="0" * 64), tmp_path)
    valid_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    for key, invalid_value in (("ticker", "SPY"), ("start", "2019-01-01"), ("end", "2025-01-02")):
        metadata_path.write_text(
            json.dumps({**valid_metadata, key: invalid_value}), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="identity or period mismatch"):
            _load_registered_dataset_files(test_definition, tmp_path)
    metadata_path.write_text(json.dumps(valid_metadata), encoding="utf-8")
    csv_path.write_bytes(csv_bytes + b"\n")
    with pytest.raises(ValueError, match="SHA-256"):
        _load_registered_dataset_files(test_definition, tmp_path)


def test_qqq_catalog_falls_back_to_pending_when_provider_hash_is_invalid():
    provider = CatalogProvider()
    original_call = provider.__call__

    def invalid_hash_provider(dataset_id: str) -> DatasetSnapshot:
        snapshot = original_call(dataset_id)
        if dataset_id == "qqq-2020-2025":
            return DatasetSnapshot(
                snapshot.dataset_id, snapshot.ticker, "invalid", snapshot.source, snapshot.data
            )
        return snapshot

    client = TestClient(create_app(invalid_hash_provider))
    items = client.get("/api/v1/datasets").json()["datasets"]
    qqq = next(item for item in items if item["ticker"] == "QQQ")
    assert qqq["validation_status"] == "pending_validation"
    assert qqq["capabilities"] == {
        "descriptive_analysis": False,
        "historical_simulation": False,
    }
    assert qqq["available_start"] is None and qqq["sha256"] is None
    assert "no está habilitado" in qqq["validation_note"]
    failed_summary = client.get("/api/v1/datasets/qqq-2020-2025/summary")
    assert failed_summary.status_code == 503
    assert "price_change" not in failed_summary.json()

    def missing_file_provider(dataset_id: str) -> DatasetSnapshot:
        if dataset_id == "qqq-2020-2025":
            raise FileNotFoundError("synthetic missing registered file")
        return CatalogProvider()(dataset_id)

    missing_client = TestClient(create_app(missing_file_provider))
    missing_catalog = missing_client.get("/api/v1/datasets").json()["datasets"]
    missing_qqq = next(item for item in missing_catalog if item["ticker"] == "QQQ")
    assert missing_qqq["validation_status"] == "pending_validation"
    assert missing_qqq["capabilities"]["descriptive_analysis"] is False
    missing_summary = missing_client.get("/api/v1/datasets/qqq-2020-2025/summary")
    assert missing_summary.status_code == 503
    assert "price_change" not in missing_summary.json()


def test_spy_historical_comparison_remains_blocked_without_loading_or_result():
    provider = CatalogProvider()
    client = TestClient(create_app(provider))

    response = client.post(
        "/api/v1/comparisons",
        json={
            "dataset_id": "spy-2020-2025",
            "initial_capital": 1000,
            "evaluation_start": "2025-03-27",
            "short_window": 5,
            "long_window": 50,
        },
    )

    assert response.status_code == 409
    assert "does not process and reconcile corporate actions" in response.json()["detail"]
    assert "buy_and_hold" not in response.json()
    assert provider.calls == []
