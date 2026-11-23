"""Kelly with frictions: borrowing dearer than lending, trading costs, volatility forecasts.

Borrowing: Zerodha's margin trading facility (MTF) charges 0.04% a day on the funded amount, about
14.6% a year, plus brokerage of 0.3% or ₹20 per order, whichever is lower (support.zerodha.com, MTF
articles, checked 2026-11). Spare cash is assumed to earn 6.5% (a liquid fund).

ETF delivery costs (zerodha.com/charges and support.zerodha.com "STT on ETFs", checked 2026-11):
STT 0.001% on sells only (gold ETFs exempt), stamp duty 0.015% on buys, NSE transaction charge
0.00322% and SEBI ₹10 per crore with 18% GST, ₹15.93 DP charge per sell day, plus 0.05% slippage
per side (assumed).

With lending at rl and borrowing at rb > rl, growth is a parabola with a kink at f = 1:
for f ≤ 1 it uses rl, above 1 it uses rb. Kelly's fraction is (mu − rl)/σ² if that is below 1,
(mu − rb)/σ² if that is above 1, and exactly 1 in between.
"""

import numpy as np
import pandas as pd

RATES = {
    "stt_sell": 0.00001,
    "stamp_buy": 0.00015,
    "exchange": 0.0000322,
    "sebi": 0.000001,
    "gst": 0.18,
    "dp_per_sell": 15.93,
    "slippage": 0.0005,
    "mtf_brokerage": 0.003,
    "mtf_order_max": 20.0,
}
MTF_RATE = 0.0004 * 365  # 0.04% a day, simple: 14.6% a year


def kelly_spread(mu: float, sigma: float, rl: float, rb: float) -> float:
    lend, borrow = (mu - rl) / sigma**2, (mu - rb) / sigma**2
    if lend <= 1:
        return max(lend, 0.0)
    return borrow if borrow >= 1 else 1.0


def growth_spread(f, mu: float, sigma: float, rl: float, rb: float):
    f = np.asarray(f, dtype=float)
    rate = np.where(f <= 1, rl, rb)
    g = rate + f * (mu - rate) - f**2 * sigma**2 / 2
    return float(g) if g.ndim == 0 else g


def etf_trade_cost(buy: float, sell: float, capital: float, mtf: bool = False,
                   rates: dict = RATES) -> float:
    """Cost of one rebalance of an ETF as a fraction of the portfolio (`buy`, `sell` are traded
    values as fractions of it; `capital` its ₹ value; `mtf` adds the margin brokerage)."""
    fees = (rates["exchange"] + rates["sebi"]) * (1 + rates["gst"]) + rates["slippage"]
    cost = buy * (fees + rates["stamp_buy"]) + sell * (fees + rates["stt_sell"])
    if sell > 0:
        cost += rates["dp_per_sell"] / capital
    if mtf and buy + sell > 0:
        cost += min(rates["mtf_brokerage"] * (buy + sell) * capital,
                    rates["mtf_order_max"]) / capital
    return float(cost)


def ewma_vol(r: pd.Series, lam: float = 0.94, per_year: float | None = None,
             seed: int = 30) -> pd.Series:
    """Annualised volatility forecast for each day from the returns before it (RiskMetrics EWMA,
    seeded with the first `seed` days); NaN until then. `per_year` defaults to the calendar rate
    of the series' own dates."""
    if per_year is None:
        per_year = (len(r) - 1) / ((r.index[-1] - r.index[0]).days / 365.25)
    x = r.to_numpy()
    out = np.full(len(x), np.nan)
    v = float(np.mean(x[:seed] ** 2))
    for t in range(seed, len(x)):
        out[t] = v
        v = lam * v + (1 - lam) * x[t] ** 2
    return pd.Series(np.sqrt(out * per_year), index=r.index)


def run_strategy(r: pd.Series, target: pd.Series, rl: float, rb: float, capital: float,
                 band: float = 0.0, costs: bool = True) -> dict:
    """Daily path of an ETF position. `target[t]` is the fraction wanted at the close of day t,
    decided from data up to then. The position drifts with returns and is traded back to target
    when it is more than `band` away. Cash earns rl; borrowing pays rb a day (simple)."""
    x, tgt, idx = r.to_numpy(), target.to_numpy(), r.index
    days = idx.to_series().diff().dt.days.fillna(0).to_numpy()
    w, f = 1.0, float(tgt[0])
    wealth, frac = np.empty(len(x)), np.empty(len(x))
    wealth[0], frac[0] = w, f
    trades, paid = 0, 0.0
    for t in range(1, len(x)):
        cash = 1 - f
        interest = ((1 + rl) ** (days[t] / 365) - 1) if cash >= 0 else rb / 365 * days[t]
        risky = f * (1 + x[t])
        w_new = w * (risky + cash * (1 + interest))
        if w_new <= 0:
            wealth[t:], frac[t:] = 0.0, 0.0
            break
        f = w * risky / w_new
        w = w_new
        if abs(tgt[t] - f) > band:
            gap = tgt[t] - f
            if costs:
                c = etf_trade_cost(max(gap, 0), max(-gap, 0), w * capital,
                                   mtf=max(f, tgt[t]) > 1)
                w *= 1 - c
                paid += c
            f = float(tgt[t])
            trades += 1
        wealth[t], frac[t] = w, f
    return {"wealth": pd.Series(wealth, index=idx), "fraction": pd.Series(frac, index=idx),
            "trades": trades, "costs": paid}
