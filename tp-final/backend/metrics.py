"""Pure financial metric calculations for QUANTLAB."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType
from typing import Mapping, Protocol

import numpy as np
import pandas as pd


TRADING_SESSIONS_PER_YEAR = 252


class _StrategyResultLike(Protocol):
    equity: pd.Series


@dataclass(frozen=True)
class StrategyMetrics:
    """Metrics for a strategy evaluation period.

    A metric is ``None`` only when its mathematical prerequisites are not
    met; ``unavailable_reasons`` explains each such case.
    """

    cumulative_return: float
    annualized_return: float | None
    annualized_volatility: float | None
    maximum_drawdown: float
    valuation_intervals: int
    unavailable_reasons: Mapping[str, str]


def calculate_strategy_metrics(
    strategy_result: _StrategyResultLike, initial_capital: Real
) -> StrategyMetrics:
    """Calculate contract metrics from a strategy's dated equity curve.

    The curve must contain only evaluated sessions. Its first point is one
    interval after contributed capital, so ``N`` equals the number of curve
    observations. Missing values are rejected; none are filled or skipped.
    """
    curve = getattr(strategy_result, "equity", None)
    if not isinstance(curve, pd.Series):
        raise TypeError("strategy_result must expose equity as a pandas Series")
    if curve.empty:
        raise ValueError("equity curve must contain at least one valuation")
    if not isinstance(curve.index, pd.DatetimeIndex):
        raise TypeError("equity curve index must be a DatetimeIndex")
    if curve.index.hasnans:
        raise ValueError("equity curve dates must not be missing")
    if not curve.index.is_unique:
        raise ValueError("equity curve dates must not contain duplicates")
    if not curve.index.is_monotonic_increasing:
        raise ValueError("equity curve dates must be in chronological order")

    initial = _finite_number("initial_capital", initial_capital)
    if initial <= 0:
        raise ValueError("initial_capital must be greater than zero")
    equity_values: list[float] = []
    for session, value in curve.items():
        amount = _finite_number(f"equity[{session}]", value)
        if amount < 0:
            raise ValueError("equity values cannot be negative")
        equity_values.append(amount)

    final_equity = equity_values[-1]
    total_return = cumulative_return(initial, final_equity)
    interval_count = len(equity_values)
    reasons: dict[str, str] = {}
    if final_equity == 0:
        annual_return = None
        reasons["annualized_return"] = (
            "not calculable because final equity must be greater than zero"
        )
    else:
        annual_return = annualized_return(initial, final_equity, interval_count)

    daily_returns: list[float | None] = []
    previous_equity = initial
    for amount in equity_values:
        if previous_equity <= 0:
            daily_returns.append(None)
        else:
            daily_returns.append(amount / previous_equity - 1.0)
        previous_equity = amount
    volatility = annualized_volatility(daily_returns)
    if volatility is None:
        reasons["annualized_volatility"] = (
            "not calculable with fewer than two valid daily returns"
        )

    drawdown = maximum_drawdown(equity_values, initial_capital=initial)
    assert drawdown is not None  # A non-empty, validated curve was supplied.
    return StrategyMetrics(
        cumulative_return=total_return,
        annualized_return=annual_return,
        annualized_volatility=volatility,
        maximum_drawdown=drawdown,
        valuation_intervals=interval_count,
        unavailable_reasons=MappingProxyType(reasons),
    )


def _finite_number(name: str, value: Real) -> float:
    """Return a finite float, rejecting booleans and non-real values."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")

    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def cumulative_return(initial_capital: Real, final_equity: Real) -> float:
    """Return ``final_equity / initial_capital - 1``.

    Initial capital must be positive. Final equity may be zero (a total loss)
    but cannot be negative.
    """
    initial = _finite_number("initial_capital", initial_capital)
    final = _finite_number("final_equity", final_equity)
    if initial <= 0:
        raise ValueError("initial_capital must be greater than zero")
    if final < 0:
        raise ValueError("final_equity cannot be negative")
    return final / initial - 1.0


def annualized_return(
    initial_capital: Real, final_equity: Real, intervals: int
) -> float:
    """Annualize cumulative return using the 252-session convention.

    ``intervals`` is the number of valuation intervals from initial capital
    to final equity. Both capital and final equity must be positive and the
    interval count must be a positive integer.
    """
    initial = _finite_number("initial_capital", initial_capital)
    final = _finite_number("final_equity", final_equity)
    if initial <= 0:
        raise ValueError("initial_capital must be greater than zero")
    if final <= 0:
        raise ValueError("final_equity must be greater than zero")
    if isinstance(intervals, bool) or not isinstance(intervals, int):
        raise TypeError("intervals must be an integer")
    if intervals <= 0:
        raise ValueError("intervals must be greater than zero")
    return (final / initial) ** (TRADING_SESSIONS_PER_YEAR / intervals) - 1.0


def annualized_volatility(daily_returns: Iterable[Real | None]) -> float | None:
    """Calculate sample daily-return volatility annualized by ``sqrt(252)``.

    ``None`` and NaN entries are treated as missing returns. Returns ``None``
    when fewer than two finite observations remain; non-real or infinite
    observations are rejected.
    """
    valid_returns: list[float] = []
    for value in daily_returns:
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError("daily returns must be real numbers or None")
        number = float(value)
        if math.isnan(number):
            continue
        if not math.isfinite(number):
            raise ValueError("daily returns must be finite")
        valid_returns.append(number)

    if len(valid_returns) < 2:
        return None

    sample_std = float(np.std(valid_returns, ddof=1))
    return sample_std * math.sqrt(TRADING_SESSIONS_PER_YEAR)


def maximum_drawdown(
    equity_values: Iterable[Real], initial_capital: Real | None = None
) -> float | None:
    """Return the largest peak-to-trough drawdown as a positive fraction.

    If supplied, ``initial_capital`` is included as the first equity point.
    Equity values must be non-negative; at least one positive prior peak must
    exist for the metric to be calculable. An empty series returns ``None``.
    """
    values = list(equity_values)
    if not values:
        return None

    peak = 0.0
    if initial_capital is not None:
        peak = _finite_number("initial_capital", initial_capital)
        if peak <= 0:
            raise ValueError("initial_capital must be greater than zero")

    maximum_drawdown_value = 0.0
    for index, value in enumerate(values):
        equity = _finite_number(f"equity_values[{index}]", value)
        if equity < 0:
            raise ValueError("equity values cannot be negative")
        if equity > peak:
            peak = equity
        elif peak == 0:
            raise ValueError("a positive prior peak is required")

        drawdown = 1.0 - equity / peak
        maximum_drawdown_value = max(maximum_drawdown_value, drawdown)

    return maximum_drawdown_value
