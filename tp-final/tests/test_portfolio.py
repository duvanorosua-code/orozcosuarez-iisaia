"""Synthetic acceptance tests for the basic portfolio ledger."""

from datetime import date, datetime

import pytest

from backend.portfolio import Portfolio, Trade, calculate_eligible_units


EX_DATE = date(2025, 3, 10)


def make_trade(side: str, units: float, trade_date) -> Trade:
    return Trade(side, units, 100, units * 100, 0, trade_date)


def test_eligible_units_include_purchase_before_ex_date():
    trades = [make_trade("buy", 10, date(2025, 3, 7))]

    assert calculate_eligible_units(trades, EX_DATE) == pytest.approx(10)


def test_eligible_units_exclude_purchase_on_ex_date():
    trades = [make_trade("buy", 10, EX_DATE)]

    assert calculate_eligible_units(trades, EX_DATE) == pytest.approx(0)


def test_eligible_units_subtract_sale_before_ex_date():
    trades = [make_trade("sell", 4, date(2025, 3, 7))]

    assert calculate_eligible_units(trades, EX_DATE, initial_units=10) == pytest.approx(6)


def test_eligible_units_keep_position_sold_on_ex_date():
    trades = [make_trade("buy", 10, date(2025, 3, 7)), make_trade("sell", 10, EX_DATE)]

    assert calculate_eligible_units(trades, EX_DATE) == pytest.approx(10)


def test_eligible_units_keep_right_after_sale_post_ex_date():
    trades = [
        make_trade("buy", 10, date(2025, 3, 7)),
        make_trade("sell", 10, date(2025, 3, 11)),
    ]

    assert calculate_eligible_units(trades, EX_DATE) == pytest.approx(10)


def test_eligible_units_handle_partial_trades_around_ex_date():
    trades = [
        make_trade("buy", 10, date(2025, 3, 6)),
        make_trade("sell", 3, date(2025, 3, 7)),
        make_trade("buy", 5, EX_DATE),
        make_trade("sell", 2, date(2025, 3, 11)),
    ]

    assert calculate_eligible_units(trades, EX_DATE) == pytest.approx(7)


def test_eligible_units_use_known_nonzero_initial_position():
    trades = [make_trade("sell", 1.5, date(2025, 3, 7))]

    assert calculate_eligible_units(trades, EX_DATE, initial_units=4) == pytest.approx(2.5)


def test_eligible_units_reject_undated_trade():
    trades = [make_trade("buy", 1, None)]

    with pytest.raises(ValueError, match="no trade_date"):
        calculate_eligible_units(trades, EX_DATE)


def test_eligible_units_reject_history_that_goes_short():
    trades = [make_trade("sell", 2, date(2025, 3, 7))]

    with pytest.raises(ValueError, match="negative position"):
        calculate_eligible_units(trades, EX_DATE, initial_units=1)


@pytest.mark.parametrize("initial_units", [-1, float("inf"), float("nan"), True])
def test_eligible_units_reject_invalid_initial_position(initial_units):
    with pytest.raises((TypeError, ValueError)):
        calculate_eligible_units([], EX_DATE, initial_units=initial_units)


@pytest.mark.parametrize(
    ("trades", "ex_date", "error"),
    [
        ([], datetime(2025, 3, 10), TypeError),
        ([make_trade("buy", 1, "2025-03-07")], EX_DATE, TypeError),
        ([make_trade("buy", float("nan"), date(2025, 3, 7))], EX_DATE, ValueError),
        ([make_trade("hold", 1, date(2025, 3, 7))], EX_DATE, ValueError),
    ],
)
def test_eligible_units_reject_invalid_dates_or_trade_values(trades, ex_date, error):
    with pytest.raises(error):
        calculate_eligible_units(trades, ex_date)


def test_initial_capital_and_valuation_without_trades():
    portfolio = Portfolio(1_000_000)

    assert portfolio.cash == pytest.approx(1_000_000)
    assert portfolio.units == pytest.approx(0)
    assert portfolio.dividends_receivable == pytest.approx(0)
    assert portfolio.equity(close_price=125) == pytest.approx(1_000_000)


