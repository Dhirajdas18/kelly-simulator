import numpy as np
import pandas as pd
import pytest

from ks.data import weekly_asset_returns
from ks.multi import capped_kelly, growth_multi, kelly_weights, tangency

RF = 0.065
MU = np.array([0.14, 0.10, 0.15])
SIG = np.array([0.17, 0.15, 0.16])
CORR = np.array([[1, -0.05, 0.3], [-0.05, 1, 0.05], [0.3, 0.05, 1]])
COV = CORR * np.outer(SIG, SIG)


def test_kelly_weights_maximise_growth_and_point_at_the_tangency_portfolio():
    w = kelly_weights(MU, COV, RF)
    assert w == pytest.approx(np.linalg.solve(COV, MU - RF))
    for d in np.eye(3) * 0.01:  # any small move lowers growth
        assert growth_multi(w + d, MU, COV, RF) < growth_multi(w, MU, COV, RF)
        assert growth_multi(w - d, MU, COV, RF) < growth_multi(w, MU, COV, RF)
    t = tangency(MU, COV, RF)
    assert t.sum() == pytest.approx(1) and t == pytest.approx(w / w.sum())
    s_tan = (t @ (MU - RF)) / np.sqrt(t @ COV @ t)
    assert growth_multi(w, MU, COV, RF) == pytest.approx(RF + s_tan**2 / 2)


def test_capped_kelly_respects_long_only_and_gross_cap():
    w = capped_kelly(MU, COV, RF, max_gross=1.0)
    assert np.all(w >= -1e-9) and w.sum() <= 1 + 1e-6
    assert w.sum() == pytest.approx(1, abs=1e-4)  # Kelly wants more than 1×, so the cap binds
    free = kelly_weights(MU, COV, RF)
    big = capped_kelly(MU, COV, RF, max_gross=50.0)
    assert big == pytest.approx(np.clip(free, 0, None), abs=1e-3)  # all positive here: uncapped


def test_weekly_asset_returns_align_calendars_and_convert_dollars():
    nse = pd.bdate_range("2020-01-01", "2020-03-31")
    us = nse[nse.day_of_week != 4]  # the US skips Fridays here: its week ends on Thursday
    prices = pd.DataFrame({"NIFTYBEES": np.linspace(100, 110, len(nse)),
                           "GOLDBEES": np.linspace(50, 52, len(nse))}, index=nse)
    glob = pd.DataFrame({"SP500TR": np.linspace(1000, 1100, len(us)),
                         "USDINR": np.linspace(70, 77, len(us))}, index=us)
    w = weekly_asset_returns(prices, glob)
    assert list(w.columns) == ["NIFTY", "gold", "US (₹)"]
    usd_inr = (glob["SP500TR"] * glob["USDINR"]).resample("W-FRI").last()
    assert w["US (₹)"].iloc[3] == pytest.approx(usd_inr.iloc[4] / usd_inr.iloc[3] - 1)
    assert not w.isna().any().any()


def test_walk_forward_multi_is_monthly_past_only_and_bounded():
    from ks.multi import walk_forward_multi

    idx = pd.date_range("2005-01-07", "2016-12-30", freq="W-FRI")
    rng = np.random.default_rng(1)
    W = pd.DataFrame(rng.multivariate_normal(MU / 52, COV / 52, len(idx)), index=idx,
                     columns=["NIFTY", "gold", "US (₹)"])
    res = walk_forward_multi(W, RF, multiple=0.5, window_years=5, max_gross=1.0,
                             start="2011-01-01")
    w = res["weights"]
    assert (w >= -1e-9).all().all() and (w.sum(axis=1) <= 1 + 1e-6).all()
    months = w.index.to_period("M")
    changes = w.diff().abs().sum(axis=1) > 1e-12
    assert not (changes & (months == months.to_series().shift().to_numpy())).any()
    t = w.index[20]
    W2 = W.copy()
    W2[W2.index >= t] += 0.02
    w2 = walk_forward_multi(W2, RF, 0.5, 5, 1.0, "2011-01-01")["weights"]
    assert w2.loc[t].to_numpy() == pytest.approx(w.loc[t].to_numpy())
    wl = res["wealth"]
    d, prev = wl.index[5], wl.index[4]
    cash = (1 + RF) ** ((d - prev).days / 365) - 1
    exp = wl[prev] * (1 + w.loc[d] @ W.loc[d] + (1 - w.loc[d].sum()) * cash)
    assert wl[d] == pytest.approx(exp)


def test_weekly_asset_returns_blank_known_bad_prints(tmp_path):
    nse = pd.bdate_range("2012-01-02", "2012-02-29")
    prices = pd.DataFrame({"NIFTYBEES": 100.0, "GOLDBEES": 50.0}, index=nse)
    glob = pd.DataFrame({"SP500TR": 1000.0, "USDINR": 50.0}, index=nse)
    glob.loc["2012-01-27", "USDINR"] = 52.5  # a bad print on a Friday
    fixes = tmp_path / "fixes.csv"
    fixes.write_text("symbol,date,action,reason\nUSDINR,2012-01-27,blank,bad print\n")
    w = weekly_asset_returns(prices, glob, fixes)
    assert w["US (₹)"].abs().max() == pytest.approx(0.0)


def test_fractional_capped_kelly_scales_the_position():
    from ks.multi import fractional_kelly

    full = capped_kelly(MU, COV, RF, max_gross=1.0)
    half = fractional_kelly(MU, COV, RF, multiple=0.5, max_gross=1.0)
    assert half == pytest.approx(0.5 * full, abs=1e-6)  # the cap binds: half the position
    free = fractional_kelly(MU, COV, RF, multiple=0.5, max_gross=50.0)
    assert free == pytest.approx(0.5 * kelly_weights(MU, COV, RF), abs=1e-3)
