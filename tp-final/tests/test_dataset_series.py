from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api import DatasetSnapshot, create_app


@dataclass
class SeriesProvider:
    dataset_id: str
    ticker: str
    data: pd.DataFrame

    def __call__(self, dataset_id: str) -> DatasetSnapshot:
        if dataset_id != self.dataset_id:
            raise KeyError(dataset_id)
        return DatasetSnapshot(
            dataset_id=dataset_id,
            ticker=self.ticker,
            sha256="a" * 64,
            source="synthetic test fixture",
            data=self.data.copy(deep=True),
        )


def close_history() -> pd.DataFrame:
    index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    close = [100.0, 102.5, 99.0, 104.0]
    return pd.DataFrame(
        {
            "Open": close,
            "High": [value + 1 for value in close],
            "Low": [value - 1 for value in close],
            "Close": close,
            "Volume": [1000] * 4,
            "Dividends": [0.0] * 4,
            "Stock Splits": [0.0] * 4,
        },
        index=index,
    )


@pytest.mark.parametrize(
    ("dataset_id", "ticker"),
    [("spy-2020-2025", "SPY"), ("qqq-2020-2025", "QQQ")],
)
def test_descriptive_series_returns_close_for_spy_and_qqq(dataset_id, ticker):
    client = TestClient(create_app(SeriesProvider(dataset_id, ticker, close_history())))

    response = client.get(f"/api/v1/datasets/{dataset_id}/series")

    assert response.status_code == 200
    body = response.json()
    assert body["dataset_id"] == dataset_id
    assert body["ticker"] == ticker
    assert body["sha256"] == "a" * 64
    assert body["first_date"] == "2024-01-02"
    assert body["last_date"] == "2024-01-05"
    assert body["session_count"] == 4
    assert body["points"] == [
        {"date": "2024-01-02", "close": 100.0},
        {"date": "2024-01-03", "close": 102.5},
        {"date": "2024-01-04", "close": 99.0},
        {"date": "2024-01-05", "close": 104.0},
    ]
    assert "path" not in response.text.lower()


def test_descriptive_series_filters_inclusive_dates():
    provider = SeriesProvider("spy-2020-2025", "SPY", close_history())
    response = TestClient(create_app(provider)).get(
        "/api/v1/datasets/spy-2020-2025/series",
        params={"start_date": "2024-01-03", "end_date": "2024-01-04"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_start"] == "2024-01-03"
    assert body["requested_end"] == "2024-01-04"
    assert [point["date"] for point in body["points"]] == ["2024-01-03", "2024-01-04"]
    assert [point["close"] for point in body["points"]] == [102.5, 99.0]


def test_descriptive_series_rejects_reversed_date_interval():
    provider = SeriesProvider("spy-2020-2025", "SPY", close_history())
    response = TestClient(create_app(provider)).get(
        "/api/v1/datasets/spy-2020-2025/series",
        params={"start_date": "2024-01-05", "end_date": "2024-01-02"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "start_date must not be after end_date"


def test_descriptive_series_rejects_unparseable_date():
    provider = SeriesProvider("spy-2020-2025", "SPY", close_history())
    response = TestClient(create_app(provider)).get(
        "/api/v1/datasets/spy-2020-2025/series",
        params={"start_date": "2024-13-40"},
    )

    assert response.status_code == 422


def test_descriptive_series_unknown_dataset_is_not_found():
    response = TestClient(create_app()).get("/api/v1/datasets/not-registered/series")

    assert response.status_code == 404
    assert response.json()["detail"] == "dataset_id is not registered"


@pytest.mark.parametrize("dataset_id", ["iwm-pending", "tlt-pending", "gld-pending"])
def test_descriptive_series_rejects_assets_without_descriptive_capability(dataset_id):
    response = TestClient(create_app()).get(f"/api/v1/datasets/{dataset_id}/series")

    assert response.status_code == 409
    assert "not enabled for descriptive analysis" in response.json()["detail"]


def test_descriptive_series_returns_clear_error_when_no_sessions_match():
    provider = SeriesProvider("spy-2020-2025", "SPY", close_history())
    response = TestClient(create_app(provider)).get(
        "/api/v1/datasets/spy-2020-2025/series",
        params={"start_date": "2023-01-01", "end_date": "2023-12-31"},
    )

    assert response.status_code == 422
    assert "no available sessions" in response.json()["detail"]
