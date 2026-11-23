import numpy as np
import pandas as pd
import pytest

from ks.frictions import (
    RATES,
    etf_trade_cost,
    ewma_vol,
    growth_spread,
    kelly_spread,
    run_strategy,
)

RL, RB = 0.065, 0.146


def test_kelly_with_a_borrowing_spread_has_a_kink_at_one():
    assert kelly_spread(0.139, 0.165, RL, RB) == 1.0  # wants 2.7× at 6.5%, but not at 14.6%
    assert kelly_spread(0.10, 0.20, RL, RB) == pytest.approx(0.035 / 0.04)  # below 1: lending
    assert kelly_spread(0.40, 0.20, RL, RB) == pytest.approx((0.40 - RB) / 0.04)  # borrows anyway
    f = np.linspace(0, 3, 3001)
    g = growth_spread(f, 0.139, 0.165, RL, RB)
    assert f[np.argmax(g)] == pytest.approx(1.0, abs=1e-3)
    assert growth_spread(2.0, 0.139, 0.165, RL, RL) == pytest.approx(
        RL + 2 * (0.139 - RL) - 2 * 0.165**2)


def test_etf_trade_cost():
    fees = (RATES["exchange"] + RATES["sebi"]) * (1 + RATES["gst"])
    c = etf_trade_cost(buy=0.10, sell=0.0, capital=1e6)
    assert c == pytest.approx(0.10 * (fees + RATES["slippage"] + RATES["stamp_buy"]))
    s = etf_trade_cost(buy=0.0, sell=0.10, capital=1e6, mtf=True)
    per_order = min(RATES["mtf_brokerage"] * 0.10 * 1e6, RATES["mtf_order_max"]) / 1e6
    assert s == pytest.approx(0.10 * (fees + RATES["slippage"] + RATES["stt_sell"])
                              + RATES["dp_per_sell"] / 1e6 + per_order)
    assert etf_trade_cost(0.0, 0.0, 1e6) == 0.0


def test_ewma_vol_uses_past_returns_only():
    r = pd.Series(np.r_[np.full(50, 0.01), 0.10], index=pd.bdate_range("2020-01-01", periods=51))
    v = ewma_vol(r, lam=0.94, per_year=250)
    assert v.iloc[-1] == pytest.approx(v.iloc[-2])  # the 10% day is not in that day's forecast
    assert v.iloc[30] == pytest.approx(0.01 * np.sqrt(250), rel=1e-6)


def test_hold_has_no_trades_and_a_constant_fraction_is_reset():
    idx = pd.bdate_range("2020-01-01", periods=300)
    r = pd.Series(np.random.default_rng(0).normal(0.0005, 0.01, 300), index=idx)
    hold = run_strategy(r, pd.Series(1.0, index=idx), RL, RB, capital=1e6, band=0.0,
                        costs=True)
    assert hold["costs"] == 0.0
    assert hold["wealth"].iloc[-1] == pytest.approx(float((1 + r.iloc[1:]).prod()))
    lev = run_strategy(r, pd.Series(1.5, index=idx), RL, RB, capital=1e6, band=0.0,
                       costs=False)
    days = idx.to_series().diff().dt.days.to_numpy()[1:]
    gross = 1 + 1.5 * r.to_numpy()[1:] - 0.5 * RB / 365 * days
    assert lev["wealth"].iloc[-1] == pytest.approx(float(np.prod(gross)))
    banded = run_strategy(r, pd.Series(1.5, index=idx), RL, RB, capital=1e6, band=0.1,
                          costs=True)
    daily = run_strategy(r, pd.Series(1.5, index=idx), RL, RB, capital=1e6, band=0.0,
                         costs=True)
    assert banded["trades"] < daily["trades"] and banded["costs"] < daily["costs"]
