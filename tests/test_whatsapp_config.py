import unittest

from whatsapp.bot import normalize_phone_id, validate_phone_id


class PhoneIdConfigTest(unittest.TestCase):
    def test_strip_plus_and_spaces(self):
        self.assertEqual(normalize_phone_id("+54 11 3472-2482"), "541134722482")

    def test_warn_e164_like(self):
        warns = validate_phone_id("541134722482")
        self.assertTrue(any("teléfono" in w for w in warns))

    def test_numeric_id_no_e164_warning(self):
        warns = validate_phone_id("723456789012345")
        self.assertFalse(any("teléfono" in w for w in warns))


if __name__ == "__main__":
    unittest.main()
