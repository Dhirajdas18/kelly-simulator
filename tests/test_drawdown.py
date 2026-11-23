import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from ks.drawdown import (
    drawdown,
    longest_underwater,
    prob_ahead,
    simulate_log_wealth,
    years_to_confidence,
)


def test_drawdown_and_longest_underwater():
    idx = pd.to_datetime(["2020-01-01", "2020-07-01", "2021-01-01", "2022-01-01", "2022-07-01"])
    w = pd.Series([1.0, 2.0, 1.0, 1.5, 2.5], index=idx)
    assert drawdown(w).tolist() == pytest.approx([0, 0, -0.5, -0.25, 0])
    # under the July 2020 peak from then until it is regained in July 2022
    assert longest_underwater(w) == pytest.approx((idx[4] - idx[1]).days / 365.25)
    still = pd.Series([1.0, 2.0, 1.0], index=idx[:3])  # never regained: counts to the end
    assert longest_underwater(still) == pytest.approx((idx[2] - idx[1]).days / 365.25)


def test_prob_ahead_formula_and_inverse():
    s, T = 0.45, 10
    assert prob_ahead(1.0, 0.5, s, T) == pytest.approx(norm.cdf(np.sqrt(T) * s * 0.25))
    assert prob_ahead(1.0, 1.0, s, T) == 0.5
    assert prob_ahead(2.0, 0.0, s, T) == pytest.approx(0.5)  # double Kelly grows like cash
    y = years_to_confidence(1.0, 0.5, s, 0.95)
    assert prob_ahead(1.0, 0.5, s, y) == pytest.approx(0.95)


def test_simulated_paths_agree_with_prob_ahead():
    mu, sig, rf = 0.139, 0.165, 0.065
    k = (mu - rf) / sig**2
    a = simulate_log_wealth(k, mu, sig, rf, years=10, n=4000, seed=3)
    b = simulate_log_wealth(0.5 * k, mu, sig, rf, years=10, n=4000, seed=3)  # same shocks
    assert a.shape == (4000, 2471)
    share = float((a[:, -1] > b[:, -1]).mean())
    assert share == pytest.approx(prob_ahead(1.0, 0.5, (mu - rf) / sig, 10), abs=0.03)
