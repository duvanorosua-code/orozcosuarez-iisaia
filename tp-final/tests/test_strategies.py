from __future__ import annotations

import pandas as pd
import pytest

from backend.strategies import (
    calculate_sma_signals,
    run_buy_and_hold,
    run_sma_crossover,
)


def make_data(closes: list[float], opens: list[float] | None = None) -> pd.DataFrame:
    if opens is None:
        opens = closes
    index = pd.date_range("2024-01-02", periods=len(closes), freq="B")
    return pd.DataFrame(
        {
            "Open": opens,
            "High": [max(o, c) + 1 for o, c in zip(opens, closes)],
            "Low": [min(o, c) - 1 for o, c in zip(opens, closes)],
            "Close": closes,
        },
        index=index,
    )


def warmup_data() -> pd.DataFrame:
    # Bullish after 50 closes, then a persistent decline that eventually
    # generates a cash target. This exercises both sides of the crossover.
    closes = [100.0] * 30 + [200.0] * 20 + [200.0] * 15 + [50.0] * 45
    return make_data(closes)


def test_buy_and_hold_buys_at_first_evaluated_open_and_holds_to_end() -> None:
    data = make_data([10, 12, 11], [9, 12, 10])
    result = run_buy_and_hold(data, 1_000, evaluation_start=data.index[1])

    assert list(result.equity.index) == list(data.index[1:])
    assert len(result.executions) == 1
    execution = result.executions[0]
    assert execution.session == data.index[1]
    assert execution.trade.side == "buy"
    assert execution.trade.price == 12
    assert result.final_units == pytest.approx(execution.trade.units)
    assert result.final_units > 0  # No artificial terminal liquidation.
    assert execution.trade.trade_date == execution.session.date()


def test_sma_has_no_signal_before_50_valid_closes() -> None:
    signals = calculate_sma_signals(pd.Series([float(i + 1) for i in range(55)]))
    assert signals["target"].iloc[:49].isna().all()
    assert signals["target"].iloc[49:].notna().all()


def test_close_signal_executes_only_at_next_session_open() -> None:
    data = warmup_data()
    start = data.index[50]
    result = run_sma_crossover(data, 1_000, evaluation_start=start)

    # The bullish signal first becomes known at close[49], so it can trade at
    # the common first evaluated Open[50], never earlier or at close[49].
    assert bool(calculate_sma_signals(data["Close"]).loc[data.index[49], "target"])
    assert result.executions[0].session == data.index[49 + 1]
    assert result.executions[0].trade.side == "buy"
    assert result.executions[0].trade.price == data.loc[data.index[49 + 1], "Open"]
    assert all(item.session >= start for item in result.executions)
    assert all(
        item.trade.trade_date == item.session.date() for item in result.executions
    )
    assert {item.trade.side for item in result.executions} == {"buy", "sell"}


def test_sma_rejects_evaluation_start_without_full_warmup() -> None:
    data = warmup_data()

    with pytest.raises(ValueError, match="50 prior valid closes"):
        run_sma_crossover(data, 1_000, evaluation_start=data.index[49])


def test_sma_accepts_evaluation_start_after_50_prior_closes() -> None:
    data = warmup_data()

    result = run_sma_crossover(data, 1_000, evaluation_start=data.index[50])

    assert result.equity.index[0] == data.index[50]


def test_sma_curve_excludes_all_warmup_sessions() -> None:
    data = warmup_data()
    evaluation_start = data.index[50]

    result = run_sma_crossover(data, 1_000, evaluation_start=evaluation_start)

    assert result.equity.index.equals(data.index[50:])
    assert not any(session < evaluation_start for session in result.equity.index)


def test_sma_never_creates_short_positions_or_negative_cash() -> None:
    data = warmup_data()
    result = run_sma_crossover(data, 1_000, evaluation_start=data.index[50])

    assert result.final_units >= 0
    assert result.final_cash >= 0
    assert all(item.trade.units > 0 for item in result.executions)


def test_strategies_share_capital_and_evaluation_period() -> None:
    data = warmup_data()
    start = data.index[50]
    buy_hold = run_buy_and_hold(data, 1_000, evaluation_start=start)
    sma = run_sma_crossover(data, 1_000, evaluation_start=start)

    assert buy_hold.equity.index.equals(sma.equity.index)
    assert buy_hold.equity.index[0] == start
    assert buy_hold.equity.index[-1] == sma.equity.index[-1]
    assert buy_hold.equity.iloc[0] <= 1_000
    assert sma.equity.iloc[0] <= 1_000


