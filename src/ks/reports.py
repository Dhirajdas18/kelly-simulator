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
        "realised growth at 0 / 0.5 / 1 / f*/2 / f* / 2f* (%/yr)": {
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


def _rupee_log(ax) -> None:
    """Log wealth axis labelled ₹1, ₹2, ₹5… instead of powers of ten."""
    from matplotlib.ticker import FuncFormatter, LogLocator

    ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"₹{v:g}"))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))


def _growth_dd(w: pd.Series) -> tuple[float, float]:
    years = (w.index[-1] - w.index[0]).days / 365.25
    return float(np.log(w.iloc[-1]) / years), float((w / w.cummax() - 1).min())


EVAL_START = "2014-01-01"  # five years after the ETF's first price, so every window is full
CAP, FLOOR = 3.0, 0.0  # long only, at most 3× (a margin limit; section 6 prices it)


def report_estimation(out_dir: Path) -> dict:
    """Kelly from estimated returns: theory, NIFTY walk-forward and 41 stocks walk-forward."""
    from ks.data import SYMBOLS
    from ks.estimation import (
        excess_growth_estimated,
        optimal_multiple,
        simulate_estimated_growth,
        walk_forward,
    )
    from ks.stock import annual_stats

    R = returns()
    nifty = R["NIFTYBEES"].loc[START:].dropna()
    s = annual_stats(nifty)
    sharpe = (s["mu"] - RF) / s["sigma"]

    fig, ax = plt.subplots(figsize=(9, 4.8))
    cs = np.linspace(0, 1.6, 161)
    for T, c in ((np.inf, plots.TEXT), (20, plots.SERIES[2]), (10, plots.SERIES[3]),
                 (5, plots.SERIES[0]), (3, plots.SERIES[1])):
        label = "known exactly" if np.isinf(T) else f"estimated from {T} years"
        ax.plot(cs, excess_growth_estimated(cs, sharpe, T) * 100, color=c, lw=2, label=label)
        best = optimal_multiple(sharpe, T)
        ax.plot([best], [excess_growth_estimated(best, sharpe, T) * 100], "o", ms=6, color=c)
    sim = {c: simulate_estimated_growth(c, s["mu"], s["sigma"], RF, 5, 4000, seed=1)
           for c in (0.25, 0.5, 0.75, 1.0, 1.25)}
    ax.plot(list(sim), [v * 100 for v in sim.values()], "s", ms=6, mfc="none",
            color=plots.SERIES[0], label="5 years, simulated")
    ax.axhline(0, color=plots.TEXT_2, lw=0.8)
    ax.text(1.58, 0.3, "cash", ha="right", fontsize=8, color=plots.TEXT_2)
    ax.set_ylim(-8, 13)
    ax.set_xlabel("bet size, × the estimated Kelly fraction")
    ax.set_ylabel("expected growth above cash, % a year")
    ax.legend(loc="lower left", fontsize=8, title=f"NIFTY's average return ({sharpe:.2f} Sharpe)",
              title_fontsize=8)
    ax.set_title(f"With 5 years of data the best bet is {optimal_multiple(sharpe, 5):.2f}× Kelly; "
                 "full Kelly earns about what cash does")
    plots.save(fig, out_dir, "est_theory")

    runs = {"hold NIFTY (1×)": walk_forward(nifty, RF, 1e-12, 5, 1.0, 1.0, EVAL_START)}
    for win, c in ((5, 0.5), (5, 1.0), (3, 1.0)):
        runs[f"{c:g}× Kelly, {win}-year estimate"] = walk_forward(nifty, RF, c, win, CAP, FLOOR,
                                                                   EVAL_START)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for (k, res), col in zip(runs.items(), (plots.TEXT, plots.SERIES[2], plots.SERIES[0],
                                            plots.SERIES[1]), strict=True):
        g, d = _growth_dd(res["wealth"])
        ax.plot(res["wealth"].index, res["wealth"].values, color=col, lw=1.6,
                label=f"{k}: {g:.1%} a year, worst fall {d:.0%}")
    ax.set_yscale("log")
    ax.set_ylabel("wealth from ₹1 in January 2014 (log scale)")
    _rupee_log(ax)
    ax.legend(loc="upper left", fontsize=8)
    g5, _ = _growth_dd(runs["1× Kelly, 5-year estimate"]["wealth"])
    g3, _ = _growth_dd(runs["1× Kelly, 3-year estimate"]["wealth"])
    ax.set_title(f"On NIFTY alone, full Kelly made {g5:.1%} a year from 5-year estimates "
                 f"and {g3:.1%} from 3-year ones")
    plots.save(fig, out_dir, "est_nifty")

    strategies = [(w, c) for w in (3, 5) for c in (0.25, 0.5, 1.0)]
    rows = {}
    for sym in SYMBOLS:
        r = R[sym].loc[START:].dropna()
        if r.empty or r.index[0] > pd.Timestamp(START) + pd.Timedelta(days=31):
            continue
        row = {"hold": _growth_dd(walk_forward(r, RF, 1e-12, 5, 1.0, 1.0, EVAL_START)["wealth"])}
        for w, c in strategies:
            row[(w, c)] = _growth_dd(walk_forward(r, RF, c, w, CAP, FLOOR, EVAL_START)["wealth"])
        rows[sym] = row
    keys = ["hold"] + strategies
    med_g = {k: float(np.median([v[k][0] for v in rows.values()])) for k in keys}
    med_d = {k: float(np.median([v[k][1] for v in rows.values()])) for k in keys}
    beat = {k: int(sum(v[k][0] > v["hold"][0] for v in rows.values())) for k in strategies}
    names = ["hold"] + [f"{c:g}× K\n{w}y" for w, c in strategies]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.6))
    xs = np.arange(len(keys))
    cols = [plots.TEXT] + [plots.SERIES[1]] * 3 + [plots.SERIES[0]] * 3
    a1.bar(xs, [med_g[k] * 100 for k in keys], color=cols)
    a2.bar(xs, [-med_d[k] * 100 for k in keys], color=cols)
    for i, k in enumerate(keys):
        a1.text(i, med_g[k] * 100 + 0.3, f"{med_g[k]:.1%}", ha="center", fontsize=7)
        a2.text(i, -med_d[k] * 100 + 1, f"{-med_d[k]:.0%}", ha="center", fontsize=7)
    for a, t in ((a1, "median growth a year, %"), (a2, "median worst fall, %")):
        a.set_xticks(xs, names, fontsize=7)
        a.set_title(t, fontsize=10, fontweight="normal")
        a.grid(axis="x", visible=False)
    fig.suptitle(f"Across {len(rows)} stocks, Kelly from estimates lost to holding: full Kelly "
                 f"on 5 years beat it {beat[(5, 1.0)]} times", fontweight="bold")
    plots.save(fig, out_dir, "est_stocks")

    nf = {k: tuple(round(x, 3) for x in _growth_dd(res["wealth"])) for k, res in runs.items()}
    return {
        "NIFTY ETF 2009-26": {"mu": round(s["mu"], 4), "sigma": round(s["sigma"], 4),
                              "Sharpe": round(sharpe, 3)},
        "optimal multiple by years of data": {T: round(optimal_multiple(sharpe, T), 2)
                                              for T in (3, 5, 10, 20)},
        "expected excess growth % at 0.25/0.5/1/1.5×, by years": {
            T: [round(excess_growth_estimated(c, sharpe, T) * 100, 2)
                for c in (0.25, 0.5, 1.0, 1.5)] for T in (3, 5, 10, 20, np.inf)},
        "simulated, 5 years": {c: round(v * 100, 2) for c, v in sim.items()},
        "NIFTY walk-forward 2014-26 (growth, worst fall)": nf,
        "NIFTY average fraction held": {k: round(float(res["fraction"].mean()), 2)
                                        for k, res in runs.items()},
        "NIFTY share of days at the 3× cap / at 0": {
            k: (round(float((res["fraction"] >= CAP).mean()), 2),
                round(float((res["fraction"] <= 0).mean()), 2)) for k, res in runs.items()},
        "stocks": len(rows),
        "stocks median growth": {str(k): round(v, 3) for k, v in med_g.items()},
        "stocks median worst fall": {str(k): round(v, 3) for k, v in med_d.items()},
        "stocks beating hold": {str(k): v for k, v in beat.items()},
    }


