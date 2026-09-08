"""Portfolio contracts and calculations: hard-coded values, no providers or credentials."""
import copy
import unittest
from unittest.mock import call, patch
from dataclasses import fields

from src.models import (
    PortfolioInput, PortfolioPositionInput, PortfolioPosition, PortfolioSnapshot,
)


from src.models import PortfolioRiskPolicy
from src.portfolio_risk import assess_portfolio_risk
from src import portfolio_data
from src.portfolio_calculations import build_portfolio_snapshot


class PortfolioModelTests(unittest.TestCase):
    def test_valid_position_input(self):
        position = PortfolioPositionInput("TEST", 2.5, 10.0)
        self.assertEqual((position.ticker, position.shares, position.average_cost),
                         ("TEST", 2.5, 10.0))
        self.assertEqual([f.name for f in fields(position)],
                         ["ticker", "shares", "average_cost"])

    def test_ticker_normalization(self):
        self.assertEqual(PortfolioPositionInput(" test ", 1, 0).ticker, "TEST")

    def test_empty_ticker_rejected(self):
        for ticker in ("", "  ", None):
            with self.subTest(ticker=ticker), self.assertRaises(ValueError):
                PortfolioPositionInput(ticker, 1, 1)

    def test_negative_shares_rejected(self):
        with self.assertRaises(ValueError):
            PortfolioPositionInput("TEST", -1, 10)

    def test_negative_average_cost_rejected(self):
        with self.assertRaises(ValueError):
            PortfolioPositionInput("TEST", 1, -10)

    def test_valid_portfolio_input(self):
        position = PortfolioPositionInput("TEST", 2, 10)
        portfolio = PortfolioInput([position], 30)
        self.assertEqual(portfolio.positions, [position])
        self.assertEqual(portfolio.cash, 30)

    def test_negative_cash_rejected(self):
        with self.assertRaises(ValueError):
            PortfolioInput([], -1)

    def test_duplicate_normalized_tickers_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            PortfolioInput([PortfolioPositionInput("TEST", 1, 10),
                            PortfolioPositionInput(" test ", 2, 20)], 0)

    def test_zero_positions_and_cash_only(self):
        position = PortfolioPositionInput("TEST", 0, 0)
        self.assertEqual(PortfolioInput([position], 0).positions, [position])
        self.assertEqual(PortfolioInput([], 100).positions, [])

    def test_invalid_numeric_inputs_rejected(self):
        for value in (float("nan"), float("inf"), True, "1", None):
            for name in ("shares", "average_cost", "cash"):
                with self.subTest(value=value, name=name), self.assertRaises(ValueError):
                    if name == "cash":
                        PortfolioInput([], value)
                    else:
                        args = {"ticker": "TEST", "shares": 1, "average_cost": 1}
                        args[name] = value
                        PortfolioPositionInput(**args)

    def test_invalid_positions_container_rejected(self):
        for positions in (None, {}, ["TEST"]):
            with self.subTest(positions=positions), self.assertRaises(ValueError):
                PortfolioInput(positions, 0)

    def test_calculated_position_construction(self):
        position = PortfolioPosition("TEST", 2, 10, 12, 20, 24, 4, .2, .6)
        self.assertEqual(position.unrealized_gain_loss_percent, .2)
        missing = PortfolioPosition("TEST", 2, 10, None, 20, None, None, None, None)
        self.assertIsNone(missing.position_value)
        self.assertEqual(missing.cost_basis, 20)

    def test_snapshot_construction(self):
        position = PortfolioPosition("TEST", 2, 10, 12, 20, 24, 4, .2, .6)
        snapshot = PortfolioSnapshot([position], 16, 24, 40, .4, "TEST", .6, .6, 1, 1 / .36, .36)
        self.assertEqual(snapshot.positions, [position])
        self.assertEqual(snapshot.total_portfolio_value, 40)
        self.assertEqual(snapshot.largest_position_ticker, "TEST")
        unavailable = PortfolioSnapshot([], 0, None, None, None, None, None, 0, 0, None, 0)
        self.assertIsNone(unavailable.largest_position_weight)


