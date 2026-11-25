import os
import sys
import unittest
from unittest.mock import MagicMock

# Stub CircuitPython-only modules so the spotprice package imports on a dev machine
for mod in (
    "board",
    "digitalio",
    "displayio",
    "vectorio",
    "bitmaptools",
    "terminalio",
    "wifi",
    "socketpool",
    "adafruit_requests",
    "adafruit_ntp",
    "adafruit_display_text",
    "adafruit_bitmap_font",
    "adafruit_miniqr",
    "rtc",
    "microcontroller",
):
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from spotprice import prices  # noqa: E402
from spotprice.display import format_price, get_price_color  # noqa: E402
from spotprice.wifi_portal import (  # noqa: E402
    html_escape,
    parse_form_data,
    toml_escape,
    update_settings,
)

# 2023-10-27 12:00:00 UTC
REF = 1698408000


def entry(start_hour, price):
    return {
        "startDate": f"2023-10-27T{start_hour:02d}:00:00.000Z",
        "endDate": f"2023-10-27T{start_hour + 1:02d}:00:00.000Z",
        "price": price,
    }


class TestParsing(unittest.TestCase):
    def test_parse_iso_timestamp_is_utc(self):
        # Must not depend on the host's timezone
        self.assertEqual(prices.parse_iso_timestamp("2023-10-27T12:00:00.000Z"), REF)
        self.assertEqual(prices.parse_iso_timestamp("1970-01-01T00:00:00Z"), 0)
        self.assertEqual(prices.parse_iso_timestamp("2024-02-29T23:59:59Z"), 1709251199)

    def test_parse_iso_timestamp_invalid(self):
        self.assertEqual(prices.parse_iso_timestamp("invalid"), 0)
        self.assertEqual(prices.parse_iso_timestamp(""), 0)

    def test_parse_prices_inclusive_end(self):
        slots = prices.parse_prices(
            [
                {
                    "startDate": "2026-11-25T12:00:00.000Z",
                    "endDate": "2026-11-25T12:14:59.999Z",
                    "price": 3.0,
                }
            ]
        )
        self.assertEqual(slots[0][1] - slots[0][0], 15 * 60)
        self.assertEqual(
            prices.find_current_price(slots, utc("2026-11-25T12:14:59Z")), 3.0
        )

    def test_parse_prices_sorts_and_drops_bad(self):
        raw = [
            entry(13, 15.0),
            entry(11, 5.0),
            {"startDate": "x", "endDate": "y", "price": 1},
        ]
        slots = prices.parse_prices(raw)
        self.assertEqual([p for _, _, p in slots], [5.0, 15.0])
        self.assertEqual(slots[0][0], REF - 3600)


class TestLookups(unittest.TestCase):
    def setUp(self):
        self.slots = prices.parse_prices(
            [entry(11, 5.0), entry(12, 10.0), entry(13, 15.0), entry(14, 20.0)]
        )

    def test_find_current_price(self):
        self.assertEqual(prices.find_current_price(self.slots, REF + 1), 10.0)
        self.assertEqual(prices.find_current_price(self.slots, REF), 10.0)
        self.assertIsNone(prices.find_current_price(self.slots, REF + 999999))

    def test_get_upcoming_prices(self):
        self.assertEqual(
            prices.get_upcoming_prices(self.slots, 2, REF + 1), [10.0, 15.0]
        )

    def test_get_prices_with_history(self):
        result, now_index, first = prices.get_prices_with_history(
            self.slots, future_slots=2, past_slots=1, now=REF + 1
        )
        self.assertEqual(result, [5.0, 10.0, 15.0])
        self.assertEqual(now_index, 1)
        self.assertEqual(first, REF - 3600)

    def test_get_prices_with_history_no_current(self):
        self.assertEqual(
            prices.get_prices_with_history(self.slots, now=REF + 999999), ([], 0, 0)
        )

    def test_future_coverage(self):
        self.assertEqual(prices.future_coverage(self.slots, REF), 3 * 3600)
        self.assertEqual(prices.future_coverage([], REF), 0)


def utc(text):
    return prices.parse_iso_timestamp(text)


class TestHttpDate(unittest.TestCase):
    def test_parse_http_date(self):
        self.assertEqual(
            prices.parse_http_date("Wed, 25 Nov 2026 19:03:00 GMT"),
            utc("2026-11-25T19:03:00Z"),
        )
        self.assertEqual(prices.parse_http_date("Thu, 01 Jan 1970 00:00:00 GMT"), 0)

    def test_parse_http_date_invalid(self):
        for bad in (
            "",
            "garbage",
            "Wed, 25 Xyz 2026 19:03:00 GMT",
            "Wed, 25 anF 2026 1:2:3 GMT",
            None,
        ):
            self.assertEqual(prices.parse_http_date(bad), 0)


