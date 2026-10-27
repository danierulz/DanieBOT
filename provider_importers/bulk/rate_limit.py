"""Backoff and stop policy for HTTP 429 on notebook bulk imports.

The wait happens before each retry. A hard stop, or a retry budget of zero,
aborts on the first rate limit without sleeping. Nothing here schedules a
Cloud Run job or a cron.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable

from provider_importers.types import ProviderImportError

# Phrases WooCommerce / our own errors use when the host is throttling.
_BODY_MARKERS = (
    "limitó las consultas",
    "limito las consultas",
    "too many request",
    "rate limit",
)
_HTTP_429_RE = re.compile(r"\b429\b")


@dataclass(frozen=True)
class RateLimitPolicy:
    """``max_retries`` counts extra attempts after the first 429.

    ``hard_stop`` aborts on the first rate limit and ignores ``max_retries``.
    Backoff is stepped: ``initial``, then ``initial * multiplier``, capped.
    """

    max_retries: int = 3
    initial_backoff_seconds: float = 15.0
    multiplier: float = 2.0
    max_backoff_seconds: float = 120.0
    cooldown_hint_seconds: int = 600
    hard_stop: bool = False

    def backoff_seconds(self, retry_index: int, *, retry_after: float | None = None) -> float:
        """Seconds to wait before retry number ``retry_index`` (1-based).

        The result is always greater than zero so a misconfigured 0 cannot
        spin. ``Retry-After`` lengthens the wait when the server asks for
        more, and never past ``max(max_backoff, cooldown hint)``.
        """
        index = max(int(retry_index), 1)
        base = self.initial_backoff_seconds if self.initial_backoff_seconds > 0 else 1.0
        factor = self.multiplier ** (index - 1) if self.multiplier > 0 else 1.0
        delay = base * factor
        cap = self.max_backoff_seconds if self.max_backoff_seconds > 0 else delay
        delay = min(delay, cap)
        if retry_after is not None and retry_after > delay:
            ceiling = max(cap, float(self.cooldown_hint_seconds))
            if ceiling <= 0:
                ceiling = retry_after
            delay = min(retry_after, ceiling)
        if delay <= 0:
            delay = 1.0
        return delay


DEFAULT_RATE_LIMIT_POLICY = RateLimitPolicy()


class RateLimitExceeded(ProviderImportError):
    """Retries are exhausted (or the policy is a hard stop)."""

    def __init__(
        self,
        message: str,
        *,
        attempts: int,
        policy: RateLimitPolicy | None = None,
        partial_urls: list[str] | None = None,
        where: str = "",
    ):
        super().__init__(message, code="rate_limit")
        self.attempts = attempts
        self.policy = policy or DEFAULT_RATE_LIMIT_POLICY
        self.partial_urls = list(partial_urls or [])
        self.where = where
        self.cooldown_hint_seconds = int(self.policy.cooldown_hint_seconds)


def policy_from_options(options) -> RateLimitPolicy:
    return RateLimitPolicy(
        max_retries=int(options.rate_limit_retries),
        initial_backoff_seconds=float(options.rate_limit_backoff_seconds),
        max_backoff_seconds=float(options.rate_limit_max_backoff_seconds),
        cooldown_hint_seconds=int(options.rate_limit_cooldown_seconds),
        hard_stop=bool(options.rate_limit_hard_stop),
    )


def _response_text(response) -> str:
    try:
        raw = response.text
    except Exception:
        return ""
    if not isinstance(raw, str):
        return ""
    return raw[:2000].lower()


def response_is_rate_limited(response) -> bool:
    """True for HTTP 429 or a body that says the host limited queries."""
    if response is None:
        return False
    if getattr(response, "status_code", None) == 429:
        return True
    body = _response_text(response)
    return any(marker in body for marker in _BODY_MARKERS)


def retry_after_seconds(exc: BaseException) -> float | None:
    """``Retry-After`` in seconds, walking ``__cause__`` for wrapped HTTP errors."""
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        response = getattr(current, "response", None)
        headers = getattr(response, "headers", None) if response is not None else None
        raw = None
        if headers is not None:
            getter = getattr(headers, "get", None)
            if callable(getter):
                raw = getter("Retry-After")
                if raw is None:
                    raw = getter("retry-after")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            value = float(raw)
            if value > 0:
                return value
        if isinstance(raw, str):
            try:
                value = float(raw.strip())
            except ValueError:
                value = -1
            if value > 0:
                return value
        current = current.__cause__ or current.__context__
    return None


def is_rate_limited(exc: BaseException) -> bool:
    if isinstance(exc, ProviderImportError) and getattr(exc, "code", "") == "rate_limit":
        return True
    if response_is_rate_limited(getattr(exc, "response", None)):
        return True
    text = str(exc).lower()
    if _HTTP_429_RE.search(text):
        return True
    return any(marker in text for marker in _BODY_MARKERS)


def call_with_rate_limit_backoff(
    operation: Callable[[], object],
    policy: RateLimitPolicy,
    *,
    sleep: Callable[[float], None] = time.sleep,
):
    """Call ``operation``. On a rate limit, sleep, then retry.

    Sleep runs before every retry and is never zero. When the budget is
    spent, or ``policy.hard_stop`` is set, raise ``RateLimitExceeded``
    without a trailing sleep.
    """
    if policy.max_retries < 0:
        raise ValueError("max_retries no puede ser negativo")
    allowed_retries = 0 if policy.hard_stop else policy.max_retries
    failures = 0
    while True:
        try:
            return operation()
        except Exception as exc:
            if not is_rate_limited(exc):
                raise
            if failures >= allowed_retries:
                raise RateLimitExceeded(
                    str(exc) or "El sitio limitó las consultas.",
                    attempts=failures + 1,
                    policy=policy,
                ) from exc
            failures += 1
            delay = policy.backoff_seconds(failures, retry_after=retry_after_seconds(exc))
            sleep(delay)
