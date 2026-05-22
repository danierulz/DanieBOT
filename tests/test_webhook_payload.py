import json
import os
import unittest
from unittest.mock import patch

from whatsapp.webhook_payload import log_webhook_payload_summary


class WebhookPayloadLogTest(unittest.TestCase):
    def test_warns_on_phone_id_mismatch(self):
        body = json.dumps(
            {
                "entry": [
                    {
                        "changes": [
                            {
                                "field": "messages",
                                "value": {
                                    "metadata": {
                                        "phone_number_id": "723456789012345",
                                        "display_phone_number": "541134722482",
                                    },
                                    "messages": [
                                        {
                                            "from": "5491111111111",
                                            "type": "text",
                                            "text": {"body": "hola"},
                                        }
                                    ],
                                },
                            }
                        ]
                    }
                ]
            }
        ).encode()

        with patch.dict(os.environ, {"PYWA_PHONE_ID": "541134722482"}):
            with self.assertLogs("whatsapp.webhook_payload", level="WARNING") as cm:
                log_webhook_payload_summary(body)
        self.assertTrue(any("IGNORADO por PyWa" in m for m in cm.output))


if __name__ == "__main__":
    unittest.main()
