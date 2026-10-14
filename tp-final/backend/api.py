"""FastAPI application for comparing QUANTLAB investment strategies."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.api_schemas import (
    ComparisonRequest,
    ComparisonResponse,
    ClosePricePoint,
    DatasetCapabilities,
    DatasetCatalogItem,
    DatasetCatalogResponse,
    ExperimentalComparisonRequest,
    ExperimentalComparisonResponse,
    ExperimentalConfiguration,
    DatasetSummaryResponse,
    DatasetPriceSeriesResponse,
    DatasetIdentity,
    EffectiveConfiguration,
    EquityPoint,
    ExecutionOutput,
    MetricsOutput,
    StrategyOutput,
)
from backend.comparison import StrategyEvaluation, StrategyComparison, compare_strategies
from backend.data_loader import DatasetValidationError, validate_history
from backend.dataset_catalog import DATASET_CATALOG, DatasetDefinition, get_dataset_definition
from backend.synthetic_data import generate_synthetic_history


@dataclass(frozen=True)
class DatasetSnapshot:
    """An allow-listed dataset plus its immutable provenance identity."""

    dataset_id: str
    ticker: str
    sha256: str
    source: str
    data: pd.DataFrame


DatasetProvider = Callable[[str], DatasetSnapshot]


def _load_allowlisted_dataset(dataset_id: str) -> DatasetSnapshot:
    """Load a cataloged local snapshot; never accept paths from a request."""
    definition = get_dataset_definition(dataset_id)
    if definition is None or not definition.csv_filename or not definition.metadata_filename:
        raise KeyError(dataset_id)
    raw_dir = Path(__file__).resolve().parents[1] / "data" / "raw"
    return _load_registered_dataset_files(definition, raw_dir)


def _load_registered_dataset_files(
    definition: DatasetDefinition,
    raw_dir: str | Path,
) -> DatasetSnapshot:
    """Read an allow-listed artifact and verify its registered provenance."""
    if not definition.csv_filename or not definition.metadata_filename:
        raise FileNotFoundError("registered dataset artifacts are not configured")
    directory = Path(raw_dir)
    csv_path = directory / definition.csv_filename
    metadata_path = directory / definition.metadata_filename
    if not csv_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"registered dataset {definition.dataset_id!r} is unavailable")

    raw_bytes = csv_path.read_bytes()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if metadata.get("sha256") != digest or metadata.get("csv_file") != csv_path.name:
        raise ValueError(f"registered dataset {definition.dataset_id!r} failed SHA-256 verification")
    expected_metadata = {
        "ticker": definition.ticker,
        "start": definition.requested_start,
        "end": definition.requested_end,
    }
    if any(
        expected is not None and metadata.get(key) != expected
        for key, expected in expected_metadata.items()
    ):
        raise ValueError(f"registered dataset {definition.dataset_id!r} metadata identity or period mismatch")
    if definition.expected_sha256 is not None and digest != definition.expected_sha256:
        raise ValueError(f"registered dataset {definition.dataset_id!r} failed registered SHA-256 verification")
    data = pd.read_csv(csv_path, index_col="Date", parse_dates=["Date"])
    validated = validate_history(data, start=metadata["start"], end=metadata["end"])
    return DatasetSnapshot(
        dataset_id=definition.dataset_id,
        ticker=definition.ticker,
        sha256=digest,
        source=str(metadata["source"]),
        data=validated,
    )


def _date(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tz is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize()


def _session_query(value: object, index: pd.DatetimeIndex) -> pd.Timestamp:
    """Interpret a calendar-date request in the dataset's session timezone."""
    timestamp = pd.Timestamp(value).normalize()
    if index.tz is not None:
        timestamp = timestamp.tz_localize(index.tz)
    return timestamp