def _levered_wealth(r: pd.Series, f: float, rf: float) -> pd.Series:
    """₹1 held at fraction f, reset daily, cash or borrowing at rf for the days between closes."""
    days = r.index.to_series().diff().dt.days.fillna(0).to_numpy()
    gross = 1 + f * r.fillna(0).to_numpy() + (1 - f) * ((1 + rf) ** (days / 365) - 1)
    gross[0] = 1.0
    return pd.Series(np.cumprod(np.maximum(gross, 0)), index=r.index)


def _runs(underwater: np.ndarray) -> int:
    """Longest run of True in a boolean array."""
    if not underwater.any():
        return 0
    edges = np.diff(np.concatenate(([0], underwater.astype(np.int8), [0])))
    return int((np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)).max())


def report_drawdown(out_dir: Path) -> dict:
    """How deep and how long the falls are at each bet size, and how long Kelly takes to win."""
    from ks.drawdown import (
        PER_YEAR,
        drawdown,
        longest_underwater,
        prob_ahead,
        simulate_log_wealth,
        years_to_confidence,
    )
    from ks.stock import annual_stats, kelly_continuous

    R = returns()
    nifty = R["NIFTYBEES"].loc[START:].dropna()
    st = annual_stats(nifty)
    mu, sig = st["mu"], st["sigma"]
    S = (mu - RF) / sig
    k = kelly_continuous(mu, sig, RF)
    hold = 1 / k  # holding NIFTY fully invested, as a multiple of Kelly

    fig, ax = plt.subplots(figsize=(9, 4.6))
    T = np.linspace(0.25, 150, 600)
    for c2, col, name in ((0.5, plots.SERIES[2], "half Kelly"),
                          (hold, plots.TEXT, f"holding NIFTY 1× ({hold:.2f}× Kelly)")):
        ax.plot(T, [prob_ahead(1.0, c2, S, t) * 100 for t in T], color=col, lw=2,
                label=f"Kelly ahead of {name}")
        y95 = years_to_confidence(1.0, c2, S, 0.95)
        if y95 <= 150:
            ax.plot([y95], [95], "o", ms=6, color=col)
            ax.annotate(f"{y95:.0f} years", (y95, 95), xytext=(-4, -16), textcoords="offset points",
                        ha="right", fontsize=8, color=plots.TEXT_2)
    ax.axhline(95, color=plots.TEXT_2, lw=0.8, ls=":")
    ax.set_ylim(48, 100)
    ax.set_xlabel("years")
    ax.set_ylabel("chance Kelly has more money, %")
    ax.legend(loc="lower right", fontsize=8, title=f"NIFTY's 2009–26 return and risk known exactly "
              f"(Sharpe {S:.2f})", title_fontsize=8)
    y_hold = years_to_confidence(1.0, hold, S, 0.95)
    ax.set_title(f"Kelly needs {y_hold:.0f} years to beat simply holding NIFTY with 95% confidence")
    plots.save(fig, out_dir, "dd_ahead")

    years, n = 20, 2000
    mults = {"¼ Kelly": 0.25, "½ Kelly": 0.5, "hold 1×": hold, "Kelly": 1.0, "1.5× Kelly": 1.5}
    sims = {}
    for name, c in mults.items():
        lw = simulate_log_wealth(c * k, mu, sig, RF, years, n, seed=11)
        peak = np.maximum.accumulate(lw, axis=1)
        dd = np.exp(lw - peak) - 1
        sims[name] = {
            "max dd": dd.min(axis=1),
            "underwater years": np.array([_runs(row < -1e-9) for row in dd]) / PER_YEAR,
            "final growth": lw[:, -1] / years,
        }
        del lw, peak, dd
    fig, ax = plt.subplots(figsize=(9, 4.6))
    xb = np.arange(len(mults))
    levels = ((0.3, plots.SERIES[3]), (0.5, plots.SERIES[1]), (0.7, plots.SERIES[7]))
    for j, (lvl, col) in enumerate(levels):
        vals = [float((sims[m]["max dd"] <= -lvl).mean()) * 100 for m in mults]
        ax.bar(xb - 0.27 + 0.27 * j, vals, 0.25, color=col,
               label=f"fell {lvl:.0%} or more from a peak")
        for i, v in enumerate(vals):
            ax.text(i - 0.27 + 0.27 * j, v + 1.5, f"{v:.0f}", ha="center", fontsize=7)
    ax.set_xticks(xb, list(mults))
    ax.set_ylim(0, 125)
    ax.set_ylabel(f"% of {n:,} simulated 20-year paths")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", fontsize=8, ncol=3)
    p50 = {m: float((sims[m]["max dd"] <= -0.5).mean()) for m in mults}
    ax.set_title(f"Over 20 years, Kelly fell 50% from a peak on {p50['Kelly']:.0%} of paths; "
                 f"half Kelly on {p50['½ Kelly']:.0%}")
    plots.save(fig, out_dir, "dd_depth")

    real = {"hold 1×": 1.0, "½ Kelly": 0.5 * k, "Kelly": k}
    wealth = {m: _levered_wealth(nifty, f, RF) for m, f in real.items()}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for (m, w), col in zip(wealth.items(), (plots.TEXT, plots.SERIES[2], plots.SERIES[0]),
                           strict=True):
        d = drawdown(w)
        ax.plot(d.index, d.values * 100, color=col, lw=1.3,
                label=f"{m} ({real[m]:.2f}×): worst {d.min():.0%}, longest "
                      f"{longest_underwater(w):.1f} years below a peak")
    ax.set_ylabel("below the previous peak, %")
    ax.set_ylim(-100, 3)
    ax.legend(loc="lower left", fontsize=8)
    ax.set_title(f"On NIFTY since 2009, hindsight Kelly ({k:.2f}×) fell "
                 f"{-drawdown(wealth['Kelly']).min():.0%} in 2020")
    plots.save(fig, out_dir, "dd_nifty")

    return {
        "NIFTY ETF": {"mu": round(mu, 4), "sigma": round(sig, 4), "Sharpe": round(S, 3),
                      "Kelly": round(k, 2), "hold as × Kelly": round(hold, 3)},
        "years to 90/95% that Kelly beats ½ Kelly": (
            round(years_to_confidence(1, 0.5, S, 0.9)), round(years_to_confidence(1, 0.5, S))),
        "years to 90/95% that Kelly beats holding 1×": (
            round(years_to_confidence(1, hold, S, 0.9)), round(years_to_confidence(1, hold, S))),
        "P(Kelly ahead of ½K / hold) at 5, 10, 20, 50 years": {
            t: (round(prob_ahead(1, 0.5, S, t), 2), round(prob_ahead(1, hold, S, t), 2))
            for t in (5, 10, 20, 50)},
        "simulated 20y: P(fell ≥30/50/70%), median worst, median longest underwater (y), "
        "median growth": {
            m: (f"{(v['max dd'] <= -0.3).mean():.0%}", f"{(v['max dd'] <= -0.5).mean():.0%}",
                f"{(v['max dd'] <= -0.7).mean():.0%}", f"{np.median(v['max dd']):.0%}",
                round(float(np.median(v["underwater years"])), 1),
                f"{np.median(v['final growth']):.1%}") for m, v in sims.items()},
        "simulated 20y: Kelly ahead of ½K / hold (share of paths)": (
            f"{(sims['Kelly']['final growth'] > sims['½ Kelly']['final growth']).mean():.0%}",
            f"{(sims['Kelly']['final growth'] > sims['hold 1×']['final growth']).mean():.0%}"),
        "NIFTY 2009-26 (worst fall, its date, longest underwater y)": {
            m: (f"{drawdown(w).min():.0%}", f"{drawdown(w).idxmin():%d %b %Y}",
                round(longest_underwater(w), 1)) for m, w in wealth.items()},
    }


