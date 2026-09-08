"""Portfolio contracts and calculations: hard-coded values, no providers or credentials."""
import copy
import unittest
from dataclasses import fields

from src.models import (
    PortfolioInput, PortfolioPositionInput, PortfolioPosition, PortfolioSnapshot,
)


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
        snapshot = PortfolioSnapshot([position], 16, 24, 40, .4, "TEST", .6)
        self.assertEqual(snapshot.positions, [position])
        self.assertEqual(snapshot.total_portfolio_value, 40)
        self.assertEqual(snapshot.largest_position_ticker, "TEST")
        unavailable = PortfolioSnapshot([], 0, None, None, None, None, None)
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
                         PortfolioSnapshot([], 100, 0, 100, 1, None, None))

    def test_empty_zero_cash(self):
        self.assertEqual(build_portfolio_snapshot(PortfolioInput([], 0), {}),
                         PortfolioSnapshot([], 0, 0, 0, None, None, None))

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


if __name__ == "__main__":
    unittest.main()