def _to_strategy_output(evaluation: StrategyEvaluation) -> StrategyOutput:
    result = evaluation.result
    metrics = evaluation.metrics
    curve = [
        EquityPoint(date=_date(session).date(), equity=_finite_json_number(value))
        for session, value in result.equity.items()
    ]
    executions = [
        ExecutionOutput(
            session=_date(execution.session).date(),
            side=execution.trade.side,
            trade_date=execution.trade.trade_date,
            units=_finite_json_number(execution.trade.units),
            price=_finite_json_number(execution.trade.price),
            notional=_finite_json_number(execution.trade.notional),
            fee=_finite_json_number(execution.trade.fee),
        )
        for execution in result.executions
    ]
    return StrategyOutput(
        equity_curve=curve,
        executions=executions,
        final_cash=_finite_json_number(result.final_cash),
        final_units=_finite_json_number(result.final_units),
        metrics=MetricsOutput(
            cumulative_return=_finite_json_number(metrics.cumulative_return),
            annualized_return=_optional_finite_json_number(metrics.annualized_return),
            annualized_volatility=_optional_finite_json_number(
                metrics.annualized_volatility
            ),
            maximum_drawdown=_finite_json_number(metrics.maximum_drawdown),
            valuation_intervals=metrics.valuation_intervals,
            unavailable_reasons=dict(metrics.unavailable_reasons),
        ),
    )


