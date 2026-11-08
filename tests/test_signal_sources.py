import unittest

from trading_app.signal_sources import parse_signal_payload


class SignalSourceTests(unittest.TestCase):
    def test_json_signal_is_unverified_xauusd_candidate(self):
        rows = parse_signal_payload(
            {"signals": [{"text": "XAUUSD BUY ENTRY 2350 SL 2340 TP 2370", "published": "2026-11-08"}]},
            "https://signals.example/feed.json",
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["symbol"], "XAUUSD")
        self.assertEqual(row["direction"], "long")
        self.assertEqual(row["entry"], 2350)
        self.assertEqual(row["stop"], 2340)
        self.assertEqual(row["target"], 2370)
        self.assertTrue(row["review_required"])
        self.assertIn("UNVERIFIED", row["status"])

    def test_ignores_non_gold_or_missing_direction(self):
        self.assertEqual(parse_signal_payload(["EURUSD BUY 1.08", "XAUUSD analysis only"], "feed"), [])

    def test_rss_signal(self):
        xml = """<rss><channel><item><title>XAUUSD SELL ENTRY 2400 SL 2410 TP 2380</title><pubDate>Today</pubDate></item></channel></rss>"""
        rows = parse_signal_payload(xml, "https://signals.example/feed.xml")
        self.assertEqual(rows[0]["direction"], "short")
        self.assertEqual(rows[0]["entry"], 2400)


if __name__ == "__main__":
    unittest.main()
