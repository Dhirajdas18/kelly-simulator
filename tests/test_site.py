import numpy as np
import pandas as pd
import pytest

from ks.data import ETFS, SYMBOLS
from ks.site import build_html, stock_data
from ks.stock import annual_stats


def _returns():
    idx = pd.bdate_range("2008-01-01", "2026-11-20")
    r = pd.DataFrame(np.random.default_rng(0).normal(0.0004, 0.012, (len(idx), len(SYMBOLS) + 3)),
                     index=idx, columns=SYMBOLS + ETFS + ["NIFTY"])
    r.loc[:"2023-12-31", SYMBOLS[0]] = np.nan  # listed recently: no 5-year window
    return r


def test_stock_data_has_each_window_from_calendar_time():
    d = stock_data(_returns())
    assert d["symbols"][:2] == ETFS and d["rf"] == 0.065
    nb = d["stats"]["NIFTYBEES"]
    r = _returns()["NIFTYBEES"]
    s = annual_stats(r[r.index > r.index[-1] - pd.DateOffset(years=3)])
    assert nb["3y"] == pytest.approx([round(s["mu"], 5), round(s["sigma"], 5),
                                      round(s["years"], 3)])
    assert d["stats"][SYMBOLS[0]]["5y"] is None and d["stats"][SYMBOLS[0]]["1y"] is not None


def test_page_builds_with_every_section(monkeypatch):
    import ks.reports

    idx = pd.date_range("2008-01-04", "2026-11-20", freq="W-FRI")
    weekly = pd.DataFrame(np.random.default_rng(1).normal(0.002, 0.02, (len(idx), 3)), index=idx,
                          columns=["NIFTY", "gold", "US (₹)"])
    monkeypatch.setattr(ks.reports, "weekly_assets", lambda: weekly)  # no data files in CI
    html = build_html(_returns())
    assert 'id="kelly-across-assets"' in html
    assert "function kellyContinuous" in html and 'id="kelly-for-a-stock"' in html
    assert "$" + "js" not in html and "$" + "data" not in html
