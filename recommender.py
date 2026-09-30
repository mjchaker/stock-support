"""Transparent, rules-based stock scoring and ranking engine.

The rest of this project *displays* Yahoo Finance data.  This module turns that
data into a decision: every stock gets a 0-100 composite score built from six
pillars (value, quality, growth, momentum, analyst sentiment, dividends), a
plain-English list of reasons, a list of red flags, and a verdict.

Design rules:

* Everything here works on plain ``dict`` objects shaped like ``yfinance``'s
  ``Ticker.info``.  No network access happens in this module, so the whole
  engine can be unit-tested offline with fixture data.
* Every threshold is a named constant in ``METRIC_RULES`` so the logic can be
  audited and tuned.  There is no black box.
* Missing data never silently becomes a good or bad score.  A metric that is
  absent is excluded, the pillar is averaged over what is present, and the
  overall ``coverage`` figure tells you how much of the picture you have.

Nothing in this file is investment advice.  The factors used (cheap valuation,
high profitability, low leverage, positive momentum) are the ones with the
strongest long-run academic evidence, but past factor premia do not guarantee
future returns.  Use the output as a shortlist, then read the filings.
"""

from __future__ import annotations

import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Scoring rules
# ---------------------------------------------------------------------------

# Each pillar's weight in the composite.  They sum to 1.0; when a pillar has no
# data its weight is redistributed proportionally to the pillars that do.
PILLAR_WEIGHTS: Dict[str, float] = {
    "value": 0.25,
    "quality": 0.25,
    "growth": 0.15,
    "momentum": 0.15,
    "analyst": 0.10,
    "dividend": 0.10,
}

# A "curve" is a list of (input, score) points.  Inputs between points are
# linearly interpolated; inputs beyond the ends are clamped to the end score.
Curve = Sequence[Tuple[float, float]]

METRIC_RULES: Dict[str, Dict[str, Curve]] = {
    "value": {
        # Trailing P/E: cheap earnings are good, but a P/E under ~5 usually
        # means the market expects earnings to collapse, so we do not reward
        # the extreme.
        "trailingPE": [(3, 60), (8, 100), (15, 70), (25, 40), (40, 10)],
        "forwardPE": [(3, 60), (8, 100), (15, 70), (25, 40), (40, 10)],
        "pegRatio": [(0.3, 90), (1.0, 100), (2.0, 50), (3.0, 10)],
        "priceToBook": [(0.3, 80), (1.0, 100), (3.0, 60), (8.0, 15)],
        "enterpriseToEbitda": [(2, 80), (6, 100), (12, 50), (20, 10)],
        # Derived: free cash flow / market cap, as a fraction.
        "fcfYield": [(-0.05, 5), (0.0, 30), (0.04, 60), (0.08, 100)],
    },
    "quality": {
        "returnOnEquity": [(-0.10, 5), (0.0, 20), (0.10, 60), (0.20, 100)],
        "returnOnAssets": [(-0.05, 5), (0.0, 20), (0.05, 60), (0.10, 100)],
        "profitMargins": [(-0.10, 5), (0.0, 25), (0.10, 70), (0.20, 100)],
        "operatingMargins": [(-0.10, 5), (0.0, 25), (0.10, 65), (0.25, 100)],
        # yfinance reports debtToEquity in percent (e.g. 45.3 == 0.45x).
        "debtToEquity": [(0, 100), (30, 100), (100, 50), (250, 5)],
        "currentRatio": [(0.5, 5), (0.8, 10), (1.0, 50), (1.5, 80), (2.0, 100)],
    },
    "growth": {
        "revenueGrowth": [(-0.20, 5), (0.0, 40), (0.10, 70), (0.25, 100)],
        "earningsGrowth": [(-0.30, 5), (0.0, 40), (0.10, 70), (0.25, 100)],
    },
    "momentum": {
        # Derived: (price / 200-day average) - 1.  Modest strength is best;
        # a stock 40 % above its 200-day average is stretched, not attractive.
        "vs200Day": [(-0.30, 5), (-0.15, 20), (0.0, 55), (0.15, 90), (0.40, 60)],
        "vs50Day": [(-0.20, 10), (-0.08, 30), (0.0, 55), (0.08, 85), (0.25, 60)],
        # Derived: where price sits in the 52-week range (0 = at low, 1 = high).
        "range52w": [(0.0, 20), (0.35, 45), (0.75, 85), (1.0, 75)],
    },
    "analyst": {
        # Derived: (targetMeanPrice / price) - 1.
        "targetUpside": [(-0.20, 5), (0.0, 40), (0.15, 75), (0.30, 100)],
        # 1 = strong buy ... 5 = sell.
        "recommendationMean": [(1.0, 100), (2.0, 80), (3.0, 50), (4.0, 20), (5.0, 0)],
    },
    "dividend": {
        # Derived: yield as a fraction (0.04 == 4 %).  No dividend is neutral,
        # not bad; a double-digit yield is usually a warning sign.
        "dividendYieldFrac": [(0.0, 40), (0.02, 65), (0.04, 90), (0.06, 100), (0.10, 50)],
        "payoutRatio": [(0.0, 90), (0.3, 100), (0.6, 100), (0.8, 60), (1.0, 15)],
    },
}

