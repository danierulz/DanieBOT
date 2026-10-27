import io
import json
import os
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("JWT_SECRET_KEY", "ci-test-jwt-secret-not-for-prod")
os.environ.setdefault("ADMIN_USERNAME", "ci-admin")

import requests

from provider_importers.bulk.rate_limit import (
    RateLimitExceeded,
    RateLimitPolicy,
    call_with_rate_limit_backoff,
    is_rate_limited,
    response_is_rate_limited,
)
from provider_importers.bulk.runner import main
from provider_importers.types import ImportedProduct, ProviderImportError


def _product(**overrides) -> ImportedProduct:
    fields = dict(
        provider="sochic",
        source_url="https://sochic.com.ar/product/campera/",
        title="Campera",
        description="d",
        price=10000,
        cod_product="sochic-campera",
        original_price=None,
    )
    fields.update(overrides)
    return ImportedProduct(**fields)


def _rate_limit(message="So Chic limitó las consultas (demasiados pedidos)."):
    return ProviderImportError(message, code="rate_limit")


class BackoffScheduleTest(unittest.TestCase):
    def test_stepped_backoff_sleeps_before_each_retry_then_stops(self):
        sleeps: list[float] = []
        calls = {"n": 0}

        def operation():
            calls["n"] += 1
            raise ProviderImportError("So Chic limitó las consultas")

        policy = RateLimitPolicy(
            max_retries=3,
            initial_backoff_seconds=15,
            multiplier=2,
            max_backoff_seconds=120,
            cooldown_hint_seconds=600,
        )
        with self.assertRaises(RateLimitExceeded) as ctx:
            call_with_rate_limit_backoff(operation, policy, sleep=sleeps.append)

        self.assertEqual(calls["n"], 4)
        self.assertEqual(sleeps, [15, 30, 60])
        self.assertTrue(all(delay > 0 for delay in sleeps))
        self.assertEqual(ctx.exception.attempts, 4)
        self.assertEqual(ctx.exception.cooldown_hint_seconds, 600)
        self.assertTrue(is_rate_limited(ctx.exception))

    def test_backoff_is_capped(self):
        sleeps: list[float] = []

        def operation():
            raise _rate_limit()

        policy = RateLimitPolicy(
            max_retries=3,
            initial_backoff_seconds=40,
            multiplier=2,
            max_backoff_seconds=50,
            cooldown_hint_seconds=600,
        )
        with self.assertRaises(RateLimitExceeded):
            call_with_rate_limit_backoff(operation, policy, sleep=sleeps.append)
        self.assertEqual(sleeps, [40, 50, 50])

    def test_retry_after_lengthens_the_wait_and_cooldown_caps_it(self):
        response = requests.Response()
        response.status_code = 429
        response.headers["Retry-After"] = "40"
        http_error = requests.HTTPError("429 Client Error", response=response)
        sleeps: list[float] = []
        calls = {"n": 0}

        def operation():
            calls["n"] += 1
            if calls["n"] == 1:
                raise _rate_limit() from http_error
            return "ok"

        policy = RateLimitPolicy(
            max_retries=1,
            initial_backoff_seconds=15,
            max_backoff_seconds=120,
            cooldown_hint_seconds=600,
        )
        result = call_with_rate_limit_backoff(operation, policy, sleep=sleeps.append)
        self.assertEqual(result, "ok")
        self.assertEqual(sleeps, [40])

        huge = requests.Response()
        huge.status_code = 429
        huge.headers["Retry-After"] = "5000"
        huge_error = requests.HTTPError("429 Client Error", response=huge)
        capped: list[float] = []

        def always():
            raise _rate_limit() from huge_error

        with self.assertRaises(RateLimitExceeded):
            call_with_rate_limit_backoff(
                always,
                RateLimitPolicy(
                    max_retries=1,
                    initial_backoff_seconds=15,
                    max_backoff_seconds=120,
                    cooldown_hint_seconds=600,
                ),
                sleep=capped.append,
            )
        self.assertEqual(capped, [600])

    def test_hard_stop_does_not_sleep_or_retry(self):
        sleeps: list[float] = []
        calls = {"n": 0}

        def operation():
            calls["n"] += 1
            raise _rate_limit()

        policy = RateLimitPolicy(max_retries=5, initial_backoff_seconds=15, hard_stop=True)
        with self.assertRaises(RateLimitExceeded) as ctx:
            call_with_rate_limit_backoff(operation, policy, sleep=sleeps.append)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(sleeps, [])
        self.assertEqual(ctx.exception.attempts, 1)

    def test_zero_backoff_cannot_spin(self):
        sleeps: list[float] = []

        def operation():
            raise _rate_limit("HTTP 429")

        policy = RateLimitPolicy(max_retries=1, initial_backoff_seconds=0, max_backoff_seconds=120)
        with self.assertRaises(RateLimitExceeded):
            call_with_rate_limit_backoff(operation, policy, sleep=sleeps.append)
        self.assertEqual(len(sleeps), 1)
        self.assertGreaterEqual(sleeps[0], 1)

    def test_other_errors_propagate_without_sleep(self):
        sleeps: list[float] = []

        def operation():
            raise ProviderImportError("No se pudo detectar el precio")

        with self.assertRaises(ProviderImportError) as ctx:
            call_with_rate_limit_backoff(operation, RateLimitPolicy(), sleep=sleeps.append)
        self.assertNotIsInstance(ctx.exception, RateLimitExceeded)
        self.assertFalse(is_rate_limited(ctx.exception))
        self.assertEqual(sleeps, [])

    def test_body_marker_without_status_429(self):
        response = MagicMock(status_code=200, text="<html>limitó las consultas</html>")
        self.assertTrue(response_is_rate_limited(response))
        self.assertTrue(response_is_rate_limited(MagicMock(status_code=429, text="")))
        self.assertFalse(response_is_rate_limited(MagicMock(status_code=200, text="<html>Campera</html>")))


