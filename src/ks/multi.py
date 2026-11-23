"""Kelly with several assets. Weights w (fractions of wealth, the rest in cash at rf); annual mean
returns mu and covariance cov. Log growth a year:

    g(w) = rf + w·(mu − rf) − ½ wᵀ·cov·w

which peaks at Kelly's weights w* = cov⁻¹(mu − rf). Scaled to add up to 1 they are the tangency
portfolio (ef/01), so Kelly = the tangency portfolio held with leverage w*.sum(), and the best
growth is rf + ½·(tangency Sharpe)².
"""

import numpy as np
from scipy.optimize import minimize


def kelly_weights(mu, cov, rf: float) -> np.ndarray:
    return np.linalg.solve(np.asarray(cov, float), np.asarray(mu, float) - rf)


def growth_multi(w, mu, cov, rf: float) -> float:
    w = np.asarray(w, float)
    return float(rf + w @ (np.asarray(mu) - rf) - w @ np.asarray(cov) @ w / 2)


def tangency(mu, cov, rf: float) -> np.ndarray:
    w = kelly_weights(mu, cov, rf)
    return w / w.sum()


def capped_kelly(mu, cov, rf: float, max_gross: float = 1.0) -> np.ndarray:
    """Growth-maximising long-only weights adding up to at most `max_gross` (1 = no borrowing)."""
    n = len(mu)
    res = minimize(lambda w: -growth_multi(w, mu, cov, rf), np.full(n, max_gross / (2 * n)),
                   jac=lambda w: -(np.asarray(mu) - rf - np.asarray(cov) @ w),
                   bounds=[(0, None)] * n, method="SLSQP",
                   constraints=[{"type": "ineq", "fun": lambda w: max_gross - w.sum()}],
                   options={"ftol": 1e-12, "maxiter": 500})
    return res.x


def walk_forward_multi(W, rf: float, multiple: float, window_years: float, max_gross: float,
                       start: str, fixed=None) -> dict:
    """Weekly returns W (assets in columns). At each month's last week, estimate mean and
    covariance from the past `window_years`, hold `multiple` × Kelly long-only with gross at most
    `max_gross` (or the `fixed` weights) through the next month. Cash or borrowing at rf."""
    import pandas as pd

    month = W.index.to_period("M")
    ends = W.index[np.append(month[1:] != month[:-1], True)]
    before = ends[ends < pd.Timestamp(start)]
    ends = ends[ends >= before[-1]] if len(before) else ends
    decided = {}
    for t in ends:
        if fixed is not None:
            decided[t] = np.asarray(fixed, float)
            continue
        past = W[(W.index <= t) & (W.index > t - pd.DateOffset(years=window_years))]
        per_year = (len(past) - 1) / ((past.index[-1] - past.index[0]).days / 365.25)
        mu, cov = past.mean().to_numpy() * per_year, past.cov().to_numpy() * per_year
        decided[t] = capped_kelly(mu, cov / multiple, rf, max_gross)  # c × Kelly = cov / c
    weights = (pd.DataFrame(decided, index=W.columns).T.reindex(W.index).ffill().shift(1))
    days = W.index.to_series().diff().dt.days.fillna(0).to_numpy()
    cash = (1 + rf) ** (days / 365) - 1
    gross = 1 + (weights.to_numpy() * W.to_numpy()).sum(axis=1) \
        + (1 - weights.sum(axis=1).to_numpy()) * cash
    live = W.index >= pd.Timestamp(start)
    first = np.argmax(live)
    gross[: first + 1] = 1.0
    wealth = pd.Series(np.cumprod(np.maximum(gross, 0)), index=W.index)[live]
    return {"wealth": wealth, "weights": weights[live]}
