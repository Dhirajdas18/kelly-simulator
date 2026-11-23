import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from ks.bets import growth_rate, kelly_fraction, summarise

JS = Path(__file__).resolve().parents[1] / "src" / "ks" / "kelly.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _node(expr: str):
    script = f"const m = require({json.dumps(str(JS))}); console.log(JSON.stringify({expr}));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_browser_formulas_match_python():
    js = _node("[m.kellyFraction(0.55, 1), m.kellyFraction(0.4, 2), m.kellyFraction(0.45, 1),"
               " m.growthRate(0.1, 0.55, 1), m.growthRate(0.3, 0.6, 1.5)]")
    assert js[:3] == pytest.approx([kelly_fraction(0.55, 1), kelly_fraction(0.4, 2), 0.0])
    assert js[3:] == pytest.approx([growth_rate(0.1, 0.55, 1), growth_rate(0.3, 0.6, 1.5)],
                                   rel=1e-12)


def test_browser_summary_matches_python():
    logw = np.log(np.array([[1, 2, 4], [1, 0.4, 0.8], [1, 1.5, 0.9], [1, 1.1, 1.3]]))
    js = _node(f"m.summarise({json.dumps(logw.tolist())})")
    py = summarise(logw)
    for k_js, k_py in (("median", "median multiple"), ("mean", "mean multiple"),
                       ("halved", "P(ever halved)"), ("behind", "P(behind at end)")):
        assert js[k_js] == pytest.approx(py[k_py], rel=1e-12)


def test_browser_simulation_grows_at_the_formula_rate_and_is_repeatable():
    js = _node("(() => { const a = m.simulate(0.1, 0.55, 1, 1000, 4000, 7);"
               " const b = m.simulate(0.1, 0.55, 1, 1000, 4000, 7);"
               " const s = m.summarise(a);"
               " return [s.typical, a[3][500] === b[3][500], a.length, a[0].length]; })()")
    assert np.log(js[0]) / 1000 == pytest.approx(growth_rate(0.1, 0.55, 1), rel=0.05)
    assert js[1] is True and js[2:] == [4000, 1001]


def test_browser_continuous_kelly_matches_python():
    from ks.stock import growth_continuous, kelly_continuous

    js = _node("[m.kellyContinuous(0.15, 0.2, 0.065), m.growthContinuous(1.5, 0.15, 0.2, 0.065)]")
    assert js == pytest.approx([kelly_continuous(0.15, 0.2, 0.065),
                                growth_continuous(1.5, 0.15, 0.2, 0.065)], rel=1e-12)


def test_browser_optimal_multiple_matches_python():
    from ks.estimation import optimal_multiple

    js = _node("[m.optimalMultiple(0.45, 5), m.optimalMultiple(-0.2, 3),"
               " m.optimalMultiple(0.3, 17.9)]")
    assert js == pytest.approx([optimal_multiple(0.45, 5), optimal_multiple(-0.2, 3),
                                optimal_multiple(0.3, 17.9)], rel=1e-12)