class PortfolioCalculationTests(unittest.TestCase):
    def test_single_position_gain(self):
        snapshot = build_portfolio_snapshot(
            PortfolioInput([PortfolioPositionInput("AAA", 2, 10)], 0), {"AAA": 15})
        self.assertEqual(snapshot.positions[0],
                         PortfolioPosition("AAA", 2, 10, 15, 20, 30, 10, .5, 1))
        self.assertEqual(snapshot.total_positions_value, 30)
        self.assertEqual(snapshot.total_portfolio_value, 30)
        self.assertEqual(snapshot.cash_weight, 0)

    def test_multiple_positions_cash_weights_and_largest(self):
        snapshot = build_portfolio_snapshot(PortfolioInput([
            PortfolioPositionInput("AAA", 2, 10), PortfolioPositionInput("BBB", 3, 20)
        ], 20), {"AAA": 10, "BBB": 20})
        self.assertEqual(snapshot.total_positions_value, 80)
        self.assertEqual(snapshot.total_portfolio_value, 100)
        self.assertEqual([p.portfolio_weight for p in snapshot.positions], [.2, .6])
        self.assertEqual(snapshot.cash_weight, .2)
        self.assertEqual((snapshot.largest_position_ticker, snapshot.largest_position_weight),
                         ("BBB", .6))

    def test_unrealized_loss(self):
        position = build_portfolio_snapshot(
            PortfolioInput([PortfolioPositionInput("AAA", 2, 10)], 0), {"AAA": 5}).positions[0]
        self.assertEqual(position.unrealized_gain_loss, -10)
        self.assertEqual(position.unrealized_gain_loss_percent, -.5)

    def test_zero_cost_basis(self):
        for shares, cost in [(2, 0), (0, 10)]:
            with self.subTest(shares=shares, cost=cost):
                position = build_portfolio_snapshot(
                    PortfolioInput([PortfolioPositionInput("AAA", shares, cost)], 0),
                    {"AAA": 5}).positions[0]
                self.assertEqual(position.cost_basis, 0)
                self.assertIsNone(position.unrealized_gain_loss_percent)

    def test_tie_and_order(self):
        snapshot = build_portfolio_snapshot(PortfolioInput([
            PortfolioPositionInput("ZZZ", 1, 10), PortfolioPositionInput("AAA", 2, 10)
        ], 0), {"AAA": 5, "ZZZ": 10})
        self.assertEqual([p.ticker for p in snapshot.positions], ["ZZZ", "AAA"])
        self.assertEqual(snapshot.largest_position_ticker, "ZZZ")
        self.assertEqual(snapshot.largest_position_weight, .5)

    def test_missing_and_none_price_disable_all_aggregate_weights(self):
        for prices in ({"AAA": 15}, {"AAA": 15, "BBB": None}):
            with self.subTest(prices=prices):
                snapshot = build_portfolio_snapshot(PortfolioInput([
                    PortfolioPositionInput("AAA", 2, 10), PortfolioPositionInput("BBB", 1, 20)
                ], 100), prices)
                self.assertEqual(snapshot.positions[0].position_value, 30)
                self.assertEqual(snapshot.positions[0].unrealized_gain_loss, 10)
                missing = snapshot.positions[1]
                self.assertEqual(missing.cost_basis, 20)
                for field in ('current_price', 'position_value', 'unrealized_gain_loss',
                              'unrealized_gain_loss_percent'):
                    self.assertIsNone(getattr(missing, field))
                for field in ('total_positions_value', 'total_portfolio_value', 'cash_weight',
                              'largest_position_ticker', 'largest_position_weight'):
                    self.assertIsNone(getattr(snapshot, field))
                self.assertTrue(all(p.portfolio_weight is None for p in snapshot.positions))

    def test_invalid_prices_rejected(self):
        portfolio = PortfolioInput([PortfolioPositionInput("AAA", 1, 10)], 0)
        for price in (-1, float('nan'), float('inf'), True, '10'):
            with self.subTest(price=price), self.assertRaises(ValueError):
                build_portfolio_snapshot(portfolio, {"AAA": price})

    def test_zero_price(self):
        snapshot = build_portfolio_snapshot(
            PortfolioInput([PortfolioPositionInput("AAA", 2, 10)], 10), {"AAA": 0})
        self.assertEqual(snapshot.positions[0],
                         PortfolioPosition("AAA", 2, 10, 0, 20, 0, -20, -1, 0))
        self.assertEqual(snapshot.total_positions_value, 0)
        self.assertEqual(snapshot.cash_weight, 1)

    def test_zero_total_with_positions(self):
        snapshot = build_portfolio_snapshot(
            PortfolioInput([PortfolioPositionInput("AAA", 1, 10)], 0), {"AAA": 0})
        self.assertEqual(snapshot.total_portfolio_value, 0)
        self.assertIsNone(snapshot.cash_weight)
        self.assertIsNone(snapshot.positions[0].portfolio_weight)
        self.assertIsNone(snapshot.largest_position_ticker)
        self.assertIsNone(snapshot.largest_position_weight)

    def test_empty_positive_cash(self):
        self.assertEqual(build_portfolio_snapshot(PortfolioInput([], 100), {}),
                         PortfolioSnapshot([], 100, 0, 100, 1, None, None, 0, 0, None, 0))

    def test_empty_zero_cash(self):
        self.assertEqual(build_portfolio_snapshot(PortfolioInput([], 0), {}),
                         PortfolioSnapshot([], 0, 0, 0, None, None, None, 0, 0, None, 0))

    def test_inputs_unchanged(self):
        portfolio = PortfolioInput([PortfolioPositionInput(" aaa ", 2, 10)], 5)
        prices = {"AAA": 15, "OTHER": None}
        originals = copy.deepcopy((portfolio, prices))
        snapshot = build_portfolio_snapshot(portfolio, prices)
        self.assertEqual((portfolio, prices), originals)
        self.assertIsNot(snapshot.positions, portfolio.positions)
        self.assertIsNot(snapshot.positions[0], portfolio.positions[0])
        snapshot.positions[0].shares = 999
        self.assertEqual((portfolio, prices), originals)


