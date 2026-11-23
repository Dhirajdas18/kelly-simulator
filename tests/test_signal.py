import numpy as np
import pandas as pd
import pytest

from ks.signal import (
    calibration,
    fit_logistic,
    monthly_panel,
    realised_growth,
    recalibrate,
    walk_forward_probs,
)


def test_fit_logistic_recovers_coefficients():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(20_000, 2))
    p = 1 / (1 + np.exp(-(0.3 + X @ np.array([0.8, -0.5]))))
    y = (rng.random(20_000) < p).astype(float)
    assert fit_logistic(X, y) == pytest.approx([0.3, 0.8, -0.5], abs=0.05)


def test_calibration_slope_of_overconfident_probabilities():
    rng = np.random.default_rng(1)
    true_logit = rng.normal(0, 0.2, 50_000)
    y = (rng.random(50_000) < 1 / (1 + np.exp(-true_logit))).astype(float)
    stated = 1 / (1 + np.exp(-2 * true_logit))  # twice as far from 50% as the truth
    a, slope = calibration(stated, y)
    assert slope == pytest.approx(0.5, abs=0.05) and a == pytest.approx(0, abs=0.02)
    fixed = recalibrate(stated, a, slope)
    assert fixed == pytest.approx(1 / (1 + np.exp(-(a + slope * 2 * true_logit))))


def test_monthly_panel_features_and_labels_use_the_right_months():
    idx = pd.bdate_range("2015-01-01", "2017-12-31")
    rng = np.random.default_rng(2)
    R = pd.DataFrame(rng.normal(0.0005, 0.01, (len(idx), 4)), index=idx, columns=list("ABCD"))
    panel = monthly_panel(R, list("ABCD"))
    px = (1 + R).cumprod()
    me = px.resample("ME").last()
    t = me.index[14]
    row = panel[(panel["t"] == t) & (panel["symbol"] == "A")].iloc[0]
    nxt = me.iloc[15] / me.iloc[14] - 1
    assert row["x"] == pytest.approx(nxt["A"] - nxt.median())
    assert row["y"] == float(nxt["A"] > nxt.median())
    mom = me.iloc[13] / me.iloc[2] - 1  # 12 months back to 1 month back
    assert row["mom"] == pytest.approx(mom.rank(pct=True)["A"])


def test_walk_forward_probs_train_only_on_earlier_months():
    rng = np.random.default_rng(3)
    months = pd.date_range("2010-01-31", periods=60, freq="ME")
    panel = pd.DataFrame({"t": np.repeat(months, 20), "mom": rng.random(1200),
                          "rev": rng.random(1200), "vol": rng.random(1200)})
    panel["y"] = (rng.random(1200) < 0.5).astype(float)
    out = walk_forward_probs(panel, ["mom", "rev", "vol"], min_months=36)
    assert out["t"].min() == months[36]
    t = months[40]
    changed = panel.copy()
    changed.loc[changed["t"] >= t, "y"] = 1.0  # a different future
    out2 = walk_forward_probs(changed, ["mom", "rev", "vol"], min_months=36)
    assert out2.loc[out2["t"] == t, "p"].to_numpy() == pytest.approx(
        out.loc[out["t"] == t, "p"].to_numpy())


def test_realised_growth_of_even_money_bets():
    f = np.array([0.1, 0.1, 0.0])
    y = np.array([1.0, 0.0, 1.0])
    assert realised_growth(f, y) == pytest.approx((np.log(1.1) + np.log(0.9)) / 3)
