from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from backend.data_loader import (
    DataAcquisitionError,
    DatasetValidationError,
    download_history,
    save_raw_dataset,
    validate_history,
)


START = "2025-01-02"
END = "2025-01-06"


def valid_response() -> pd.DataFrame:
    index = pd.DatetimeIndex(["2025-01-02", "2025-01-03"])
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.0, 102.0],
            "Adj Close": [100.5, 101.5],
            "Volume": [1_000, 1_200],
            "Dividends": [0.0, 0.0],
            "Stock Splits": [0.0, 0.0],
        },
        index=index,
    )


def fake_downloader(response, seen=None):
    def download(ticker, **kwargs):
        if seen is not None:
            seen["ticker"] = ticker
            seen.update(kwargs)
        return response.copy(deep=True)

    return download


def test_download_valid_dataset_with_explicit_unadjusted_actions_parameters():
    seen = {}
    source = valid_response()

    result = download_history(
        "spy",
        start=START,
        end=END,
        downloader=fake_downloader(source, seen),
        yfinance_version="1.7.0",
    )

    pd.testing.assert_frame_equal(result.data, source)
    assert result.ticker == "SPY"
    assert seen["ticker"] == "SPY"
    assert seen["start"] == START
    assert seen["end"] == END
    assert seen["interval"] == "1d"
    assert seen["auto_adjust"] is False
    assert seen["actions"] is True
    assert seen["back_adjust"] is False
    assert seen["repair"] is False
    assert seen["keepna"] is True
    assert seen["prepost"] is False
    assert seen["rounding"] is False
    assert seen["progress"] is False
    assert seen["multi_level_index"] is False
    assert result.metadata["yfinance_version"] == "1.7.0"


def test_empty_response_is_rejected():
    with pytest.raises(DatasetValidationError, match="empty dataset"):
        download_history(
            start=START,
            end=END,
            downloader=fake_downloader(valid_response().iloc[:0]),
        )


@pytest.mark.parametrize("missing_column", ["Close", "Dividends", "Stock Splits"])
def test_required_columns_are_rejected_when_missing(missing_column: str):
    source = valid_response().drop(columns=missing_column)

    with pytest.raises(DatasetValidationError, match="missing required columns"):
        validate_history(source, start=START, end=END)


@pytest.mark.parametrize(
    "index",
    [
        pd.DatetimeIndex(["2025-01-02", "2025-01-02"]),
        pd.DatetimeIndex(["2025-01-03", "2025-01-02"]),
    ],
)
def test_duplicate_or_unsorted_dates_are_rejected(index):
    source = valid_response()
    source.index = index

    with pytest.raises(DatasetValidationError, match="session dates"):
        validate_history(source, start=START, end=END)


@pytest.mark.parametrize(
    ("column", "values", "message"),
    [
        ("Open", [0.0, 101.0], "greater than zero"),
        ("High", [float("inf"), 103.0], "finite"),
        ("Close", [100.0, float("nan")], "finite"),
        ("Volume", [1000, -1], "cannot be negative"),
        ("Volume", [1000, 1.5], "integer"),
        ("Dividends", [0.0, -0.1], "cannot be negative"),
        ("Stock Splits", [0.0, float("inf")], "finite"),
    ],
)
def test_invalid_column_values_are_rejected(column, values, message):
    source = valid_response()
    source[column] = values

    with pytest.raises(DatasetValidationError, match=message):
        validate_history(source, start=START, end=END)


def test_invalid_ohlc_relationship_is_rejected():
    source = valid_response()
    source.loc[source.index[0], "High"] = 99.5

    with pytest.raises(DatasetValidationError, match="OHLC relationships"):
        validate_history(source, start=START, end=END)


def test_corporate_actions_are_preserved_without_adjustment():
    source = valid_response()
    source.loc[source.index[1], "Dividends"] = 0.25
    source.loc[source.index[0], "Stock Splits"] = 2.0
    source["Capital Gains"] = [0.0, 0.5]

    result = download_history(
        start=START,
        end=END,
        downloader=fake_downloader(source),
    )

    assert result.data.loc[source.index[1], "Dividends"] == 0.25
    assert result.data.loc[source.index[0], "Stock Splits"] == 2.0
    assert result.data["Close"].equals(source["Close"])
    assert result.data["Capital Gains"].equals(source["Capital Gains"])


