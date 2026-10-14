"""Offline-testable Yahoo Finance historical data acquisition and storage."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from numbers import Real
from pathlib import Path
from typing import Any, Callable, Mapping

import pandas as pd


class DataAcquisitionError(RuntimeError):
    """The remote data source could not return a response."""


class DatasetValidationError(ValueError):
    """The source response does not satisfy the QUANTLAB data contract."""


@dataclass(frozen=True)
class HistoricalDataset:
    ticker: str
    start: str
    end: str
    data: pd.DataFrame
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class StoredDataset:
    csv_path: Path
    metadata_path: Path
    sha256: str
    metadata: Mapping[str, Any]


REQUIRED_COLUMNS = (
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "Dividends",
    "Stock Splits",
)
OPTIONAL_COLUMNS = ("Adj Close",)
KNOWN_COLUMNS = frozenset((*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS))


def _iso_date(value: date | str, field: str) -> str:
    if isinstance(value, datetime):
        raise ValueError(f"{field} must be a calendar date without a time")
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a date or YYYY-MM-DD string")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise ValueError(f"{field} must use YYYY-MM-DD format") from error
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must use YYYY-MM-DD format")
    return value


def _validate_numeric_column(
    series: pd.Series,
    name: str,
    *,
    strictly_positive: bool = False,
    non_negative: bool = False,
    integer: bool = False,
) -> None:
    for position, value in enumerate(series):
        if pd.api.types.is_bool_dtype(type(value)) or not pd.api.types.is_number(value):
            raise DatasetValidationError(f"{name}[{position}] must be numeric")
        try:
            number = float(value)
        except (OverflowError, TypeError, ValueError) as error:
            raise DatasetValidationError(f"{name}[{position}] must be finite numeric data") from error
        if not math.isfinite(number):
            raise DatasetValidationError(f"{name}[{position}] must be finite")
        if strictly_positive and number <= 0:
            raise DatasetValidationError(f"{name}[{position}] must be greater than zero")
        if non_negative and number < 0:
            raise DatasetValidationError(f"{name}[{position}] cannot be negative")
        if integer and not number.is_integer():
            raise DatasetValidationError(f"{name}[{position}] must be an integer")


def _validate_additional_column(series: pd.Series, name: str) -> None:
    """Accept losslessly representable scalar source values, without semantics.

    Extra columns must be homogeneous strings or finite real numbers. Missing,
    boolean, mixed, and non-scalar values are rejected rather than coerced.
    These fields are retained as source data only; they are not ledger inputs.
    """
    value_kinds: set[str] = set()
    for position, value in enumerate(series):
        if isinstance(value, str):
            value_kinds.add("text")
        elif isinstance(value, Real) and not isinstance(value, bool):
            if not math.isfinite(float(value)):
                raise DatasetValidationError(
                    f"additional column {name!r}[{position}] must be finite"
                )
            value_kinds.add("numeric")
        else:
            raise DatasetValidationError(
                f"additional column {name!r}[{position}] must be a non-missing string "
                "or finite real number"
            )
    if len(value_kinds) > 1:
        raise DatasetValidationError(
            f"additional column {name!r} cannot mix text and numeric values"
        )


def validate_history(
    data: pd.DataFrame,
    *,
    start: date | str,
    end: date | str,
) -> pd.DataFrame:
    """Validate and copy an unadjusted daily OHLC/action response.

    ``start`` is inclusive and ``end`` is exclusive. This validates supplied
    rows but deliberately does not infer missing exchange sessions; no prices
    or corporate actions are filled, normalized, or adjusted.
    """
    start_iso = _iso_date(start, "start")
    end_iso = _iso_date(end, "end")
    start_date = date.fromisoformat(start_iso)
    end_date = date.fromisoformat(end_iso)
    if start_date >= end_date:
        raise ValueError("start must be earlier than end")
    if not isinstance(data, pd.DataFrame):
        raise TypeError("source response must be a pandas DataFrame")
    if data.empty:
        raise DatasetValidationError("source returned an empty dataset")
    if isinstance(data.columns, pd.MultiIndex):
        raise DatasetValidationError("multi-level columns are not supported for one ticker")
    if not data.columns.is_unique:
        raise DatasetValidationError("column names must be unique")
    for name in data.columns:
        if not isinstance(name, str) or not name.strip() or name != name.strip():
            raise DatasetValidationError("column names must be non-empty normalized strings")
    if not isinstance(data.index, pd.DatetimeIndex):
        raise DatasetValidationError("dataset index must be a DatetimeIndex")
    if data.index.hasnans:
        raise DatasetValidationError("dataset contains missing session dates")
    if not data.index.is_unique or not data.index.normalize().is_unique:
        raise DatasetValidationError("session dates must be unique")
    if not data.index.is_monotonic_increasing:
        raise DatasetValidationError("session dates must be in chronological order")
    if not data.index.equals(data.index.normalize()):
        raise DatasetValidationError("daily session timestamps must be normalized to midnight")

    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise DatasetValidationError(
            f"source response is missing required columns: {', '.join(missing)}"
        )
    additional_columns = [column for column in data.columns if column not in KNOWN_COLUMNS]

    session_dates = data.index.date
    if any(session < start_date or session >= end_date for session in session_dates):
        raise DatasetValidationError("source returned sessions outside [start, end)")

    for column in ("Open", "High", "Low", "Close"):
        _validate_numeric_column(data[column], column, strictly_positive=True)
    for column in ("Volume", "Dividends", "Stock Splits"):
        _validate_numeric_column(
            data[column], column, non_negative=True, integer=(column == "Volume")
        )
    if "Adj Close" in data.columns:
        _validate_numeric_column(data["Adj Close"], "Adj Close", strictly_positive=True)
    for column in additional_columns:
        _validate_additional_column(data[column], column)

    invalid_ohlc = (
        (data["Low"] > data[["Open", "Close"]].min(axis=1))
        | (data["High"] < data[["Open", "Close"]].max(axis=1))
        | (data["Low"] > data["High"])
    )
    if invalid_ohlc.any():
        raise DatasetValidationError("OHLC relationships are invalid")
    return data.copy(deep=True)


def download_history(
    ticker: str = "SPY",
    *,
    start: date | str,
    end: date | str,
    downloader: Callable[..., pd.DataFrame] | None = None,
    yfinance_version: str | None = None,
) -> HistoricalDataset:
    """Fetch and validate daily bars; pass ``downloader`` for offline tests."""
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError("ticker must be a non-empty string")
    ticker = ticker.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.^=_-]+", ticker):
        raise ValueError("ticker contains unsupported characters")
    start_iso = _iso_date(start, "start")
    end_iso = _iso_date(end, "end")
    if date.fromisoformat(start_iso) >= date.fromisoformat(end_iso):
        raise ValueError("start must be earlier than end")

    if downloader is None:
        try:
            import yfinance as yf

            downloader = yf.download
            installed_version = version("yfinance")
        except (ImportError, PackageNotFoundError) as error:
            raise DataAcquisitionError(
                "yfinance is not installed; install the project dependencies before acquisition"
            ) from error
        yfinance_version = installed_version
    elif yfinance_version is None:
        yfinance_version = "injected-downloader"

    parameters = {
        "start": start_iso,
        "end": end_iso,
        "interval": "1d",
        "auto_adjust": False,
        "actions": True,
        "back_adjust": False,
        "repair": False,
        "keepna": True,
        "prepost": False,
        "rounding": False,
        "progress": False,
        "multi_level_index": False,
        "group_by": "column",
    }
    try:
        response = downloader(ticker, **parameters)
    except Exception as error:
        raise DataAcquisitionError(
            f"Yahoo Finance request failed for {ticker} [{start_iso}, {end_iso})"
        ) from error

    validated = validate_history(response, start=start_iso, end=end_iso)
    metadata = {
        "ticker": ticker,
        "start": start_iso,
        "end": end_iso,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance via yfinance",
        "yfinance_version": yfinance_version,
        "parameters": {"ticker": ticker, **parameters},
        "timezone": str(validated.index.tz) if validated.index.tz is not None else None,
        "calendar_validation": "not_performed; missing sessions are not inferred",
    }
    return HistoricalDataset(ticker, start_iso, end_iso, validated, metadata)


def save_raw_dataset(
    dataset: HistoricalDataset, raw_dir: str | Path | None = None
) -> StoredDataset:
    """Save a CSV snapshot and JSON provenance sidecar without overwriting."""
    if not isinstance(dataset, HistoricalDataset):
        raise TypeError("dataset must be a HistoricalDataset")
    if raw_dir is None:
        raw_dir = Path(__file__).resolve().parents[1] / "data" / "raw"
    directory = Path(raw_dir)
    directory.mkdir(parents=True, exist_ok=True)

    safe_ticker = re.sub(r"[^A-Z0-9_-]", "_", dataset.ticker)
    stem = f"{safe_ticker}_{dataset.start}_{dataset.end}"
    csv_path = directory / f"{stem}.csv"
    metadata_path = directory / f"{stem}.metadata.json"
    csv_bytes = dataset.data.to_csv(index=True, index_label="Date").encode("utf-8")
    digest = hashlib.sha256(csv_bytes).hexdigest()
    metadata = {
        **dict(dataset.metadata),
        "csv_file": csv_path.name,
        "sha256": digest,
    }
    metadata_bytes = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8")

    created_csv = False
    try:
        with csv_path.open("xb") as csv_file:
            created_csv = True
            csv_file.write(csv_bytes)
        with metadata_path.open("xb") as metadata_file:
            metadata_file.write(metadata_bytes)
    except FileExistsError as error:
        if created_csv:
            csv_path.unlink(missing_ok=True)
        raise FileExistsError(
            f"refusing to overwrite existing dataset artifact: {error.filename}"
        ) from error
    except OSError:
        if created_csv:
            csv_path.unlink(missing_ok=True)
        raise

    return StoredDataset(csv_path, metadata_path, digest, metadata)
