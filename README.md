# Stock Support

A TSX stock screener that turns Yahoo Finance data into a ranked, explained
shortlist. Every stock gets a 0-100 score, a verdict (Strong Buy / Buy / Hold /
Avoid), the reasons behind it, and any red flags, so you spend your time on the
handful of names worth reading about instead of scrolling through ratios.

## Quick start

```bash
pip install -r requirements.txt

python stock_recomend.py                      # score the built-in watchlist
python stock_recomend.py CEU.TO CCO.TO SHOP   # score specific symbols (".TO" is added if missing)
python stock_recomend.py --detail CEU.TO      # full explanation for one stock
python stock_recomend.py --all --top 25       # scan the whole TSX interlisted list
python stock_recomend.py --all --min-score 70 --capital 10000 --excel
```

Fetched data is cached in `.stock_cache.json` for 12 hours so a full-exchange
scan only pays the download cost once a day. Pass `--cache ''` to disable.

Interfaces:

| Command | What you get |
| --- | --- |
| `python stock_recomend.py` | Ranking table, per-stock explanations, position sizing, Excel export |
| `python stock_web_gui.py` | Browser UI at http://127.0.0.1:8000 with a verdict card per stock and a "Rank These Stocks" panel |
| `python stock_gui.py` | Desktop (Tkinter) UI with a Verdict section on the Analysis tab |

## How the score works

The engine lives in `recommender.py` and is deliberately simple: a set of
piecewise-linear curves that map each metric to 0-100, averaged into six
pillars, then weighted into one composite.

| Pillar | Weight | Metrics |
| --- | --- | --- |
| Value | 25% | trailing and forward P/E, PEG, price/book, EV/EBITDA, free-cash-flow yield |
| Quality | 25% | ROE, ROA, net and operating margin, debt/equity, current ratio |
| Growth | 15% | revenue growth, earnings growth |
| Momentum | 15% | price vs 50- and 200-day averages, position in the 52-week range |
| Analyst | 10% | upside to mean target, consensus rating |
| Dividend | 10% | yield, payout ratio |

Rules that matter:

* Missing metrics are excluded, never assumed. A pillar with no data drops out
  and its weight is redistributed. The `coverage` figure tells you how much of
  the picture is present, and under 40% no verdict is given.
* Red flags are checked separately from the score. Critical ones (very high
  leverage, current ratio under 0.8, loss-making while burning cash) cap the
  verdict at Hold no matter how good the numbers look on paper.
* Extremes are not rewarded. A P/E of 3 or a 12% dividend yield scores worse
  than a P/E of 8 or a 5% yield, because those extremes usually mean the market
  expects something to break.
* Position sizing (`--capital`) only includes Buy and Strong Buy names, weights
  them by how far they sit above the Hold line, and caps any single name at 20%.
  Whatever is left is reported as cash.

Every threshold is a named constant at the top of `recommender.py`. If you
disagree with one, change it and re-run the tests.

## Tests

The scoring engine is pure Python over plain dictionaries, so it is tested
offline with fixture data:

```bash
python -m unittest discover -s tests -v
```

## Disclaimer

This is a rules-based screen of public data, not personalised financial advice.
The factors it favours (cheap valuation, high profitability, low leverage,
positive momentum) are the ones with the strongest long-run evidence, but past
factor premia do not guarantee future returns. Verify the numbers, read the
filings, diversify, and never invest money you cannot afford to lose.
