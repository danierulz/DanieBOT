import os
import smtplib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("SITE_BRAND_NAME", "Outfit Jazmines Test")

from services.advisor_notify import notify_advisor_new_web_order, notify_advisor_order_received
from services.email_notify import is_email_notify_configured, send_admin_email


class EmailNotifyConfiguredTest(unittest.TestCase):
    @patch("services.email_notify.is_admin_notify_email_enabled", return_value=False)
    def test_disabled_when_flag_off(self, _enabled):
        self.assertFalse(is_email_notify_configured())

    @patch("services.email_notify.is_admin_notify_email_enabled", return_value=True)
    @patch("services.email_notify.get_admin_notify_email", return_value="")
    @patch("services.email_notify.get_smtp_host", return_value="smtp.test")
    @patch("services.email_notify.get_smtp_user", return_value="user@test")
    @patch("services.email_notify.get_smtp_password", return_value="secret")
    def test_disabled_when_recipient_missing(self, *_mocks):
        self.assertFalse(is_email_notify_configured())

    @patch("services.email_notify.is_admin_notify_email_enabled", return_value=True)
    @patch("services.email_notify.get_admin_notify_email", return_value="admin@test.com")
    @patch("services.email_notify.get_smtp_host", return_value="smtp.test")
    @patch("services.email_notify.get_smtp_user", return_value="user@test")
    @patch("services.email_notify.get_smtp_password", return_value="secret")
    def test_enabled_when_fully_configured(self, *_mocks):
        self.assertTrue(is_email_notify_configured())


class SendAdminEmailTest(unittest.TestCase):
    @patch("services.email_notify.is_email_notify_configured", return_value=False)
    @patch("services.email_notify.smtplib.SMTP")
    def test_skips_smtp_when_not_configured(self, mock_smtp, _configured):
        self.assertFalse(send_admin_email("Subject", "Body"))
        mock_smtp.assert_not_called()

    @patch("services.email_notify.get_smtp_port", return_value=587)
    @patch("services.email_notify.get_smtp_from", return_value="from@test.com")
    @patch("services.email_notify.get_smtp_password", return_value="secret")
    @patch("services.email_notify.get_smtp_user", return_value="user@test")
    @patch("services.email_notify.get_smtp_host", return_value="smtp.test")
    @patch("services.email_notify.get_admin_notify_email", return_value="admin@test.com")
    @patch("services.email_notify.is_email_notify_configured", return_value=True)
    @patch("services.email_notify.smtplib.SMTP")
    def test_sends_email_with_starttls(
        self,
        mock_smtp_cls,
        _configured,
        _recipient,
        _host,
        _user,
        _password,
        _from,
        _port,
    ):
        smtp_instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = smtp_instance

        self.assertTrue(send_admin_email("Nuevo pedido OJ-123", "Detalle del pedido"))

        mock_smtp_cls.assert_called_once_with("smtp.test", 587, timeout=10)
        smtp_instance.starttls.assert_called_once()
        smtp_instance.login.assert_called_once_with("user@test", "secret")
        smtp_instance.send_message.assert_called_once()
        sent_msg = smtp_instance.send_message.call_args[0][0]
        self.assertEqual(sent_msg["Subject"], "Nuevo pedido OJ-123")
        self.assertEqual(sent_msg["To"], "admin@test.com")
        self.assertEqual(sent_msg.get_content().strip(), "Detalle del pedido")

    @patch("services.email_notify.get_smtp_port", return_value=587)
    @patch("services.email_notify.get_smtp_from", return_value="from@test.com")
    @patch("services.email_notify.get_smtp_password", return_value="secret")
    @patch("services.email_notify.get_smtp_user", return_value="user@test")
    @patch("services.email_notify.get_smtp_host", return_value="smtp.test")
    @patch("services.email_notify.get_admin_notify_email", return_value="admin@test.com")
    @patch("services.email_notify.is_email_notify_configured", return_value=True)
    @patch("services.email_notify.smtplib.SMTP")
    def test_returns_false_on_smtp_error(self, mock_smtp_cls, *_mocks):
        smtp_instance = MagicMock()
        smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
        mock_smtp_cls.return_value.__enter__.return_value = smtp_instance

        self.assertFalse(send_admin_email("Subject", "Body"))


class AdvisorNotifyEmailIntegrationTest(unittest.TestCase):
    def _sample_order(self):
        item = SimpleNamespace(title_snapshot="Jean azul", quantity=1, subtotal=50000.0)
        return SimpleNamespace(
            order_code="OJ-20260621-TEST",
            status="enviado_whatsapp",
            total=50000.0,
            items=[item],
        )

    @patch("services.advisor_notify.send_admin_email", return_value=True)
    @patch("services.advisor_notify._send_to_advisor", return_value=False)
    def test_new_web_order_sends_email(self, mock_wa, mock_email):
        order = self._sample_order()
        self.assertTrue(notify_advisor_new_web_order(order))
        mock_wa.assert_called_once()
        mock_email.assert_called_once()
        subject, body = mock_email.call_args[0]
        self.assertIn("OJ-20260621-TEST", subject)
        self.assertIn("pendiente", subject.lower())
        self.assertIn("OJ-20260621-TEST", body)
        self.assertIn("no sabemos", body.lower())
        self.assertIn("/admin-panel", body)

    @patch("services.advisor_notify.send_admin_email", return_value=True)
    @patch("services.advisor_notify._send_to_advisor", return_value=False)
    def test_order_received_sends_email(self, mock_wa, mock_email):
        order = self._sample_order()
        order.status = "recibido"
        self.assertTrue(
            notify_advisor_order_received(
                order,
                customer_name="María",
                customer_wa_id="5491112345678",
            )
        )
        mock_wa.assert_called_once()
        mock_email.assert_called_once()
        subject, body = mock_email.call_args[0]
        self.assertIn("confirmado", subject.lower())
        self.assertIn("María", body)
        self.assertIn("5491112345678", body)


if __name__ == "__main__":
    unittest.main()
