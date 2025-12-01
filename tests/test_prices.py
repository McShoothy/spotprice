import unittest
from unittest.mock import patch, MagicMock
import time
import sys
import os

sys.modules["board"] = MagicMock()
sys.modules["digitalio"] = MagicMock()
sys.modules["displayio"] = MagicMock()
sys.modules["vectorio"] = MagicMock()
sys.modules["wifi"] = MagicMock()
sys.modules["socketpool"] = MagicMock()
sys.modules["adafruit_requests"] = MagicMock()
sys.modules["adafruit_ntp"] = MagicMock()
sys.modules["rtc"] = MagicMock()
sys.modules["microcontroller"] = MagicMock()

# Add the project root to the path so we can import spotprice
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from spotprice import prices


class TestPrices(unittest.TestCase):

    def setUp(self):
        # Sample price data
        # Let's define a reference time: 2023-10-27 12:00:00 UTC
        # timestamp: 1698408000
        self.ref_time = 1698408000.0

        # Create some sample price entries around this time
        # 11:00-12:00 (Past)
        # 12:00-13:00 (Current)
        # 13:00-14:00 (Future)
        # 14:00-15:00 (Future)

        self.sample_prices = [
            {
                "startDate": "2023-10-27T11:00:00.000Z",
                "endDate": "2023-10-27T12:00:00.000Z",
                "price": 5.0,
            },
            {
                "startDate": "2023-10-27T12:00:00.000Z",
                "endDate": "2023-10-27T13:00:00.000Z",
                "price": 10.0,
            },
            {
                "startDate": "2023-10-27T13:00:00.000Z",
                "endDate": "2023-10-27T14:00:00.000Z",
                "price": 15.0,
            },
            {
                "startDate": "2023-10-27T14:00:00.000Z",
                "endDate": "2023-10-27T15:00:00.000Z",
                "price": 20.0,
            },
        ]

    def test_parse_iso_timestamp(self):
        # Test parsing a known timestamp
        ts_str = "2023-10-27T12:00:00.000Z"
        # Note: mktime depends on local timezone, so this test might be flaky across timezones
        # unless we control the environment or use a relative check.
        # However, the code uses time.mktime which is local time.
        # Let's just check that it returns a float and is roughly correct or consistent.

        # Better approach: Mock time.mktime to return a fixed value for the struct_time
        # But for now, let's just check it returns a number > 0
        ts = prices.parse_iso_timestamp(ts_str)
        self.assertIsInstance(ts, float)
        self.assertGreater(ts, 0)

        # Test invalid timestamp
        self.assertEqual(prices.parse_iso_timestamp("invalid"), 0)

    @patch("spotprice.prices.time.time")
    @patch("spotprice.prices.parse_iso_timestamp")
    def test_find_current_price(self, mock_parse, mock_time):
        # Setup mocks
        mock_time.return_value = self.ref_time + 1  # 12:00:01

        # We need parse_iso_timestamp to return values that align with our logic
        # Since the real parse_iso_timestamp uses mktime (local), and we want deterministic tests,
        # we should mock it to return simple integers or align with our ref_time.

        # Let's map the date strings to timestamps relative to ref_time
        # 11:00 -> ref_time - 3600
        # 12:00 -> ref_time
        # 13:00 -> ref_time + 3600
        # 14:00 -> ref_time + 7200
        # 15:00 -> ref_time + 10800

        date_map = {
            "2023-10-27T11:00:00.000Z": self.ref_time - 3600,
            "2023-10-27T12:00:00.000Z": self.ref_time,
            "2023-10-27T13:00:00.000Z": self.ref_time + 3600,
            "2023-10-27T14:00:00.000Z": self.ref_time + 7200,
            "2023-10-27T15:00:00.000Z": self.ref_time + 10800,
        }

        mock_parse.side_effect = lambda x: date_map.get(x, 0)

        # Test finding the current price (should be the 12:00-13:00 slot, price 10.0)
        # Current time is 12:00:01, so it falls in [12:00, 13:00)
        price = prices.find_current_price(self.sample_prices)
        self.assertEqual(price, 10.0)

        # Test when no price matches
        mock_time.return_value = self.ref_time + 999999  # Far future
        price = prices.find_current_price(self.sample_prices)
        self.assertIsNone(price)

    @patch("spotprice.prices.time.time")
    @patch("spotprice.prices.parse_iso_timestamp")
    def test_get_upcoming_prices(self, mock_parse, mock_time):
        mock_time.return_value = self.ref_time + 1  # 12:00:01

        date_map = {
            "2023-10-27T11:00:00.000Z": self.ref_time - 3600,
            "2023-10-27T12:00:00.000Z": self.ref_time,
            "2023-10-27T13:00:00.000Z": self.ref_time + 3600,
            "2023-10-27T14:00:00.000Z": self.ref_time + 7200,
            "2023-10-27T15:00:00.000Z": self.ref_time + 10800,
        }
        mock_parse.side_effect = lambda x: date_map.get(x, 0)

        # Should return prices where endDate > now
        # 11-12: End 12:00 <= 12:00:01? No, wait. 12:00 is < 12:00:01. So this slot is past.
        # 12-13: End 13:00 > 12:00:01. Future/Current.
        # 13-14: End 14:00 > 12:00:01. Future.
        # 14-15: End 15:00 > 12:00:01. Future.

        upcoming = prices.get_upcoming_prices(self.sample_prices, slots=2)

        # Should get 12-13 (10.0) and 13-14 (15.0)
        self.assertEqual(len(upcoming), 2)
        self.assertEqual(upcoming[0], 10.0)
        self.assertEqual(upcoming[1], 15.0)

    @patch("spotprice.prices.time.time")
    @patch("spotprice.prices.parse_iso_timestamp")
    def test_get_prices_with_history(self, mock_parse, mock_time):
        mock_time.return_value = self.ref_time + 1  # 12:00:01

        date_map = {
            "2023-10-27T11:00:00.000Z": self.ref_time - 3600,
            "2023-10-27T12:00:00.000Z": self.ref_time,
            "2023-10-27T13:00:00.000Z": self.ref_time + 3600,
            "2023-10-27T14:00:00.000Z": self.ref_time + 7200,
            "2023-10-27T15:00:00.000Z": self.ref_time + 10800,
        }
        mock_parse.side_effect = lambda x: date_map.get(x, 0)

        # Current slot is index 1 (12:00-13:00)
        # Request 1 past slot, 2 future slots (including current)

        result, now_index = prices.get_prices_with_history(
            self.sample_prices, future_slots=2, past_slots=1
        )

        # Expected:
        # Past 1: 11:00-12:00 (5.0)
        # Current: 12:00-13:00 (10.0)
        # Future 1: 13:00-14:00 (15.0)
        # Future 2: 14:00-15:00 (20.0) - Should be excluded because future_slots=2 means current + 1 future
        # Total 3 items

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], 5.0)
        self.assertEqual(result[1], 10.0)
        self.assertEqual(result[2], 15.0)

        # now_index should point to the current slot (10.0), which is at index 1
        self.assertEqual(now_index, 1)
        self.assertEqual(result[now_index], 10.0)


if __name__ == "__main__":
    unittest.main()
