"""Kelly with an estimated edge.

If the average return is estimated from T years of data, the estimate's error has variance σ²/T, so
the estimated Kelly fraction f̂ = (μ̂ − r)/σ² scatters around the true f* with variance 1/(σ²T).
Betting c·f̂, the expected growth above cash is (S = Sharpe ratio)

    c·S² − c²/2 · (S² + 1/T)

which peaks at c = S²T / (S²T + 1): the noisier the estimate, the smaller the multiple of Kelly.
"""

import numpy as np
import pandas as pd

from ks.stock import annual_stats, kelly_continuous


def optimal_multiple(sharpe: float, years: float) -> float:
    if np.isinf(years):
        return 1.0
    x = sharpe**2 * years
    return x / (x + 1)


def excess_growth_estimated(c, sharpe: float, years: float):
    """Expected log growth a year above cash when betting c × an estimated Kelly fraction."""
    c = np.asarray(c, dtype=float)
    noise = 0.0 if np.isinf(years) else 1 / years
    g = c * sharpe**2 - c**2 / 2 * (sharpe**2 + noise)
    return float(g) if g.ndim == 0 else g


def simulate_estimated_growth(c: float, mu: float, sigma: float, rf: float, years: float,
                              n: int = 2000, per_year: int = 247, seed=None) -> float:
    """Monte Carlo check: estimate μ and σ from `years` of simulated daily returns, bet c × the
    estimated Kelly fraction, and average the true expected growth above cash that earns."""
    rng = np.random.default_rng(seed)
    days = int(years * per_year)
    x = rng.normal(mu / per_year, sigma / np.sqrt(per_year), (n, days))
    mu_hat = x.mean(axis=1) * per_year
    sig_hat = x.std(axis=1, ddof=1) * np.sqrt(per_year)
    f = c * (mu_hat - rf) / sig_hat**2
    return float(np.mean(f * (mu - rf) - f**2 * sigma**2 / 2))


def walk_forward(r: pd.Series, rf: float, multiple: float, window_years: float | None,
                 cap: float, floor: float, start: str) -> dict:
    """Each month end, estimate Kelly from the past `window_years` (None = all history so far),
    hold `multiple` × it (clipped to [floor, cap]) through the next month, reset daily.
    Returns daily wealth (from ₹1 at `start`) and the fraction held each day."""
    r = r.dropna()
    month = r.index.to_period("M")
    month_ends = r.index[np.append(month[1:] != month[:-1], True)]  # last trading day of each
    decisions = {}
    before = month_ends[month_ends < pd.Timestamp(start)]
    if len(before):  # only the month end before `start` onwards is needed
        month_ends = month_ends[month_ends >= before[-1]]
    for t in month_ends:
        past = r[r.index <= t]
        if window_years is not None:
            past = past[past.index > t - pd.DateOffset(years=window_years)]
        s = annual_stats(past)
        decisions[t] = float(np.clip(multiple * kelly_continuous(s["mu"], s["sigma"], rf),
                                     floor, cap))
    frac = pd.Series(decisions).reindex(r.index).ffill().shift(1)  # decided at close, held after
    days = r.index.to_series().diff().dt.days.fillna(0).to_numpy()
    cash = (1 + rf) ** (days / 365) - 1
    live = r.index >= pd.Timestamp(start)
    first = np.argmax(live)
    gross = 1 + frac.to_numpy() * r.to_numpy() + (1 - frac.to_numpy()) * cash
    gross[: first + 1] = 1.0  # wealth starts at ₹1 on the first live day's close
    wealth = pd.Series(np.cumprod(np.maximum(gross, 0)), index=r.index)[live]
    return {"wealth": wealth, "fraction": frac[live]}
