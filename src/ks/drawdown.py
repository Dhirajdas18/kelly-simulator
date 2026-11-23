"""Drawdowns and time under Kelly sizing.

Holding c × Kelly of an asset with Sharpe ratio S (cash at r), log wealth grows by
r + S²(c − c²/2) a year with volatility c·S. Two bet sizes c1 > c2 on the same asset differ by a
normal amount, so the chance that c1 ends ahead after T years is

    Φ( √T · S · (1 − (c1 + c2)/2) )

Kelly against half Kelly is Φ(√T·S/4): with S 0.45 that needs 214 years for 95% confidence.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

PER_YEAR = 247  # trading days a year, from NSE's calendar 2009-2026 (ks/02)


def drawdown(w: pd.Series) -> pd.Series:
    return w / w.cummax() - 1


def longest_underwater(w: pd.Series) -> float:
    """Longest calendar time (years) from a peak until wealth regains it (or the data ends)."""
    peak = w.cummax()
    longest, start, prev = 0.0, None, w.index[0]  # the first day is its own peak
    for t, below in zip(w.index, (w < peak).to_numpy(), strict=True):
        if below and start is None:
            start = prev
        if not below and start is not None:
            longest = max(longest, (t - start).days / 365.25)
            start = None
        prev = t
    if start is not None:
        longest = max(longest, (w.index[-1] - start).days / 365.25)
    return longest


def prob_ahead(c1: float, c2: float, sharpe: float, years: float) -> float:
    """Chance c1 × Kelly ends with more than c2 × Kelly after `years` (same asset, c1 ≠ c2)."""
    if c1 == c2:
        return 0.5
    hi, lo = max(c1, c2), min(c1, c2)
    p = float(norm.cdf(np.sqrt(years) * sharpe * (1 - (hi + lo) / 2)))
    return p if c1 > c2 else 1 - p


def years_to_confidence(c1: float, c2: float, sharpe: float, p: float = 0.95) -> float:
    edge = sharpe * abs(1 - (c1 + c2) / 2)
    return float((norm.ppf(p) / edge) ** 2)


def simulate_log_wealth(f: float, mu: float, sigma: float, rf: float, years: float,
                        n: int = 2000, seed=None, per_year: int = PER_YEAR) -> np.ndarray:
    """Daily log wealth (from 0) holding fraction f of a lognormal asset, the rest at rf; the same
    seed gives the same market shocks for every f, so bet sizes can be compared path by path."""
    rng = np.random.default_rng(seed)
    days = int(round(years * per_year))
    dt = 1 / per_year
    z = rng.standard_normal((n, days)).astype(np.float32)
    step = (rf + f * (mu - rf) - f**2 * sigma**2 / 2) * dt + f * sigma * np.sqrt(dt) * z
    out = np.zeros((n, days + 1), dtype=np.float32)
    np.cumsum(step, axis=1, out=out[:, 1:])
    return out