def test_trade_stores_supplied_trade_date():
    portfolio = Portfolio(1_000)
    trade_date = date(2025, 3, 10)

    trade = portfolio.buy(units=1, price=100, trade_date=trade_date)

    assert trade.trade_date == trade_date
    assert portfolio.trades[-1].trade_date == trade_date


def test_legacy_trade_calls_leave_trade_date_unset():
    portfolio = Portfolio(1_000)

    trade = portfolio.buy(units=1, price=100)
    sale = portfolio.sell(units=1, price=110)

    assert trade.trade_date is None
    assert sale.trade_date is None
    assert [item.trade_date for item in portfolio.trades] == [None, None]


def test_buy_charges_fee_and_reconciles_cash_position_and_equity():
    portfolio = Portfolio(1_000_000, transaction_cost_rate=0.001)

    trade = portfolio.buy(units=10, price=10_000)

    assert trade.notional == pytest.approx(100_000)
    assert trade.fee == pytest.approx(100)
    assert portfolio.cash == pytest.approx(899_900)
    assert portfolio.units == pytest.approx(10)
    assert portfolio.units * 10_000 == pytest.approx(100_000)
    assert portfolio.equity(close_price=10_000) == pytest.approx(999_900)


def test_partial_sale_charges_fee_on_sale_notional():
    portfolio = Portfolio(1_000_000)
    portfolio.buy(units=10, price=10_000)

    trade = portfolio.sell(units=4, price=12_000)

    assert trade.notional == pytest.approx(48_000)
    assert trade.fee == pytest.approx(48)
    assert portfolio.cash == pytest.approx(947_852)
    assert portfolio.units == pytest.approx(6)
    assert portfolio.equity(close_price=12_000) == pytest.approx(1_019_852)


def test_buy_that_would_make_cash_negative_is_rejected_without_mutation():
    portfolio = Portfolio(1_000, transaction_cost_rate=0.001)

    with pytest.raises(ValueError, match="cash negative"):
        portfolio.buy(units=1, price=1_000)

    assert portfolio.cash == pytest.approx(1_000)
    assert portfolio.units == pytest.approx(0)
    assert portfolio.trades == ()


def test_sale_that_would_create_short_position_is_rejected_without_mutation():
    portfolio = Portfolio(1_000)
    portfolio.buy(units=1, price=100)
    cash_before = portfolio.cash

    with pytest.raises(ValueError, match="short position"):
        portfolio.sell(units=1.01, price=100)

    assert portfolio.cash == pytest.approx(cash_before)
    assert portfolio.units == pytest.approx(1)
    assert len(portfolio.trades) == 1


def test_dividend_receivable_does_not_increase_available_cash():
    portfolio = Portfolio(10_000)
    portfolio.buy(units=10, price=100)
    cash_before = portfolio.cash

    receivable = portfolio.record_dividend(
        "synthetic-dividend-1",
        ex_date=date(2025, 3, 10),
        eligible_units=10,
        amount_per_unit=2,
        currency="USD",
    )

    assert receivable.amount == pytest.approx(20)
    assert portfolio.cash == pytest.approx(cash_before)
    assert portfolio.dividends_receivable == pytest.approx(20)
    assert portfolio.equity(close_price=110) == pytest.approx(cash_before + 1_100 + 20)


def test_record_dividend_from_history_uses_pre_ex_date_position_only():
    portfolio = Portfolio(10_000)
    portfolio.buy(10, 100, trade_date=date(2025, 3, 6))
    portfolio.sell(4, 100, trade_date=date(2025, 3, 7))
    portfolio.buy(5, 100, trade_date=date(2025, 3, 10))
    portfolio.sell(11, 100, trade_date=date(2025, 3, 11))
    cash_before = portfolio.cash

    receivable = portfolio.record_dividend_from_history(
        "history-based-event",
        ex_date=date(2025, 3, 10),
        amount_per_unit=2,
        currency="USD",
    )

    assert receivable.eligible_units == pytest.approx(6)
    assert receivable.amount == pytest.approx(12)
    assert portfolio.units == pytest.approx(0)
    assert portfolio.cash == pytest.approx(cash_before)
    assert portfolio.dividends_receivable == pytest.approx(12)