class TestFetchSchedule(unittest.TestCase):
    # Winter: Finland = UTC+2. Today's data (before 14:00) ends 01:00 local.
    TODAY_END = utc("2026-11-25T23:00:00Z")
    TOMORROW_END = utc("2026-11-26T23:00:00Z")

    def plan(self, now, data_end, jitter=0):
        return prices.plan_next_fetch(utc(now), data_end, jitter=jitter)

    def test_morning_waits_for_publish(self):
        # 10:00 local -> first try 14:05 local (12:05Z) + jitter
        self.assertEqual(
            self.plan("2026-11-25T08:00:00Z", self.TODAY_END),
            utc("2026-11-25T12:05:00Z"),
        )
        self.assertEqual(
            self.plan("2026-11-25T08:00:00Z", self.TODAY_END, jitter=300),
            utc("2026-11-25T12:10:00Z"),
        )

    def test_not_published_yet_retries_fast_then_slow(self):
        self.assertEqual(
            self.plan("2026-11-25T12:10:00Z", self.TODAY_END),
            utc("2026-11-25T12:25:00Z"),
        )
        self.assertEqual(  # 16:00 local: after FAST_UNTIL 15:30
            self.plan("2026-11-25T14:00:00Z", self.TODAY_END),
            utc("2026-11-25T14:45:00Z"),
        )

    def test_gives_up_in_evening_until_data_runs_out(self):
        # 21:30 local: next slow retry would be after 22:00 -> wait for 01:00
        self.assertEqual(
            self.plan("2026-11-25T19:30:00Z", self.TODAY_END), self.TODAY_END
        )

    def test_has_tomorrow_waits_until_next_day(self):
        self.assertTrue(
            prices.has_tomorrow(self.TOMORROW_END, utc("2026-11-25T12:10:00Z"))
        )
        self.assertFalse(
            prices.has_tomorrow(self.TODAY_END, utc("2026-11-25T12:10:00Z"))
        )
        self.assertEqual(
            self.plan("2026-11-25T12:10:00Z", self.TOMORROW_END, jitter=60),
            utc("2026-11-26T12:06:00Z"),
        )

    def test_no_current_data_retries(self):
        self.assertEqual(
            self.plan("2026-11-25T23:30:00Z", self.TODAY_END),
            utc("2026-11-25T23:45:00Z"),
        )

    def test_never_sleeps_past_data_end(self):
        # 00:30 local, yesterday's retries failed: data ends at 01:00 local
        self.assertEqual(
            self.plan("2026-11-25T22:30:00Z", self.TODAY_END), self.TODAY_END
        )

    def test_summer_time(self):
        # Finland = UTC+3: 14:05 local is 11:05Z
        self.assertEqual(
            self.plan("2026-07-15T09:00:00Z", utc("2026-07-15T22:00:00Z")),
            utc("2026-07-15T11:05:00Z"),
        )

    def test_dst_switch_weekend(self):
        # Sat 2026-10-24 (EEST). Tomorrow (Sun 25th) switches to EET at 04:00.
        now = utc("2026-10-24T11:10:00Z")
        self.assertTrue(prices.has_tomorrow(utc("2026-10-25T23:00:00Z"), now))
        self.assertEqual(  # Sunday 14:05 EET = 12:05Z
            prices.plan_next_fetch(now, utc("2026-10-25T23:00:00Z")),
            utc("2026-10-25T12:05:00Z"),
        )


class TestFinnishTime(unittest.TestCase):
    def test_utc_offset(self):
        # 2023 EU summer time: 2023-03-26 01:00 UTC to 2023-10-29 01:00 UTC
        ts = prices.parse_iso_timestamp
        self.assertEqual(prices.utc_offset(ts("2023-01-15T12:00:00Z")), 7200)
        self.assertEqual(prices.utc_offset(ts("2023-07-15T12:00:00Z")), 10800)
        self.assertEqual(prices.utc_offset(ts("2023-03-26T00:59:59Z")), 7200)
        self.assertEqual(prices.utc_offset(ts("2023-03-26T01:00:00Z")), 10800)
        self.assertEqual(prices.utc_offset(ts("2023-10-29T00:59:59Z")), 10800)
        self.assertEqual(prices.utc_offset(ts("2023-10-29T01:00:00Z")), 7200)


