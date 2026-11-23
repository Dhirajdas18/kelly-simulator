"""Interactive dashboard: a live Kelly simulator plus charts, as one static page."""

import json
import re
from pathlib import Path
from string import Template

import pandas as pd

from ks import plots

FONT = "system-ui, -apple-system, \"Segoe UI\", Roboto, sans-serif"
ICON = (
    "data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 16%22%3E"
    "%3Cpath d=%22M1 14C5 13 8 9 9 2c1 7 3 10 6 12%22 fill=%22none%22 stroke=%22%232a78d6%22"
    " stroke-width=%222%22/%3E"
    "%3C/svg%3E"
)
HERE = Path(__file__).parent
JS = (HERE / "kelly.js").read_text(encoding="utf-8")
SIMULATOR = (HERE / "simulator.html").read_text(encoding="utf-8")
STOCK = (HERE / "stock.html").read_text(encoding="utf-8")
LABELS = {"NIFTYBEES": "NIFTY 50 ETF (NIFTYBEES)", "GOLDBEES": "Gold ETF (GOLDBEES)"}
WINDOWS = {"1y": 1, "3y": 3, "5y": 5, "2009": None}
PAGE = Template((HERE / "page.html").read_text(encoding="utf-8"))
REPO = "https://github.com/Dhirajdas18/kelly-simulator"


def simulator_section(data: pd.DataFrame | None) -> str:
    return SIMULATOR.replace("$js", JS)


def stock_data(r: pd.DataFrame) -> dict:
    """Annual mean and volatility (calendar time) of each holding over each window."""
    from ks.data import ETFS, SYMBOLS
    from ks.reports import RF, START
    from ks.stock import annual_stats

    symbols = ETFS + sorted(SYMBOLS)
    end = r.index[-1]
    stats = {}
    for sym in symbols:
        x = r[sym].loc[START:].dropna()
        stats[sym] = {}
        for key, yrs in WINDOWS.items():
            w = x if yrs is None else x[x.index > end - pd.DateOffset(years=yrs)]
            full = len(w) > 1 and (yrs is None or w.index[0] <= end - pd.DateOffset(years=yrs)
                                   + pd.DateOffset(days=10))
            if not full:
                stats[sym][key] = None
                continue
            s = annual_stats(w)
            stats[sym][key] = [round(s["mu"], 5), round(s["sigma"], 5), round(s["years"], 3)]
    return {"symbols": symbols, "labels": LABELS, "rf": RF, "last": f"{end:%d %b %Y}",
            "stats": stats}


def stock_section(data: pd.DataFrame) -> str:
    return STOCK.replace("$data", json.dumps(stock_data(data), separators=(",", ":")))


SECTIONS = [
    ("Kelly simulator",
     "A repeated bet: you win the stated amount per ₹1 staked with the chosen chance, otherwise "
     "lose the ₹1. Kelly’s rule bets the fraction of your money that makes it grow fastest. "
     "Change the bet size and watch 2,000 simulated players: the typical one, the middle 80%, "
     "and how many halve their money along the way.",
     simulator_section),
    ("Kelly for a stock",
     "Hold a fraction of your money in one stock or ETF and the rest in cash at 6.5% (above 1 "
     "means borrowing at 6.5%). Kelly’s fraction is the average return above cash divided by the "
     "variance. Pick a holding and a window: the numbers come from that window’s daily returns, "
     "so they show what Kelly would have said with hindsight, not a forecast.",
     stock_section),
]


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def build_html(data: pd.DataFrame | None = None) -> str:
    parts, nav = [], []
    sections = SECTIONS if data is not None else SECTIONS[:1]
    for title, blurb, make in sections:
        out = make(data)
        body = out if isinstance(out, str) else out.to_html(
            full_html=False, include_plotlyjs=False,
            config={"displaylogo": False, "responsive": True})
        sid = _slug(title)
        nav.append(f'<li><a href="#{sid}">{title}</a></li>')
        parts.append(f'<section id="{sid}">\n<h2>{title}</h2>\n<p>{blurb}</p>\n{body}\n</section>')
    updated = data.index[-1] if data is not None else pd.Timestamp.today()
    d = plots.DARK
    return PAGE.substitute(
        icon=ICON, font=FONT, repo=REPO, updated=f"{updated:%d %b %Y}",
        surface=plots.SURFACE, text=plots.TEXT, text2=plots.TEXT_2, grid=plots.GRID,
        accent=plots.SERIES[0], muted=plots.MUTED, d_surface=d[plots.SURFACE], d_text=d[plots.TEXT],
        d_text2=d[plots.TEXT_2], d_grid=d[plots.GRID], d_accent=d[plots.SERIES[0]],
        d_muted="#6b6a64",
        dark=json.dumps({k.lower(): v for k, v in d.items()}),
        dark_lines=json.dumps({k.lower(): v for k, v in plots.DARK_LINES.items()}),
        nav="\n".join(nav), sections="\n".join(parts),
    )
