import numpy as np
import pytest

from ks.bets import growth_rate, halving_probability, kelly_fraction, simulate, summarise


def test_kelly_fraction_is_edge_over_odds():
    assert kelly_fraction(0.55, 1.0) == pytest.approx(0.10)
    assert kelly_fraction(0.40, 2.0) == pytest.approx(0.10)  # 0.4 − 0.6/2
    assert kelly_fraction(0.45, 1.0) == 0.0  # no edge: don't bet


def test_growth_rate_peaks_at_kelly_and_is_zero_near_double_kelly():
    f = np.linspace(0.001, 0.25, 2000)
    g = growth_rate(f, 0.55, 1.0)
    assert f[np.argmax(g)] == pytest.approx(0.10, abs=1e-3)
    assert growth_rate(0.0, 0.55, 1.0) == 0.0
    assert abs(growth_rate(0.20, 0.55, 1.0)) < 2e-4  # double Kelly: about no growth
    assert growth_rate(0.30, 0.55, 1.0) < 0


def test_simulated_median_growth_matches_the_formula():
    logw = simulate(0.10, 0.55, 1.0, n_bets=1000, n_paths=20_000, seed=1)
    assert logw.shape == (20_000, 1001) and np.all(logw[:, 0] == 0)
    per_bet = np.median(logw[:, -1]) / 1000
    assert per_bet == pytest.approx(growth_rate(0.10, 0.55, 1.0), rel=0.05)


def test_summarise_reads_paths():
    logw = np.log(np.array([[1, 2, 4], [1, 0.4, 0.8], [1, 1.5, 0.9]]))
    s = summarise(logw)
    assert s["median multiple"] == pytest.approx(0.9)
    assert s["mean multiple"] == pytest.approx((4 + 0.8 + 0.9) / 3)
    assert s["P(ever halved)"] == pytest.approx(1 / 3)
    assert s["P(behind at end)"] == pytest.approx(2 / 3)


def test_halving_probability_continuous_limit():
    # betting c × Kelly, P(wealth ever falls to x) = x^(2/c − 1)
    assert halving_probability(1.0) == pytest.approx(0.5)
    assert halving_probability(0.5) == pytest.approx(0.125)
    assert halving_probability(2.0) == 1.0