def weekly_assets() -> pd.DataFrame:
    """Weekly returns of NIFTY (ETF), gold (ETF) and the US market in rupees since January 2009,
    from the repaired NSE prices and the US/rupee table."""
    from ks.data import DATA_PATH, GLOBAL_PATH, daily_returns, weekly_asset_returns

    px = pd.read_parquet(DATA_PATH)["adj_close"][["NIFTYBEES", "GOLDBEES"]]
    repaired = (1 + daily_returns(px).fillna(0)).cumprod().where(px.notna())
    return weekly_asset_returns(repaired, pd.read_parquet(GLOBAL_PATH)).loc[START:]


def report_multi(out_dir: Path) -> dict:
    """Kelly across NIFTY, gold and the US: hindsight weights, growth, and a walk-forward."""
    from ks.multi import (
        capped_kelly,
        fractional_kelly,
        growth_multi,
        kelly_weights,
        tangency,
        walk_forward_multi,
    )

    W = weekly_assets()
    years = (W.index[-1] - W.index[0]).days / 365.25
    per_year = (len(W) - 1) / years
    mu, cov = W.mean().to_numpy() * per_year, W.cov().to_numpy() * per_year
    names = list(W.columns)
    k = kelly_weights(mu, cov, RF)
    tan = tangency(mu, cov, RF)
    s_tan = float(tan @ (mu - RF) / np.sqrt(tan @ cov @ tan))
    variants = {"Kelly": k, "½ Kelly": k / 2,
                "best with no borrowing": capped_kelly(mu, cov, RF, 1),
                "½ Kelly, no borrowing": fractional_kelly(mu, cov, RF, 0.5, 1)}

    fig, ax = plt.subplots(figsize=(9, 4.6))
    xb = np.arange(len(variants))
    cols = (plots.SERIES[0], plots.SERIES[3], plots.SERIES[2])
    for j, (a, c) in enumerate(zip(names, cols, strict=True)):
        vals = [v[j] for v in variants.values()]
        ax.bar(xb - 0.27 + 0.27 * j, vals, 0.25, color=c, label=a)
        for i, v in enumerate(vals):
            ax.text(i - 0.27 + 0.27 * j, v + 0.06, f"{v:.2f}", ha="center", fontsize=7)
    ax.set_xticks(xb, [f"{n}\n(total {v.sum():.2f}×)" for n, v in variants.items()])
    ax.set_ylabel("fraction of wealth (above 1 in total = borrowing)")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"With hindsight Kelly held {k.sum():.1f}× across NIFTY, gold and the US; "
                 "unborrowed, all US")
    plots.save(fig, out_dir, "multi_weights")

    fig, ax = plt.subplots(figsize=(9, 4.6))
    lev = np.linspace(0, 12, 241)
    ax.plot(lev, [growth_multi(L * tan, mu, cov, RF) * 100 for L in lev], color=plots.SERIES[0],
            lw=2, label="tangency mix (" + ", ".join(
                f"{a} {w:.0%}" for a, w in zip(names, tan, strict=True)) + ")")
    kn = (mu[0] - RF) / cov[0, 0]
    ax.plot(lev, [growth_multi(np.array([L, 0, 0]), mu, cov, RF) * 100 for L in lev],
            color=plots.SERIES[1], lw=2, label="NIFTY alone")
    ax.plot([k.sum()], [growth_multi(k, mu, cov, RF) * 100], "o", ms=7, color=plots.SERIES[0])
    ax.plot([kn], [growth_multi(np.array([kn, 0, 0]), mu, cov, RF) * 100], "o", ms=7,
            color=plots.SERIES[1])
    ax.axhline(RF * 100, color=plots.TEXT_2, lw=0.8, ls=":")
    ax.set_ylim(-10, 50)
    ax.set_xlabel("total exposure, × wealth (above 1 = borrowing at 6.5%)")
    ax.set_ylabel("expected growth a year, % (log), with hindsight")
    ax.legend(loc="upper right", fontsize=8)
    gk, gn = growth_multi(k, mu, cov, RF), growth_multi(np.array([kn, 0, 0]), mu, cov, RF)
    ax.set_title(f"Mixing raised Kelly's hindsight growth from {gn:.0%} to {gk:.0%} "
                 f"({k.sum():.1f}× leverage, not {kn:.1f}×)")
    plots.save(fig, out_dir, "multi_growth")

    runs = {"hold NIFTY": dict(fixed=[1, 0, 0]), "equal thirds": dict(fixed=[1 / 3] * 3),
            "½ Kelly, no borrowing": dict(multiple=0.5, max_gross=1.0),
            "½ Kelly, up to 2×": dict(multiple=0.5, max_gross=2.0),
            "Kelly, up to 3×": dict(multiple=1.0, max_gross=3.0)}
    res = {n: walk_forward_multi(W, RF, a.get("multiple", 1.0), 5, a.get("max_gross", 1.0),
                                 EVAL_START, a.get("fixed")) for n, a in runs.items()}
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for (n, r_), c in zip(res.items(), (plots.TEXT, plots.SERIES[2], plots.SERIES[0],
                                        plots.SERIES[3], plots.SERIES[1]), strict=True):
        g, d = _growth_dd(r_["wealth"])
        ax.plot(r_["wealth"].index, r_["wealth"].values, color=c, lw=1.6,
                label=f"{n}: {g:.1%} a year, worst fall {d:.0%}")
    ax.set_yscale("log")
    ax.set_ylabel("wealth from ₹1 in January 2014 (log scale)")
    _rupee_log(ax)
    ax.legend(loc="upper left", fontsize=8)
    g3, _ = _growth_dd(res["equal thirds"]["wealth"])
    gh, _ = _growth_dd(res["½ Kelly, no borrowing"]["wealth"])
    ax.set_title(f"Out of sample, equal thirds made {g3:.1%} a year; half Kelly from 5-year "
                 f"estimates {gh:.1%}")
    plots.save(fig, out_dir, "multi_walk")

    return {
        "weekly 2009-26": {"weeks": len(W), "per year": round(per_year, 2)},
        "mean / vol": {a: (f"{m:.1%}", f"{np.sqrt(v):.1%}") for a, m, v in
                       zip(names, mu, np.diag(cov), strict=True)},
        "correlation": W.corr().round(2).to_dict(),
        "hindsight weights": {n: dict(zip(names, np.round(v, 2), strict=True))
                              for n, v in variants.items()},
        "hindsight growth": {n: f"{growth_multi(v, mu, cov, RF):.1%}" for n, v in variants.items()},
        "tangency": dict(zip(names, np.round(tan, 3), strict=True)),
        "tangency Sharpe, NIFTY Sharpe": (round(s_tan, 3),
                                          round((mu[0] - RF) / np.sqrt(cov[0, 0]), 3)),
        "NIFTY-alone Kelly and growth": (round(kn, 2), f"{gn:.1%}"),
        "walk-forward 2014-26 (growth, worst fall, average weights, average total)": {
            n: (*(round(x, 3) for x in _growth_dd(r_["wealth"])),
                r_["weights"].mean().round(2).to_dict(),
                round(float(r_["weights"].sum(axis=1).mean()), 2)) for n, r_ in res.items()},
    }


