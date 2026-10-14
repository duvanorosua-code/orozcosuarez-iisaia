"""Synthetic acceptance tests for QUANTLAB financial metrics and ledger."""

import math
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.metrics import (
    annualized_return,
    annualized_volatility,
    calculate_strategy_metrics,
    cumulative_return,
    maximum_drawdown,
)
from backend.strategies import run_sma_crossover


def make_strategy_result(equity_values, dates=None):
    if dates is None:
        dates = pd.date_range("2025-01-02", periods=len(equity_values), freq="B")
    return SimpleNamespace(equity=pd.Series(equity_values, index=dates, dtype=float))


def test_cumulative_return_positive_10_percent():
    """1_000_000 initial and 1_100_000 final equity produce 10%."""
    assert cumulative_return(1_000_000, 1_100_000) == pytest.approx(0.10)


def test_cumulative_return_negative_10_percent():
    """1_000_000 initial and 900_000 final equity produce -10%."""
    assert cumulative_return(1_000_000, 900_000) == pytest.approx(-0.10)


@pytest.mark.parametrize(
    ("initial_capital", "final_equity"),
    [(0, 100), (-1, 100), (100, -1), (math.inf, 100), (100, math.nan)],
)
def test_cumulative_return_rejects_invalid_values(initial_capital, final_equity):
    with pytest.raises(ValueError):
        cumulative_return(initial_capital, final_equity)


def test_cumulative_return_rejects_non_numeric_values():
    with pytest.raises(TypeError):
        cumulative_return("100", 110)


def test_annualized_return_uses_252_intervals_per_year():
    assert annualized_return(100, 110, 252) == pytest.approx(0.10)


def test_annualized_return_scales_periods_shorter_than_one_year():
    # 10% over 126 sessions annualizes to (1.10 ** 2) - 1 = 21%.
    assert annualized_return(100, 110, 126) == pytest.approx(0.21)


@pytest.mark.parametrize(
    ("initial_capital", "final_equity", "intervals"),
    [
        (0, 100, 252),
        (100, 0, 252),
        (100, -1, 252),
        (100, 110, 0),
        (100, 110, -1),
        (100, 110, 1.5),
    ],
)
def test_annualized_return_rejects_invalid_inputs(
    initial_capital, final_equity, intervals
):
    with pytest.raises((TypeError, ValueError)):
        annualized_return(initial_capital, final_equity, intervals)


def test_annualized_volatility_uses_sample_standard_deviation_and_252_sessions():
    returns = [0.01, 0.03]
    expected = math.sqrt(0.0002) * math.sqrt(252)
    assert annualized_volatility(returns) == pytest.approx(expected)


def test_annualized_volatility_is_zero_for_constant_returns():
    assert annualized_volatility([0.02, 0.02, 0.02]) == pytest.approx(0.0)


@pytest.mark.parametrize("returns", [[], [0.01], [None, math.nan, 0.01]])
def test_annualized_volatility_is_not_calculable_with_fewer_than_two_valid_returns(
    returns,
):
    assert annualized_volatility(returns) is None


def test_annualized_volatility_rejects_infinite_returns():
    with pytest.raises(ValueError):
        annualized_volatility([0.01, math.inf])


def test_maximum_drawdown_from_peak_is_25_percent():
    assert maximum_drawdown([100, 120, 90]) == pytest.approx(0.25)


def test_maximum_drawdown_includes_initial_capital_when_supplied():
    assert maximum_drawdown([90], initial_capital=120) == pytest.approx(0.25)


def test_maximum_drawdown_is_zero_for_non_decreasing_equity():
    assert maximum_drawdown([100, 110, 120]) == pytest.approx(0.0)


def test_maximum_drawdown_is_not_calculable_for_empty_series():
    assert maximum_drawdown([]) is None


@pytest.mark.parametrize(
    "equity_values",
    [[-1, 100], [100, math.nan], [100, math.inf], [0, 0]],
)
def test_maximum_drawdown_rejects_invalid_equity_series(equity_values):
    with pytest.raises(ValueError):
        maximum_drawdown(equity_values)


