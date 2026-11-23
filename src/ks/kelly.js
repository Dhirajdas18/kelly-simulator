// Kelly betting simulator in the browser. Mirrors src/ks/bets.py; tests compare the two.

function kellyFraction(p, b) { return Math.max(0, p - (1 - p) / b); }

function growthRate(f, p, b) { return p * Math.log1p(f * b) + (1 - p) * Math.log1p(-f); }

function mulberry32(seed) {  // small seeded generator: the same inputs give the same paths
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Log wealth (0 = ₹1) after each bet, one array per path.
function simulate(f, p, b, nBets, nPaths, seed = 1) {
  const rand = mulberry32(seed), up = Math.log1p(f * b), down = Math.log1p(-f), out = [];
  for (let i = 0; i < nPaths; i++) {
    const path = new Float64Array(nBets + 1);
    for (let t = 1; t <= nBets; t++) path[t] = path[t - 1] + (rand() < p ? up : down);
    out.push(path);
  }
  return out;
}

function median(xs) {
  const s = [...xs].sort((a, b) => a - b), n = s.length;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

function summarise(logw) {
  const last = logw.map((p) => p[p.length - 1]), n = logw.length;
  const final = last.map(Math.exp), half = Math.log(0.5);
  return {
    median: median(final),
    mean: final.reduce((a, b) => a + b, 0) / n,
    typical: Math.exp(last.reduce((a, b) => a + b, 0) / n),
    halved: logw.filter((p) => p.some((x) => x <= half)).length / n,
    behind: final.filter((x) => x < 1).length / n,
  };
}

function quantile(sorted, q) {  // numpy's default (linear interpolation)
  const i = q * (sorted.length - 1), lo = Math.floor(i), f = i - lo;
  return lo + 1 < sorted.length ? sorted[lo] + f * (sorted[lo + 1] - sorted[lo]) : sorted[lo];
}

// Kelly for a stock (mirrors src/ks/stock.py): fraction f in the stock, the rest in cash at rf.
function kellyContinuous(mu, sigma, rf) { return (mu - rf) / (sigma * sigma); }
function growthContinuous(f, mu, sigma, rf) { return rf + f * (mu - rf) - f * f * sigma * sigma / 2; }

// Best multiple of an estimated Kelly fraction with `years` of data (mirrors ks/estimation.py).
function optimalMultiple(sharpe, years) { const x = sharpe * sharpe * years; return x / (x + 1); }

if (typeof module !== "undefined") module.exports = { kellyFraction, growthRate, simulate, summarise, quantile, median, kellyContinuous, growthContinuous, optimalMultiple };
