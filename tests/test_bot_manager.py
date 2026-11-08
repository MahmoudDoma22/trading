import json
import tempfile
import unittest
from pathlib import Path

from trading_app.bot_manager import BotManager
from trading_app.config import BotDefinition


class BotManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "bots.json"
        self.manager = BotManager(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_default_library_persists(self):
        self.assertEqual(len(self.manager.get_bots()), 4)
        reloaded = BotManager(self.path)
        self.assertEqual([b.name for b in reloaded.get_bots()], [b.name for b in self.manager.get_bots()])

    def test_add_duplicate_toggle_and_delete(self):
        source = self.manager.get_bots()[0]
        clone = self.manager.duplicate_bot(source.name)
        self.assertNotEqual(clone.name, source.name)
        self.manager.set_enabled(clone.name, False)
        self.assertFalse(self.manager.is_enabled(clone))
        self.manager.delete_bot(clone.name)
        self.assertEqual(len(self.manager.get_bots()), 4)

    def test_risk_limit_is_capped(self):
        bot = BotDefinition("Test", "test", max_risk_usd=5, max_trade_size_lots=0.01)
        self.manager.add_bot(bot)
        self.assertEqual(self.manager.get_bots()[-1].max_risk_usd, 5)

    def test_import_rejects_risk_above_five(self):
        path = Path(self.temp.name) / "bad.json"
        path.write_text(json.dumps([{
            "name": "Unsafe", "description": "test", "default_timeframe": "M15",
            "min_confidence": 20, "max_risk_usd": 25, "max_trade_size_lots": 0.01,
            "settings": {"stop_atr_multiplier": 1.5}
        }]), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.manager.import_json(path)

    def test_non_gold_instrument_is_rejected(self):
        with self.assertRaises(ValueError):
            self.manager.evaluate("EURUSD", {}, self.manager.get_bots()[0])


if __name__ == "__main__":
    unittest.main()