class PortfolioRetrievalTests(unittest.TestCase):
    def setUp(self):
        blocker = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden'))
        blocker.start()
        self.addCleanup(blocker.stop)
        self.portfolio = PortfolioInput([
            PortfolioPositionInput('ZZZ', 2, 10), PortfolioPositionInput('AAA', 1, 20)
        ], 10)

    def test_single_quote(self):
        portfolio = PortfolioInput(self.portfolio.positions[:1], 0)
        with patch.object(portfolio_data.api, 'get_global_quote',
                          return_value={'Global Quote': {'05. price': '12.50'}}) as quote:
            self.assertEqual(portfolio_data.get_portfolio_prices(portfolio), {'ZZZ': 12.5})
            quote.assert_called_once_with('ZZZ')

    def test_multiple_quotes_in_order_once_each(self):
        with patch.object(portfolio_data.api, 'get_global_quote', side_effect=[
            {'Global Quote': {'05. price': '15'}}, {'Global Quote': {'05. price': '20'}}
        ]) as quote:
            prices = portfolio_data.get_portfolio_prices(self.portfolio)
            self.assertEqual(prices, {'ZZZ': 15, 'AAA': 20})
            self.assertEqual(list(prices), ['ZZZ', 'AAA'])
            self.assertEqual(quote.call_args_list, [call('ZZZ'), call('AAA')])

    def test_one_failure_continues_without_retry(self):
        with patch.object(portfolio_data.api, 'get_global_quote', side_effect=[
            RuntimeError('Alpha Vantage Information: Fixture limit'),
            {'Global Quote': {'05. price': '20'}}
        ]) as quote, self.assertLogs(portfolio_data.__name__, level='WARNING') as logs:
            self.assertEqual(portfolio_data.get_portfolio_prices(self.portfolio),
                             {'ZZZ': None, 'AAA': 20})
            self.assertEqual(quote.call_args_list, [call('ZZZ'), call('AAA')])
        self.assertIn('Alpha Vantage Information: Fixture limit', logs.output[0])

    def test_all_failures(self):
        with patch.object(portfolio_data.api, 'get_global_quote',
                          side_effect=RuntimeError('Fixture unavailable')) as quote, \
             self.assertLogs(portfolio_data.__name__, level='WARNING'):
            self.assertEqual(portfolio_data.get_portfolio_prices(self.portfolio),
                             {'ZZZ': None, 'AAA': None})
            self.assertEqual(quote.call_args_list, [call('ZZZ'), call('AAA')])

    def test_empty_no_requests(self):
        with patch.object(portfolio_data.api, 'get_global_quote') as quote:
            self.assertEqual(portfolio_data.get_portfolio_prices(PortfolioInput([], 10)), {})
            quote.assert_not_called()

    def test_unusable_prices_and_zero(self):
        for value, expected in [(None, None), ('invalid', None), ('NaN', None),
                                ('Infinity', None), ('-1', None), ('0', 0)]:
            with self.subTest(value=value), patch.object(
                portfolio_data.api, 'get_global_quote', side_effect=[
                    {'Global Quote': {'05. price': value}}, {}
                ]
            ) as quote:
                self.assertEqual(portfolio_data.get_portfolio_prices(self.portfolio),
                                 {'ZZZ': expected, 'AAA': None})
                self.assertEqual(quote.call_count, 2)

    def test_snapshot_delegates_to_existing_calculator(self):
        with patch.object(portfolio_data.api, 'get_global_quote', side_effect=[
            {'Global Quote': {'05. price': '15'}}, {'Global Quote': {'05. price': '20'}}
        ]) as quote, patch.object(portfolio_data, 'build_portfolio_snapshot',
                                 wraps=build_portfolio_snapshot) as calculator:
            snapshot = portfolio_data.build_live_portfolio_snapshot(self.portfolio)
            calculator.assert_called_once_with(self.portfolio, {'ZZZ': 15, 'AAA': 20})
            self.assertEqual(snapshot.total_portfolio_value, 60)
            self.assertEqual(snapshot.positions[0].portfolio_weight, .5)
            self.assertEqual(quote.call_count, 2)

    def test_missing_price_integration(self):
        with patch.object(portfolio_data.api, 'get_global_quote', side_effect=[
            {}, {'Global Quote': {'05. price': '20'}}
        ]) as quote:
            snapshot = portfolio_data.build_live_portfolio_snapshot(self.portfolio)
            self.assertIsNone(snapshot.total_positions_value)
            self.assertIsNone(snapshot.total_portfolio_value)
            self.assertIsNone(snapshot.cash_weight)
            self.assertIsNone(snapshot.largest_position_ticker)
            self.assertTrue(all(p.portfolio_weight is None for p in snapshot.positions))
            self.assertEqual(snapshot.positions[1].position_value, 20)
            self.assertEqual(quote.call_count, 2)