def test_record_dividend_from_history_ignores_all_ex_date_trades():
    portfolio = Portfolio(10_000)
    portfolio.buy(5, 100, trade_date=date(2025, 3, 7))
    portfolio.sell(5, 100, trade_date=date(2025, 3, 10))
    cash_before = portfolio.cash

    receivable = portfolio.record_dividend_from_history(
        "ex-date-trade-event",
        ex_date=date(2025, 3, 10),
        amount_per_unit=3,
        currency="USD",
    )

    assert receivable.eligible_units == pytest.approx(5)
    assert receivable.amount == pytest.approx(15)
    assert portfolio.cash == pytest.approx(cash_before)


def test_history_based_dividend_right_survives_later_sale():
    portfolio = Portfolio(10_000)
    portfolio.buy(5, 100, trade_date=date(2025, 3, 7))
    portfolio.record_dividend_from_history(
        "right-survives-sale",
        ex_date=date(2025, 3, 10),
        amount_per_unit=2,
        currency="USD",
    )

    portfolio.sell(5, 100, trade_date=date(2025, 3, 11))

    assert portfolio.units == pytest.approx(0)
    assert portfolio.dividends_receivable == pytest.approx(10)


def test_history_based_dividend_rejects_undated_trades_without_mutation():
    portfolio = Portfolio(1_000)
    portfolio.buy(1, 100)
    state_before = (
        portfolio.cash,
        portfolio.units,
        dict(portfolio.dividend_receivables),
        portfolio.processed_dividend_event_ids,
    )

    with pytest.raises(ValueError, match="no trade_date"):
        portfolio.record_dividend_from_history(
            "incomplete-history-event",
            ex_date=date(2025, 3, 10),
            amount_per_unit=2,
            currency="USD",
        )

    assert (
        portfolio.cash,
        portfolio.units,
        dict(portfolio.dividend_receivables),
        portfolio.processed_dividend_event_ids,
    ) == state_before


def test_history_based_dividend_duplicate_is_rejected_without_mutation():
    portfolio = Portfolio(1_000)
    portfolio.buy(2, 100, trade_date=date(2025, 3, 7))
    args = {
        "ex_date": date(2025, 3, 10),
        "amount_per_unit": 2,
        "currency": "USD",
    }
    portfolio.record_dividend_from_history("same-history-event", **args)
    state_before = (
        portfolio.cash,
        portfolio.units,
        dict(portfolio.dividend_receivables),
        portfolio.processed_dividend_event_ids,
        portfolio.equity(close_price=110),
    )

    with pytest.raises(ValueError, match="already recorded"):
        portfolio.record_dividend_from_history("same-history-event", **args)

    assert (
        portfolio.cash,
        portfolio.units,
        dict(portfolio.dividend_receivables),
        portfolio.processed_dividend_event_ids,
        portfolio.equity(close_price=110),
    ) == state_before


def test_history_based_dividend_invalid_amount_does_not_mutate_ledger():
    portfolio = Portfolio(1_000)
    portfolio.buy(2, 100, trade_date=date(2025, 3, 7))
    state_before = (portfolio.cash, portfolio.units, dict(portfolio.dividend_receivables))

    with pytest.raises(ValueError, match="greater than zero"):
        portfolio.record_dividend_from_history(
            "invalid-history-amount",
            ex_date=date(2025, 3, 10),
            amount_per_unit=-2,
            currency="USD",
        )

    assert (portfolio.cash, portfolio.units, dict(portfolio.dividend_receivables)) == state_before


