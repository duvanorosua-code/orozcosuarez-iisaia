"""Run Buy and Hold and SMA20/SMA50 under one shared configuration."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real

import pandas as pd

from backend.metrics import StrategyMetrics, calculate_strategy_metrics
from backend.portfolio import DEFAULT_TRANSACTION_COST_RATE
from backend.strategies import (
    StrategyResult,
    _evaluation_position,
    _validated_ohlc,
    calculate_sma_signals,
    run_buy_and_hold,
    run_sma_crossover,
)


@dataclass(frozen=True)
class ComparisonParameters:
    initial_capital: float
    transaction_cost_rate: float
    evaluation_start: pd.Timestamp
    evaluation_end: pd.Timestamp
    short_window: int
    long_window: int


@dataclass(frozen=True)
class StrategyEvaluation:
    result: StrategyResult
    metrics: StrategyMetrics


@dataclass(frozen=True)
class StrategyComparison:
    parameters: ComparisonParameters
    dates: pd.DatetimeIndex
    buy_and_hold: StrategyEvaluation
    sma_crossover: StrategyEvaluation


def compare_strategies(
    data: pd.DataFrame,
    initial_capital: Real,
    *,
    evaluation_start: object,
    evaluation_end: object | None = None,
    transaction_cost_rate: Real = DEFAULT_TRANSACTION_COST_RATE,
    short_window: int = 20,
    long_window: int = 50,
) -> StrategyComparison:
    """Compare both strategies with the same capital, fee, and evaluation dates.

    ``evaluation_end`` is inclusive and defaults to the final supplied session.
    Rows before ``evaluation_start`` are retained only as SMA indicator
    warmup; the returned curves and metrics contain evaluated dates only.
    The input must already be reconciled for corporate actions: event columns
    containing non-zero actions are rejected by the shared strategy validator.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    if data.empty:
        raise ValueError("data must contain at least one session")
    if not isinstance(data.index, pd.DatetimeIndex):
        raise TypeError("data index must be a DatetimeIndex")
    if data.index.hasnans:
        raise ValueError("session dates must not be missing")
    if not data.index.is_unique:
        raise ValueError("session index must not contain duplicates")
    if not data.index.is_monotonic_increasing:
        raise ValueError("sessions must be in chronological order")

    start_position = _evaluation_position(data.index, evaluation_start)
    end_label = data.index[-1] if evaluation_end is None else evaluation_end
    end_position = _evaluation_position(data.index, end_label)
    if end_position < start_position:
        raise ValueError("evaluation_end must not precede evaluation_start")

    # Validate only the history that can affect this comparison: warmup plus
    # the inclusive evaluation period. Later rows are outside the experiment.
    comparison_data = data.iloc[: end_position + 1].copy(deep=True)
    validated = _validated_ohlc(comparison_data)
    # Reuse the indicator validator before starting either portfolio so bad
    # window settings or insufficient warmup cannot yield a partial run.
    calculate_sma_signals(validated["Close"], short_window, long_window)
    if start_position < long_window:
        raise ValueError(
            f"comparison requires at least {long_window} valid warmup closes "
            "before evaluation_start"
        )

    start_date = data.index[start_position]
    end_date = data.index[end_position]
    buy_hold_result = run_buy_and_hold(
        comparison_data,
        initial_capital,
        evaluation_start=start_date,
        transaction_cost_rate=transaction_cost_rate,
    )
    sma_result = run_sma_crossover(
        comparison_data,
        initial_capital,
        evaluation_start=start_date,
        short_window=short_window,
        long_window=long_window,
        transaction_cost_rate=transaction_cost_rate,
    )

    expected_dates = data.index[start_position : end_position + 1]
    if not buy_hold_result.equity.index.equals(expected_dates):
        raise RuntimeError("Buy and Hold valuation dates differ from the evaluation period")
    if not sma_result.equity.index.equals(expected_dates):
        raise RuntimeError("SMA valuation dates differ from the evaluation period")
    if not buy_hold_result.equity.index.equals(sma_result.equity.index):
        raise RuntimeError("strategy valuation dates do not match")

    buy_hold_metrics = calculate_strategy_metrics(buy_hold_result, initial_capital)
    sma_metrics = calculate_strategy_metrics(sma_result, initial_capital)
    params = ComparisonParameters(
        initial_capital=float(initial_capital),
        transaction_cost_rate=float(transaction_cost_rate),
        evaluation_start=start_date,
        evaluation_end=end_date,
        short_window=short_window,
        long_window=long_window,
    )
    return StrategyComparison(
        parameters=params,
        dates=expected_dates.copy(),
        buy_and_hold=StrategyEvaluation(buy_hold_result, buy_hold_metrics),
        sma_crossover=StrategyEvaluation(sma_result, sma_metrics),
    )
