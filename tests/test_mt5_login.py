import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from trading_app.config import MqlConfig
from trading_app.mt5_client import MT5Connection


class MT5LoginTests(unittest.TestCase):
    def make_fake(self, login=123456, server="Demo-Server"):
        fake = Mock()
        fake.initialize.return_value = True
        fake.terminal_info.return_value = object()
        fake.account_info.return_value = SimpleNamespace(login=login, server=server)
        fake.symbol_info.return_value = None
        fake.symbols_get.return_value = []
        fake.shutdown.return_value = None
        return fake

    def test_explicit_login_uses_account_and_exact_server(self):
        fake = self.make_fake()
        with patch("trading_app.mt5_client.mt5", fake):
            client = MT5Connection(MqlConfig())
            self.assertTrue(client.connect(login=123456, password="runtime-only", server="Demo-Server"))
            fake.initialize.assert_called_once_with(login=123456, password="runtime-only", server="Demo-Server")
            self.assertTrue(client.connected)

    def test_wrong_account_identity_is_rejected(self):
        fake = self.make_fake(login=999999)
        with patch("trading_app.mt5_client.mt5", fake):
            client = MT5Connection(MqlConfig())
            self.assertFalse(client.connect(login=123456, password="runtime-only", server="Demo-Server"))
            fake.shutdown.assert_called()

    def test_failed_login_stays_disconnected(self):
        fake = self.make_fake()
        fake.initialize.return_value = False
        with patch("trading_app.mt5_client.mt5", fake):
            client = MT5Connection(MqlConfig())
            self.assertFalse(client.connect(login=123456, password="bad", server="Demo-Server"))
            self.assertFalse(client.connected)


if __name__ == "__main__":
    unittest.main()