# Human-readable labels for the "reasons" output.
METRIC_LABELS: Dict[str, str] = {
    "trailingPE": "trailing P/E",
    "forwardPE": "forward P/E",
    "pegRatio": "PEG ratio",
    "priceToBook": "price/book",
    "enterpriseToEbitda": "EV/EBITDA",
    "fcfYield": "free-cash-flow yield",
    "returnOnEquity": "return on equity",
    "returnOnAssets": "return on assets",
    "profitMargins": "net margin",
    "operatingMargins": "operating margin",
    "debtToEquity": "debt/equity",
    "currentRatio": "current ratio",
    "revenueGrowth": "revenue growth",
    "earningsGrowth": "earnings growth",
    "vs200Day": "price vs 200-day average",
    "vs50Day": "price vs 50-day average",
    "range52w": "position in 52-week range",
    "targetUpside": "upside to analyst target",
    "recommendationMean": "analyst consensus",
    "dividendYieldFrac": "dividend yield",
    "payoutRatio": "payout ratio",
}

# Metrics shown as percentages in the reasons text.
PERCENT_METRICS = {
    "fcfYield", "returnOnEquity", "returnOnAssets", "profitMargins",
    "operatingMargins", "revenueGrowth", "earningsGrowth", "vs200Day",
    "vs50Day", "targetUpside", "dividendYieldFrac", "payoutRatio", "range52w",
}

# Verdict thresholds on the composite score.
VERDICT_STRONG_BUY = 75.0
VERDICT_BUY = 62.0
VERDICT_HOLD = 45.0
MIN_COVERAGE = 0.40  # below this share of metrics we refuse to give a verdict.

# Default universe when no symbols are supplied.
DEFAULT_WATCHLIST: List[str] = ["CEU.TO", "CCO.TO", "TSAT.TO"]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class RedFlag:
    code: str
    message: str
    critical: bool = False


