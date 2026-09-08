"""Offline V0.1 regression boundaries; no credentials or provider requests."""
import copy
import json
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from src import analysis, calculations as calc, research_pipeline as pipeline
from src.evidence import build_evidence_catalog, build_material_evidence_checklist, resolve_evidence_id
from src.models import BalanceSheetPeriod, CashFlowPeriod, EarningsPeriod, IncomeStatementPeriod


def evidence():
    return {
        "ticker": "TEST",
        "retrieved_facts": {"stock": {"pe_ratio": 20, "forward_pe": 18, "current_price": None}},
        "calculated_metrics": {
            "cash_flow_metrics": {"free_cash_flow_growth": -0.1},
            "balance_sheet_metrics": {"debt_to_equity": 1.5},
        },
        "missing_data": ["Fixture missing data"],
    }


def payload(data):
    catalog = build_evidence_catalog(data)
    result = {name: "Fixture interpretation" for name in analysis.TEXT_FIELDS}
    result.update(ticker=data["ticker"], recommendation="Hold", confidence_score=60,
                  missing_data=[], material_evidence_review={
                      ref: {"observation": "Fixture observation", "thesis_relevance": "Fixture relevance"}
                      for refs in build_material_evidence_checklist(data).values() for ref in refs
                  })
    result.update({name: [{"text": "Fixture statement", "evidence_refs": [catalog[0]["evidence_id"]]}]
                   for name in analysis.STATEMENT_LISTS})
    return result


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.network = patch("socket.socket.connect", side_effect=AssertionError("Network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_income_growth_and_margins(self):
        periods = [IncomeStatementPeriod("2025-12-31", 120, 30, 18),
                   IncomeStatementPeriod("2024-12-31", 100, 20, 15)]
        result = calc.calculate_income_statement_metrics(periods)
        self.assertAlmostEqual(result["revenue_growth"], .2)
        self.assertAlmostEqual(result["net_income_growth"], .2)
        self.assertAlmostEqual(result["operating_margin"], .25)
        self.assertAlmostEqual(result["net_margin"], .15)

    def test_missing_and_zero_denominators(self):
        for current, previous in [(None, 1), (1, None), (1, 0)]:
            self.assertIsNone(calc.calculate_growth_rate(current, previous))
            self.assertIsNone(calc.calculate_ratio(current, previous))
        self.assertTrue(all(v is None for v in calc.calculate_income_statement_metrics([]).values()))
        one = calc.calculate_income_statement_metrics([IncomeStatementPeriod("2025-12-31", 100, 20, 10)])
        self.assertIsNone(one["revenue_growth"])
        self.assertEqual(one["net_margin"], .1)
        self.assertIsNone(calc.calculate_free_cash_flow(None, 2))

    def test_cash_flow_matches_revenue_period(self):
        cash = [CashFlowPeriod("2025-12-31", 100, 20), CashFlowPeriod("2024-12-31", 110, 10)]
        income = [IncomeStatementPeriod("2026-12-31", 999), IncomeStatementPeriod("2025-12-31", 200)]
        result = calc.calculate_cash_flow_metrics(cash, income)
        self.assertEqual(result, {"free_cash_flow": 80, "free_cash_flow_growth": -.2,
                                  "free_cash_flow_margin": .4})
        self.assertIsNone(calc.calculate_cash_flow_metrics(cash, income[:1])["free_cash_flow_margin"])

    def test_balance_sheet_ratios(self):
        period = BalanceSheetPeriod("2025-12-31", 20, 200, 150, total_debt=100, shareholder_equity=50)
        self.assertEqual(calc.calculate_balance_sheet_metrics([period]),
                         {"debt_to_equity": 2, "liabilities_to_assets": .75, "cash_to_debt": .2})
        self.assertTrue(all(v is None for v in calc.calculate_balance_sheet_metrics([]).values()))

    def test_earnings_latest_average_and_four_period_limit(self):
        periods = [EarningsPeriod("2025-12-31", reported_eps=2, estimated_eps=1, surprise_percentage=10),
                   EarningsPeriod("2025-09-30", reported_eps=1, estimated_eps=2, surprise_percentage=-5),
                   EarningsPeriod("2025-06-30", reported_eps=1, estimated_eps=1),
                   EarningsPeriod("2025-03-31"),
                   EarningsPeriod("2024-12-31", surprise_percentage=999)]
        self.assertEqual(calc.calculate_earnings_metrics(periods),
                         {"latest_surprise_percentage": 10, "average_surprise_percentage": 2.5,
                          "beats_last_4_quarters": 1, "misses_last_4_quarters": 1})

    def test_catalog_provenance_and_tampering(self):
        data = evidence()
        catalog = build_evidence_catalog(data)
        self.assertEqual(catalog, build_evidence_catalog(copy.deepcopy(data)))
        self.assertEqual(catalog[0], {"evidence_id": "E001", "path": "retrieved_facts.stock.pe_ratio", "value": 20})
        self.assertFalse(any(e["path"].endswith("current_price") for e in catalog))
        for entry in catalog:
            self.assertEqual(resolve_evidence_id(entry["evidence_id"], catalog, data), entry)
        tampered = copy.deepcopy(catalog)
        tampered[0]["value"] = 21
        with self.assertRaises(ValueError):
            resolve_evidence_id("E001", tampered, data)

    def test_material_reviews_exact_keys_and_nonempty_text(self):
        data = evidence()
        good = payload(data)
        required = list(good["material_evidence_review"])
        schema = analysis.build_analysis_schema(data)["properties"]["material_evidence_review"]
        self.assertEqual(schema["required"], required)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(list(analysis._validate_analysis(good, data).material_evidence_review), required)
        for ref in required:
            with self.subTest(omitted=ref):
                bad = copy.deepcopy(good)
                del bad["material_evidence_review"][ref]
                with self.assertRaises(ValueError):
                    analysis._validate_analysis(bad, data)
        for ref in ["E999", "retrieved_facts.stock.pe_ratio"]:
            bad = copy.deepcopy(good)
            bad["material_evidence_review"][ref] = good["material_evidence_review"][required[0]]
            with self.assertRaises(ValueError):
                analysis._validate_analysis(bad, data)
        for field in ["observation", "thesis_relevance"]:
            bad = copy.deepcopy(good)
            bad["material_evidence_review"][required[0]][field] = " "
            with self.assertRaises(ValueError):
                analysis._validate_analysis(bad, data)

    def test_statement_ids_reject_unknown_and_old_paths(self):
        for ref in ["E999", "retrieved_facts.stock.pe_ratio", "earnings[0]"]:
            data = evidence()
            bad = payload(data)
            bad["bull_case"][0]["evidence_refs"] = [ref]
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                analysis._validate_analysis(bad, data)

    def test_recommendations_confidence_and_missing_data(self):
        data = evidence()
        for recommendation in ["Buy", "Accumulate", "Hold", "Trim", "Avoid"]:
            for score in [0, 100]:
                good = payload(data)
                good.update(recommendation=recommendation, confidence_score=score)
                self.assertEqual(analysis._validate_analysis(good, data).missing_data, data["missing_data"])
        for field, value in [("recommendation", "Sell"), ("confidence_score", -1),
                             ("confidence_score", 101), ("confidence_score", True),
                             ("confidence_score", float("nan"))]:
            bad = payload(data)
            bad[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                analysis._validate_analysis(bad, data)

    def test_mocked_pipeline_failure_policies_and_request_counts(self):
        responses = {
            "get_company_overview": {"Symbol": "TEST", "Name": "Fixture company"},
            "get_global_quote": {"Global Quote": {"05. price": "10"}},
            "get_income_statement": {"annualReports": []},
            "get_balance_sheet": {"annualReports": []},
            "get_cash_flow": {"annualReports": []},
            "get_earnings": {"quarterlyEarnings": [{"fiscalDateEnding": "2025-06-30"}]},
            "get_news_sentiment": {"feed": []},
            "get_earnings_call_transcript": {"transcript": [{"content": "Fixture transcript"}]},
        }
        optional = ["get_global_quote", "get_news_sentiment", "get_earnings_call_transcript"]
        critical = [name for name in responses if name not in optional]
        for failures in [[], *[[n] for n in optional], optional, *[[n] for n in critical]]:
            with self.subTest(failures=failures), ExitStack() as stack:
                mocks = {}
                for name, response in responses.items():
                    mock = stack.enter_context(patch.object(pipeline.api, name, return_value=copy.deepcopy(response)))
                    mock.__name__ = name
                    if name in failures:
                        mock.side_effect = RuntimeError("Fixture provider failure")
                    mocks[name] = mock
                captured = []
                def respond(**kwargs):
                    data = json.loads(kwargs["input"])["evidence_package"]
                    captured.append(data)
                    return json.dumps(payload(data))
                request = stack.enter_context(patch.object(analysis, "request_text", side_effect=respond))
                stack.enter_context(patch("logging.Logger.warning"))
                if any(name in critical for name in failures):
                    with self.assertRaises(RuntimeError):
                        pipeline.run_stock_research(" test ")
                    request.assert_not_called()
                else:
                    result = pipeline.run_stock_research(" test ")
                    self.assertEqual(result.ticker, "TEST")
                    request.assert_called_once()
                    self.assertEqual(result.missing_data, captured[0]["missing_data"])
                    for name, label in zip(optional, ["Latest available quote unavailable",
                                                      "Recent relevant news unavailable",
                                                      "Earnings call transcript unavailable"]):
                        if name in failures:
                            self.assertEqual(result.missing_data.count(label), 1)
                    mocks["get_earnings_call_transcript"].assert_called_once_with("TEST", "2025Q2")
                for mock in mocks.values():
                    self.assertLessEqual(mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
