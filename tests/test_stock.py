import numpy as np
import pandas as pd
import pytest

from ks.stock import (
    annual_stats,
    growth_continuous,
    kelly_continuous,
    levered_growth,
    rolling_kelly,
)

RF = 0.065


def _gbm(mu=0.15, sigma=0.20, years=40, seed=0):
    idx = pd.bdate_range("1990-01-01", periods=int(years * 250))
    per_year = (len(idx) - 1) / ((idx[-1] - idx[0]).days / 365.25)
    r = np.random.default_rng(seed).normal(mu / per_year, sigma / np.sqrt(per_year), len(idx))
    return pd.Series(r, index=idx)


def test_annual_stats_use_calendar_time():
    r = _gbm()
    s = annual_stats(r)
    years = (r.index[-1] - r.index[0]).days / 365.25
    assert s["per_year"] == pytest.approx((len(r) - 1) / years)
    assert s["mu"] == pytest.approx(r.mean() * s["per_year"])
    assert s["sigma"] == pytest.approx(r.std() * np.sqrt(s["per_year"]))


def test_kelly_and_growth_formulas():
    assert kelly_continuous(0.15, 0.20, RF) == pytest.approx(0.085 / 0.04)
    f = np.linspace(0, 5, 501)
    g = growth_continuous(f, 0.15, 0.20, RF)
    assert f[np.argmax(g)] == pytest.approx(2.125, abs=0.01)
    top = growth_continuous(2.125, 0.15, 0.20, RF)
    assert top == pytest.approx(RF + (0.085 / 0.20) ** 2 / 2)  # rf + Sharpe² / 2
    assert growth_continuous(0.0, 0.15, 0.20, RF) == pytest.approx(RF)


def test_realised_levered_growth_peaks_near_kelly():
    r = _gbm(seed=3)
    s = annual_stats(r)
    fs = np.linspace(0.5, 4, 36)
    g = [levered_growth(r, f, RF) for f in fs]
    best = fs[int(np.argmax(g))]
    assert best == pytest.approx(kelly_continuous(s["mu"], s["sigma"], RF), abs=0.15)
    assert levered_growth(r, 0.0, RF) == pytest.approx(np.log(1 + RF), rel=1e-3)


def test_levered_growth_is_ruin_when_a_day_wipes_out():
    r = pd.Series([0.01, -0.2, 0.01], index=pd.bdate_range("2020-01-01", periods=3))
    assert levered_growth(r, 5.0, RF) == -np.inf


def test_rolling_kelly_uses_only_the_trailing_window():
    r = _gbm(years=10)
    roll = rolling_kelly(r, RF, years=3)
    t = roll.dropna().index[100]
    window = r[(r.index > t - pd.DateOffset(years=3)) & (r.index <= t)]
    s = annual_stats(window)
    assert roll[t] == pytest.approx(kelly_continuous(s["mu"], s["sigma"], RF))
    assert roll[: r.index[0] + pd.DateOffset(years=3) - pd.Timedelta(days=1)].isna().all()
