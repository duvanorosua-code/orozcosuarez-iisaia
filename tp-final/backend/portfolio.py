"""Basic single-asset, single-currency portfolio ledger."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from numbers import Real
from types import MappingProxyType
from typing import Literal


DEFAULT_TRANSACTION_COST_RATE = 0.001


def _finite_number(name: str, value: Real) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _session_date(name: str, value: date) -> date:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise TypeError(f"{name} must be a date without a time component")
    return value


def _trade_date(value: date | None) -> date | None:
    """Validate a trade's calendar date, normalizing datetime sessions."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, date):
        raise TypeError("trade_date must be a date or None")
    return value


@dataclass(frozen=True)
class Trade:
    """A completed trade and its calculated transaction cost."""

    side: Literal["buy", "sell"]
    units: float
    price: float
    notional: float
    fee: float
    trade_date: date | None = None


@dataclass(frozen=True)
class DividendReceivable:
    """A confirmed dividend entitlement kept separate from available cash."""

    event_id: str
    ex_date: date
    eligible_units: float
    amount_per_unit: float
    currency: str
    payment_date: date | None = None

    @property
    def amount(self) -> float:
        return self.eligible_units * self.amount_per_unit


def calculate_eligible_units(
    trades: Iterable[Trade],
    ex_date: date,
    initial_units: Real = 0,
) -> float:
    """Reconstruct units entitled immediately before ex-date trading.

    Trades dated before ``ex_date`` affect entitlement; trades on that date or
    later do not. The full dated history is checked chronologically for short
    positions. ``initial_units`` is the known position before the first trade
    in the supplied history. This uses trade dates only; settlement dates,
    special distribution rules, and split conversions are not inferred.
    """
    event_date = _session_date("ex_date", ex_date)
    starting_units = _finite_number("initial_units", initial_units)
    if starting_units < 0:
        raise ValueError("initial_units cannot be negative")

    try:
        history = tuple(trades)
    except TypeError as error:
        raise TypeError("trades must be an iterable of Trade objects") from error

    dated: list[tuple[date, int, Trade, float]] = []
    for position, trade in enumerate(history):
        if not isinstance(trade, Trade):
            raise TypeError(f"trades[{position}] must be a Trade")
        trade_date = _trade_date(trade.trade_date)
        if trade_date is None:
            raise ValueError(f"trades[{position}] has no trade_date")
        if trade.side not in ("buy", "sell"):
            raise ValueError(f"trades[{position}] has an invalid side")
        quantity = _finite_number(f"trades[{position}].units", trade.units)
        if quantity <= 0:
            raise ValueError(f"trades[{position}].units must be greater than zero")
        dated.append((trade_date, position, trade, quantity))

    chronological = sorted(dated, key=lambda item: (item[0], item[1]))
    position_units = starting_units
    eligible_units = starting_units
    for trade_date, _, trade, quantity in chronological:
        change = quantity if trade.side == "buy" else -quantity
        position_units += change
        if position_units < 0:
            raise ValueError("trade history produces a negative position")
        if trade_date < event_date:
            eligible_units += change
            if eligible_units < 0:
                raise ValueError("pre-ex-date history produces a negative position")

    return eligible_units