def test_strategy_metrics_for_constant_equity():
    metrics = calculate_strategy_metrics(make_strategy_result([100, 100, 100]), 100)

    assert metrics.cumulative_return == pytest.approx(0)
    assert metrics.annualized_return == pytest.approx(0)
    assert metrics.annualized_volatility == pytest.approx(0)
    assert metrics.maximum_drawdown == pytest.approx(0)
    assert metrics.valuation_intervals == 3
    assert metrics.unavailable_reasons == {}


def test_strategy_metrics_for_positive_return_and_sample_volatility():
    metrics = calculate_strategy_metrics(make_strategy_result([100, 110]), 100)

    assert metrics.cumulative_return == pytest.approx(0.10)
    assert metrics.annualized_return == pytest.approx(1.1 ** 126 - 1)
    # Returns are [0.0, 0.1], whose sample variance is 0.005.
    assert metrics.annualized_volatility == pytest.approx(math.sqrt(0.005 * 252))
    assert metrics.valuation_intervals == 2


def test_strategy_metrics_for_negative_return():
    metrics = calculate_strategy_metrics(make_strategy_result([90, 80]), 100)

    assert metrics.cumulative_return == pytest.approx(-0.20)
    assert metrics.annualized_return == pytest.approx(0.8 ** 126 - 1)


def test_strategy_metrics_drawdown_includes_initial_capital_reference():
    metrics = calculate_strategy_metrics(make_strategy_result([120, 90]), 100)

    assert metrics.maximum_drawdown == pytest.approx(0.25)


def test_one_valuation_has_annualized_return_but_volatility_is_not_calculable():
    metrics = calculate_strategy_metrics(make_strategy_result([105]), 100)

    assert metrics.cumulative_return == pytest.approx(0.05)
    assert metrics.annualized_return == pytest.approx(1.05 ** 252 - 1)
    assert metrics.annualized_volatility is None
    assert "fewer than two valid daily returns" in metrics.unavailable_reasons[
        "annualized_volatility"
    ]


def test_zero_final_equity_marks_annualized_return_unavailable():
    metrics = calculate_strategy_metrics(make_strategy_result([0]), 100)

    assert metrics.cumulative_return == pytest.approx(-1)
    assert metrics.annualized_return is None
    assert "final equity" in metrics.unavailable_reasons["annualized_return"]


def test_empty_strategy_equity_curve_is_rejected():
    with pytest.raises(ValueError, match="at least one valuation"):
        calculate_strategy_metrics(make_strategy_result([]), 100)


def test_strategy_metrics_use_only_evaluated_sma_curve_not_warmup():
    dates = pd.date_range("2025-01-02", periods=52, freq="B")
    data = pd.DataFrame(
        {
            "Open": [100.0] * len(dates),
            "High": [101.0] * len(dates),
            "Low": [99.0] * len(dates),
            "Close": [100.0] * len(dates),
        },
        index=dates,
    )
    evaluation_start = dates[50]
    strategy_result = run_sma_crossover(
        data, 100, evaluation_start=evaluation_start
    )

    metrics = calculate_strategy_metrics(strategy_result, initial_capital=100)

    assert strategy_result.equity.index.equals(dates[50:])
    assert metrics.valuation_intervals == 2


@pytest.mark.parametrize(
    "dates",
    [
        pd.DatetimeIndex(["2025-01-02", "2025-01-02"]),
        pd.DatetimeIndex(["2025-01-03", "2025-01-02"]),
        pd.DatetimeIndex(["2025-01-02", None]),
    ],
)
def test_strategy_metrics_reject_duplicate_unsorted_or_missing_dates(dates):
    with pytest.raises(ValueError):
        calculate_strategy_metrics(make_strategy_result([100, 110], dates), 100)


@pytest.mark.parametrize("values", [[100, math.nan], [100, math.inf], [100, -1], [100, None]])
def test_strategy_metrics_reject_invalid_equity_values(values):
    curve = pd.Series(values, index=pd.date_range("2025-01-02", periods=2, freq="B"))
    with pytest.raises((TypeError, ValueError)):
        calculate_strategy_metrics(SimpleNamespace(equity=curve), 100)