def report_frictions(out_dir: Path) -> dict:
    """Kelly on NIFTY with Zerodha's margin rate and ETF costs, against volatility targeting."""
    from ks.frictions import MTF_RATE, ewma_vol, growth_spread, kelly_spread, run_strategy
    from ks.stock import annual_stats, kelly_continuous

    r = returns()["NIFTYBEES"].loc[START:].dropna()
    st = annual_stats(r)
    mu, sig = st["mu"], st["sigma"]
    k_one, k_spread = kelly_continuous(mu, sig, RF), kelly_spread(mu, sig, RF, MTF_RATE)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    f = np.linspace(0, 4, 401)
    ax.plot(f, growth_spread(f, mu, sig, RF, RF) * 100, color=plots.SERIES[0], lw=2,
            label="borrow at 6.5%, like cash")
    ax.plot(f, growth_spread(f, mu, sig, RF, MTF_RATE) * 100, color=plots.SERIES[1], lw=2,
            label=f"borrow at Zerodha's MTF rate ({MTF_RATE:.1%})")
    for kk, c in ((k_one, plots.SERIES[0]), (k_spread, plots.SERIES[1])):
        rb = RF if c == plots.SERIES[0] else MTF_RATE
        ax.plot([kk], [growth_spread(kk, mu, sig, RF, rb) * 100], "o", ms=7, color=c)
    ax.axhline(RF * 100, color=plots.TEXT_2, lw=0.8, ls=":")
    ax.set_ylim(0, 20)
    ax.set_xlabel("fraction of wealth in NIFTY (above 1 = borrowing)")
    ax.set_ylabel("expected growth a year, %, with hindsight")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"Borrowing at {MTF_RATE:.1%} moved NIFTY's hindsight Kelly from "
                 f"{k_one:.1f}× to {k_spread:.0f}×")
    plots.save(fig, out_dir, "fric_spread")

    x = r.loc[EVAL_START:]
    years = (x.index[-1] - x.index[0]).days / 365.25

    def run(target, rb=MTF_RATE, band=0.0, costs=True):
        res = run_strategy(x, target.reindex(x.index), RF, rb, 1e6, band, costs)
        g, d = _growth_dd(res["wealth"])
        vol = float(np.log(res["wealth"]).diff().std() * np.sqrt(st["per_year"]))
        return {"growth": g, "worst": d, "vol": vol, "avg f": float(res["fraction"].mean()),
                "trades a year": res["trades"] / years, "costs a year": res["costs"] / years,
                "wealth": res["wealth"]}

    const = lambda v: pd.Series(v, index=r.index)  # noqa: E731
    pre = annual_stats(r[r.index < EVAL_START])  # inputs from before the test period only
    half = round(kelly_continuous(pre["mu"], pre["sigma"], RF) / 2, 2)
    target = round(pre["sigma"], 3)
    lev = {"borrow at 6.5%, no costs": run(const(half), RF, costs=False),
           "borrow at 14.6%, no costs": run(const(half), costs=False),
           "+ ETF costs, reset daily": run(const(half)),
           "+ ETF costs, reset beyond ±0.1": run(const(half), band=0.1)}
    hold = run(const(1.0))
    fig, ax = plt.subplots(figsize=(9, 4.6))
    xb = np.arange(len(lev))
    vals = [v["growth"] * 100 for v in lev.values()]
    ax.bar(xb, vals, 0.6, color=[plots.SERIES[0], plots.SERIES[1], plots.SERIES[1],
                                 plots.SERIES[1]])
    for i, v in enumerate(vals):
        ax.text(i, v + 0.2, f"{v:.1f}%", ha="center", fontsize=8)
    ax.axhline(hold["growth"] * 100, color=plots.TEXT, lw=1.2, ls="--")
    ax.text(len(lev) - 0.5, hold["growth"] * 100 + 0.25, f"hold 1×: {hold['growth']:.1%}",
            ha="right", fontsize=8)
    ax.set_xticks(xb, list(lev), fontsize=8)
    ax.set_ylim(0, 16)
    ax.set_ylabel("growth a year 2014–26, %")
    ax.grid(axis="x", visible=False)
    spread_cost = lev["borrow at 6.5%, no costs"]["growth"] - lev["borrow at 14.6%, no costs"][
        "growth"]
    ax.set_title(f"At {half}×, the 14.6% margin rate cost {spread_cost * 100:.1f} points a year; "
                 f"daily trading {lev['+ ETF costs, reset daily']['costs a year'] * 100:.1f}")
    plots.save(fig, out_dir, "fric_costs")

    sig_next = ewma_vol(r, per_year=st["per_year"]).shift(-1).ffill()  # tomorrow's, from today
    mu5 = r.rolling("1826D").mean() * st["per_year"]  # past five years' average return
    dyn = {"hold 1×": hold,
           f"volatility target {target:.0%}, up to 1×": run((target / sig_next).clip(upper=1),
                                                             band=0.1),
           "½ Kelly with EWMA volatility, up to 1×": run(
               (0.5 * (mu5 - RF) / sig_next**2).clip(0, 1), band=0.1),
           f"volatility target {target:.0%}, up to 1.5×": run((target / sig_next).clip(upper=1.5),
                                                       band=0.1)}
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for (n, v), c in zip(dyn.items(), (plots.TEXT, plots.SERIES[2], plots.SERIES[0],
                                       plots.SERIES[1]), strict=True):
        ax.plot(v["wealth"].index, v["wealth"].values, color=c, lw=1.6,
                label=f"{n}: {v['growth']:.1%} a year, worst fall {v['worst']:.0%}")
    ax.set_yscale("log")
    ax.set_ylabel("wealth from ₹1 in January 2014 (log scale)")
    _rupee_log(ax)
    ax.legend(loc="upper left", fontsize=8)
    vt = dyn[f"volatility target {target:.0%}, up to 1×"]
    cost = (hold["growth"] - vt["growth"]) * 100
    ax.set_title(f"Sizing by forecast volatility cut the worst fall from {-hold['worst']:.0%} to "
                 f"{-vt['worst']:.0%} for {cost:.1f} points a year")
    plots.save(fig, out_dir, "fric_voltarget")

    keep = ("growth", "worst", "vol", "avg f", "trades a year", "costs a year")
    return {
        "NIFTY ETF 2009-26": {"mu": round(mu, 4), "sigma": round(sig, 4)},
        "Kelly: one rate / lend 6.5% borrow 14.6%": (round(k_one, 2), round(k_spread, 2)),
        "hindsight growth at Kelly": (f"{growth_spread(k_one, mu, sig, RF, RF):.1%}",
                                      f"{growth_spread(k_spread, mu, sig, RF, MTF_RATE):.1%}"),
        "before 2014 (mu, sigma, Kelly/2 used, vol target used)": (
            round(pre["mu"], 4), round(pre["sigma"], 4), half, target),
        "2014-26 levered": {n: {kk: round(v[kk], 4) for kk in keep} for n, v in lev.items()},
        "2014-26 dynamic": {n: {kk: round(v[kk], 4) for kk in keep} for n, v in dyn.items()},
    }