class ConcentrationTests(unittest.TestCase):
    def snapshot(self, values, cash=0):
        portfolio = PortfolioInput([
            PortfolioPositionInput(str(i), 1, 1) for i in range(len(values))
        ], cash)
        return build_portfolio_snapshot(portfolio, dict(zip(
            [p.ticker for p in portfolio.positions], values)))

    def test_single_fully_invested(self):
        s = self.snapshot([100])
        self.assertEqual((s.position_count, s.top_3_weight, s.herfindahl_index,
                          s.effective_position_count), (1, 1, 1, 1))

    def test_two_equal(self):
        s = self.snapshot([100, 100])
        self.assertEqual((s.position_count, s.top_3_weight, s.herfindahl_index,
                          s.effective_position_count), (2, 1, .5, 2))

    def test_exactly_three(self):
        s = self.snapshot([20, 30, 50])
        self.assertEqual(s.position_count, 3)
        self.assertAlmostEqual(s.top_3_weight, 1)
        self.assertAlmostEqual(s.herfindahl_index, .38)
        self.assertAlmostEqual(s.effective_position_count, 1 / .38)

    def test_top_three_not_input_order(self):
        s = self.snapshot([10, 40, 20, 30])
        self.assertAlmostEqual(s.top_3_weight, .9)
        self.assertEqual(s.position_count, 4)
        self.assertEqual([p.ticker for p in s.positions], ['0', '1', '2', '3'])
        self.assertEqual(s.largest_position_ticker, '1')
        self.assertEqual(s.largest_position_weight, .4)

    def test_cash_excluded_from_hhi(self):
        s = self.snapshot([100, 100], cash=800)
        self.assertAlmostEqual(s.top_3_weight, .2)
        self.assertAlmostEqual(s.herfindahl_index, .02)
        self.assertAlmostEqual(s.effective_position_count, 50)
        self.assertLess(s.herfindahl_index, self.snapshot([100, 100]).herfindahl_index)

    def test_empty(self):
        for cash in (0, 100):
            with self.subTest(cash=cash):
                s = self.snapshot([], cash)
                self.assertEqual((s.position_count, s.top_3_weight, s.herfindahl_index),
                                 (0, 0, 0))
                self.assertIsNone(s.effective_position_count)
                self.assertIsNone(s.largest_position_ticker)
                self.assertIsNone(s.largest_position_weight)

    def test_missing_prices(self):
        portfolio = PortfolioInput([PortfolioPositionInput('AAA', 1, 1)], 100)
        for prices in ({}, {'AAA': None}):
            with self.subTest(prices=prices):
                s = build_portfolio_snapshot(portfolio, prices)
                self.assertEqual(s.position_count, 1)
                self.assertIsNone(s.top_3_weight)
                self.assertIsNone(s.herfindahl_index)
                self.assertIsNone(s.effective_position_count)

    def test_zero_weight_and_undefined_weight(self):
        s = self.snapshot([0], cash=100)
        self.assertEqual(s.herfindahl_index, 0)
        self.assertEqual(s.top_3_weight, 0)
        self.assertIsNone(s.effective_position_count)
        s = self.snapshot([0])
        self.assertIsNone(s.top_3_weight)
        self.assertIsNone(s.herfindahl_index)
        self.assertIsNone(s.effective_position_count)

    def test_immutability_and_tie_preserved(self):
        portfolio = PortfolioInput([PortfolioPositionInput('ZZZ', 1, 1),
                                    PortfolioPositionInput('AAA', 1, 1)], 0)
        prices = {'ZZZ': 10, 'AAA': 10}
        before = copy.deepcopy((portfolio, prices))
        s = build_portfolio_snapshot(portfolio, prices)
        self.assertEqual((portfolio, prices), before)
        self.assertEqual([p.ticker for p in s.positions], ['ZZZ', 'AAA'])
        self.assertEqual([p.position_value for p in s.positions], [10, 10])
        self.assertEqual(s.largest_position_ticker, 'ZZZ')