def test_history_based_dividend_full_cycle_counts_entitlement_once():
    portfolio = Portfolio(10_000)
    portfolio.buy(10, 100, trade_date=date(2025, 3, 7))
    portfolio.sell(10, 110, trade_date=date(2025, 3, 11))
    cash_before_right = portfolio.cash
    equity_before_right = portfolio.equity(close_price=110)

    portfolio.record_dividend_from_history(
        "synthetic-full-cycle",
        ex_date=date(2025, 3, 10),
        amount_per_unit=2,
        currency="USD",
    )
    equity_with_receivable = portfolio.equity(close_price=110)

    assert portfolio.units == pytest.approx(0)
    assert portfolio.cash == pytest.approx(cash_before_right)
    assert portfolio.dividends_receivable == pytest.approx(20)
    assert equity_with_receivable == pytest.approx(equity_before_right + 20)

    portfolio.confirm_dividend_payment_date("synthetic-full-cycle", date(2025, 3, 20))
    paid = portfolio.pay_dividend("synthetic-full-cycle", date(2025, 3, 20))

    assert paid == pytest.approx(20)
    assert portfolio.cash == pytest.approx(cash_before_right + 20)
    assert portfolio.dividends_receivable == pytest.approx(0)
    assert portfolio.equity(close_price=110) == pytest.approx(equity_with_receivable)

    state_after_payment = (
        portfolio.cash,
        portfolio.units,
        dict(portfolio.dividend_receivables),
        portfolio.processed_dividend_event_ids,
        portfolio.equity(close_price=110),
    )
    with pytest.raises(KeyError, match="unknown dividend event"):
        portfolio.pay_dividend("synthetic-full-cycle", date(2025, 3, 20))
    with pytest.raises(ValueError, match="already recorded"):
        portfolio.record_dividend_from_history(
            "synthetic-full-cycle",
            ex_date=date(2025, 3, 10),
            amount_per_unit=2,
            currency="USD",
        )
    assert (
        portfolio.cash,
        portfolio.units,
        dict(portfolio.dividend_receivables),
        portfolio.processed_dividend_event_ids,
        portfolio.equity(close_price=110),
    ) == state_after_payment


def test_dividend_receivable_cannot_fund_a_purchase():
    portfolio = Portfolio(1_000)
    portfolio.buy(units=1, price=100)
    portfolio.record_dividend(
        "synthetic-dividend-not-cash",
        ex_date=date(2025, 3, 10),
        eligible_units=1,
        amount_per_unit=200,
        currency="USD",
    )
    cash_before = portfolio.cash

    with pytest.raises(ValueError, match="cash negative"):
        portfolio.buy(units=1, price=900)

    assert portfolio.cash == pytest.approx(cash_before)
    assert portfolio.units == pytest.approx(1)
    assert portfolio.dividends_receivable == pytest.approx(200)


def test_confirmed_dividend_payment_transfers_receivable_without_double_counting():
    portfolio = Portfolio(10_000)
    portfolio.buy(units=10, price=100)
    portfolio.record_dividend(
        "synthetic-dividend-2",
        ex_date=date(2025, 3, 10),
        eligible_units=10,
        amount_per_unit=2,
        currency="USD",
    )
    equity_before_payment = portfolio.equity(close_price=110)
    cash_before_payment = portfolio.cash

    with pytest.raises(ValueError, match="not been confirmed"):
        portfolio.pay_dividend("synthetic-dividend-2", on_date=date(2025, 3, 20))
    assert portfolio.cash == pytest.approx(cash_before_payment)

    payment_date = date(2025, 3, 25)
    portfolio.confirm_dividend_payment_date("synthetic-dividend-2", payment_date)
    with pytest.raises(ValueError, match="not payable"):
        portfolio.pay_dividend("synthetic-dividend-2", on_date=date(2025, 3, 24))

    paid_amount = portfolio.pay_dividend("synthetic-dividend-2", on_date=payment_date)

    assert paid_amount == pytest.approx(20)
    assert portfolio.cash == pytest.approx(cash_before_payment + 20)
    assert portfolio.dividends_receivable == pytest.approx(0)
    assert portfolio.equity(close_price=110) == pytest.approx(equity_before_payment)
    assert portfolio.processed_dividend_event_ids == {"synthetic-dividend-2"}


