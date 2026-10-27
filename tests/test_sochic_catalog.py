import unittest
from unittest.mock import MagicMock, patch

import requests

from provider_importers.bulk.delays import LISTING_PAGE_DELAY_SECONDS
from provider_importers.bulk.rate_limit import RateLimitExceeded, RateLimitPolicy
from provider_importers.sochic_catalog import (
    discover_sochic_product_urls,
    extract_product_urls_from_listing,
    normalize_sochic_product_url,
)
from provider_importers.types import ProviderImportError


CATALOG_HTML = """
<html><body>
  <a href="https://sochic.com.ar/product/campera-friza/">Campera</a>
  <a href="/product/top-morley/">Top</a>
  <a href="https://www.sochic.com.ar/product/campera-friza/?add-to-cart=9">dup</a>
  <a href="https://sochic.com.ar/product-category/camperas/">Camperas</a>
  <a href="https://sochic.com.ar/shop/">Shop</a>
  <a href="/shop/page/2/">2</a>
</body></html>
"""

PAGE_TWO = """
<html><body>
  <a href="/product/pollera-satin/">Pollera</a>
</body></html>
"""


class SochicCatalogTest(unittest.TestCase):
    def test_normalize_product_url(self):
        url = normalize_sochic_product_url(
            "https://www.sochic.com.ar/product/campera-friza/?ref=1",
            "https://sochic.com.ar/shop/",
        )
        self.assertEqual(url, "https://sochic.com.ar/product/campera-friza/")

    def test_normalize_rejects_category_and_shop(self):
        self.assertIsNone(
            normalize_sochic_product_url(
                "https://sochic.com.ar/product-category/camperas/",
                "https://sochic.com.ar/shop/",
            )
        )
        self.assertIsNone(
            normalize_sochic_product_url(
                "https://sochic.com.ar/shop/page/2/",
                "https://sochic.com.ar/shop/",
            )
        )

    def test_extract_product_urls_from_listing(self):
        urls = extract_product_urls_from_listing(CATALOG_HTML, "https://sochic.com.ar/shop/")
        self.assertEqual(
            urls,
            [
                "https://sochic.com.ar/product/campera-friza/",
                "https://sochic.com.ar/product/top-morley/",
            ],
        )

    def test_discover_paginates_then_stops(self):
        session = MagicMock()
        session.headers = {}
        page1 = MagicMock(status_code=200, text=CATALOG_HTML, url="https://sochic.com.ar/shop/")
        page1.raise_for_status = MagicMock()
        page2 = MagicMock(status_code=200, text=PAGE_TWO, url="https://sochic.com.ar/shop/page/2/")
        page2.raise_for_status = MagicMock()
        page3 = MagicMock(status_code=404, text="", url="https://sochic.com.ar/shop/page/3/")
        page3.raise_for_status.side_effect = __import__("requests").HTTPError("404")
        session.get.side_effect = [page1, page2, page3]

        with patch("provider_importers.sochic_catalog.time.sleep") as sleep:
            urls = discover_sochic_product_urls(session, max_pages=5)

        self.assertEqual(
            urls,
            [
                "https://sochic.com.ar/product/campera-friza/",
                "https://sochic.com.ar/product/top-morley/",
                "https://sochic.com.ar/product/pollera-satin/",
            ],
        )
        self.assertEqual(session.get.call_count, 3)
        sleep.assert_called()
        self.assertEqual(
            session.get.call_args_list[0].args[0],
            "https://sochic.com.ar/shop/",
        )
        self.assertEqual(
            session.get.call_args_list[1].args[0],
            "https://sochic.com.ar/shop/page/2/",
        )

    def test_category_and_max_pages(self):
        session = MagicMock()
        session.headers = {}
        page = MagicMock(status_code=200, text=CATALOG_HTML, url="https://sochic.com.ar/product-category/camperas/")
        page.raise_for_status = MagicMock()
        session.get.return_value = page

        urls = discover_sochic_product_urls(session, category_slug="Camperas", max_pages=1)
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(
            session.get.call_args.args[0],
            "https://sochic.com.ar/product-category/camperas/",
        )
        self.assertEqual(len(urls), 2)

    def test_invalid_category_slug(self):
        with self.assertRaises(ProviderImportError):
            discover_sochic_product_urls(MagicMock(), category_slug="../shop")