@dataclass
class StockScore:
    symbol: str
    name: str = ""
    sector: str = ""
    price: Optional[float] = None
    composite: Optional[float] = None
    pillars: Dict[str, Optional[float]] = field(default_factory=dict)
    metrics: Dict[str, Optional[float]] = field(default_factory=dict)
    coverage: float = 0.0
    verdict: str = "Insufficient data"
    reasons: List[str] = field(default_factory=list)
    red_flags: List[RedFlag] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_buy(self) -> bool:
        return self.verdict in ("Buy", "Strong Buy")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _num(value) -> Optional[float]:
    """Return ``value`` as a finite float, or ``None``."""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def interpolate(curve: Curve, x: float) -> float:
    """Piecewise-linear lookup of ``x`` on ``curve`` with end clamping."""
    pts = sorted(curve)
    if x <= pts[0][0]:
        return float(pts[0][1])
    if x >= pts[-1][0]:
        return float(pts[-1][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return float(y1)
            t = (x - x0) / (x1 - x0)
            return float(y0 + t * (y1 - y0))
    return float(pts[-1][1])  # pragma: no cover - unreachable


def normalize_symbol(symbol: str, default_suffix: str = ".TO") -> str:
    """Upper-case a symbol and add the TSX suffix when none is present.

    TSX class shares are written ``BAM.A`` on tsx.com but ``BAM-A.TO`` on
    Yahoo, so a single dot is turned into a dash before the suffix is added.
    """
    s = symbol.strip().upper()
    if not s:
        return s
    if ":" in s:
        s = s.split(":")[0]
    known_suffixes = (".TO", ".V", ".CN", ".NE")
    if s.endswith(known_suffixes):
        return s
    if "." in s:
        s = s.replace(".", "-")
    return s + default_suffix


def derive_metrics(info: dict) -> Dict[str, Optional[float]]:
    """Pull the raw metrics we score out of a ``Ticker.info``-style dict."""
    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    market_cap = _num(info.get("marketCap"))
    m: Dict[str, Optional[float]] = {}

    for pillar_rules in METRIC_RULES.values():
        for key in pillar_rules:
            m[key] = _num(info.get(key))

    # Derived metrics ----------------------------------------------------
    fcf = _num(info.get("freeCashflow"))
    m["fcfYield"] = fcf / market_cap if fcf is not None and market_cap else None

    avg200 = _num(info.get("twoHundredDayAverage"))
    avg50 = _num(info.get("fiftyDayAverage"))
    m["vs200Day"] = price / avg200 - 1 if price and avg200 else None
    m["vs50Day"] = price / avg50 - 1 if price and avg50 else None

    hi = _num(info.get("fiftyTwoWeekHigh"))
    lo = _num(info.get("fiftyTwoWeekLow"))
    if price is not None and hi is not None and lo is not None and hi > lo:
        m["range52w"] = min(1.0, max(0.0, (price - lo) / (hi - lo)))
    else:
        m["range52w"] = None

    target = _num(info.get("targetMeanPrice"))
    m["targetUpside"] = target / price - 1 if price and target else None

    m["dividendYieldFrac"] = dividend_yield_fraction(info, price)

    # A negative trailing P/E means negative earnings; yfinance usually omits
    # it in that case, but guard anyway so it is not scored as "cheap".
    for key in ("trailingPE", "forwardPE", "pegRatio", "enterpriseToEbitda", "priceToBook"):
        if m.get(key) is not None and m[key] <= 0:
            m[key] = None
    return m


def dividend_yield_fraction(info: dict, price: Optional[float]) -> Optional[float]:
    """Return the dividend yield as a fraction (0.04 == 4 %).

    ``yfinance`` has flipped ``dividendYield`` between fraction and percent
    form across versions, so the annual rate divided by price is used when
    both are present and the raw field is only a fallback.
    """
    rate = _num(info.get("dividendRate"))
    if rate is not None and price:
        return max(0.0, rate / price)
    raw = _num(info.get("dividendYield"))
    if raw is None:
        return None
    if raw < 0:
        return 0.0
    # No real company yields more than 100 %; anything above 1 must be percent.
    return raw / 100.0 if raw > 1.0 else raw


def _fmt(key: str, value: float) -> str:
    if key in PERCENT_METRICS:
        return f"{value * 100:.1f}%"
    if key == "debtToEquity":
        return f"{value / 100:.2f}x"
    return f"{value:.2f}"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_pillars(metrics: Dict[str, Optional[float]]) -> Tuple[Dict[str, Optional[float]], Dict[str, float], int]:
    """Score each pillar.  Returns (pillar scores, per-metric scores, metric count)."""
    pillar_scores: Dict[str, Optional[float]] = {}
    metric_scores: Dict[str, float] = {}
    available = 0
    for pillar, rules in METRIC_RULES.items():
        vals = []
        for key, curve in rules.items():
            v = metrics.get(key)
            if v is None:
                continue
            s = interpolate(curve, v)
            metric_scores[key] = s
            vals.append(s)
            available += 1
        pillar_scores[pillar] = sum(vals) / len(vals) if vals else None
    return pillar_scores, metric_scores, available


def composite_score(pillar_scores: Dict[str, Optional[float]], weights: Dict[str, float] = PILLAR_WEIGHTS) -> Optional[float]:
    """Weighted average of the pillars that have data."""
    num = 0.0
    den = 0.0
    for pillar, w in weights.items():
        s = pillar_scores.get(pillar)
        if s is None:
            continue
        num += w * s
        den += w
    return round(num / den, 1) if den else None


def find_red_flags(info: dict, metrics: Dict[str, Optional[float]]) -> List[RedFlag]:
    flags: List[RedFlag] = []
    de = metrics.get("debtToEquity")
    cr = metrics.get("currentRatio")
    margin = metrics.get("profitMargins")
    fcf = _num(info.get("freeCashflow"))
    mcap = _num(info.get("marketCap"))
    vol = _num(info.get("averageVolume"))
    payout = metrics.get("payoutRatio")
    yld = metrics.get("dividendYieldFrac")
    beta = _num(info.get("beta"))
    eg = metrics.get("earningsGrowth")
    rng = metrics.get("range52w")

    if de is not None and de > 200:
        flags.append(RedFlag("leverage", f"Debt/equity of {de / 100:.1f}x is very high", critical=True))
    if cr is not None and cr < 1.0:
        flags.append(RedFlag("liquidity", f"Current ratio {cr:.2f} is below 1: short-term obligations exceed liquid assets", critical=cr < 0.8))
    if margin is not None and margin < 0 and fcf is not None and fcf < 0:
        flags.append(RedFlag("burning_cash", "Loss-making and burning cash (negative net margin and free cash flow)", critical=True))
    if mcap is not None and mcap < 50_000_000:
        flags.append(RedFlag("micro_cap", f"Micro-cap ({mcap / 1e6:.0f}M): thin liquidity and high volatility", critical=False))
    if vol is not None and vol < 20_000:
        flags.append(RedFlag("illiquid", f"Average volume {vol:,.0f} shares/day is very thin", critical=False))
    if payout is not None and payout > 1.0:
        flags.append(RedFlag("payout", f"Paying out {payout * 100:.0f}% of earnings: dividend may not be sustainable", critical=False))
    if yld is not None and yld > 0.10:
        flags.append(RedFlag("yield_trap", f"Dividend yield {yld * 100:.1f}% is suspiciously high (possible yield trap)", critical=False))
    if beta is not None and beta > 2.0:
        flags.append(RedFlag("volatile", f"Beta {beta:.1f}: moves roughly {beta:.1f}x the market", critical=False))
    if rng is not None and rng < 0.15 and eg is not None and eg < 0:
        flags.append(RedFlag("falling_knife", "Near 52-week low with shrinking earnings", critical=False))
    return flags


def decide_verdict(composite: Optional[float], coverage: float, flags: List[RedFlag]) -> str:
    if composite is None or coverage < MIN_COVERAGE:
        return "Insufficient data"
    has_critical = any(f.critical for f in flags)
    if composite >= VERDICT_STRONG_BUY and not has_critical:
        return "Strong Buy"
    if composite >= VERDICT_BUY and not has_critical:
        return "Buy"
    if composite >= VERDICT_HOLD or (composite >= VERDICT_BUY and has_critical):
        return "Hold"
    return "Avoid"


def build_reasons(metrics: Dict[str, Optional[float]], metric_scores: Dict[str, float], limit: int = 3) -> List[str]:
    """Top strengths and weaknesses in plain English."""
    scored = [(k, s) for k, s in metric_scores.items() if metrics.get(k) is not None]
    if not scored:
        return []
    strengths = sorted(scored, key=lambda kv: -kv[1])[:limit]
    weaknesses = sorted(scored, key=lambda kv: kv[1])[:limit]
    out: List[str] = []
    for k, s in strengths:
        if s >= 70:
            out.append(f"+ {METRIC_LABELS[k]} {_fmt(k, metrics[k])}")
    for k, s in weaknesses:
        if s <= 40:
            out.append(f"- {METRIC_LABELS[k]} {_fmt(k, metrics[k])}")
    return out


def score_stock(symbol: str, info: Optional[dict], error: Optional[str] = None) -> StockScore:
    """Score one stock from its ``Ticker.info`` dict."""
    result = StockScore(symbol=symbol, error=error)
    if not info or error:
        result.error = error or "No data returned"
        return result

    result.name = info.get("longName") or info.get("shortName") or ""
    result.sector = info.get("sector") or ""
    result.price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))

    metrics = derive_metrics(info)
    pillar_scores, metric_scores, available = score_pillars(metrics)
    total_metrics = sum(len(r) for r in METRIC_RULES.values())

    result.metrics = metrics
    result.pillars = {k: (round(v, 1) if v is not None else None) for k, v in pillar_scores.items()}
    result.coverage = round(available / total_metrics, 2)
    result.composite = composite_score(pillar_scores)
    result.red_flags = find_red_flags(info, metrics)
    result.verdict = decide_verdict(result.composite, result.coverage, result.red_flags)
    result.reasons = build_reasons(metrics, metric_scores)
    return result


