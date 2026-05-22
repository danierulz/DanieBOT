import os
import unittest

os.environ.setdefault("SITE_PUBLIC_URL", "http://localhost:5000")

from whatsapp import email_flow


class EmailFlowTest(unittest.TestCase):
    def setUp(self):
        email_flow._sessions.clear()
        email_flow._timers.clear()
        email_flow._processed_callback_ids.clear()

    def test_start_only_once(self):
        self.assertTrue(email_flow.start_email_collection("wa1"))
        self.assertFalse(email_flow.start_email_collection("wa1"))

    def test_valid_email_moves_to_consent(self):
        email_flow.start_email_collection("wa1")
        result = email_flow.handle_email_text("wa1", "test@example.com")
        self.assertEqual(result, (None, True))
        self.assertTrue(email_flow.is_awaiting_consent("wa1"))

    def test_invalid_email_stays_awaiting(self):
        email_flow.start_email_collection("wa1")
        result = email_flow.handle_email_text("wa1", "not-an-email")
        self.assertIsNotNone(result)
        self.assertIn("válido", result[0])
        self.assertTrue(email_flow.is_awaiting_email("wa1"))

    def test_clear_on_decline(self):
        email_flow.start_email_collection("wa1")
        email_flow.clear_email_flow("wa1")
        self.assertFalse(email_flow.is_collecting_email("wa1"))

    def test_pop_pending_after_consent_step(self):
        email_flow.start_email_collection("wa1")
        email_flow.handle_email_text("wa1", "a@b.com")
        email = email_flow.pop_pending_email("wa1")
        self.assertEqual(email, "a@b.com")
        self.assertFalse(email_flow.is_collecting_email("wa1"))

    def test_callback_dedup(self):
        self.assertFalse(email_flow.is_callback_duplicate("msg-1"))
        self.assertTrue(email_flow.is_callback_duplicate("msg-1"))

    def test_text_outside_flow_returns_none(self):
        self.assertIsNone(email_flow.handle_email_text("wa1", "hola"))


if __name__ == "__main__":
    unittest.main()
