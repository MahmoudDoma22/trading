import os
import tempfile
import unittest
from unittest.mock import patch

from trading_app.signal_source_settings import load_signal_sources, save_signal_sources


class SignalSourceSettingsTests(unittest.TestCase):
    def test_settings_are_saved_and_editable_locally(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"APPDATA": directory}):
                save_signal_sources([
                    {"name": "Provider A", "url": "https://example.com/feed.json", "enabled": True},
                    {"name": "Unsafe URL", "url": "http://example.com/feed", "enabled": True},
                ])
                self.assertEqual(load_signal_sources(), [
                    {"name": "Provider A", "url": "https://example.com/feed.json", "enabled": True}
                ])

    def test_missing_settings_start_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"APPDATA": directory}):
                self.assertEqual(load_signal_sources(), [])


if __name__ == "__main__":
    unittest.main()