def rank_stocks(scores: Iterable[StockScore]) -> List[StockScore]:
    """Best first.  Unscorable stocks sink to the bottom."""
    return sorted(scores, key=lambda s: (s.composite is None, -(s.composite or 0.0), s.symbol))


# ---------------------------------------------------------------------------
# Portfolio construction
# ---------------------------------------------------------------------------


def suggest_allocation(ranked: Sequence[StockScore], capital: float, max_positions: int = 10, max_weight: float = 0.20) -> List[dict]:
    """Turn buys into position sizes.

    Weights are proportional to how far each score sits above the "Hold" line,
    capped at ``max_weight`` per name so one idea cannot sink the portfolio.
    Whatever is not allocated is reported as cash.
    """
    buys = [s for s in ranked if s.is_buy and s.price][:max_positions]
    if not buys or capital <= 0:
        return [{"symbol": "CASH", "weight": 1.0, "amount": round(capital, 2), "shares": None}]

    raw = [max(s.composite - VERDICT_HOLD, 1.0) for s in buys]
    total = sum(raw)
    weights = [min(max_weight, r / total) for r in raw]

    rows = []
    invested = 0.0
    for s, w in zip(buys, weights):
        amount = capital * w
        shares = math.floor(amount / s.price) if s.price else 0
        spent = shares * s.price
        invested += spent
        rows.append({
            "symbol": s.symbol,
            "name": s.name,
            "verdict": s.verdict,
            "score": s.composite,
            "weight": round(w, 4),
            "price": s.price,
            "shares": shares,
            "amount": round(spent, 2),
        })
    rows.append({"symbol": "CASH", "weight": round(1 - invested / capital, 4), "amount": round(capital - invested, 2), "shares": None})
    return rows