def test_changing_future_prices_does_not_change_prior_signals_or_trades() -> None:
    data = warmup_data()
    start = data.index[50]
    changed = data.copy()
    changed.loc[data.index[80]:, ["Open", "High", "Low", "Close"]] *= 1.7

    original = run_sma_crossover(data, 1_000, evaluation_start=start)
    perturbed = run_sma_crossover(changed, 1_000, evaluation_start=start)
    cutoff = data.index[79]
    assert original.signals.loc[:cutoff].equals(perturbed.signals.loc[:cutoff])
    original_prior = [x for x in original.executions if x.session <= cutoff]
    perturbed_prior = [x for x in perturbed.executions if x.session <= cutoff]
    assert original_prior == perturbed_prior


def test_open_position_is_valued_at_final_close_without_liquidation() -> None:
    data = warmup_data()
    result = run_buy_and_hold(data, 1_000, evaluation_start=data.index[50])

    assert result.final_units > 0
    assert len(result.executions) == 1
    last_close = data.iloc[-1]["Close"]
    assert result.equity.iloc[-1] == pytest.approx(
        result.final_cash + result.final_units * last_close
    )


def test_transaction_costs_are_charged_by_portfolio_ledger() -> None:
    data = make_data([10, 11], [10, 10])
    result = run_buy_and_hold(data, 1_000, evaluation_start=data.index[0], transaction_cost_rate=0.01)
    trade = result.executions[0].trade

    assert trade.fee == pytest.approx(trade.notional * 0.01)
    assert result.final_cash == pytest.approx(1_000 - trade.notional - trade.fee)
    assert len(result.executions) == 1


def test_identical_inputs_produce_identical_results() -> None:
    data = warmup_data()
    start = data.index[50]
    first = run_sma_crossover(data, 1_000, evaluation_start=start)
    second = run_sma_crossover(data.copy(), 1_000, evaluation_start=start)

    pd.testing.assert_series_equal(first.equity, second.equity)
    assert first.executions == second.executions
    assert first.final_cash == second.final_cash
    assert first.final_units == second.final_units


@pytest.mark.parametrize(
    "bad_data",
    [
        pd.DataFrame(columns=["Open", "High", "Low", "Close"]),
        pd.DataFrame({"Open": [1], "High": [2], "Low": [0], "Close": [1]}),
    ],
)
def test_invalid_or_empty_ohlc_is_rejected(bad_data: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        run_buy_and_hold(bad_data, 100, evaluation_start=bad_data.index[0] if len(bad_data) else None)


def event_test_data() -> pd.DataFrame:
    return make_data([100.0] * 60)


def execute_strategy(strategy, data: pd.DataFrame):
    evaluation_start = data.index[50]
    return strategy(data, 1_000, evaluation_start=evaluation_start)


@pytest.mark.parametrize("strategy", [run_buy_and_hold, run_sma_crossover])
def test_strategies_accept_data_without_event_columns(strategy) -> None:
    result = execute_strategy(strategy, event_test_data())

    assert not result.equity.empty


@pytest.mark.parametrize("strategy", [run_buy_and_hold, run_sma_crossover])
def test_strategies_accept_zero_dividends(strategy) -> None:
    data = event_test_data()
    data["Dividends"] = 0.0

    result = execute_strategy(strategy, data)

    assert not result.equity.empty


@pytest.mark.parametrize("strategy", [run_buy_and_hold, run_sma_crossover])
def test_strategies_accept_splits_column_without_events(strategy) -> None:
    data = event_test_data()
    data["Stock Splits"] = 0.0

    result = execute_strategy(strategy, data)

    assert not result.equity.empty


@pytest.mark.parametrize("strategy", [run_buy_and_hold, run_sma_crossover])
@pytest.mark.parametrize(
    ("column", "event_value", "message"),
    [
        ("Dividends", 0.25, "does not process and reconcile corporate actions"),
        ("Stock Splits", 2.0, "does not process and reconcile corporate actions"),
    ],
)
def test_unprocessed_corporate_actions_block_result(
    strategy, column: str, event_value: float, message: str
) -> None:
    data = event_test_data()
    data[column] = 0.0
    data.iloc[55, data.columns.get_loc(column)] = event_value

    with pytest.raises(ValueError, match=message):
        execute_strategy(strategy, data)


@pytest.mark.parametrize("column", ["Dividends", "Stock Splits"])
@pytest.mark.parametrize(
    "invalid_value", [None, float("inf"), -1.0, "not-a-number", True]
)
def test_invalid_event_values_block_simulation(column: str, invalid_value) -> None:
    data = event_test_data()
    data[column] = pd.Series(0.0, index=data.index, dtype=object)
    data.at[data.index[55], column] = invalid_value

    with pytest.raises(ValueError, match=column):
        run_buy_and_hold(data, 1_000, evaluation_start=data.index[50])