def _finite_json_number(value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("motor result contains a non-finite number")
    return number


def _optional_finite_json_number(value: float | None) -> float | None:
    return None if value is None else _finite_json_number(value)


def _catalog_item(
    definition: DatasetDefinition,
    dataset: DatasetSnapshot | None = None,
    *,
    status_override: str | None = None,
    note_override: str | None = None,
) -> DatasetCatalogItem:
    available_start = available_end = digest = None
    if dataset is not None:
        if dataset.dataset_id != definition.dataset_id or dataset.ticker != definition.ticker:
            raise ValueError("dataset provider identity does not match catalog entry")
        if dataset.data.empty or not isinstance(dataset.data.index, pd.DatetimeIndex):
            raise ValueError("catalog dataset has no valid dated observations")
        available_start = _date(dataset.data.index[0]).date()
        available_end = _date(dataset.data.index[-1]).date()
        digest = dataset.sha256
    status = status_override or definition.validation_status
    descriptive_analysis = status in ("descriptive_only", "historical_simulation")
    historical_simulation = status == "historical_simulation"
    return DatasetCatalogItem(
        dataset_id=definition.dataset_id,
        ticker=definition.ticker,
        name=definition.name,
        asset_type=definition.asset_type,
        exposure=definition.exposure,
        currency=definition.currency,
        available_start=available_start,
        available_end=available_end,
        sha256=digest,
        validation_status=status,
        capabilities=DatasetCapabilities(
            descriptive_analysis=descriptive_analysis,
            historical_simulation=historical_simulation,
        ),
        validation_note=note_override or definition.validation_note,
    )


def create_app(dataset_provider: DatasetProvider = _load_allowlisted_dataset) -> FastAPI:
    """Build an app; tests can inject deterministic synthetic datasets."""
    app = FastAPI(title="QUANTLAB API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5500"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

    def load_catalog_snapshot(definition: DatasetDefinition) -> DatasetSnapshot:
        try:
            dataset = dataset_provider(definition.dataset_id)
            if dataset.dataset_id != definition.dataset_id or dataset.ticker != definition.ticker:
                raise ValueError("dataset provider identity does not match catalog entry")
            if dataset.data.empty or not isinstance(dataset.data.index, pd.DatetimeIndex):
                raise DatasetValidationError("catalog dataset has no dated observations")
            validate_history(
                dataset.data,
                start=dataset.data.index[0].date(),
                end=dataset.data.index[-1].date() + pd.Timedelta(days=1).to_pytimedelta(),
            )
            if len(dataset.sha256) != 64 or any(char not in "0123456789abcdef" for char in dataset.sha256):
                raise ValueError("dataset provider returned an invalid SHA-256")
            return dataset
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=503, detail="registered local dataset is unavailable") from error
        except (OSError, ValueError, DatasetValidationError) as error:
            raise HTTPException(status_code=503, detail=f"registered dataset failed validation: {error}") from error

    def catalog_item_for_response(definition: DatasetDefinition) -> DatasetCatalogItem:
        if not definition.csv_filename:
            return _catalog_item(definition)
        try:
            return _catalog_item(definition, load_catalog_snapshot(definition))
        except HTTPException:
            if definition.dataset_id != "qqq-2020-2025":
                raise
            return _catalog_item(
                definition,
                status_override="pending_validation",
                note_override=(
                    "QQQ no está habilitado: el archivo local, sus metadatos, el SHA-256 "
                    "o la validación estructural no superaron las comprobaciones."
                ),
            )

    @app.get("/api/v1/datasets", response_model=DatasetCatalogResponse)
    def list_datasets() -> DatasetCatalogResponse:
        return DatasetCatalogResponse(
            datasets=[catalog_item_for_response(definition) for definition in DATASET_CATALOG]
        )

    @app.get("/api/v1/datasets/{dataset_id}", response_model=DatasetCatalogItem)
    def get_dataset_metadata(dataset_id: str) -> DatasetCatalogItem:
        definition = get_dataset_definition(dataset_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="dataset_id is not registered")
        return catalog_item_for_response(definition)

    @app.get(
        "/api/v1/datasets/{dataset_id}/summary",
        response_model=DatasetSummaryResponse,
    )
    def dataset_summary(
        dataset_id: str,
        start_date: date | None = Query(default=None),
        end_date: date | None = Query(default=None),
    ) -> DatasetSummaryResponse:
        """Return Close-price description without invoking the strategy engine."""
        definition = get_dataset_definition(dataset_id)
        if definition is not None and not definition.descriptive_analysis:
            raise HTTPException(
                status_code=409,
                detail="dataset is pending validation and not enabled for descriptive analysis",
            )
        if start_date is not None and end_date is not None and start_date > end_date:
            raise HTTPException(status_code=422, detail="start_date must not be after end_date")
        try:
            dataset = (
                load_catalog_snapshot(definition)
                if definition is not None
                else dataset_provider(dataset_id)
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="dataset_id is not registered") from error
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=422, detail=f"dataset could not be loaded: {error}") from error

        try:
            if not isinstance(dataset.data, pd.DataFrame) or dataset.data.empty:
                raise DatasetValidationError("dataset is empty")
            # Reuse canonical structural/OHLC/action validation for injected
            # providers too. The observed bounds make no calendar claims.
            first_day = dataset.data.index[0].date()
            last_day = dataset.data.index[-1].date()
            validated = validate_history(
                dataset.data,
                start=first_day,
                end=last_day + pd.Timedelta(days=1).to_pytimedelta(),
            )
            all_dates = pd.Index(validated.index.date)
            mask = pd.Series(True, index=validated.index)
            if start_date is not None:
                mask &= all_dates >= start_date
            if end_date is not None:
                mask &= all_dates <= end_date
            selected = validated.loc[mask.to_numpy()]
            if selected.empty:
                raise DatasetValidationError(
                    "no available sessions fall within the requested inclusive date range"
                )
            closes = selected["Close"].astype(float)
            unavailable_reasons: dict[str, str] = {}
            price_change = None
            volatility = None
            maximum_drawdown = None
            if len(closes) >= 2:
                price_change = float(closes.iloc[-1] / closes.iloc[0] - 1.0)
                drawdown = closes.div(closes.cummax()).sub(1.0)
                maximum_drawdown = float(drawdown.min())
            else:
                unavailable_reasons["price_change"] = "Se requieren al menos dos cierres del período."
                unavailable_reasons["maximum_drawdown"] = "Se requieren al menos dos cierres del período."
            if len(closes) >= 3:
                returns = closes.pct_change(fill_method=None).iloc[1:]
                volatility = float(returns.std(ddof=1) * math.sqrt(252))
            else:
                unavailable_reasons["annualized_volatility"] = (
                    "Se requieren al menos tres cierres (dos rendimientos diarios) "
                    "para calcular la desviación estándar muestral."
                )
            values = [float(closes.iloc[0]), float(closes.iloc[-1])]
            finite_metrics = [value for value in (price_change, volatility, maximum_drawdown) if value is not None]
            if not all(math.isfinite(value) for value in [*values, *finite_metrics]):
                raise DatasetValidationError("summary contains non-finite values")
        except (AttributeError, TypeError, ValueError, DatasetValidationError) as error:
            raise HTTPException(status_code=422, detail=f"dataset cannot be summarized: {error}") from error

        effective_start = selected.index[0].date()
        effective_end = selected.index[-1].date()
        alignment = []
        if start_date is None:
            alignment.append("inicio tomado de la primera sesión disponible")
        elif start_date == effective_start:
            alignment.append("fecha inicial coincide con una sesión disponible")
        else:
            alignment.append(f"fecha inicial ajustada a {effective_start}")
        if end_date is None:
            alignment.append("final tomado de la última sesión disponible")
        elif end_date == effective_end:
            alignment.append("fecha final coincide con una sesión disponible")
        else:
            alignment.append(f"fecha final ajustada a {effective_end}")

        return DatasetSummaryResponse(
            dataset_id=dataset.dataset_id,
            ticker=dataset.ticker,
            name=definition.name if definition is not None else dataset.ticker,
            sha256=dataset.sha256,
            session_count=len(selected),
            first_date=selected.index[0].date(),
            last_date=selected.index[-1].date(),
            requested_start=start_date,
            requested_end=end_date,
            period_note=(
                f"Rango solicitado inclusivo: {start_date or 'inicio disponible'} a "
                f"{end_date or 'fin disponible'}. Período efectivo: "
                f"{effective_start} a {effective_end}. " + "; ".join(alignment) + "."
            ),
            initial_close=values[0],
            final_close=values[1],
            price_change=price_change,
            annualized_volatility=volatility,
            maximum_drawdown=maximum_drawdown,
            unavailable_reasons=unavailable_reasons,
            dividend_events=int((selected["Dividends"] > 0).sum()),
            split_events=int((selected["Stock Splits"] > 0).sum()),
        )

    @app.get(
        "/api/v1/datasets/{dataset_id}/series",
        response_model=DatasetPriceSeriesResponse,
    )
    def dataset_close_series(
        dataset_id: str,
        start_date: date | None = Query(default=None),
        end_date: date | None = Query(default=None),
    ) -> DatasetPriceSeriesResponse:
        """Return descriptive Close points for an enabled catalog dataset."""
        definition = get_dataset_definition(dataset_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="dataset_id is not registered")
        if not definition.descriptive_analysis:
            raise HTTPException(
                status_code=409,
                detail="dataset is pending validation and not enabled for descriptive analysis",
            )
        if start_date is not None and end_date is not None and start_date > end_date:
            raise HTTPException(status_code=422, detail="start_date must not be after end_date")

        try:
            dataset = load_catalog_snapshot(definition)
        except HTTPException as error:
            # Do not expose server paths, validation traces, or storage details.
            raise HTTPException(
                status_code=503,
                detail="registered local dataset is unavailable or did not pass validation",
            ) from error

        dates = pd.Index(dataset.data.index.date)
        mask = pd.Series(True, index=dataset.data.index)
        if start_date is not None:
            mask &= dates >= start_date
        if end_date is not None:
            mask &= dates <= end_date
        selected = dataset.data.loc[mask.to_numpy(), "Close"]
        if selected.empty:
            raise HTTPException(
                status_code=422,
                detail="no available sessions fall within the requested inclusive date range",
            )

        points = [
            ClosePricePoint(date=_date(session).date(), close=_finite_json_number(value))
            for session, value in selected.items()
        ]
        return DatasetPriceSeriesResponse(
            dataset_id=dataset.dataset_id,
            ticker=dataset.ticker,
            sha256=dataset.sha256,
            requested_start=start_date,
            requested_end=end_date,
            first_date=points[0].date,
            last_date=points[-1].date,
            session_count=len(points),
            points=points,
        )

    @app.post(
        "/api/v1/experimental/comparisons",
        response_model=ExperimentalComparisonResponse,
        response_model_exclude_none=False,
    )
    def create_experimental_comparison(
        request: ExperimentalComparisonRequest,
    ) -> ExperimentalComparisonResponse:
        """Compare strategies using generated data clearly marked synthetic."""
        try:
            data = generate_synthetic_history(
                request.scenario,
                session_count=request.session_count,
                warmup_sessions=request.long_window,
            )
            start = data.index[request.long_window]
            end = data.index[-1]
            comparison: StrategyComparison = compare_strategies(
                data,
                request.initial_capital,
                evaluation_start=start,
                evaluation_end=end,
                transaction_cost_rate=request.transaction_cost_rate,
                short_window=request.short_window,
                long_window=request.long_window,
            )
        except (TypeError, ValueError, DatasetValidationError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        synthetic_id = f"synthetic-{request.scenario}"
        digest = hashlib.sha256(
            data.to_csv(index=True, index_label="Date").encode("utf-8")
        ).hexdigest()
        notice = (
            "Resultados experimentales con datos sintéticos. No representan "
            "rentabilidades históricas reales ni constituyen una recomendación de inversión."
        )
        response = ExperimentalComparisonResponse(
            scenario=request.scenario,
            notice=notice,
            configuration=ExperimentalConfiguration(
                scenario=request.scenario,
                session_count=len(comparison.dates),
                initial_capital=comparison.parameters.initial_capital,
                transaction_cost_rate=comparison.parameters.transaction_cost_rate,
                evaluation_start=_date(comparison.parameters.evaluation_start).date(),
                evaluation_end=_date(comparison.parameters.evaluation_end).date(),
                short_window=comparison.parameters.short_window,
                long_window=comparison.parameters.long_window,
            ),
            dataset=DatasetIdentity(
                dataset_id=synthetic_id,
                ticker="SYNTHETIC",
                sha256=digest,
                source="QUANTLAB deterministic synthetic generator v1",
            ),
            evaluation_dates=[_date(session).date() for session in comparison.dates],
            buy_and_hold=_to_strategy_output(comparison.buy_and_hold),
            sma_crossover=_to_strategy_output(comparison.sma_crossover),
            warnings=[
                "Experimental comparison uses generated OHLC values and a weekday sequence; it is not historical market data."
            ],
        )
        try:
            return JSONResponse(
                status_code=200,
                content=json.loads(response.model_dump_json()),
            )
        except (ValueError, TypeError) as error:
            raise HTTPException(
                status_code=500,
                detail="experimental result could not be serialized as finite JSON",
            ) from error

    @app.post(
        "/api/v1/comparisons",
        response_model=ComparisonResponse,
        response_model_exclude_none=False,
    )
    def create_comparison(request: ComparisonRequest) -> ComparisonResponse:
        definition = get_dataset_definition(request.dataset_id)
        if definition is not None and not definition.historical_simulation:
            detail = (
                "dataset does not process and reconcile corporate actions; "
                "historical simulation is not enabled"
                if definition.validation_status == "descriptive_only"
                else "dataset is pending validation and not enabled for historical simulation"
            )
            raise HTTPException(status_code=409, detail=detail)
        try:
            dataset = dataset_provider(request.dataset_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="dataset_id is not registered") from error
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=422, detail=f"dataset could not be loaded: {error}") from error

        try:
            comparison: StrategyComparison = compare_strategies(
                dataset.data,
                request.initial_capital,
                evaluation_start=_session_query(request.evaluation_start, dataset.data.index),
                evaluation_end=(
                    _session_query(request.evaluation_end, dataset.data.index)
                    if request.evaluation_end is not None
                    else None
                ),
                transaction_cost_rate=request.transaction_cost_rate,
                short_window=request.short_window,
                long_window=request.long_window,
            )
        except (TypeError, ValueError, DatasetValidationError) as error:
            status = (
                409
                if "does not process and reconcile corporate actions" in str(error)
                else 422
            )
            raise HTTPException(status_code=status, detail=str(error)) from error

        response = ComparisonResponse(
            configuration=EffectiveConfiguration(
                dataset_id=dataset.dataset_id,
                initial_capital=comparison.parameters.initial_capital,
                transaction_cost_rate=comparison.parameters.transaction_cost_rate,
                evaluation_start=_date(comparison.parameters.evaluation_start).date(),
                evaluation_end=_date(comparison.parameters.evaluation_end).date(),
                short_window=comparison.parameters.short_window,
                long_window=comparison.parameters.long_window,
            ),
            dataset=DatasetIdentity(
                dataset_id=dataset.dataset_id,
                ticker=dataset.ticker,
                sha256=dataset.sha256,
                source=dataset.source,
            ),
            evaluation_dates=[_date(session).date() for session in comparison.dates],
            buy_and_hold=_to_strategy_output(comparison.buy_and_hold),
            sma_crossover=_to_strategy_output(comparison.sma_crossover),
            warnings=[
                "Corporate actions are not processed by this API; datasets with non-zero dividends or splits are rejected."
            ],
        )
        # Enforce strict JSON output: NaN and Infinity are not valid JSON numbers.
        try:
            return JSONResponse(
                status_code=200,
                content=json.loads(response.model_dump_json()),
            )
        except (ValueError, TypeError) as error:
            raise HTTPException(status_code=500, detail="result could not be serialized as finite JSON") from error

    return app


app = create_app()
