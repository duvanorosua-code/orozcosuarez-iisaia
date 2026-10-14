"""Deterministic OHLC fixtures for QUANTLAB's explicitly experimental mode."""

from __future__ import annotations

import math
from typing import Literal

import pandas as pd


Scenario = Literal["uptrend", "sideways", "high_volatility"]


def generate_synthetic_history(
    scenario: Scenario,
    *,
    session_count: int,
    warmup_sessions: int,
) -> pd.DataFrame:
    """Generate deterministic, non-market OHLC rows including indicator warmup.

    The generated weekday index is only a synthetic sequence; it is not an
    exchange calendar and carries no claim about SPY prices or sessions.
    """
    if scenario not in ("uptrend", "sideways", "high_volatility"):
        raise ValueError("unsupported synthetic scenario")
    if isinstance(session_count, bool) or not isinstance(session_count, int) or session_count < 2:
        raise ValueError("session_count must be an integer of at least two")
    if isinstance(warmup_sessions, bool) or not isinstance(warmup_sessions, int) or warmup_sessions < 1:
        raise ValueError("warmup_sessions must be a positive integer")

    total = session_count + warmup_sessions
    dates = pd.bdate_range("2020-01-02", periods=total, name="Date")
    closes: list[float] = []
    for position in range(total):
        if scenario == "uptrend":
            close = 100.0 * (1.0015**position)
        elif scenario == "sideways":
            close = 100.0 + 7.0 * math.sin(position * 2.0 * math.pi / 28.0)
        else:
            # Bounded oscillations create a deliberately volatile path while
            # keeping all prices positive and exactly reproducible.
            close = 100.0 * math.exp(
                0.16 * math.sin(position * 2.0 * math.pi / 9.0)
                + 0.07 * math.sin(position * 2.0 * math.pi / 3.0)
            )
        closes.append(close)

    opens = [closes[0], *closes[:-1]]
    return pd.DataFrame(
        {
            "Open": opens,
            "High": [max(open_price, close) * 1.002 for open_price, close in zip(opens, closes)],
            "Low": [min(open_price, close) * 0.998 for open_price, close in zip(opens, closes)],
            "Close": closes,
            "Volume": [1_000_000] * total,
            "Dividends": [0.0] * total,
            "Stock Splits": [0.0] * total,
        },
        index=dates,
    )
