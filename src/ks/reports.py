"""README findings, one function per topic: `ks report <topic>` writes charts to out/."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ks import plots
from ks.bets import growth_rate, halving_probability, kelly_fraction, simulate, summarise

GAME = {"p": 0.55, "b": 1.0}  # win 55% of even-money bets: Kelly bets 10%
MULTIPLES = (0.25, 0.5, 1.0, 1.5, 2.0, 3.0)
N_BETS, N_PATHS = 1000, 10_000


def report_bets(out_dir: Path) -> dict:
    """One repeated bet: growth against bet size, wealth paths, and the odds of a bad outcome."""
    p, b = GAME["p"], GAME["b"]
    fk = kelly_fraction(p, b)
    paths = {m: simulate(m * fk, p, b, N_BETS, N_PATHS, seed=0) for m in MULTIPLES}
    stats = {m: summarise(L) for m, L in paths.items()}
    g = {m: growth_rate(m * fk, p, b) for m in MULTIPLES}

    fig, ax = plt.subplots(figsize=(9, 4.6))
    xs = np.linspace(0, 3.05, 300)
    ax.plot(xs, growth_rate(xs * fk, p, b) * 1000, color=plots.SERIES[0], lw=2)
    ax.axhline(0, color=plots.TEXT_2, lw=0.8)
    for m in (0.5, 1.0, 1.5, 2.0):
        ax.plot([m], [g[m] * 1000], "o", ms=7, color=plots.SERIES[0])
        label = {0.5: "half Kelly", 1.0: "Kelly", 1.5: "1.5× Kelly", 2.0: "double Kelly"}[m]
        ax.annotate(f"{label}\n{g[m] * 1000:.2f}", (m, g[m] * 1000), xytext=(0, 10),
                    textcoords="offset points", ha="center", fontsize=8, color=plots.TEXT_2)
    ax.set_xlabel(f"bet size as a multiple of Kelly's fraction ({fk:.0%} of wealth)")
    ax.set_ylabel("growth per bet, thousandths of log wealth")
    ax.set_ylim(-12, 8)
    ratio = stats[1.5]["P(ever halved)"] / stats[0.5]["P(ever halved)"]
    ax.set_title(f"Half Kelly keeps {g[0.5] / g[1.0]:.0%} of the growth; 1.5× Kelly grows the same "
                 f"with {ratio:.1f}× the risk of halving")
    plots.save(fig, out_dir, "bets_growth")

    fig, ax = plt.subplots(figsize=(9, 4.8))
    n = np.arange(0, N_BETS + 1, 10)  # every 10th bet: even and odd counts alternate in wealth
    for m, c, name in ((0.5, plots.SERIES[2], "half Kelly"), (1.0, plots.SERIES[0], "Kelly"),
                       (2.0, plots.SERIES[1], "double Kelly")):
        q10, q90 = np.exp(np.quantile(paths[m][:, n], [0.1, 0.9], axis=0))
        typical = np.exp(paths[m][:, n].mean(axis=0))  # geometric average: smooth, ≈ the median
        ax.fill_between(n, q10, q90, color=c, alpha=0.12, lw=0)
        ax.plot(n, typical, color=c, lw=2, label=f"{name}: typical ₹{typical[-1]:,.2f}")
    ax.set_yscale("log")
    ax.set_ylim(1e-2, 1e5)
    ax.axhline(1, color=plots.TEXT_2, lw=0.8)
    ax.set_xlabel("bets (each 55% to win, even money)")
    ax.set_ylabel("wealth from ₹1 (log scale)")
    ax.legend(loc="upper left", fontsize=8, title="shaded: middle 80% of 10,000 paths",
              title_fontsize=8)
    typ = {m: float(np.exp(paths[m][:, -1].mean())) for m in (1.0, 2.0)}
    ax.set_title(f"After 1,000 bets the typical Kelly bettor has ₹{typ[1.0]:.0f}; "
                 f"the double-Kelly one ₹{typ[2.0]:.2f}")
    plots.save(fig, out_dir, "bets_paths")

    fig, ax = plt.subplots(figsize=(9, 4.6))
    xb = np.arange(len(MULTIPLES))
    for j, (k, c) in enumerate((("P(ever halved)", plots.SERIES[0]),
                                ("P(behind at end)", plots.SERIES[1]))):
        vals = [stats[m][k] * 100 for m in MULTIPLES]
        ax.bar(xb - 0.2 + 0.4 * j, vals, 0.38, color=c,
               label={"P(ever halved)": "wealth halved at some point",
                      "P(behind at end)": "behind after 1,000 bets"}[k])
        for i, v in enumerate(vals):
            ax.text(i - 0.2 + 0.4 * j, v + 1.5, f"{v:.0f}%", ha="center", fontsize=8)
    ax.set_xticks(xb, [f"{m:g}× Kelly" for m in MULTIPLES])
    ax.set_ylabel("% of 10,000 paths")
    ax.set_ylim(0, 110)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title(f"Kelly halves your money at some point on {stats[1.0]['P(ever halved)']:.0%} of "
                 f"paths; half Kelly on {stats[0.5]['P(ever halved)']:.0%}")
    plots.save(fig, out_dir, "bets_outcomes")

    return {
        "game": f"p {p}, net odds {b}, Kelly fraction {fk:.0%}, {N_BETS} bets, {N_PATHS} paths",
        "growth per bet (×1000)": {m: round(v * 1000, 2) for m, v in g.items()},
        "typical multiple, exp(mean log wealth)": {
            m: round(float(np.exp(L[:, -1].mean())), 2) for m, L in paths.items()},
        "outcomes": {m: {k: round(v, 3) for k, v in s.items()} for m, s in stats.items()},
        "P(ever halved), continuous-limit formula": {m: round(halving_probability(m), 3)
                                                     for m in MULTIPLES},
        "10th / 90th percentile multiple": {
            m: tuple(round(float(x), 2) for x in np.exp(np.quantile(L[:, -1], [0.1, 0.9])))
            for m, L in paths.items()},
    }


RF = 0.065  # assumed risk-free rate (India 91-day T-bills ran roughly 3-7% over 2009-2026)
START = "2009-01-02"  # first day the NIFTY ETF trades on Yahoo


def returns() -> pd.DataFrame:
    from ks.data import DATA_PATH, daily_returns

    return daily_returns(pd.read_parquet(DATA_PATH)["adj_close"])


def stock_table(R: pd.DataFrame, start: str = START, min_years: float = 3) -> pd.DataFrame:
    """In-sample annual mean, volatility and Kelly fraction for every stock since `start`."""
    from ks.data import SYMBOLS
    from ks.stock import annual_stats, kelly_continuous

    rows = {}
    for sym in SYMBOLS:
        r = R[sym].loc[start:].dropna()
        if len(r) < 2:
            continue
        s = annual_stats(r)
        if s["years"] >= min_years:
            rows[sym] = {"mu": s["mu"], "sigma": s["sigma"], "years": s["years"],
                         "kelly": kelly_continuous(s["mu"], s["sigma"], RF)}
    return pd.DataFrame(rows).T.astype(float).sort_values("kelly")


def report_stock(out_dir: Path) -> dict:
    """Continuous Kelly on the NIFTY ETF, the NIFTY index and today's NIFTY 50 stocks."""
    from ks.stock import (
        annual_stats,
        growth_continuous,
        kelly_continuous,
        levered_growth,
        rolling_kelly,
    )

    R = returns()
    series = {"NIFTY ETF, Jan 2009–": R["NIFTYBEES"].loc[START:].dropna(),
              "NIFTY index (no dividends), Sep 2007–": R["NIFTY"].dropna()}
    stats = {k: annual_stats(r) for k, r in series.items()}
    fstar = {k: kelly_continuous(s["mu"], s["sigma"], RF) for k, s in stats.items()}

    fig, ax = plt.subplots(figsize=(9, 4.8))
    fs = np.linspace(0, 6, 61)
    for (k, r), c in zip(series.items(), (plots.SERIES[0], plots.SERIES[1]), strict=True):
        s = stats[k]
        real = [levered_growth(r, f, RF) for f in fs]
        ax.plot(fs, np.array(real) * 100, color=c, lw=2, label=f"{k}: realised")
        ax.plot(fs, growth_continuous(fs, s["mu"], s["sigma"], RF) * 100, color=c, lw=1.2,
                ls="--", label=f"{k}: formula")
        ax.plot([fstar[k]], [levered_growth(r, fstar[k], RF) * 100], "o", ms=7, color=c)
    ax.axhline(np.log(1 + RF) * 100, color=plots.TEXT_2, lw=0.8, ls=":")
    ax.text(5.9, np.log(1 + RF) * 100 + 0.4, "cash, 6.5%", ha="right", fontsize=8,
            color=plots.TEXT_2)
    ax.set_ylim(-6, 20)
    ax.set_xlabel("fraction of wealth in NIFTY (above 1 = borrowing at 6.5%), rebalanced daily")
    ax.set_ylabel("growth per year, % (log)")
    ax.legend(loc="lower left", fontsize=8)
    k1, k2 = list(series)
    ax.set_title(f"With hindsight, Kelly said {fstar[k1]:.1f}× NIFTY from 2009 "
                 f"but {fstar[k2]:.1f}× from 2007")
    plots.save(fig, out_dir, "stock_growth")

    tab = stock_table(R)
    fig, ax = plt.subplots(figsize=(9, 5))
    sig = np.linspace(0.1, 0.52, 100)
    for f in (1, 2, 3):
        ax.plot(sig * 100, f * sig**2 * 100, color=plots.MUTED, lw=1, ls="--")
        x = 0.50 if f == 1 else (0.44 / f) ** 0.5  # where the line is labelled, inside the frame
        ax.text(x * 100 - 0.6, f * x**2 * 100 + 1, f"Kelly {f}×", fontsize=8,
                color=plots.TEXT_2, ha="right")
    order = tab.sort_values("sigma")
    ax.plot(order["sigma"] * 100, (order["mu"] - RF) * 100, "o", ms=6, color=plots.SERIES[0],
            label="today's NIFTY 50 stocks, 2009– (or listing)")
    n = stats[k1]
    ax.plot([n["sigma"] * 100], [(n["mu"] - RF) * 100], "D", ms=8, color=plots.SERIES[1],
            label="NIFTY ETF")
    for sym in ("BAJFINANCE", "EICHERMOT", "HDFCBANK", "ONGC", "NTPC", "JIOFIN", "ADANIENT"):
        if sym in tab.index:
            ax.annotate(sym, (tab.loc[sym, "sigma"] * 100, (tab.loc[sym, "mu"] - RF) * 100),
                        xytext=(5, 3), textcoords="offset points", fontsize=7,
                        color=plots.TEXT_2)
    ax.axhline(0, color=plots.TEXT_2, lw=0.8)
    ax.set_xlim(10, 52)
    ax.set_ylim(-10, 50)
    ax.set_xlabel("volatility, % a year")
    ax.set_ylabel("average return above 6.5% cash, % a year")
    ax.legend(loc="upper left", fontsize=8)
    lev = int((tab["kelly"] > 1).sum())
    ax.set_title(f"With hindsight, Kelly would have borrowed to buy {lev} of today's "
                 f"{len(tab)} NIFTY stocks")
    plots.save(fig, out_dir, "stock_fstar")

    roll = {k: rolling_kelly(r, RF, years=3) for k, r in series.items()}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for (k, rk), c in zip(roll.items(), (plots.SERIES[0], plots.SERIES[1]), strict=True):
        rk = rk.dropna()
        ax.plot(rk.index, rk.values, color=c, lw=1.5, label=k)
    ax.axhline(1, color=plots.TEXT_2, lw=0.8, ls="--")
    ax.axhline(0, color=plots.TEXT_2, lw=0.8)
    ax.set_ylabel("Kelly fraction from the past 3 years")
    ax.legend(loc="upper left", fontsize=8)
    e = roll[k1].dropna()
    ax.set_title(f"Three years of data put NIFTY's Kelly fraction anywhere from "
                 f"{e.min():.1f} to {e.max():.1f}")
    plots.save(fig, out_dir, "stock_rolling")

    return {
        "stats": {k: {"mu": f"{s['mu']:.1%}", "sigma": f"{s['sigma']:.1%}",
                      "Sharpe": round((s["mu"] - RF) / s["sigma"], 2),
                      "years": round(s["years"], 1),
                      "Kelly": round(fstar[k], 2)} for k, s in stats.items()},
        "realised growth at 0 / 0.5 / 1 / f* / 2f* (%/yr)": {
            k: [round(levered_growth(r, f, RF) * 100, 1)
                for f in (0, 0.5, 1, fstar[k] / 2, fstar[k], 2 * fstar[k])]
            for k, r in series.items()},
        "formula growth at f* (%/yr)": {k: round(growth_continuous(
            fstar[k], stats[k]["mu"], stats[k]["sigma"], RF) * 100, 1) for k in series},
        "stocks: count, Kelly > 1, 0-1, < 0": (len(tab), int((tab.kelly > 1).sum()),
                                               int(tab.kelly.between(0, 1).sum()),
                                               int((tab.kelly < 0).sum())),
        "stocks Kelly quartiles": tab.kelly.quantile([0, 0.25, 0.5, 0.75, 1]).round(2).tolist(),
        "rolling 3y NIFTY ETF Kelly: min, max, share of days < 0, share > 2": (
            round(e.min(), 2), round(e.max(), 2), f"{(e < 0).mean():.0%}", f"{(e > 2).mean():.0%}",
            f"min on {e.idxmin():%b %Y}, max on {e.idxmax():%b %Y}"),
        "worst NIFTY ETF day; leverage that would wipe out": (
            f"{series[k1].min():.1%}", round(-1 / series[k1].min(), 1)),
    }


REPORTS = {"bets": report_bets, "stock": report_stock}
