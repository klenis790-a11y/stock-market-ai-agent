"""Portfolio contracts only: hard-coded values, no providers or credentials."""
import unittest
from dataclasses import fields

from src.models import (
    PortfolioInput, PortfolioPositionInput, PortfolioPosition, PortfolioSnapshot,
)


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


if __name__ == "__main__":
    unittest.main()