def test_start_is_inclusive_and_end_is_exclusive():
    source = valid_response()
    with pytest.raises(DatasetValidationError, match=r"outside \[start, end\)"):
        validate_history(
            pd.concat(
                [
                    source,
                    pd.DataFrame(
                        {column: [value] for column, value in source.iloc[-1].items()},
                        index=pd.DatetimeIndex([END]),
                    ),
                ]
            ),
            start=START,
            end=END,
        )


def test_source_connection_error_is_wrapped_clearly():
    def broken_source(ticker, **kwargs):
        raise TimeoutError("network unavailable")

    with pytest.raises(DataAcquisitionError, match="Yahoo Finance request failed"):
        download_history(start=START, end=END, downloader=broken_source)


def test_valid_capital_gains_column_is_accepted_and_preserved():
    source = valid_response()
    source["Capital Gains"] = [0.0, 1.25]

    result = validate_history(source, start=START, end=END)

    pd.testing.assert_frame_equal(result, source)
    assert result["Capital Gains"].tolist() == [0.0, 1.25]


def test_invalid_ohlc_is_rejected_even_with_additional_columns():
    source = valid_response()
    source["Capital Gains"] = [0.0, 1.25]
    source.loc[source.index[0], "High"] = 98.0

    with pytest.raises(DatasetValidationError, match="OHLC relationships"):
        validate_history(source, start=START, end=END)


@pytest.mark.parametrize(
    "values",
    [
        [0.0, float("nan")],
        [0.0, float("inf")],
        [0.0, True],
        [0.0, None],
        [0.0, object()],
        [0.0, "text"],
    ],
)
def test_invalid_additional_column_values_are_rejected(values):
    source = valid_response()
    source["Capital Gains"] = values

    with pytest.raises(DatasetValidationError, match="additional column"):
        validate_history(source, start=START, end=END)


def test_additional_text_column_is_preserved_when_values_are_consistent():
    source = valid_response()
    source["Source Note"] = ["original A", "original B"]

    result = validate_history(source, start=START, end=END)

    assert result["Source Note"].tolist() == ["original A", "original B"]


def test_saved_csv_hash_and_metadata_are_consistent(tmp_path):
    source = valid_response()
    source["Capital Gains"] = [0.0, 1.25]
    dataset = download_history(
        start=START,
        end=END,
        downloader=fake_downloader(source),
        yfinance_version="1.7.0",
    )

    stored = save_raw_dataset(dataset, tmp_path)

    csv_bytes = stored.csv_path.read_bytes()
    file_metadata = json.loads(stored.metadata_path.read_text(encoding="utf-8"))
    assert stored.csv_path.parent == tmp_path
    assert stored.sha256 == hashlib.sha256(csv_bytes).hexdigest()
    assert file_metadata["sha256"] == stored.sha256
    assert file_metadata["ticker"] == "SPY"
    assert file_metadata["start"] == START
    assert file_metadata["end"] == END
    assert file_metadata["source"] == "Yahoo Finance via yfinance"
    assert file_metadata["yfinance_version"] == "1.7.0"
    assert file_metadata["parameters"]["auto_adjust"] is False
    assert file_metadata["parameters"]["actions"] is True
    assert datetime_from_iso(file_metadata["downloaded_at_utc"]) is not None
    persisted = pd.read_csv(stored.csv_path)
    assert "Capital Gains" in persisted.columns
    assert persisted["Capital Gains"].tolist() == [0.0, 1.25]


def datetime_from_iso(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)


def test_save_refuses_to_overwrite_existing_dataset(tmp_path):
    dataset = download_history(
        start=START,
        end=END,
        downloader=fake_downloader(valid_response()),
    )
    first = save_raw_dataset(dataset, tmp_path)
    original_csv = first.csv_path.read_bytes()
    original_metadata = first.metadata_path.read_bytes()

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        save_raw_dataset(dataset, tmp_path)

    assert first.csv_path.read_bytes() == original_csv
    assert first.metadata_path.read_bytes() == original_metadata
