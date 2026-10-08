"""Offline tests for the scoring engine.  No network access is needed."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import recommender as r  # noqa: E402


def make_info(**overrides):
    """A profitable, reasonably priced, growing company with modest momentum."""
    base = {
        "longName": "Good Co",
        "sector": "Industrials",
        "currentPrice": 100.0,
        "marketCap": 5_000_000_000,
        "trailingPE": 12.0,
        "forwardPE": 11.0,
        "pegRatio": 1.0,
        "priceToBook": 1.8,
        "enterpriseToEbitda": 7.0,
        "freeCashflow": 300_000_000,
        "returnOnEquity": 0.18,
        "returnOnAssets": 0.08,
        "profitMargins": 0.15,
        "operatingMargins": 0.20,
        "debtToEquity": 40.0,
        "currentRatio": 1.8,
        "revenueGrowth": 0.12,
        "earningsGrowth": 0.15,
        "twoHundredDayAverage": 92.0,
        "fiftyDayAverage": 96.0,
        "fiftyTwoWeekHigh": 110.0,
        "fiftyTwoWeekLow": 70.0,
        "targetMeanPrice": 120.0,
        "recommendationMean": 1.8,
        "dividendRate": 3.0,
        "dividendYield": 0.03,
        "payoutRatio": 0.4,
        "averageVolume": 500_000,
        "beta": 0.9,
    }
    base.update(overrides)
    return base


class InterpolateTests(unittest.TestCase):
    def test_clamps_below_and_above(self):
        curve = [(0, 10), (10, 90)]
        self.assertEqual(r.interpolate(curve, -5), 10)
        self.assertEqual(r.interpolate(curve, 50), 90)

    def test_linear_between_points(self):
        curve = [(0, 0), (10, 100)]
        self.assertAlmostEqual(r.interpolate(curve, 2.5), 25.0)

    def test_unsorted_curve_is_sorted(self):
        curve = [(10, 100), (0, 0)]
        self.assertAlmostEqual(r.interpolate(curve, 5), 50.0)


class NormalizeSymbolTests(unittest.TestCase):
    def test_adds_tsx_suffix(self):
        self.assertEqual(r.normalize_symbol("ceu"), "CEU.TO")

    def test_keeps_existing_suffix(self):
        self.assertEqual(r.normalize_symbol("CEU.TO"), "CEU.TO")
        self.assertEqual(r.normalize_symbol("abc.v"), "ABC.V")

    def test_class_shares_use_dash(self):
        self.assertEqual(r.normalize_symbol("BAM.A"), "BAM-A.TO")

    def test_strips_exchange_prefix_format(self):
        self.assertEqual(r.normalize_symbol("AAV:US"), "AAV.TO")


class DividendYieldTests(unittest.TestCase):
    def test_prefers_rate_over_price(self):
        self.assertAlmostEqual(r.dividend_yield_fraction({"dividendRate": 4, "dividendYield": 99}, 100), 0.04)

    def test_percent_form_is_converted(self):
        self.assertAlmostEqual(r.dividend_yield_fraction({"dividendYield": 3.5}, None), 0.035)

    def test_fraction_form_is_kept(self):
        self.assertAlmostEqual(r.dividend_yield_fraction({"dividendYield": 0.035}, None), 0.035)

    def test_missing_is_none(self):
        self.assertIsNone(r.dividend_yield_fraction({}, 100))


class DeriveMetricsTests(unittest.TestCase):
    def test_derived_values(self):
        m = r.derive_metrics(make_info())
        self.assertAlmostEqual(m["fcfYield"], 0.06)
        self.assertAlmostEqual(m["vs200Day"], 100 / 92 - 1)
        self.assertAlmostEqual(m["range52w"], 0.75)
        self.assertAlmostEqual(m["targetUpside"], 0.2)
        self.assertAlmostEqual(m["dividendYieldFrac"], 0.03)

    def test_negative_pe_is_not_scored_as_cheap(self):
        m = r.derive_metrics(make_info(trailingPE=-4.0))
        self.assertIsNone(m["trailingPE"])

    def test_garbage_values_become_none(self):
        m = r.derive_metrics(make_info(trailingPE="n/a", returnOnEquity=float("nan"), currentRatio=True))
        self.assertIsNone(m["trailingPE"])
        self.assertIsNone(m["returnOnEquity"])
        self.assertIsNone(m["currentRatio"])

    def test_falls_back_to_regular_market_price(self):
        info = make_info()
        del info["currentPrice"]
        info["regularMarketPrice"] = 100.0
        self.assertAlmostEqual(r.derive_metrics(info)["range52w"], 0.75)


class ScoreStockTests(unittest.TestCase):
    def test_good_company_is_a_buy(self):
        s = r.score_stock("GOOD.TO", make_info())
        self.assertIn(s.verdict, ("Buy", "Strong Buy"))
        self.assertGreaterEqual(s.composite, r.VERDICT_BUY)
        self.assertEqual(s.name, "Good Co")
        self.assertEqual(s.coverage, 1.0)
        self.assertEqual(s.red_flags, [])
        self.assertTrue(any(line.startswith("+") for line in s.reasons))

    def test_expensive_unprofitable_company_is_avoided(self):
        bad = make_info(
            trailingPE=95.0, forwardPE=80.0, pegRatio=4.0, priceToBook=12.0, enterpriseToEbitda=40.0,
            freeCashflow=-200_000_000, returnOnEquity=-0.2, returnOnAssets=-0.1, profitMargins=-0.3,
            operatingMargins=-0.2, debtToEquity=320.0, currentRatio=0.6, revenueGrowth=-0.25,
            earningsGrowth=-0.5, twoHundredDayAverage=150.0, fiftyDayAverage=130.0,
            fiftyTwoWeekHigh=200.0, fiftyTwoWeekLow=95.0, targetMeanPrice=80.0, recommendationMean=4.2,
            dividendRate=0, dividendYield=0, payoutRatio=0,
        )
        s = r.score_stock("BAD.TO", bad)
        self.assertEqual(s.verdict, "Avoid")
        self.assertLess(s.composite, r.VERDICT_HOLD)
        codes = {f.code for f in s.red_flags}
        self.assertIn("leverage", codes)
        self.assertIn("liquidity", codes)
        self.assertIn("burning_cash", codes)
        self.assertIn("falling_knife", codes)
        self.assertTrue(any(f.critical for f in s.red_flags))

    def test_critical_red_flag_caps_verdict_at_hold(self):
        s = r.score_stock("LEV.TO", make_info(debtToEquity=300.0))
        self.assertGreaterEqual(s.composite, r.VERDICT_BUY)  # still scores well on paper
        self.assertEqual(s.verdict, "Hold")
        self.assertFalse(s.is_buy)

    def test_missing_pillar_redistributes_weight(self):
        info = make_info()
        for k in ("dividendRate", "dividendYield", "payoutRatio"):
            del info[k]
        s = r.score_stock("NODIV.TO", info)
        self.assertIsNone(s.pillars["dividend"])
        self.assertIsNotNone(s.composite)
        self.assertLess(s.coverage, 1.0)

    def test_too_little_data_gives_no_verdict(self):
        s = r.score_stock("THIN.TO", {"longName": "Thin Co", "currentPrice": 5.0, "trailingPE": 10.0})
        self.assertEqual(s.verdict, "Insufficient data")
        self.assertLess(s.coverage, r.MIN_COVERAGE)

    def test_error_and_empty_info(self):
        s = r.score_stock("ERR.TO", None, "boom")
        self.assertEqual(s.error, "boom")
        self.assertIsNone(s.composite)
        self.assertEqual(s.verdict, "Insufficient data")
        s2 = r.score_stock("EMPTY.TO", {})
        self.assertEqual(s2.error, "No data returned")

    def test_yield_trap_and_payout_flags(self):
        s = r.score_stock("TRAP.TO", make_info(dividendRate=14.0, payoutRatio=1.4))
        codes = {f.code for f in s.red_flags}
        self.assertIn("yield_trap", codes)
        self.assertIn("payout", codes)
        self.assertFalse(any(f.critical for f in s.red_flags))

    def test_to_dict_is_json_friendly(self):
        import json
        s = r.score_stock("GOOD.TO", make_info(debtToEquity=300.0))
        text = json.dumps(s.to_dict())
        self.assertIn('"red_flags"', text)


class RankAndAllocateTests(unittest.TestCase):
    def setUp(self):
        self.good = r.score_stock("GOOD.TO", make_info())
        self.meh = r.score_stock("MEH.TO", make_info(trailingPE=30, forwardPE=28, pegRatio=2.5, returnOnEquity=0.04,
                                                     profitMargins=0.03, revenueGrowth=0.0, targetMeanPrice=100))
        self.err = r.score_stock("ERR.TO", None, "timeout")

    def test_rank_puts_best_first_and_errors_last(self):
        ranked = r.rank_stocks([self.err, self.meh, self.good])
        self.assertEqual([s.symbol for s in ranked], ["GOOD.TO", "MEH.TO", "ERR.TO"])

    def test_allocation_only_buys_and_caps_weight(self):
        ranked = r.rank_stocks([self.good, self.meh, self.err])
        rows = r.suggest_allocation(ranked, 10_000)
        symbols = [row["symbol"] for row in rows]
        self.assertIn("GOOD.TO", symbols)
        self.assertNotIn("ERR.TO", symbols)
        self.assertEqual(symbols[-1], "CASH")
        for row in rows[:-1]:
            self.assertLessEqual(row["weight"], 0.20 + 1e-9)
            self.assertEqual(row["amount"], row["shares"] * row["price"])
        self.assertAlmostEqual(sum(row["amount"] for row in rows), 10_000, places=2)

    def test_allocation_with_no_buys_is_all_cash(self):
        rows = r.suggest_allocation([self.err], 500)
        self.assertEqual(rows, [{"symbol": "CASH", "weight": 1.0, "amount": 500, "shares": None}])


class ScreenTests(unittest.TestCase):
    def test_screen_uses_fetcher_and_cache(self):
        calls = []

        def fetcher(sym):
            calls.append(sym)
            if sym == "FAIL.TO":
                raise RuntimeError("network down")
            return make_info(longName=sym)

        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = os.path.join(tmp, "cache.json")
            ranked = r.screen(["good", "FAIL.TO", "good"], fetcher, workers=2, cache_path=cache)
            self.assertEqual(sorted(calls), ["FAIL.TO", "GOOD.TO"])  # de-duplicated
            self.assertEqual(ranked[0].symbol, "GOOD.TO")
            self.assertEqual(ranked[-1].symbol, "FAIL.TO")
            self.assertEqual(ranked[-1].error, "network down")

            calls.clear()
            ranked2 = r.screen(["GOOD.TO", "FAIL.TO"], fetcher, workers=2, cache_path=cache)
            self.assertEqual(calls, [])  # everything came from cache
            self.assertEqual(ranked2[0].composite, ranked[0].composite)

    def test_progress_callback(self):
        seen = []
        r.screen(["A", "B"], lambda s: make_info(), workers=1, progress=lambda d, t, s: seen.append((d, t)))
        self.assertEqual(sorted(seen), [(1, 2), (2, 2)])


class PresentationTests(unittest.TestCase):
    def test_table_and_detail_render(self):
        good = r.score_stock("GOOD.TO", make_info())
        err = r.score_stock("ERR.TO", None, "timeout")
        table = r.format_table([good, err])
        self.assertIn("GOOD.TO", table)
        self.assertIn("timeout", table)
        detail = r.format_detail(r.score_stock("LEV.TO", make_info(debtToEquity=300.0)))
        self.assertIn("Red flags", detail)
        self.assertIn("!!", detail)

    def test_dataframe_columns(self):
        df = r.to_dataframe([r.score_stock("GOOD.TO", make_info())])
        for col in ("Symbol", "Score", "Verdict", "Value", "Quality", "Reasons", "Red flags"):
            self.assertIn(col, df.columns)
        self.assertEqual(df.iloc[0]["Symbol"], "GOOD.TO")


if __name__ == "__main__":
    unittest.main()