class RunnerRateLimitTest(unittest.TestCase):
    def _session(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        @contextmanager
        def session():
            yield db

        return session

    def test_429_persists_earlier_rows_then_aborts_the_rest(self):
        calls: list[str] = []
        persisted: list[str] = []

        def fetch(url):
            calls.append(url)
            if url.endswith("/a/"):
                return _product(source_url=url, cod_product="sochic-a")
            raise ProviderImportError("So Chic limitó las consultas (demasiados pedidos).")

        def persist(session, product, payload, uploader, **kwargs):
            persisted.append(product.cod_product)
            return {"created": True}

        sleeps: list[float] = []
        buf = io.StringIO()
        with patch("provider_importers.bulk.runner.read_known_source_urls", return_value=set()):
            with patch.dict("provider_importers.bulk.runner._FETCHERS", {"sochic": fetch}):
                with patch("provider_importers.bulk.runner.persist_imported_product", side_effect=persist):
                    with patch("provider_importers.bulk.runner.create_uploader", return_value=MagicMock()):
                        with patch("provider_importers.bulk.runner.get_db_session", self._session()):
                            with patch("provider_importers.bulk.runner.time.sleep", sleeps.append):
                                with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                                    code = main(
                                        [
                                            "--provider",
                                            "sochic",
                                            "--delay-ms",
                                            "0",
                                            "--rate-limit-retries",
                                            "2",
                                            "--rate-limit-backoff-seconds",
                                            "10",
                                            "--rate-limit-cooldown-seconds",
                                            "90",
                                            "--price-markup-percent",
                                            "0",
                                            "--url",
                                            "https://sochic.com.ar/product/a/",
                                            "--url",
                                            "https://sochic.com.ar/product/b/",
                                            "--url",
                                            "https://sochic.com.ar/product/c/",
                                        ]
                                    )
        self.assertEqual(code, 1)
        self.assertEqual(
            calls,
            [
                "https://sochic.com.ar/product/a/",
                "https://sochic.com.ar/product/b/",
                "https://sochic.com.ar/product/b/",
                "https://sochic.com.ar/product/b/",
            ],
        )
        self.assertEqual(sleeps, [10, 20])
        self.assertEqual(persisted, ["sochic-a"])
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["rate_limited"])
        self.assertEqual(payload["cooldown_hint_seconds"], 90)
        self.assertEqual(payload["stopped_during"], "product")
        self.assertEqual(payload["aborted_remaining"], 1)
        self.assertEqual(payload["rate_limit_attempts"], 3)
        self.assertEqual(payload["created"], 1)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual(payload["errors"][0]["code"], "rate_limit")
        self.assertIn("limitó las consultas", payload["errors"][0]["error"])
        self.assertTrue(payload["skip_existing"])
        self.assertEqual(payload["delay_ms"], 0)
        self.assertEqual(payload["price_markup_percent"], 0)

    def test_successful_retry_does_not_abort_the_wave(self):
        calls: list[str] = []
        state = {"b": 0}

        def fetch(url):
            calls.append(url)
            if url.endswith("/b/"):
                state["b"] += 1
                if state["b"] == 1:
                    raise _rate_limit()
            slug = url.rstrip("/").split("/")[-1]
            return _product(source_url=url, cod_product=f"sochic-{slug}")

        sleeps: list[float] = []
        buf = io.StringIO()
        with patch("provider_importers.bulk.runner.read_known_source_urls", return_value=set()):
            with patch.dict("provider_importers.bulk.runner._FETCHERS", {"sochic": fetch}):
                with patch(
                    "provider_importers.bulk.runner.persist_imported_product",
                    return_value={"created": True},
                ):
                    with patch("provider_importers.bulk.runner.create_uploader", return_value=MagicMock()):
                        with patch("provider_importers.bulk.runner.get_db_session", self._session()):
                            with patch("provider_importers.bulk.runner.time.sleep", sleeps.append):
                                with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                                    code = main(
                                        [
                                            "--provider",
                                            "sochic",
                                            "--delay-ms",
                                            "0",
                                            "--rate-limit-retries",
                                            "2",
                                            "--rate-limit-backoff-seconds",
                                            "15",
                                            "--url",
                                            "https://sochic.com.ar/product/a/",
                                            "--url",
                                            "https://sochic.com.ar/product/b/",
                                            "--url",
                                            "https://sochic.com.ar/product/c/",
                                        ]
                                    )
        self.assertEqual(code, 0)
        self.assertEqual(sleeps, [15])
        self.assertEqual(calls.count("https://sochic.com.ar/product/b/"), 2)
        self.assertIn("https://sochic.com.ar/product/c/", calls)
        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["rate_limited"])
        self.assertEqual(payload["created"], 3)
        self.assertEqual(payload["aborted_remaining"], 0)
        self.assertEqual(payload["cooldown_hint_seconds"], 0)

    def test_hard_stop_skips_the_rest_without_sleeping(self):
        calls: list[str] = []

        def fetch(url):
            calls.append(url)
            raise _rate_limit()

        sleeps: list[float] = []
        buf = io.StringIO()
        with patch("provider_importers.bulk.runner.read_known_source_urls", return_value=set()):
            with patch.dict("provider_importers.bulk.runner._FETCHERS", {"sochic": fetch}):
                with patch(
                    "provider_importers.bulk.runner.persist_imported_product",
                    side_effect=AssertionError("no persiste"),
                ):
                    with patch("provider_importers.bulk.runner.create_uploader", return_value=MagicMock()):
                        with patch("provider_importers.bulk.runner.get_db_session", self._session()):
                            with patch("provider_importers.bulk.runner.time.sleep", sleeps.append):
                                with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                                    code = main(
                                        [
                                            "--provider",
                                            "sochic",
                                            "--delay-ms",
                                            "0",
                                            "--rate-limit-retries",
                                            "5",
                                            "--rate-limit-hard-stop",
                                            "--url",
                                            "https://sochic.com.ar/product/a/",
                                            "--url",
                                            "https://sochic.com.ar/product/b/",
                                        ]
                                    )
        self.assertEqual(code, 1)
        self.assertEqual(calls, ["https://sochic.com.ar/product/a/"])
        self.assertEqual(sleeps, [])
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["rate_limited"])
        self.assertEqual(payload["aborted_remaining"], 1)
        self.assertEqual(payload["rate_limit_attempts"], 1)
        self.assertEqual(payload["created"], 0)
        self.assertEqual(payload["cooldown_hint_seconds"], 600)

    def test_ordinary_error_still_continues(self):
        calls: list[str] = []

        def fetch(url):
            calls.append(url)
            if url.endswith("/a/"):
                raise ProviderImportError("No se pudo detectar el precio")
            return _product(source_url=url, cod_product="sochic-b")

        buf = io.StringIO()
        with patch("provider_importers.bulk.runner.read_known_source_urls", return_value=set()):
            with patch.dict("provider_importers.bulk.runner._FETCHERS", {"sochic": fetch}):
                with patch(
                    "provider_importers.bulk.runner.persist_imported_product",
                    return_value={"created": True},
                ):
                    with patch("provider_importers.bulk.runner.create_uploader", return_value=MagicMock()):
                        with patch("provider_importers.bulk.runner.get_db_session", self._session()):
                            with patch("provider_importers.bulk.runner.time.sleep"):
                                with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                                    code = main(
                                        [
                                            "--provider",
                                            "sochic",
                                            "--delay-ms",
                                            "0",
                                            "--url",
                                            "https://sochic.com.ar/product/a/",
                                            "--url",
                                            "https://sochic.com.ar/product/b/",
                                        ]
                                    )
        self.assertEqual(code, 1)
        self.assertEqual(len(calls), 2)
        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["rate_limited"])
        self.assertEqual(payload["created"], 1)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual(payload["aborted_remaining"], 0)

    def test_listing_429_aborts_before_product_fetches(self):
        exc = RateLimitExceeded(
            "So Chic limitó las consultas en el listado (https://sochic.com.ar/shop/).",
            attempts=4,
            policy=RateLimitPolicy(cooldown_hint_seconds=600),
            partial_urls=[
                "https://sochic.com.ar/product/a/",
                "https://sochic.com.ar/product/b/",
            ],
            where="listing",
        )
        buf = io.StringIO()
        with patch(
            "provider_importers.bulk.runner.discover_sochic_product_urls",
            side_effect=exc,
        ):
            with patch(
                "provider_importers.bulk.runner.read_known_source_urls",
                side_effect=AssertionError("no debería leer la base"),
            ):
                with patch.dict(
                    "provider_importers.bulk.runner._FETCHERS",
                    {"sochic": MagicMock(side_effect=AssertionError("no debería fetchear"))},
                ):
                    with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                        code = main(
                            [
                                "--provider",
                                "sochic",
                                "--max-pages",
                                "2",
                                "--delay-ms",
                                "0",
                            ]
                        )
        self.assertEqual(code, 1)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["rate_limited"])
        self.assertEqual(payload["stopped_during"], "listing")
        self.assertEqual(payload["discovered"], 2)
        self.assertEqual(payload["aborted_remaining"], 2)
        self.assertEqual(payload["created"], 0)
        self.assertEqual(payload["cooldown_hint_seconds"], 600)
        self.assertEqual(payload["rate_limit_attempts"], 4)
        self.assertIn("limitó las consultas", payload["errors"][0]["error"])

    def test_delay_ms_still_runs_between_successful_fetches(self):
        sleeps: list[float] = []

        def fetch(url):
            slug = url.rstrip("/").split("/")[-1]
            return _product(source_url=url, cod_product=f"sochic-{slug}")

        with patch("provider_importers.bulk.runner.read_known_source_urls", return_value=set()):
            with patch.dict("provider_importers.bulk.runner._FETCHERS", {"sochic": fetch}):
                with patch(
                    "provider_importers.bulk.runner.persist_imported_product",
                    return_value={"created": True},
                ):
                    with patch("provider_importers.bulk.runner.create_uploader", return_value=MagicMock()):
                        with patch("provider_importers.bulk.runner.get_db_session", self._session()):
                            with patch("provider_importers.bulk.runner.time.sleep", sleeps.append):
                                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                                    code = main(
                                        [
                                            "--provider",
                                            "sochic",
                                            "--delay-ms",
                                            "2500",
                                            "--url",
                                            "https://sochic.com.ar/product/a/",
                                            "--url",
                                            "https://sochic.com.ar/product/b/",
                                        ]
                                    )
        self.assertEqual(code, 0)
        self.assertEqual(sleeps, [2.5, 2.5])

    def test_zero_backoff_flag_is_rejected(self):
        with patch(
            "provider_importers.bulk.runner.discover_sochic_product_urls",
            side_effect=AssertionError("no debería descubrir"),
        ):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main(
                        [
                            "--provider",
                            "sochic",
                            "--dry-run",
                            "--rate-limit-backoff-seconds",
                            "0",
                            "--url",
                            "https://sochic.com.ar/product/a/",
                        ]
                    )


class RateLimitDocTest(unittest.TestCase):
    def test_ops_and_manifest_docs_describe_the_stop(self):
        root = Path(__file__).resolve().parents[1]
        ops = (root / "docs/ops/scraping-cuidados.md").read_text(encoding="utf-8")
        manifest = (root / "docs/ops/meta-garments-manifest.md").read_text(encoding="utf-8")
        self.assertIn("rate_limited", ops)
        self.assertIn("cooldown_hint_seconds", ops)
        self.assertIn("--rate-limit-hard-stop", ops)
        self.assertIn("--rate-limit-retries", ops)
        self.assertIn("--delay-ms", ops)
        self.assertIn("--skip-existing", ops)
        self.assertIn("--price-markup-percent", ops)
        self.assertIn("Cloud Scheduler", ops)
        self.assertIn("ya-publicados.txt", manifest)
        self.assertIn("sochic-300", manifest)
        self.assertIn("un id por línea", manifest)


if __name__ == "__main__":
    unittest.main()