class PortfolioPolicyTests(unittest.TestCase):
    def snapshot(self, values, cash=0):
        return build_portfolio_snapshot(PortfolioInput([
            PortfolioPositionInput(ticker, 1, 1) for ticker in values
        ], cash), values)

    def test_defaults(self):
        self.assertEqual(PortfolioRiskPolicy(), PortfolioRiskPolicy(.25, .60, .05))

    def test_invalid_thresholds(self):
        for name in ('max_single_position_weight', 'max_top_3_weight', 'minimum_cash_weight'):
            for value in (-.1, 1.1, float('nan'), float('inf'), True):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    PortfolioRiskPolicy(**{name: value})
        PortfolioRiskPolicy(0, 1, 0)

    def test_single_oversized(self):
        result = assess_portfolio_risk(self.snapshot({'AAA': 80}, 20))
        self.assertEqual(result.oversized_positions, ['AAA'])
        self.assertTrue(result.largest_position_over_limit)
        self.assertIn('AAA exceeds max single-position weight.', result.notes)

    def test_multiple_preserve_order(self):
        result = assess_portfolio_risk(self.snapshot({'ZZZ': 40, 'AAA': 50}, 10))
        self.assertEqual(result.oversized_positions, ['ZZZ', 'AAA'])

    def test_exact_single_boundary(self):
        result = assess_portfolio_risk(self.snapshot({'AAA': 25}, 75))
        self.assertEqual(result.oversized_positions, [])
        self.assertFalse(result.largest_position_over_limit)

    def test_top_three_over_and_boundary(self):
        self.assertTrue(assess_portfolio_risk(self.snapshot({'AAA': 61}, 39)).top_3_concentration_over_limit)
        self.assertFalse(assess_portfolio_risk(self.snapshot({'AAA': 60}, 40)).top_3_concentration_over_limit)

    def test_cash_below_and_boundary(self):
        self.assertTrue(assess_portfolio_risk(self.snapshot({'AAA': 96}, 4)).minimum_cash_below_target)
        self.assertFalse(assess_portfolio_risk(self.snapshot({'AAA': 95}, 5)).minimum_cash_below_target)

    def test_compliant(self):
        result = assess_portfolio_risk(self.snapshot({'AAA': 10, 'BBB': 20}, 70))
        self.assertTrue(result.concentration_policy_evaluable)
        self.assertEqual(result.notes, [])
        self.assertFalse(result.largest_position_over_limit)
        self.assertFalse(result.top_3_concentration_over_limit)
        self.assertFalse(result.minimum_cash_below_target)

    def test_missing_price(self):
        result = assess_portfolio_risk(self.snapshot({'AAA': 10, 'BBB': None}, 70))
        self.assertFalse(result.concentration_policy_evaluable)
        self.assertEqual(result.oversized_positions, [])
        self.assertIsNone(result.largest_position_over_limit)
        self.assertIsNone(result.top_3_concentration_over_limit)
        self.assertIsNone(result.minimum_cash_below_target)
        self.assertIn('prices are missing', result.notes[0])

    def test_empty_cash_only(self):
        result = assess_portfolio_risk(self.snapshot({}, 100))
        self.assertTrue(result.concentration_policy_evaluable)
        self.assertFalse(result.largest_position_over_limit)
        self.assertFalse(result.top_3_concentration_over_limit)
        self.assertFalse(result.minimum_cash_below_target)
        self.assertEqual(result.oversized_positions, [])
        self.assertEqual(result.notes, [])

    def test_zero_total_undefined(self):
        result = assess_portfolio_risk(self.snapshot({}))
        self.assertFalse(result.concentration_policy_evaluable)
        self.assertIsNone(result.minimum_cash_below_target)
        self.assertIn('undefined', result.notes[0])

    def test_custom_policy_and_immutability(self):
        snapshot = self.snapshot({'AAA': 40}, 60)
        policy = PortfolioRiskPolicy(.5, .3, .7)
        before = copy.deepcopy((snapshot, policy))
        result = assess_portfolio_risk(snapshot, policy)
        self.assertFalse(result.largest_position_over_limit)
        self.assertTrue(result.top_3_concentration_over_limit)
        self.assertTrue(result.minimum_cash_below_target)
        self.assertEqual((snapshot, policy), before)


