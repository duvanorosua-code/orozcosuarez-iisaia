from __future__ import annotations

import pandas as pd
import pytest

from backend.comparison import compare_strategies
from backend.portfolio import Portfolio
from backend.strategies import run_buy_and_hold, run_sma_crossover


def make_data(length: int = 70) -> pd.DataFrame:
    closes = [100.0] * 30 + [120.0] * 20 + [120.0] * 8 + [90.0] * 12
    closes = closes[:length]
    index = pd.date_range("2025-01-02", periods=length, freq="B")
    opens = [value for value in closes]
    return pd.DataFrame(
        {
            "Open": opens,
            "High": [value + 1 for value in closes],
            "Low": [value - 1 for value in closes],
            "Close": closes,
        },
        index=index,
    )


def compare(data: pd.DataFrame, **kwargs):
    start = kwargs.pop("evaluation_start", data.index[50])
    return compare_strategies(data, 1_000, evaluation_start=start, **kwargs)


def test_comparison_uses_same_capital_fee_and_evaluation_period():
    data = make_data()
    result = compare(
        data,
        evaluation_end=data.index[64],
        transaction_cost_rate=0.002,
    )

    assert result.parameters.initial_capital == 1_000
    assert result.parameters.transaction_cost_rate == 0.002
    assert result.parameters.evaluation_start == data.index[50]
    assert result.parameters.evaluation_end == data.index[64]
    assert result.buy_and_hold.result.final_cash >= 0
    assert result.sma_crossover.result.final_cash >= 0


def test_comparison_returns_identical_valuation_dates_and_excludes_warmup():
    data = make_data()
    result = compare(data, evaluation_end=data.index[64])
    expected_dates = data.index[50:65]

    assert result.dates.equals(expected_dates)
    assert result.buy_and_hold.result.equity.index.equals(expected_dates)
    assert result.sma_crossover.result.equity.index.equals(expected_dates)
    assert all(date >= data.index[50] for date in result.dates)


def test_comparison_calculates_metrics_for_both_strategies():
    result = compare(make_data(), evaluation_end=make_data().index[64])

    for evaluation in (result.buy_and_hold, result.sma_crossover):
        assert evaluation.metrics.valuation_intervals == 15
        assert evaluation.metrics.cumulative_return is not None
        assert evaluation.metrics.annualized_return is not None
        assert evaluation.metrics.annualized_volatility is not None
        assert evaluation.metrics.maximum_drawdown is not None


def test_comparison_rejects_period_without_sma_warmup():
    data = make_data()

    with pytest.raises(ValueError, match="50 valid warmup closes"):
        compare(data, evaluation_start=data.index[49])


@pytest.mark.parametrize(
    "bad_data",
    [
        make_data().assign(Close=lambda frame: frame["Close"].mask(frame.index == frame.index[55], float("nan"))),
        make_data().assign(Dividends=0.0),
    ],
)
def test_comparison_rejects_invalid_or_unprocessed_input(bad_data: pd.DataFrame):
    if "Dividends" in bad_data:
        bad_data.loc[bad_data.index[55], "Dividends"] = 0.5
        message = "does not process and reconcile corporate actions"
    else:
        message = "finite and greater than zero"

    with pytest.raises(ValueError, match=message):
        compare(bad_data)


def test_comparison_is_reproducible():
    data = make_data()
    first = compare(data, evaluation_end=data.index[64])
    second = compare(data.copy(deep=True), evaluation_end=data.index[64])

    pd.testing.assert_series_equal(first.buy_and_hold.result.equity, second.buy_and_hold.result.equity)
    pd.testing.assert_series_equal(first.sma_crossover.result.equity, second.sma_crossover.result.equity)
    assert first.buy_and_hold.result.executions == second.buy_and_hold.result.executions
    assert first.sma_crossover.result.executions == second.sma_crossover.result.executions
    assert first.buy_and_hold.metrics == second.buy_and_hold.metrics
    assert first.sma_crossover.metrics == second.sma_crossover.metrics


def test_comparison_does_not_mutate_input_prior_results_or_existing_portfolio():
    data = make_data()
    input_before = data.copy(deep=True)
    start = data.index[50]
    standalone_buy_hold = run_buy_and_hold(data, 1_000, evaluation_start=start)
    standalone_sma = run_sma_crossover(data, 1_000, evaluation_start=start)
    buy_hold_equity_before = standalone_buy_hold.equity.copy()
    sma_equity_before = standalone_sma.equity.copy()
    buy_hold_trades_before = standalone_buy_hold.executions
    sma_trades_before = standalone_sma.executions
    portfolio = Portfolio(1_000)
    portfolio.buy(2, 100)
    portfolio_state_before = (portfolio.cash, portfolio.units, portfolio.trades)

    compare(data, evaluation_end=data.index[64])

    pd.testing.assert_frame_equal(data, input_before)
    pd.testing.assert_series_equal(standalone_buy_hold.equity, buy_hold_equity_before)
    pd.testing.assert_series_equal(standalone_sma.equity, sma_equity_before)
    assert standalone_buy_hold.executions == buy_hold_trades_before
    assert standalone_sma.executions == sma_trades_before
    assert (portfolio.cash, portfolio.units, portfolio.trades) == portfolio_state_before
