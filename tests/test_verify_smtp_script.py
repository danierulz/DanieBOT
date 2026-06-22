import os
import sys
import unittest
from io import StringIO
from unittest.mock import patch

# Asegurar import del script desde la raíz del repo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class VerifySmtpScriptTest(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "ADMIN_NOTIFY_EMAIL": "",
            "SMTP_HOST": "",
            "SMTP_USER": "",
            "SMTP_PASSWORD": "",
        },
        clear=False,
    )
    @patch("services.email_notify.is_admin_notify_email_enabled", return_value=True)
    def test_incomplete_config_exits_nonzero(self, _enabled):
        import importlib
        import config
        import services.email_notify as email_notify

        importlib.reload(config)
        importlib.reload(email_notify)

        import scripts.verify_smtp as verify_smtp

        importlib.reload(verify_smtp)
        with patch.object(verify_smtp.sys, "argv", ["verify_smtp.py"]):
            code = verify_smtp.main()
        self.assertEqual(code, 1)

    @patch("scripts.verify_smtp.send_admin_email", return_value=True)
    @patch("scripts.verify_smtp.is_email_notify_configured", return_value=True)
    @patch("scripts.verify_smtp.get_admin_notify_email", return_value="admin@test.com")
    def test_send_test_success(self, _recipient, _configured, mock_send):
        import scripts.verify_smtp as verify_smtp

        with patch.object(verify_smtp.sys, "argv", ["verify_smtp.py", "--send-test"]):
            code = verify_smtp.main()
        self.assertEqual(code, 0)
        mock_send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