class TestFormatPrice(unittest.TestCase):
    def test_at_most_four_digits(self):
        cases = {
            0.05: "0.05",
            -0.5: "-0.50",
            0.999: "1.0",
            9.96: "10.0",
            12.5: "12.5",
            99.94: "99.9",
            99.96: "100",
            123.4: "123",
            -3.2: "-3.2",
            -9.96: "-10",
            -25.3: "-25",
        }
        for price, text in cases.items():
            self.assertEqual(format_price(price), text, price)
            self.assertLessEqual(sum(c.isdigit() for c in text), 4)


class TestPriceColor(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(get_price_color(-1)[0], 0x0000FF)  # blue
        self.assertEqual(get_price_color(0.5)[0], 0x00FF00)  # green
        self.assertEqual(get_price_color(2.0)[0], 0x66FF66)  # light green
        self.assertEqual(get_price_color(8.0)[0], 0xFFE000)  # yellow at PRICE_HIGH
        self.assertEqual(get_price_color(13.0), (0xFF0000, 0xFFFFFF))  # red

    def test_gradient_passes_through_yellow_not_olive(self):
        for p in (5.0, 6.0, 7.0, 9.0, 10.0):
            c = get_price_color(p)[0]
            r, g = c >> 16, (c >> 8) & 0xFF
            self.assertGreaterEqual(max(r, g), 0xE0, p)  # bright, never muddy

    def test_text_contrast(self):
        self.assertEqual(get_price_color(6.0)[1], 0x000000)
        self.assertEqual(get_price_color(12.5)[1], 0xFFFFFF)


class TestPortalHelpers(unittest.TestCase):
    def test_html_escape(self):
        self.assertEqual(
            html_escape('<script>"x"&\''), "&lt;script&gt;&quot;x&quot;&amp;&#39;"
        )

    def test_toml_escape(self):
        self.assertEqual(toml_escape('pa"ss\\word'), 'pa\\"ss\\\\word')
        self.assertEqual(toml_escape("a\nb"), "a\\u000ab")

    def test_toml_escape_drops_nul(self):
        self.assertEqual(toml_escape("a\x00b"), "ab")

    def test_parse_form_data_utf8(self):
        # Browsers percent-encode UTF-8 bytes
        self.assertEqual(
            parse_form_data("ssid=K%C3%A4pyl%C3%A4&password=%E2%82%AC1"),
            {"ssid": "Käpylä", "password": "€1"},
        )
        self.assertEqual(parse_form_data("password=abc%21"), {"password": "abc!"})
        self.assertEqual(parse_form_data("password=100%"), {"password": "100%"})

    def test_update_settings_keeps_other_keys(self):
        old = (
            "# my settings\n"
            'CIRCUITPY_WEB_API_PASSWORD = "secret"\n'
            'CIRCUITPY_WIFI_SSID = "old"\n'
            'CIRCUITPY_WIFI_SSID = "dupe"\n'
            "\n"
            "[table]\n"
            "x = 1\n"
        )
        new = update_settings(
            old, {"CIRCUITPY_WIFI_SSID": 'Net"1', "CIRCUITPY_WIFI_PASSWORD": "pw"}
        )
        self.assertEqual(
            new,
            'CIRCUITPY_WIFI_PASSWORD = "pw"\n'
            "# my settings\n"
            'CIRCUITPY_WEB_API_PASSWORD = "secret"\n'
            'CIRCUITPY_WIFI_SSID = "Net\\"1"\n'
            "\n"
            "[table]\n"
            "x = 1\n",
        )

    def test_update_settings_ignores_keys_in_tables(self):
        # os.getenv() can't see keys after a [table], so add a top-level one
        self.assertEqual(
            update_settings(
                '[wifi]\nCIRCUITPY_WIFI_SSID = "old"\n', {"CIRCUITPY_WIFI_SSID": "new"}
            ),
            'CIRCUITPY_WIFI_SSID = "new"\n[wifi]\nCIRCUITPY_WIFI_SSID = "old"\n',
        )

    def test_update_settings_empty_file(self):
        self.assertEqual(
            update_settings("", {"A": "1", "B": "2"}), 'A = "1"\nB = "2"\n'
        )

    def test_parse_form_data(self):
        self.assertEqual(
            parse_form_data("ssid=My+Net%21&password=p%26w%3D1"),
            {"ssid": "My Net!", "password": "p&w=1"},
        )


if __name__ == "__main__":
    unittest.main()
