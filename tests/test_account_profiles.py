import os
import tempfile
import unittest
from unittest.mock import patch

from trading_app.account_profiles import load_profiles, save_profiles


class BrokerProfileTests(unittest.TestCase):
    def test_profiles_persist_without_password_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"APPDATA": directory}):
                save_profiles([
                    {"broker": "Example Broker", "login": "123456", "server": "Example-Demo", "password": "must-not-persist"},
                    {"broker": "Invalid", "login": "not-numeric", "server": "Server"},
                ])
                rows = load_profiles()
                self.assertEqual(rows, [{"broker": "Example Broker", "email": "", "login": "123456", "server": "Example-Demo"}])
                self.assertNotIn("password", rows[0])

    def test_profiles_default_to_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"APPDATA": directory}):
                self.assertEqual(load_profiles(), [])


if __name__ == "__main__":
    unittest.main()