# ---------------------------------------------------------------------------
# Screening (network access happens only through the injected fetcher)
# ---------------------------------------------------------------------------

Fetcher = Callable[[str], dict]


def _load_cache(path: Optional[str], max_age_hours: float) -> dict:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    cutoff = time.time() - max_age_hours * 3600
    return {k: v for k, v in data.items() if v.get("fetched_at", 0) >= cutoff}


def _save_cache(path: Optional[str], cache: dict) -> None:
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
    except (OSError, TypeError):
        pass


def screen(symbols: Sequence[str], fetcher: Fetcher, workers: int = 8, cache_path: Optional[str] = None,
           cache_hours: float = 12.0, progress: Optional[Callable[[int, int, str], None]] = None) -> List[StockScore]:
    """Fetch and score many symbols concurrently.  Returns a ranked list.

    ``fetcher`` is any callable returning a ``Ticker.info``-style dict for a
    symbol; the stock handler's ``get_company_info`` is the usual choice.
    Results are cached as JSON (when ``cache_path`` is given) so re-running a
    full-exchange scan the same day is instant.
    """
    symbols = [normalize_symbol(s) for s in symbols if s and s.strip()]
    symbols = list(dict.fromkeys(symbols))  # de-duplicate, keep order
    cache = _load_cache(cache_path, cache_hours)
    results: List[StockScore] = []
    todo = [s for s in symbols if s not in cache]
    done = 0
    total = len(symbols)

    for s in symbols:
        if s in cache:
            entry = cache[s]
            results.append(score_stock(s, entry.get("info"), entry.get("error")))
            done += 1
            if progress:
                progress(done, total, s)

    def fetch(sym: str):
        try:
            info = fetcher(sym)
            if not isinstance(info, dict) or not info or info.get("quoteType") is None and info.get("longName") is None:
                return sym, None, "No data returned"
            return sym, info, None
        except Exception as exc:  # network / parsing failures must not kill the scan
            return sym, None, str(exc)

    if todo:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = [pool.submit(fetch, s) for s in todo]
            for fut in as_completed(futures):
                sym, info, err = fut.result()
                cache[sym] = {"info": _json_safe(info), "error": err, "fetched_at": time.time()}
                results.append(score_stock(sym, info, err))
                done += 1
                if progress:
                    progress(done, total, sym)
        _save_cache(cache_path, cache)

    return rank_stocks(results)


