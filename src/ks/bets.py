"""Kelly sizing for a repeated bet: win probability p, net odds b (win b per 1 staked, else lose 1).

Bet a fraction f of current wealth each time. Wealth multiplies by (1 + f·b) on a win and (1 − f)
on a loss, so what compounds is the expected log of that factor, the growth rate per bet:

    g(f) = p·ln(1 + f·b) + (1 − p)·ln(1 − f)

Kelly's fraction maximises g: f* = p − (1 − p)/b (the edge divided by the odds).
"""

import numpy as np


def kelly_fraction(p: float, b: float) -> float:
    return max(0.0, p - (1 - p) / b)


def growth_rate(f, p: float, b: float):
    """Expected log growth per bet at fraction f (scalar or array)."""
    f = np.asarray(f, dtype=float)
    g = p * np.log1p(f * b) + (1 - p) * np.log1p(-f)
    return float(g) if g.ndim == 0 else g


def simulate(f: float, p: float, b: float, n_bets: int = 1000, n_paths: int = 10_000,
             seed=None) -> np.ndarray:
    """Log wealth (starting at 0 = ₹1) for each path after each bet: shape (n_paths, n_bets + 1)."""
    rng = np.random.default_rng(seed)
    win = rng.random((n_paths, n_bets)) < p
    step = np.where(win, np.log1p(f * b), np.log1p(-f))
    out = np.zeros((n_paths, n_bets + 1))
    np.cumsum(step, axis=1, out=out[:, 1:])
    return out


def summarise(logw: np.ndarray) -> dict:
    final = np.exp(logw[:, -1])
    return {
        "median multiple": float(np.median(final)),
        "mean multiple": float(final.mean()),
        "P(ever halved)": float((logw.min(axis=1) <= np.log(0.5)).mean()),
        "P(behind at end)": float((final < 1).mean()),
    }


def halving_probability(multiple: float, x: float = 0.5) -> float:
    """Chance wealth ever falls to x of its start when betting `multiple` × Kelly, in the
    continuous (many small bets) limit: x^(2/multiple − 1). At 2× Kelly or more it is certain."""
    if multiple >= 2:
        return 1.0
    return float(x ** (2 / multiple - 1))
