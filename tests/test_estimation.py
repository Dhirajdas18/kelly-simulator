import numpy as np
import pandas as pd
import pytest

from ks.estimation import (
    excess_growth_estimated,
    optimal_multiple,
    simulate_estimated_growth,
    walk_forward,
)

RF = 0.065


def test_optimal_multiple_and_excess_growth_formulas():
    assert optimal_multiple(0.45, 5) == pytest.approx(0.2025 * 5 / (0.2025 * 5 + 1))
    assert optimal_multiple(0.45, np.inf) == 1.0
    c = np.linspace(0, 2, 2001)
    g = excess_growth_estimated(c, 0.45, 5)
    assert c[np.argmax(g)] == pytest.approx(optimal_multiple(0.45, 5), abs=1e-3)
    assert excess_growth_estimated(1.0, 0.45, np.inf) == pytest.approx(0.45**2 / 2)


def test_simulation_matches_the_formula():
    for c in (0.5, 1.0):
        sim = simulate_estimated_growth(c, mu=0.139, sigma=0.165, rf=RF, years=5, n=4000, seed=2)
        assert sim == pytest.approx(excess_growth_estimated(c, (0.139 - RF) / 0.165, 5), abs=0.006)


def test_walk_forward_uses_past_data_only_and_respects_limits():
    idx = pd.bdate_range("2005-01-01", "2016-12-31")
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.0005, 0.01, len(idx)), index=idx)
    res = walk_forward(r, RF, multiple=1.0, window_years=5, cap=3.0, floor=0.0,
                       start="2011-01-01")
    f = res["fraction"]
    assert f.index[0] >= pd.Timestamp("2011-01-01")
    assert f.between(0, 3).all()
    # the fraction held after a month end is decided from data up to that close only
    t = f.index[f.index.to_series().dt.month.diff().ne(0)][6]  # first day of a month
    r2 = r.copy()
    r2[r2.index >= t] += 0.01  # a different future from that day on
    f2 = walk_forward(r2, RF, 1.0, 5, 3.0, 0.0, start="2011-01-01")["fraction"]
    assert f2[t] == f[t]
    assert f.diff().ne(0)[f.index.to_series().dt.month.diff().eq(0)].sum() == 0  # monthly
    # wealth compounds the held fraction of each day's return plus cash on the rest
    w = res["wealth"]
    d = w.index[10]
    prev = w.index[9]
    days = (d - prev).days
    expected = w[prev] * (1 + f[d] * r[d] + (1 - f[d]) * ((1 + RF) ** (days / 365) - 1))
    assert w[d] == pytest.approx(expected)