def _http_response(status: int, body: str, url: str) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = body
    response.url = url
    response.headers = {}
    if status >= 400 and status != 429:
        response.raise_for_status.side_effect = requests.HTTPError(f"{status}", response=response)
    else:
        response.raise_for_status = MagicMock()
    return response


class SochicListingRateLimitTest(unittest.TestCase):
    def test_429_backs_off_then_reads_the_page(self):
        session = MagicMock()
        session.headers = {}
        limited = _http_response(429, "Too Many Requests", "https://sochic.com.ar/shop/")
        ok = _http_response(200, CATALOG_HTML, "https://sochic.com.ar/shop/")
        session.get.side_effect = [limited, limited, ok]
        sleeps: list[float] = []
        policy = RateLimitPolicy(
            max_retries=2,
            initial_backoff_seconds=10,
            multiplier=2,
            max_backoff_seconds=120,
            cooldown_hint_seconds=600,
        )

        urls = discover_sochic_product_urls(
            session,
            max_pages=1,
            rate_limit_policy=policy,
            sleep=sleeps.append,
        )

        self.assertEqual(sleeps, [10, 20])
        self.assertTrue(all(delay > 0 for delay in sleeps))
        self.assertEqual(session.get.call_count, 3)
        self.assertEqual(len(urls), 2)

    def test_exhausted_listing_stops_with_partial_urls_and_no_tight_loop(self):
        session = MagicMock()
        session.headers = {}
        page1 = _http_response(200, CATALOG_HTML, "https://sochic.com.ar/shop/")
        limited = _http_response(429, "limitó las consultas", "https://sochic.com.ar/shop/page/2/")
        session.get.side_effect = [page1, limited, limited, limited]
        sleeps: list[float] = []
        policy = RateLimitPolicy(
            max_retries=1,
            initial_backoff_seconds=8,
            multiplier=2,
            max_backoff_seconds=120,
            cooldown_hint_seconds=600,
        )

        with self.assertRaises(RateLimitExceeded) as ctx:
            discover_sochic_product_urls(
                session,
                max_pages=5,
                rate_limit_policy=policy,
                sleep=sleeps.append,
            )

        self.assertEqual(session.get.call_count, 3)
        self.assertEqual(sleeps, [LISTING_PAGE_DELAY_SECONDS, 8])
        self.assertTrue(all(delay > 0 for delay in sleeps))
        self.assertEqual(ctx.exception.where, "listing")
        self.assertEqual(ctx.exception.attempts, 2)
        self.assertEqual(len(ctx.exception.partial_urls), 2)
        self.assertIn("limitó las consultas", str(ctx.exception))

    def test_rate_limit_body_without_429_hard_stops(self):
        session = MagicMock()
        session.headers = {}
        challenge = _http_response(
            200,
            "<html>So Chic limitó las consultas</html>",
            "https://sochic.com.ar/shop/",
        )
        session.get.return_value = challenge
        sleeps: list[float] = []
        policy = RateLimitPolicy(max_retries=4, hard_stop=True, initial_backoff_seconds=15)

        with self.assertRaises(RateLimitExceeded) as ctx:
            discover_sochic_product_urls(
                session,
                max_pages=3,
                rate_limit_policy=policy,
                sleep=sleeps.append,
            )

        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(sleeps, [])
        self.assertEqual(ctx.exception.attempts, 1)
        self.assertEqual(ctx.exception.partial_urls, [])


if __name__ == "__main__":
    unittest.main()
