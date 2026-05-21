import os
import re
import secrets
from datetime import datetime

ORDER_CODE_PATTERN = re.compile(r"([A-Z]{2})-(\d{8})-([A-HJ-NP-Z2-9]{4})")

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def order_code_prefix() -> str:
    return os.getenv("ORDER_CODE_PREFIX", "OJ").upper()[:8]


def generate_order_code() -> str:
    prefix = order_code_prefix()
    date_part = datetime.utcnow().strftime("%Y%m%d")
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(4))
    return f"{prefix}-{date_part}-{suffix}"


def extract_order_code(text: str | None) -> str | None:
    if not text:
        return None
    match = ORDER_CODE_PATTERN.search(text.upper())
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