def _json_safe(info: Optional[dict]) -> Optional[dict]:
    if info is None:
        return None
    out = {}
    for k, v in info.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            out[k] = str(v)
    return out


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------


def to_dataframe(scores: Sequence[StockScore]):
    """Flatten scores into a pandas DataFrame (imported lazily)."""
    import pandas as pd

    rows = []
    for s in scores:
        row = {
            "Symbol": s.symbol,
            "Name": s.name,
            "Sector": s.sector,
            "Price": s.price,
            "Score": s.composite,
            "Verdict": s.verdict,
            "Coverage": s.coverage,
        }
        for p in PILLAR_WEIGHTS:
            row[p.capitalize()] = s.pillars.get(p)
        row["Reasons"] = "; ".join(s.reasons)
        row["Red flags"] = "; ".join(f.message for f in s.red_flags)
        row["Error"] = s.error or ""
        rows.append(row)
    return pd.DataFrame(rows)


def export_excel(scores: Sequence[StockScore], filename: str = "tsx_recommendations.xlsx") -> str:
    df = to_dataframe(scores)
    df.to_excel(filename, index=False)
    return filename


def format_table(scores: Sequence[StockScore], limit: Optional[int] = None) -> str:
    """Console-friendly ranking table."""
    rows = list(scores)[:limit] if limit else list(scores)
    header = f"{'#':>3} {'Symbol':<10} {'Score':>5} {'Verdict':<17} {'Val':>4} {'Qual':>4} {'Grow':>4} {'Mom':>4} {'Anly':>4} {'Div':>4}  Name"
    lines = [header, "-" * len(header)]
    for i, s in enumerate(rows, 1):
        if s.composite is None:
            lines.append(f"{i:>3} {s.symbol:<10} {'--':>5} {s.verdict:<17} {'':>29}  {s.error or ''}")
            continue

        def p(k):
            v = s.pillars.get(k)
            return f"{v:4.0f}" if v is not None else "  --"

        lines.append(
            f"{i:>3} {s.symbol:<10} {s.composite:5.1f} {s.verdict:<17} "
            f"{p('value')} {p('quality')} {p('growth')} {p('momentum')} {p('analyst')} {p('dividend')}  {s.name[:40]}"
        )
    return "\n".join(lines)


def format_detail(s: StockScore) -> str:
    """Multi-line explanation for a single stock."""
    lines = [f"{s.symbol}  {s.name}".rstrip()]
    if s.composite is None:
        lines.append(f"  Verdict: {s.verdict} ({s.error or 'not enough data'})")
        return "\n".join(lines)
    lines.append(f"  Verdict: {s.verdict}   Score: {s.composite}/100   Data coverage: {s.coverage * 100:.0f}%")
    pillar_txt = "   ".join(
        f"{k}: {v:.0f}" if v is not None else f"{k}: --" for k, v in s.pillars.items()
    )
    lines.append(f"  Pillars: {pillar_txt}")
    if s.reasons:
        lines.append("  Why:")
        lines.extend(f"    {r}" for r in s.reasons)
    if s.red_flags:
        lines.append("  Red flags:")
        lines.extend(f"    {'!! ' if f.critical else '!  '}{f.message}" for f in s.red_flags)
    return "\n".join(lines)


DISCLAIMER = (
    "Scores are a rules-based screen of public Yahoo Finance data, not personalised "
    "financial advice. Verify the numbers, read the filings, diversify, and never "
    "invest money you cannot afford to lose."
)
