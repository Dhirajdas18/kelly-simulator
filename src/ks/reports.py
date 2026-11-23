"""README findings, one function per topic: `ks report <topic>` writes charts to out/."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

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


REPORTS = {"bets": report_bets}
