"""Kelly sizing for a trading signal: the bet is only as good as the probability behind it.

The signal: each month end, for today's NIFTY 50 stocks, the chance a stock beats the median of the
same stocks next month, from a logistic model of three cross-sectional ranks (12-to-1-month
momentum, last month's return, 60-day volatility), refitted each month on earlier months only.
Using the median of the same stocks as the bar keeps survivorship (today's members did well) out of
the label.

Calibration: fit P(win) = sigmoid(a + slope·logit(p)) on past predictions. A slope below 1 means the
model is overconfident: its probabilities sit too far from 50%. For an even-money bet Kelly stakes
2p − 1, so an overconfident p over-bets by about 1/slope.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize

FEATURES = ["mom", "rev", "vol"]


def _logit(p):
    p = np.asarray(p, float)
    return np.log(p / (1 - p))


def fit_logistic(X, y) -> np.ndarray:
    """Maximum-likelihood logistic regression; returns [intercept, coefficients...]."""
    X1 = np.c_[np.ones(len(X)), np.asarray(X, float)]
    y = np.asarray(y, float)

    def nll(b):
        z = X1 @ b
        return np.sum(np.logaddexp(0, z)) - y @ z

    def grad(b):
        return X1.T @ (1 / (1 + np.exp(-(X1 @ b))) - y)

    return minimize(nll, np.zeros(X1.shape[1]), jac=grad, method="BFGS").x


def calibration(p, y) -> tuple[float, float]:
    """(a, slope) of P(win) = sigmoid(a + slope·logit(p)); slope 1 and a 0 = calibrated."""
    a, slope = fit_logistic(_logit(p)[:, None], y)
    return float(a), float(slope)


def recalibrate(p, a: float, slope: float):
    return 1 / (1 + np.exp(-(a + slope * _logit(p))))


def monthly_panel(R: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    """One row per stock and month end t: feature ranks known at t, and next month's return
    above the median of the same stocks (x) and whether it beat that median (y)."""
    px = (1 + R[symbols].fillna(0)).cumprod().where(R[symbols].notna())
    me = px.resample("ME").last()
    ret = me.pct_change(fill_method=None)
    vol = R[symbols].rolling(60).std().resample("ME").last()
    rows = []
    for i in range(12, len(me) - 1):
        t = me.index[i]
        nxt = ret.iloc[i + 1]
        d = pd.DataFrame({
            "mom": (me.iloc[i - 1] / me.iloc[i - 12] - 1).rank(pct=True),
            "rev": ret.iloc[i].rank(pct=True),
            "vol": vol.loc[t].rank(pct=True),
            "x": nxt - nxt.median(),
            "y": (nxt > nxt.median()).astype(float).where(nxt.notna()),
        }).dropna()
        d["t"] = t
        rows.append(d.rename_axis("symbol").reset_index())
    return pd.concat(rows, ignore_index=True)


def walk_forward_probs(panel: pd.DataFrame, features: list[str] = FEATURES,
                       min_months: int = 36) -> pd.DataFrame:
    """Predicted win probability for each row, from a model fitted on earlier months only."""
    months = sorted(panel["t"].unique())
    out = []
    for i, t in enumerate(months):
        if i < min_months:
            continue
        train = panel[panel["t"] < t]
        b = fit_logistic(train[features].to_numpy() - 0.5, train["y"].to_numpy())
        test = panel[panel["t"] == t].copy()
        z = np.c_[np.ones(len(test)), test[features].to_numpy() - 0.5] @ b
        test["p"] = 1 / (1 + np.exp(-z))
        out.append(test)
    return pd.concat(out, ignore_index=True)


def realised_growth(f, y) -> float:
    """Average log growth per even-money bet: stake f wins f when y = 1, loses f when y = 0."""
    f, y = np.asarray(f, float), np.asarray(y, float)
    return float(np.mean(y * np.log1p(f) + (1 - y) * np.log1p(-f)))
