"""Kelly for a stock: hold a fraction f of wealth in it, the rest in cash at rate rf (f > 1 means
borrowing at rf). With annual expected return mu and volatility sigma, wealth grows at

    g(f) = rf + f·(mu − rf) − f²·sigma²/2      (log growth per year)

which peaks at Kelly's f* = (mu − rf) / sigma², where the growth is rf + Sharpe²/2.

Annual figures come from calendar time: trading days per year = (days − 1) / years elapsed.
"""

import numpy as np
import pandas as pd


def annual_stats(r: pd.Series) -> dict:
    r = r.dropna()
    years = (r.index[-1] - r.index[0]).days / 365.25
    per_year = (len(r) - 1) / years
    return {"mu": float(r.mean() * per_year), "sigma": float(r.std() * np.sqrt(per_year)),
            "per_year": per_year, "years": years}


def kelly_continuous(mu: float, sigma: float, rf: float) -> float:
    return (mu - rf) / sigma**2


def growth_continuous(f, mu: float, sigma: float, rf: float):
    f = np.asarray(f, dtype=float)
    g = rf + f * (mu - rf) - f**2 * sigma**2 / 2
    return float(g) if g.ndim == 0 else g


def levered_growth(r: pd.Series, f: float, rf: float) -> float:
    """Realised annual log growth holding fraction f, rebalanced daily, cash (or borrowing) at rf
    accrued over the calendar days between closes. −inf if a day wipes the account out."""
    r = r.dropna()
    days = np.diff(r.index.values).astype("timedelta64[D]").astype(float)
    cash = (1 + rf) ** (days / 365) - 1
    gross = 1 + f * r.to_numpy()[1:] + (1 - f) * cash
    if np.any(gross <= 0):
        return -np.inf
    years = (r.index[-1] - r.index[0]).days / 365.25
    return float(np.log(gross).sum() / years)


def rolling_kelly(r: pd.Series, rf: float, years: int = 3) -> pd.Series:
    """Kelly's fraction from the trailing `years` of returns, for each day once that much exists."""
    r = r.dropna()
    out = pd.Series(np.nan, index=r.index)
    start = r.index[0] + pd.DateOffset(years=years)
    for t in r.index[r.index >= start]:
        s = annual_stats(r[(r.index > t - pd.DateOffset(years=years)) & (r.index <= t)])
        out[t] = kelly_continuous(s["mu"], s["sigma"], rf)
    return out
