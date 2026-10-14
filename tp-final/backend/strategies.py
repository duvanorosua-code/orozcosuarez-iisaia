"""Synthetic-data-ready Buy and Hold and SMA crossover strategies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

import pandas as pd

from backend.portfolio import DEFAULT_TRANSACTION_COST_RATE, Portfolio, Trade


@dataclass(frozen=True)
class Execution:
    """A ledger trade together with the session where it was executed."""

    session: object
    trade: Trade


@dataclass(frozen=True)
class StrategyResult:
    """Daily close valuation and trace of a strategy run."""

    equity: pd.Series
    executions: tuple[Execution, ...]
    final_cash: float
    final_units: float
    signals: pd.Series | None = None


def _validated_ohlc(data: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    required = ("Open", "High", "Low", "Close")
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"missing OHLC columns: {', '.join(missing)}")
    if data.empty:
        raise ValueError("data must contain at least one session")
    if not data.index.is_unique:
        raise ValueError("session index must not contain duplicates")
    if not data.index.is_monotonic_increasing:
        raise ValueError("sessions must be in chronological order")

    _validate_no_unprocessed_events(data, "Dividends")
    _validate_no_unprocessed_events(data, "Stock Splits")

    result = data.loc[:, required].copy()
    for column in required:
        try:
            result[column] = pd.to_numeric(result[column], errors="raise")
        except (TypeError, ValueError) as error:
            raise ValueError(f"{column} must contain numeric values") from error
        values = result[column].to_numpy(dtype=float)
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError(f"{column} values must be finite and greater than zero")

    invalid = (
        (result["Low"] > result[["Open", "Close"]].min(axis=1))
        | (result["High"] < result[["Open", "Close"]].max(axis=1))
        | (result["Low"] > result["High"])
    )
    if invalid.any():
        raise ValueError("OHLC relationships are invalid")
    return result


def _validate_no_unprocessed_events(data: pd.DataFrame, column: str) -> None:
    """Require any supplied corporate-action column to prove no event exists.

    Strategy execution does not process dividend entitlements or split basis
    changes yet. Zero means no event in the current yfinance action columns;
    any non-zero value blocks simulation until reconciled by an event-aware
    execution path.
    """
    if column not in data.columns:
        return

    raw_values = data[column]
    if not isinstance(raw_values, pd.Series):
        raise ValueError(f"{column} must be an unambiguous single column")
    values: list[float] = []
    for value in raw_values:
        if pd.api.types.is_bool_dtype(type(value)):
            raise ValueError(f"{column} must contain numeric event values, not booleans")
        try:
            missing = pd.isna(value)
        except (TypeError, ValueError):
            missing = False
        if isinstance(missing, bool) and missing:
            raise ValueError(
                f"{column} contains missing values; event absence cannot be verified"
            )
        if not pd.api.types.is_number(value):
            raise ValueError(f"{column} must contain numeric event values")
        try:
            number = float(value)
        except (OverflowError, TypeError, ValueError) as error:
            raise ValueError(f"{column} must contain finite numeric event values") from error
        if not math.isfinite(number):
            raise ValueError(f"{column} contains non-finite values")
        if number < 0:
            raise ValueError(f"{column} values cannot be negative")
        values.append(number)

    if any(value > 0 for value in values):
        event_name = "dividends" if column == "Dividends" else "stock splits"
        raise ValueError(
            f"{column} contains {event_name}; simulation is blocked because "
            "this execution path does not process and reconcile corporate actions"
        )


def _evaluation_position(index: pd.Index, evaluation_start: object) -> int:
    try:
        position = index.get_loc(evaluation_start)
    except KeyError as error:
        raise ValueError("evaluation_start must identify a session in data") from error
    if not isinstance(position, int):
        raise ValueError("evaluation_start must identify exactly one session")
    if position >= len(index):
        raise ValueError("evaluation_start is outside the data")
    return position


def _capital_units(portfolio: Portfolio, price: float) -> float:
    quantity = portfolio.cash / (price * (1.0 + portfolio.transaction_cost_rate))
    # Match Portfolio.buy's separate notional and fee calculations exactly.
    # A single nextafter step is not always enough because division and the
    # ledger's multiplication/addition can round in opposite directions.
    while quantity > 0:
        notional = quantity * price
        total_cost = notional + notional * portfolio.transaction_cost_rate
        if math.isfinite(total_cost) and total_cost <= portfolio.cash:
            return quantity
        quantity = math.nextafter(quantity, 0.0)
    raise ValueError("available cash is insufficient to purchase a fractional unit")


def _result(
    portfolio: Portfolio,
    dates: list[object],
    values: list[float],
    executions: list[Execution],
    signals: pd.Series | None = None,
) -> StrategyResult:
    equity = pd.Series(values, index=pd.Index(dates), name="equity", dtype=float)
    return StrategyResult(
        equity=equity,
        executions=tuple(executions),
        final_cash=portfolio.cash,
        final_units=portfolio.units,
        signals=signals,
    )


def run_buy_and_hold(
    data: pd.DataFrame,
    initial_capital: Real,
    *,
    evaluation_start: object,
    transaction_cost_rate: Real = DEFAULT_TRANSACTION_COST_RATE,
) -> StrategyResult:
    """Buy at the first evaluated Open, then value the unliquidated holding."""
    ohlc = _validated_ohlc(data)
    start = _evaluation_position(ohlc.index, evaluation_start)
    portfolio = Portfolio(initial_capital, transaction_cost_rate)
    dates = list(ohlc.index[start:])
    executions: list[Execution] = []
    values: list[float] = []

    first_date = dates[0]
    units = _capital_units(portfolio, float(ohlc.iloc[start]["Open"]))
    trade = portfolio.buy(
        units, float(ohlc.iloc[start]["Open"]), trade_date=first_date
    )
    executions.append(Execution(first_date, trade))
    for row in ohlc.iloc[start:].itertuples():
        values.append(portfolio.equity(float(row.Close)))
    return _result(portfolio, dates, values, executions)


def calculate_sma_signals(
    closes: pd.Series, short_window: int = 20, long_window: int = 50
) -> pd.DataFrame:
    """Calculate close-only moving averages and desired long/cash state.

    ``target`` remains missing until ``long_window`` valid closes are present.
    The target for a session is only actionable at the following session Open.
    """
    for name, window in (("short_window", short_window), ("long_window", long_window)):
        if isinstance(window, bool) or not isinstance(window, int):
            raise TypeError(f"{name} must be an integer")
        if window <= 0:
            raise ValueError(f"{name} must be greater than zero")
    if short_window >= long_window:
        raise ValueError("short_window must be less than long_window")
    if not isinstance(closes, pd.Series):
        raise TypeError("closes must be a pandas Series")
    if closes.empty or not closes.index.is_unique or not closes.index.is_monotonic_increasing:
        raise ValueError("closes must have a non-empty, unique chronological index")
    try:
        values = pd.to_numeric(closes, errors="raise").astype(float)
    except (TypeError, ValueError) as error:
        raise ValueError("closes must contain numeric values") from error
    if values.isna().any() or not all(math.isfinite(value) and value > 0 for value in values):
        raise ValueError("closes must be finite and greater than zero")

    short_sma = values.rolling(short_window, min_periods=short_window).mean()
    long_sma = values.rolling(long_window, min_periods=long_window).mean()
    target = pd.Series(pd.NA, index=values.index, dtype="boolean", name="target")
    valid = long_sma.notna()
    target.loc[valid] = (short_sma.loc[valid] > long_sma.loc[valid]).to_numpy()
    return pd.DataFrame({"short_sma": short_sma, "long_sma": long_sma, "target": target})


def run_sma_crossover(
    data: pd.DataFrame,
    initial_capital: Real,
    *,
    evaluation_start: object,
    short_window: int = 20,
    long_window: int = 50,
    transaction_cost_rate: Real = DEFAULT_TRANSACTION_COST_RATE,
) -> StrategyResult:
    """Trade SMA targets at the next Open, using prior closes only.

    ``evaluation_start`` must have one complete long-window of validated
    closes before it. Those rows are indicator warmup only and are excluded
    from the returned valuation curve.
    """
    ohlc = _validated_ohlc(data)
    start = _evaluation_position(ohlc.index, evaluation_start)
    signals = calculate_sma_signals(ohlc["Close"], short_window, long_window)["target"]
    if start < long_window:
        raise ValueError(
            f"evaluation_start requires at least {long_window} prior valid closes"
        )
    portfolio = Portfolio(initial_capital, transaction_cost_rate)
    dates = list(ohlc.index[start:])
    executions: list[Execution] = []
    values: list[float] = []

    for position in range(start, len(ohlc)):
        prior_target = signals.iloc[position - 1] if position > 0 else pd.NA
        row = ohlc.iloc[position]
        if not pd.isna(prior_target):
            if bool(prior_target) and portfolio.units == 0:
                units = _capital_units(portfolio, float(row["Open"]))
                trade = portfolio.buy(
                    units, float(row["Open"]), trade_date=ohlc.index[position]
                )
                executions.append(Execution(ohlc.index[position], trade))
            elif not bool(prior_target) and portfolio.units > 0:
                trade = portfolio.sell(
                    portfolio.units, float(row["Open"]), trade_date=ohlc.index[position]
                )
                executions.append(Execution(ohlc.index[position], trade))
        values.append(portfolio.equity(float(row["Close"])))

    return _result(
        portfolio,
        dates,
        values,
        executions,
        signals=signals.iloc[start:].copy(),
    )