class PortfolioAnalysisTests(unittest.TestCase):
    def setUp(self):
        from src.portfolio_context import build_portfolio_analysis_context
        from test_v01 import evidence, payload
        self.data = evidence()
        self.payload = payload(self.data)
        self.payload['portfolio_assessment'] = 'Fixture portfolio interpretation.'
        self.snapshot = build_portfolio_snapshot(PortfolioInput([
            PortfolioPositionInput('TEST', 2, 10)], 10), {'TEST': 20})
        self.risk = assess_portfolio_risk(self.snapshot)
        self.builder = build_portfolio_analysis_context
        self.context = self.builder(self.snapshot, self.risk, ' test ')
        blocker = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def test_owned_context_and_provenance(self):
        c = self.context
        self.assertTrue(c.owns_target)
        self.assertEqual((c.target_ticker, c.target_shares, c.target_average_cost), ('TEST', 2, 10))
        self.assertEqual((c.target_current_price, c.target_position_value,
                          c.target_unrealized_gain_loss, c.target_unrealized_gain_loss_percent),
                         (20, 40, 20, 1))
        self.assertEqual(c.target_portfolio_weight, .8)
        for name in ('cash_weight', 'largest_position_ticker', 'largest_position_weight',
                     'top_3_weight', 'herfindahl_index', 'effective_position_count'):
            self.assertEqual(getattr(c, name), getattr(self.snapshot, name))
        self.assertEqual(c.portfolio_risk_assessment, self.risk)

    def test_not_owned(self):
        c = self.builder(self.snapshot, self.risk, 'OTHER')
        self.assertFalse(c.owns_target)
        self.assertEqual(c.target_shares, 0)
        self.assertIsNone(c.target_average_cost)
        self.assertIsNone(c.target_current_price)
        self.assertEqual(c.target_position_value, 0)
        self.assertEqual(c.target_portfolio_weight, 0)

    def test_missing_valuation(self):
        s = build_portfolio_snapshot(PortfolioInput([PortfolioPositionInput('TEST', 1, 10)], 0), {})
        for ticker in ('TEST', 'OTHER'):
            c = self.builder(s, assess_portfolio_risk(s), ticker)
            self.assertIsNone(c.target_portfolio_weight)
            self.assertFalse(c.portfolio_risk_assessment.concentration_policy_evaluable)

    def test_no_mutation_or_alias(self):
        before = copy.deepcopy((self.snapshot, self.risk))
        c = self.builder(self.snapshot, self.risk, 'TEST')
        c.portfolio_risk_assessment.notes.append('Local change')
        self.assertEqual((self.snapshot, self.risk), before)

    def test_zero_shares_not_owned(self):
        s = build_portfolio_snapshot(PortfolioInput([PortfolioPositionInput('TEST', 0, 10)], 100), {'TEST': 20})
        self.assertFalse(self.builder(s, assess_portfolio_risk(s), 'TEST').owns_target)

    def test_request_and_parsing(self):
        import json
        from src import analysis
        from dataclasses import asdict
        with patch.object(analysis, 'request_text', return_value=json.dumps(self.payload)) as request:
            result = analysis.analyze_investment(self.data, self.context)
        request.assert_called_once()
        sent = json.loads(request.call_args.kwargs['input'])
        self.assertEqual(sent['PORTFOLIO_CONTEXT'], asdict(self.context))
        self.assertEqual(sent['evidence_package'], self.data)
        self.assertEqual(result.portfolio_assessment, self.payload['portfolio_assessment'])
        self.assertEqual(result.missing_data, self.data['missing_data'])
        schema = request.call_args.kwargs['text']['format']['schema']
        self.assertIn('portfolio_assessment', schema['required'])
        self.assertIn('Avoid sunk-cost reasoning', request.call_args.kwargs['instructions'])

    def test_required_assessment(self):
        from src import analysis
        for value in (None, '', ' '):
            bad = copy.deepcopy(self.payload)
            bad['portfolio_assessment'] = value
            with self.assertRaises(ValueError):
                analysis._validate_analysis(bad, self.data, self.context)
        bad = copy.deepcopy(self.payload)
        del bad['portfolio_assessment']
        with self.assertRaises(ValueError):
            analysis._validate_analysis(bad, self.data, self.context)

    def test_existing_strict_validation_with_context(self):
        from src import analysis
        for recommendation in ('Buy', 'Accumulate', 'Hold', 'Trim', 'Avoid'):
            for confidence in (0, 100):
                good = copy.deepcopy(self.payload)
                good.update(recommendation=recommendation, confidence_score=confidence)
                analysis._validate_analysis(good, self.data, self.context)
        for field, value in [('recommendation', 'Sell'), ('confidence_score', -1),
                             ('confidence_score', 101), ('material_evidence_review', {})]:
            bad = copy.deepcopy(self.payload)
            bad[field] = value
            with self.assertRaises(ValueError):
                analysis._validate_analysis(bad, self.data, self.context)
        for ref in ('E999', 'retrieved_facts.stock.pe_ratio'):
            bad = copy.deepcopy(self.payload)
            bad['bull_case'][0]['evidence_refs'] = [ref]
            with self.assertRaises(ValueError):
                analysis._validate_analysis(bad, self.data, self.context)

    def test_no_context_unchanged(self):
        import json
        from src import analysis
        from test_v01 import payload
        with patch.object(analysis, 'request_text', return_value=json.dumps(payload(self.data))) as request:
            result = analysis.analyze_investment(self.data)
        self.assertEqual(result.portfolio_assessment, 'Portfolio context not supplied.')
        self.assertNotIn('PORTFOLIO_CONTEXT', json.loads(request.call_args.kwargs['input']))
        self.assertEqual(request.call_args.kwargs['instructions'], analysis.INSTRUCTIONS)
        self.assertNotIn('portfolio_assessment', request.call_args.kwargs['text']['format']['schema']['required'])

    def test_missing_context_limitation_preserved(self):
        from src import analysis
        self.context.portfolio_risk_assessment.concentration_policy_evaluable = False
        result = analysis._validate_analysis(self.payload, self.data, self.context)
        self.assertTrue(any('Portfolio concentration policy unavailable' in item for item in result.missing_data))
        self.assertTrue(all(item in result.missing_data for item in self.data['missing_data']))

    def test_mismatched_ticker_no_request(self):
        from src import analysis
        self.context.target_ticker = 'OTHER'
        with patch.object(analysis, 'request_text') as request, self.assertRaises(ValueError):
            analysis.analyze_investment(self.data, self.context)
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