def test_open_position_is_valued_at_final_close_without_liquidation():
    portfolio = Portfolio(1_000_000)
    portfolio.buy(units=10, price=10_000)

    final_equity = portfolio.equity(close_price=11_000)

    assert portfolio.units == pytest.approx(10)
    assert portfolio.cash == pytest.approx(899_900)
    assert final_equity == pytest.approx(1_009_900)
    assert len(portfolio.trades) == 1


def test_dividend_entitlement_survives_sale_after_ex_date():
    portfolio = Portfolio(10_000)
    portfolio.buy(units=10, price=100)
    portfolio.record_dividend(
        "synthetic-dividend-3",
        ex_date=date(2025, 3, 10),
        eligible_units=10,
        amount_per_unit=2,
        currency="USD",
    )

    portfolio.sell(units=10, price=105)

    assert portfolio.units == pytest.approx(0)
    assert portfolio.dividends_receivable == pytest.approx(20)


def test_dividend_rejects_units_above_current_holdings():
    portfolio = Portfolio(1_000)

    with pytest.raises(ValueError, match="cannot exceed current"):
        portfolio.record_dividend(
            "synthetic-dividend-4",
            ex_date=date(2025, 3, 10),
            eligible_units=1,
            amount_per_unit=2,
            currency="USD",
        )


def test_duplicate_dividend_id_is_rejected_before_payment_without_mutation():
    portfolio = Portfolio(10_000)
    portfolio.buy(units=10, price=100)
    event_id = "duplicate-before-payment"
    portfolio.record_dividend(
        event_id,
        ex_date=date(2025, 3, 10),
        eligible_units=10,
        amount_per_unit=2,
        currency="USD",
    )
    state_before = (
        portfolio.cash,
        portfolio.units,
        dict(portfolio.dividend_receivables),
        portfolio.processed_dividend_event_ids,
        portfolio.equity(close_price=110),
    )

    with pytest.raises(ValueError, match="already recorded"):
        portfolio.record_dividend(
            event_id,
            ex_date=date(2025, 3, 10),
            eligible_units=10,
            amount_per_unit=5,
            currency="USD",
        )

    assert (
        portfolio.cash,
        portfolio.units,
        dict(portfolio.dividend_receivables),
        portfolio.processed_dividend_event_ids,
        portfolio.equity(close_price=110),
    ) == state_before


def test_duplicate_dividend_id_is_rejected_after_payment_without_mutation():
    portfolio = Portfolio(10_000)
    portfolio.buy(units=10, price=100)
    event_id = "duplicate-after-payment"
    portfolio.record_dividend(
        event_id,
        ex_date=date(2025, 3, 10),
        eligible_units=10,
        amount_per_unit=2,
        currency="USD",
    )
    portfolio.confirm_dividend_payment_date(event_id, date(2025, 3, 25))
    portfolio.pay_dividend(event_id, date(2025, 3, 25))
    equity_after_payment = portfolio.equity(close_price=110)
    cash_after_payment = portfolio.cash
    units_after_payment = portfolio.units
    event_ids_after_payment = portfolio.processed_dividend_event_ids

    with pytest.raises(ValueError, match="already recorded"):
        portfolio.record_dividend(
            event_id,
            ex_date=date(2025, 3, 10),
            eligible_units=10,
            amount_per_unit=2,
            currency="USD",
        )

    assert portfolio.cash == pytest.approx(cash_after_payment)
    assert portfolio.units == pytest.approx(units_after_payment)
    assert portfolio.dividend_receivables == {}
    assert portfolio.processed_dividend_event_ids == event_ids_after_payment
    assert portfolio.equity(close_price=110) == pytest.approx(equity_after_payment)


