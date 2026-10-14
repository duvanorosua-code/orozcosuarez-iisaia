"""HTTP request and response schemas for QUANTLAB's comparison API."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
    initial_capital: float = Field(gt=0, allow_inf_nan=False)
    evaluation_start: date
    evaluation_end: date | None = None
    transaction_cost_rate: float = Field(default=0.001, ge=0, lt=1, allow_inf_nan=False)
    short_window: int = Field(default=20, gt=0, strict=True)
    long_window: int = Field(default=50, gt=0, strict=True)

    @field_validator("initial_capital", "transaction_cost_rate", mode="before")
    @classmethod
    def reject_boolean_numbers(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean values are not valid numeric parameters")
        return value

    @model_validator(mode="after")
    def validate_windows(self) -> ComparisonRequest:
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be less than long_window")
        if self.evaluation_end is not None and self.evaluation_end < self.evaluation_start:
            raise ValueError("evaluation_end must not precede evaluation_start")
        return self


class EffectiveConfiguration(BaseModel):
    dataset_id: str
    initial_capital: float
    transaction_cost_rate: float
    evaluation_start: date
    evaluation_end: date
    short_window: int
    long_window: int


class DatasetIdentity(BaseModel):
    dataset_id: str
    ticker: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source: str


class EquityPoint(BaseModel):
    date: date
    equity: float


class ExecutionOutput(BaseModel):
    session: date
    side: Literal["buy", "sell"]
    trade_date: date | None
    units: float
    price: float
    notional: float
    fee: float


class MetricsOutput(BaseModel):
    cumulative_return: float
    annualized_return: float | None
    annualized_volatility: float | None
    maximum_drawdown: float
    valuation_intervals: int
    unavailable_reasons: dict[str, str]


class StrategyOutput(BaseModel):
    equity_curve: list[EquityPoint]
    executions: list[ExecutionOutput]
    final_cash: float
    final_units: float
    metrics: MetricsOutput


class ComparisonResponse(BaseModel):
    configuration: EffectiveConfiguration
    dataset: DatasetIdentity
    evaluation_dates: list[date]
    buy_and_hold: StrategyOutput
    sma_crossover: StrategyOutput
    warnings: list[str]


class DatasetSummaryResponse(BaseModel):
    """Descriptive statistics based only on the dataset's Close prices."""

    dataset_id: str
    ticker: str
    name: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    session_count: int
    first_date: date
    last_date: date
    requested_start: date | None
    requested_end: date | None
    period_note: str
    initial_close: float
    final_close: float
    price_change: float | None
    annualized_volatility: float | None
    maximum_drawdown: float | None
    unavailable_reasons: dict[str, str]
    dividend_events: int
    split_events: int
    price_basis: Literal["Close"] = "Close"
    includes_distributions: bool = False
    is_strategy_result: bool = False
    interpretation: str = (
        "Estadísticas descriptivas del precio Close; la variación no incluye "
        "distribuciones y no representa rentabilidad total ni resultados de estrategia."
    )


class ClosePricePoint(BaseModel):
    date: date
    close: float


class DatasetPriceSeriesResponse(BaseModel):
    """Descriptive Close observations from a registered local dataset."""

    dataset_id: str
    ticker: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    requested_start: date | None
    requested_end: date | None
    first_date: date
    last_date: date
    session_count: int
    points: list[ClosePricePoint]


class DatasetCapabilities(BaseModel):
    descriptive_analysis: bool
    historical_simulation: bool


class DatasetCatalogItem(BaseModel):
    dataset_id: str
    ticker: str
    name: str
    asset_type: Literal["equity_etf", "fixed_income_etf", "commodity_etf"]
    exposure: str
    currency: str
    available_start: date | None
    available_end: date | None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    validation_status: Literal[
        "pending_validation", "descriptive_only", "historical_simulation"
    ]
    capabilities: DatasetCapabilities
    validation_note: str


class DatasetCatalogResponse(BaseModel):
    datasets: list[DatasetCatalogItem]


class ExperimentalComparisonRequest(BaseModel):
    """Bounded configuration for a deterministic synthetic experiment."""

    model_config = ConfigDict(extra="forbid")

    scenario: Literal["uptrend", "sideways", "high_volatility"]
    initial_capital: float = Field(default=1_000_000, gt=0, allow_inf_nan=False)
    session_count: int = Field(default=252, ge=2, le=2000, strict=True)
    transaction_cost_rate: float = Field(default=0.001, ge=0, lt=1, allow_inf_nan=False)
    short_window: int = Field(default=20, gt=0, le=499, strict=True)
    long_window: int = Field(default=50, gt=1, le=500, strict=True)

    @field_validator("initial_capital", "transaction_cost_rate", mode="before")
    @classmethod
    def reject_boolean_parameters(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean values are not valid numeric parameters")
        return value

    @model_validator(mode="after")
    def validate_windows(self) -> ExperimentalComparisonRequest:
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be less than long_window")
        return self


class ExperimentalConfiguration(BaseModel):
    scenario: Literal["uptrend", "sideways", "high_volatility"]
    session_count: int
    initial_capital: float
    transaction_cost_rate: float
    evaluation_start: date
    evaluation_end: date
    short_window: int
    long_window: int


class ExperimentalComparisonResponse(BaseModel):
    mode: Literal["experimental"] = "experimental"
    data_origin: Literal["synthetic"] = "synthetic"
    scenario: Literal["uptrend", "sideways", "high_volatility"]
    notice: str
    configuration: ExperimentalConfiguration
    dataset: DatasetIdentity
    evaluation_dates: list[date]
    buy_and_hold: StrategyOutput
    sma_crossover: StrategyOutput
    warnings: list[str]