def report_signal(out_dir: Path) -> dict:
    """Kelly from a model's probabilities: what overconfidence costs, and a real walk-forward."""
    from ks.bets import growth_rate
    from ks.data import SYMBOLS
    from ks.signal import (
        FEATURES,
        calibration,
        monthly_panel,
        realised_growth,
        recalibrate,
        walk_forward_probs,
    )

    true_p = 0.53
    fig, ax = plt.subplots(figsize=(9, 4.6))
    stated = np.linspace(0.5, 0.6, 201)
    ax.plot(stated * 100, growth_rate(2 * stated - 1, true_p, 1.0) * 1000, color=plots.SERIES[0],
            lw=2)
    for sp, lab in ((0.53, "calibrated:\nKelly"), (0.545, "1.5× Kelly"),
                    (0.56, "twice as far\nfrom 50%: 2× Kelly")):
        g = growth_rate(2 * sp - 1, true_p, 1.0) * 1000
        ax.plot([sp * 100], [g], "o", ms=7, color=plots.SERIES[0])
        ax.annotate(lab, (sp * 100, g), xytext=(0, 10), textcoords="offset points", ha="center",
                    fontsize=8, color=plots.TEXT_2)
    ax.axhline(0, color=plots.TEXT_2, lw=0.8)
    ax.set_ylim(-1.5, 2.6)
    ax.set_xlabel("win probability the model states, % (the truth is 53%, even-money bets)")
    ax.set_ylabel("growth per bet, thousandths of log wealth")
    ax.set_title("A model that says 56% when the truth is 53% bets 2× Kelly and grows at zero")
    plots.save(fig, out_dir, "sig_theory")

    panel = monthly_panel(returns().loc[START:], SYMBOLS)
    preds = walk_forward_probs(panel, FEATURES, min_months=36)
    months = sorted(preds["t"].unique())
    rows = []
    for i, t in enumerate(months):
        if i < 12:  # need a year of earlier predictions to measure the calibration
            continue
        past = preds[preds["t"] < t]
        a, slope = calibration(past["p"], past["y"])
        cur = preds[preds["t"] == t].copy()
        cur["p_cal"] = recalibrate(cur["p"], a, slope)
        cur["slope"] = slope
        rows.append(cur)
    bets = pd.concat(rows, ignore_index=True)
    a_all, slope_all = calibration(preds["p"], preds["y"])
    stakes = {"Kelly on the model's p": np.clip(2 * bets["p"] - 1, 0, None),
              "½ Kelly on the model's p": np.clip(bets["p"] - 0.5, 0, None),
              "Kelly on recalibrated p": np.clip(2 * bets["p_cal"] - 1, 0, None),
              "½ Kelly on recalibrated p": np.clip(bets["p_cal"] - 0.5, 0, None)}
    rng = np.random.default_rng(0)
    groups = bets.groupby("t").indices
    keys = list(groups)
    res = {}
    for n, f in stakes.items():
        g = realised_growth(f, bets["y"])
        boot = []
        for _ in range(1000):  # resample whole months: bets in the same month move together
            idx = np.concatenate([groups[k] for k in rng.choice(keys, len(keys))])
            boot.append(realised_growth(f.to_numpy()[idx], bets["y"].to_numpy()[idx]))
        res[n] = (g, np.quantile(boot, 0.05), np.quantile(boot, 0.95), float(f.mean()),
                  float((f > 0).mean()))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    bins = pd.qcut(bets["p"], 10, labels=False)
    rel = bets.groupby(bins).agg(p=("p", "mean"), pc=("p_cal", "mean"), hit=("y", "mean"))
    ax.plot([40, 60], [40, 60], color=plots.TEXT_2, lw=0.8, ls="--")
    ax.plot(rel["p"] * 100, rel["hit"] * 100, "o-", color=plots.SERIES[1], lw=1.5,
            label="model's probability")
    ax.plot(rel["pc"] * 100, rel["hit"] * 100, "o-", color=plots.SERIES[0], lw=1.5,
            label="recalibrated on earlier predictions")
    ax.set_xlim(40, 60)
    ax.set_ylim(40, 60)
    ax.set_xlabel("predicted chance of beating the median next month, % (tenths of predictions)")
    ax.set_ylabel("how often it did, %")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title(f"Out of sample, the model's probabilities were too far from 50%: calibration "
                 f"slope {slope_all:.2f}")
    plots.save(fig, out_dir, "sig_reliability")

    fig, ax = plt.subplots(figsize=(9, 4.6))
    names = list(res)
    xs = np.arange(len(names))
    vals = [res[n][0] * 1000 for n in names]
    err = np.array([[res[n][0] - res[n][1], res[n][2] - res[n][0]] for n in names]).T * 1000
    ax.bar(xs, vals, 0.55, color=[plots.SERIES[1], plots.SERIES[1], plots.SERIES[0],
                                  plots.SERIES[0]], yerr=err, capsize=4,
           error_kw=dict(ecolor=plots.TEXT_2, lw=1))
    for i, v in enumerate(vals):
        ax.text(i + 0.3, v, f"{v:+.2f}", va="center", fontsize=8)
    ax.axhline(0, color=plots.TEXT_2, lw=0.8)
    ax.set_xticks(xs, names, fontsize=8)
    ax.set_ylabel("realised growth per bet, thousandths (90% range)")
    ax.grid(axis="x", visible=False)
    best = max(names, key=lambda n: res[n][0])
    ax.set_title(f"{len(bets):,} real bets, 2014–26: the 90% ranges of all four sizings "
                 "include zero")
    plots.save(fig, out_dir, "sig_sizing")

    return {
        "panel": {"rows": len(panel), "months": panel["t"].nunique(),
                  "base rate": round(float(panel["y"].mean()), 3)},
        "out-of-sample predictions": {"rows": len(preds), "from": f"{preds['t'].min():%b %Y}",
                                      "p 1/10/50/90/99%": preds["p"].quantile(
                                          [0.01, 0.1, 0.5, 0.9, 0.99]).round(3).tolist()},
        "calibration (all out-of-sample)": (round(a_all, 3), round(slope_all, 3)),
        "walk-forward slope range": (round(float(bets["slope"].min()), 2),
                                     round(float(bets["slope"].max()), 2)),
        "reliability by tenth (p, recalibrated p, hit)": rel.round(3).to_dict("records"),
        "Brier model / base rate": (round(float(((preds["p"] - preds["y"]) ** 2).mean()), 5),
                                    round(float(((preds["y"].mean() - preds["y"]) ** 2).mean()),
                                          5)),
        "bets": len(bets),
        "sizing (growth ×1000, 5%, 95%, average stake, share of bets placed)": {
            n: (round(v[0] * 1000, 3), round(v[1] * 1000, 3), round(v[2] * 1000, 3),
                round(v[3], 4), round(v[4], 3)) for n, v in res.items()},
        "best": best,
        "theory: growth ×1000 at stated 0.53/0.545/0.56/0.60, true 0.53": [
            round(growth_rate(2 * sp - 1, true_p, 1.0) * 1000, 3)
            for sp in (0.53, 0.545, 0.56, 0.60)],
    }


REPORTS = {"bets": report_bets, "stock": report_stock, "estimation": report_estimation,
           "drawdown": report_drawdown, "multi": report_multi, "frictions": report_frictions,
           "signal": report_signal}