def test_failed_dividend_registration_does_not_reserve_event_id_or_mutate_state():
    portfolio = Portfolio(1_000)
    portfolio.buy(units=1, price=100)
    event_id = "retry-after-invalid-registration"
    state_before = (portfolio.cash, portfolio.units, dict(portfolio.dividend_receivables))

    with pytest.raises(ValueError, match="cannot exceed current"):
        portfolio.record_dividend(
            event_id,
            ex_date=date(2025, 3, 10),
            eligible_units=2,
            amount_per_unit=2,
            currency="USD",
        )

    assert (portfolio.cash, portfolio.units, dict(portfolio.dividend_receivables)) == state_before
    assert portfolio.processed_dividend_event_ids == frozenset()
    portfolio.record_dividend(
        event_id,
        ex_date=date(2025, 3, 10),
        eligible_units=1,
        amount_per_unit=2,
        currency="USD",
    )
    assert portfolio.processed_dividend_event_ids == {event_id}


@pytest.mark.parametrize(
    ("eligible_units", "amount_per_unit", "currency", "ex_date", "error"),
    [
        (1, -2, "USD", date(2025, 3, 10), ValueError),
        (1, float("inf"), "USD", date(2025, 3, 10), ValueError),
        (1, float("nan"), "USD", date(2025, 3, 10), ValueError),
        (float("inf"), 2, "USD", date(2025, 3, 10), ValueError),
        (1, 2, "EUR", date(2025, 3, 10), ValueError),
        (1, 2, "USD", "2025-03-10", TypeError),
    ],
)
def test_invalid_dividend_events_are_rejected_without_mutation(
    eligible_units, amount_per_unit, currency, ex_date, error
):
    portfolio = Portfolio(1_000)
    portfolio.buy(units=2, price=100)
    state_before = (
        portfolio.cash,
        portfolio.units,
        dict(portfolio.dividend_receivables),
        portfolio.processed_dividend_event_ids,
        portfolio.equity(close_price=110),
    )

    with pytest.raises(error):
        portfolio.record_dividend(
            "invalid-synthetic-event",
            ex_date=ex_date,
            eligible_units=eligible_units,
            amount_per_unit=amount_per_unit,
            currency=currency,
        )

    assert (
        portfolio.cash,
        portfolio.units,
        dict(portfolio.dividend_receivables),
        portfolio.processed_dividend_event_ids,
        portfolio.equity(close_price=110),
    ) == state_before


def test_dividend_cannot_be_paid_twice():
    portfolio = Portfolio(1_000)
    portfolio.buy(units=2, price=100)
    portfolio.record_dividend(
        "synthetic-pay-once",
        ex_date=date(2025, 3, 10),
        eligible_units=2,
        amount_per_unit=2,
        currency="USD",
    )
    portfolio.confirm_dividend_payment_date("synthetic-pay-once", date(2025, 3, 25))
    portfolio.pay_dividend("synthetic-pay-once", date(2025, 3, 25))
    state_after_payment = (
        portfolio.cash,
        portfolio.units,
        dict(portfolio.dividend_receivables),
        portfolio.processed_dividend_event_ids,
        portfolio.equity(close_price=110),
    )

    with pytest.raises(KeyError, match="unknown dividend event"):
        portfolio.pay_dividend("synthetic-pay-once", date(2025, 3, 25))

    assert (
        portfolio.cash,
        portfolio.units,
        dict(portfolio.dividend_receivables),
        portfolio.processed_dividend_event_ids,
        portfolio.equity(close_price=110),
    ) == state_after_payment


def test_payment_date_before_ex_date_is_rejected_without_mutation():
    portfolio = Portfolio(1_000)
    portfolio.buy(units=2, price=100)
    portfolio.record_dividend(
        "synthetic-invalid-payment-date",
        ex_date=date(2025, 3, 10),
        eligible_units=2,
        amount_per_unit=2,
        currency="USD",
    )
    receivables_before = dict(portfolio.dividend_receivables)

    with pytest.raises(ValueError, match="cannot precede ex_date"):
        portfolio.confirm_dividend_payment_date(
            "synthetic-invalid-payment-date", date(2025, 3, 9)
        )

    assert dict(portfolio.dividend_receivables) == receivables_before
    assert portfolio.cash == pytest.approx(799.8)
    assert portfolio.equity(close_price=110) == pytest.approx(1_023.8)