class Portfolio:
    """Portfolio state for one asset and one currency.

    Dividend entitlements must be recorded on the ex-date before any trade
    for that session, with ``eligible_units`` supplied by the caller. A
    payment date is never inferred: it must be explicitly confirmed before a
    receivable can become available cash.
    """

    def __init__(
        self,
        initial_capital: Real,
        transaction_cost_rate: Real = DEFAULT_TRANSACTION_COST_RATE,
        currency: str = "USD",
    ) -> None:
        capital = _finite_number("initial_capital", initial_capital)
        if capital <= 0:
            raise ValueError("initial_capital must be greater than zero")

        cost_rate = _finite_number("transaction_cost_rate", transaction_cost_rate)
        if not 0 <= cost_rate < 1:
            raise ValueError("transaction_cost_rate must be in [0, 1)")

        if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a three-letter code")

        self._initial_capital = capital
        self._cash = capital
        self._units = 0.0
        self._transaction_cost_rate = cost_rate
        self._currency = currency.upper()
        self._trades: list[Trade] = []
        self._dividend_receivables: dict[str, DividendReceivable] = {}
        self._processed_dividend_event_ids: set[str] = set()

    @property
    def initial_capital(self) -> float:
        return self._initial_capital

    @property
    def cash(self) -> float:
        """Spendable cash; excludes dividend receivables."""
        return self._cash

    @property
    def units(self) -> float:
        return self._units

    @property
    def transaction_cost_rate(self) -> float:
        return self._transaction_cost_rate

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def trades(self) -> tuple[Trade, ...]:
        return tuple(self._trades)

    @property
    def dividend_receivables(self) -> Mapping[str, DividendReceivable]:
        """Read-only mapping of unpaid dividend entitlements by event ID."""
        return MappingProxyType(self._dividend_receivables)

    @property
    def processed_dividend_event_ids(self) -> frozenset[str]:
        """IDs recorded during this portfolio's lifetime, paid or unpaid."""
        return frozenset(self._processed_dividend_event_ids)

    @property
    def dividends_receivable(self) -> float:
        return sum(item.amount for item in self._dividend_receivables.values())

    def buy(self, units: Real, price: Real, *, trade_date: date | None = None) -> Trade:
        """Buy fractional units, charging the fee on purchase notional."""
        execution_date = _trade_date(trade_date)
        quantity = _finite_number("units", units)
        execution_price = _finite_number("price", price)
        if quantity <= 0:
            raise ValueError("units must be greater than zero")
        if execution_price <= 0:
            raise ValueError("price must be greater than zero")

        notional = quantity * execution_price
        fee = notional * self._transaction_cost_rate
        total_cost = notional + fee
        if (
            not math.isfinite(notional)
            or not math.isfinite(fee)
            or not math.isfinite(total_cost)
        ):
            raise ValueError("purchase amounts exceed the supported numeric range")
        if total_cost > self._cash:
            raise ValueError("purchase would make available cash negative")

        trade = Trade("buy", quantity, execution_price, notional, fee, execution_date)
        self._cash -= total_cost
        self._units += quantity
        self._trades.append(trade)
        return trade

    def sell(self, units: Real, price: Real, *, trade_date: date | None = None) -> Trade:
        """Sell fractional units, charging the fee on sale notional."""
        execution_date = _trade_date(trade_date)
        quantity = _finite_number("units", units)
        execution_price = _finite_number("price", price)
        if quantity <= 0:
            raise ValueError("units must be greater than zero")
        if execution_price <= 0:
            raise ValueError("price must be greater than zero")
        if quantity > self._units:
            raise ValueError("sale would create a short position")

        notional = quantity * execution_price
        fee = notional * self._transaction_cost_rate
        if not math.isfinite(notional) or not math.isfinite(fee):
            raise ValueError("sale amounts exceed the supported numeric range")
        trade = Trade("sell", quantity, execution_price, notional, fee, execution_date)
        self._units -= quantity
        self._cash += notional - fee
        self._trades.append(trade)
        return trade

    def record_dividend(
        self,
        event_id: str,
        *,
        ex_date: date,
        eligible_units: Real,
        amount_per_unit: Real,
        currency: str,
    ) -> DividendReceivable:
        """Record the entitlement using units eligible on the ex-date.

        Call before processing trades for ``ex_date``. The explicit eligible
        unit count avoids inferring entitlement from ambiguous intraday order
        timing. No payment date or cash is inferred here.
        """
        return self._record_dividend(
            event_id,
            ex_date=ex_date,
            eligible_units=eligible_units,
            amount_per_unit=amount_per_unit,
            currency=currency,
            require_current_units=True,
        )

    def record_dividend_from_history(
        self,
        event_id: str,
        *,
        ex_date: date,
        amount_per_unit: Real,
        currency: str,
    ) -> DividendReceivable:
        """Calculate entitlement from this ledger's complete dated trade history.

        The portfolio starts with zero units, so the ledger's trade history is
        used with ``initial_units=0``. A right earned before ex-date remains
        valid even if later sales leave fewer current units.
        """
        eligible_units = calculate_eligible_units(
            self._trades, ex_date=ex_date, initial_units=0
        )
        return self._record_dividend(
            event_id,
            ex_date=ex_date,
            eligible_units=eligible_units,
            amount_per_unit=amount_per_unit,
            currency=currency,
            require_current_units=False,
        )

    def _record_dividend(
        self,
        event_id: str,
        *,
        ex_date: date,
        eligible_units: Real,
        amount_per_unit: Real,
        currency: str,
        require_current_units: bool,
    ) -> DividendReceivable:
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id must be a non-empty string")
        if event_id in self._processed_dividend_event_ids:
            raise ValueError(f"dividend event {event_id!r} is already recorded")

        event_date = _session_date("ex_date", ex_date)
        quantity = _finite_number("eligible_units", eligible_units)
        amount = _finite_number("amount_per_unit", amount_per_unit)
        if quantity <= 0:
            raise ValueError("eligible_units must be greater than zero")
        if require_current_units and quantity > self._units:
            raise ValueError("eligible_units cannot exceed current portfolio units")
        if amount <= 0:
            raise ValueError("amount_per_unit must be greater than zero")
        if not math.isfinite(quantity * amount):
            raise ValueError("dividend amount exceeds the supported numeric range")
        if not isinstance(currency, str) or currency.upper() != self._currency:
            raise ValueError("dividend currency must match portfolio currency")

        receivable = DividendReceivable(
            event_id=event_id,
            ex_date=event_date,
            eligible_units=quantity,
            amount_per_unit=amount,
            currency=self._currency,
        )
        self._dividend_receivables[event_id] = receivable
        self._processed_dividend_event_ids.add(event_id)
        return receivable

    def confirm_dividend_payment_date(self, event_id: str, payment_date: date) -> None:
        """Store a payment date explicitly verified by the caller."""
        receivable = self._get_receivable(event_id)
        confirmed_date = _session_date("payment_date", payment_date)
        if confirmed_date < receivable.ex_date:
            raise ValueError("payment_date cannot precede ex_date")
        if receivable.payment_date is not None and receivable.payment_date != confirmed_date:
            raise ValueError("a different payment_date is already confirmed")
        self._dividend_receivables[event_id] = replace(
            receivable, payment_date=confirmed_date
        )

    def pay_dividend(self, event_id: str, on_date: date) -> float:
        """Transfer a due, date-confirmed receivable into available cash."""
        receivable = self._get_receivable(event_id)
        payment_date = _session_date("on_date", on_date)
        if receivable.payment_date is None:
            raise ValueError("dividend payment date has not been confirmed")
        if payment_date < receivable.payment_date:
            raise ValueError("dividend is not payable before its confirmed date")

        amount = receivable.amount
        self._cash += amount
        del self._dividend_receivables[event_id]
        return amount

    def equity(self, close_price: Real) -> float:
        """Value the open position at Close plus cash and receivables."""
        close = _finite_number("close_price", close_price)
        if close <= 0:
            raise ValueError("close_price must be greater than zero")
        value = self._cash + self._units * close + self.dividends_receivable
        if not math.isfinite(value):
            raise ValueError("portfolio equity exceeds the supported numeric range")
        return value

    def _get_receivable(self, event_id: str) -> DividendReceivable:
        try:
            return self._dividend_receivables[event_id]
        except KeyError as error:
            raise KeyError(f"unknown dividend event {event_id!r}") from error
