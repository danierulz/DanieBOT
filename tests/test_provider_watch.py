"""Local provider watch: classify new vs duplicate, no import, no cron."""

import inspect
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("JWT_SECRET_KEY", "ci-test-jwt-secret-not-for-prod")
os.environ.setdefault("ADMIN_USERNAME", "ci-admin")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.models  # noqa: F401
import main
from database.init_db import Base
from database.models.Products import Products
from database.models.ProviderImportRun import ProviderImportRun
from database.models.ProviderImportRunItem import ProviderImportRunItem
from provider_importers.bulk.brands import get_brand
from provider_importers.bulk.existing import DedupIndex, canonical_source_url, load_dedup_index, load_known_source_urls
from provider_importers.bulk.watch import (
    STATUS_DUPLICATE,
    STATUS_NEW,
    WatchRequestError,
    classify_listing_hit,
    cli_dry_run_command,
    normalize_watch_limit,
    normalize_watch_providers,
    redact_secrets,
    scan_watch,
)
import requests

from provider_importers.bulk.watch_listings import (
    USER_AGENT,
    ListingHit,
    ListingPage,
    WatchListingError,
    extract_laslocas_listing_hits,
    extract_nissie_listing_hits,
    extract_sochic_listing_hits,
    fetch_provider_listing,
    parse_ars_amount,
)
from provider_importers.nissie_catalog import NISSIE_CATALOG_URL
from provider_importers.sochic_catalog import SOCHIC_SHOP_URL


SOCHIC_LISTING = """
<ul class="products">
  <li class="product type-product">
    <a href="/product/campera-friza/">
      <h2 class="woocommerce-loop-product__title">Campera Friza</h2>
    </a>
    <span class="price">
      <del><span class="woocommerce-Price-amount amount"><bdi>$35.000</bdi></span></del>
      <ins><span class="woocommerce-Price-amount amount"><bdi>$29.000</bdi></span></ins>
    </span>
    <span class="sku" data-sku="3515">3515</span>
  </li>
  <li class="product">
    <a href="https://www.sochic.com.ar/product/top-morley/?add-to-cart=9">Top Morley</a>
    <span class="price"><span class="amount"><bdi>$18.500</bdi></span></span>
  </li>
</ul>
<a href="/shop/page/2/">2</a>
"""

NISSIE_LISTING = """
<div class="js-item-product" data-product-id="1">
  <a href="/productos/denim-blue/"><div class="js-item-name">Denim Blue</div></a>
  <span class="js-price-display">$12.000</span>
</div>
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Denim Blue",
  "productGroupID": "282540155",
  "url": "https://nissiedenim.com.ar/productos/denim-blue/",
  "offers": {"@type": "Offer", "price": "12000"}
}
</script>
<a href="/productos/?page=2">2</a>
"""

LASLOCAS_LISTING = """
<div class="item">
  <a href="/ficha-9-jean">Jean Nuevo</a>
  <span class="precio">$15.000</span>
  <span class="codProd">BSPOR</span>
</div>
"""

LASLOCAS_STOREFRONT_LISTING = """
<nav><a href="/productos/desde-el-menu/">Menu</a></nav>
<div class="js-item-product item-product" data-product-id="368135223">
  <a href="/productos/clasico-black/?variant=1">
    <div class="js-item-name">CLASICO BLACK</div>
  </a>
  <span class="js-price-display">$24.500,00</span>
</div>
<a href="/jeans/?page=2">2</a>
"""


class ParseListingTest(unittest.TestCase):
    def test_ars_amounts(self):
        self.assertEqual(parse_ars_amount("$29.000"), 29000)
        self.assertEqual(parse_ars_amount("$12.000,50"), 12001)
        self.assertEqual(parse_ars_amount("29000.50"), 29001)
        self.assertIsNone(parse_ars_amount("sin precio"))

    def test_sochic_card_keeps_sale_price_title_and_code(self):
        hits = extract_sochic_listing_hits(SOCHIC_LISTING, SOCHIC_SHOP_URL)
        self.assertEqual(
            [hit.url for hit in hits],
            [
                "https://sochic.com.ar/product/campera-friza/",
                "https://sochic.com.ar/product/top-morley/",
            ],
        )
        self.assertEqual(hits[0].title, "Campera Friza")
        self.assertEqual(hits[0].price, 29000)
        self.assertEqual(hits[0].cod_product, "sochic-3515-campera-friza")
        self.assertEqual(hits[1].title, "Top Morley")
        self.assertEqual(hits[1].price, 18500)

    def test_nissie_jsonld_code_overrides_card_id(self):
        hits = extract_nissie_listing_hits(NISSIE_LISTING, NISSIE_CATALOG_URL)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].url, "https://nissiedenim.com.ar/productos/denim-blue/")
        self.assertEqual(hits[0].title, "Denim Blue")
        self.assertEqual(hits[0].price, 12000)
        self.assertEqual(hits[0].cod_product, "nissie-282540155")

    def test_laslocas_card_title_price_and_code(self):
        hits = extract_laslocas_listing_hits(
            LASLOCAS_LISTING,
            "https://laslocas.com/productos/jean?page=1&ajax=1",
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].url, "https://laslocas.com/ficha-9-jean")
        self.assertEqual(hits[0].title, "Jean Nuevo")
        self.assertEqual(hits[0].price, 15000)
        self.assertEqual(hits[0].cod_product, "BSPOR")

    def test_laslocas_storefront_card_skips_the_menu(self):
        hits = extract_laslocas_listing_hits(
            LASLOCAS_STOREFRONT_LISTING,
            "https://laslocas.com/jeans/?page=1&ajax=1",
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].url, "https://laslocas.com/productos/clasico-black/")
        self.assertEqual(hits[0].title, "CLASICO BLACK")
        self.assertEqual(hits[0].price, 24500)


class FirstPageFetchTest(unittest.TestCase):
    def test_sochic_reads_one_shop_page_and_stops_on_429(self):
        session = MagicMock()
        session.headers = {}
        ok = MagicMock(status_code=200, text=SOCHIC_LISTING, url=SOCHIC_SHOP_URL)
        ok.raise_for_status = MagicMock()
        session.get.return_value = ok
        page = fetch_provider_listing("sochic", limit=5, laslocas_category="denim", session=session)
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(session.get.call_args[0][0], SOCHIC_SHOP_URL)
        self.assertEqual(page.discovered, 2)
        self.assertEqual(len(page.hits), 2)

        limited = MagicMock(
            status_code=429,
            text="too many requests https://sochic.com.ar/product/baggy-cargo-gabardina/",
            url="https://sochic.com.ar/product/baggy-cargo-gabardina/",
        )
        session.get.reset_mock()
        session.get.return_value = limited
        with self.assertRaises(WatchListingError) as caught:
            fetch_provider_listing("sochic", limit=5, laslocas_category="denim", session=session)
        message = str(caught.exception)
        self.assertIn("limitó", message.lower())
        self.assertIn("no se pidieron fichas", message.lower())
        self.assertEqual(session.get.call_count, 1)
        requested = session.get.call_args[0][0]
        self.assertEqual(requested, SOCHIC_SHOP_URL)
        self.assertNotIn("/product/", requested)

    def test_listing_replaces_the_python_requests_user_agent(self):
        session = requests.Session()
        self.assertIn("python-requests", session.headers["User-Agent"])
        seen = {}

        def fake_get(url, timeout=None, headers=None):
            seen["ua"] = session.headers.get("User-Agent")
            seen["accept"] = session.headers.get("Accept")
            ok = MagicMock(status_code=200, text=NISSIE_LISTING, url=url)
            ok.raise_for_status = MagicMock()
            return ok

        session.get = fake_get
        page = fetch_provider_listing("nissie", limit=5, laslocas_category="denim", session=session)
        self.assertEqual(seen["ua"], USER_AGENT)
        self.assertNotIn("python-requests", seen["ua"])
        self.assertIn("text/html", seen["accept"])
        self.assertEqual(len(page.hits), 1)

    def test_nissie_does_not_follow_page_two(self):
        session = MagicMock()
        session.headers = {}
        ok = MagicMock(status_code=200, text=NISSIE_LISTING, url=NISSIE_CATALOG_URL)
        ok.raise_for_status = MagicMock()
        session.get.return_value = ok
        page = fetch_provider_listing("nissie", limit=5, laslocas_category="denim", session=session)
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(session.get.call_args[0][0], NISSIE_CATALOG_URL)
        self.assertEqual(len(page.hits), 1)

    def test_holic_uses_new_in_listing(self):
        session = MagicMock()
        session.headers = {}
        html = '<ul class="products"><li class="product"><a href="/product/demo-new/">Demo</a></li></ul>'
        ok = MagicMock(status_code=200, text=html, url="https://holiclothing.com.ar/product-category/new-in/")
        ok.raise_for_status = MagicMock()
        session.get.return_value = ok
        page = fetch_provider_listing("holic", limit=5, laslocas_category="denim", session=session)
        self.assertEqual(session.get.call_count, 1)
        self.assertIn("/product-category/new-in", session.get.call_args[0][0])
        self.assertEqual(page.hits[0].url, "https://holiclothing.com.ar/product/demo-new/")

    def test_laslocas_ajax_first_page_does_not_login_when_session_is_given(self):
        session = MagicMock()
        session.headers = {}
        ok = MagicMock(
            status_code=200,
            text=LASLOCAS_LISTING,
            url="https://laslocas.com/nuevos-ingresos/?page=1&ajax=1",
        )
        ok.raise_for_status = MagicMock()
        session.get.return_value = ok
        with patch(
            "provider_importers.bulk.watch_listings._authenticated_session",
            side_effect=AssertionError("no debería loguear"),
        ):
            page = fetch_provider_listing(
                "laslocas",
                limit=5,
                laslocas_category="denim",
                session=session,
            )
        self.assertEqual(session.get.call_count, 1)
        self.assertIn("nuevos-ingresos", session.get.call_args[0][0])
        self.assertIn("ajax=1", session.get.call_args[0][0])
        self.assertEqual(page.hits[0].cod_product, "BSPOR")

    def test_limit_slices_the_first_cards(self):
        cards = []
        for number in range(6):
            cards.append(
                f'<li class="product"><a href="/product/item-{number}/">Item {number}</a></li>'
            )
        html = "<ul>" + "".join(cards) + "</ul>"
        session = MagicMock()
        session.headers = {}
        ok = MagicMock(status_code=200, text=html, url=SOCHIC_SHOP_URL)
        ok.raise_for_status = MagicMock()
        session.get.return_value = ok
        page = fetch_provider_listing("sochic", limit=5, laslocas_category="denim", session=session)
        self.assertEqual(page.discovered, 6)
        self.assertEqual(len(page.hits), 5)
        self.assertEqual(page.hits[0].url, "https://sochic.com.ar/product/item-0/")


class ClassifyWatchTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    def test_classify_url_run_and_code(self):
        index = DedupIndex(
            product_urls=frozenset({canonical_source_url("https://www.sochic.com.ar/product/vieja/?utm=1")}),
            run_urls=frozenset({canonical_source_url("https://nissiedenim.com.ar/productos/from-run/")}),
            cod_products=frozenset({"BSPOR", "nissie-282540155"}),
        )
        cases = [
            (
                ListingHit(url="https://sochic.com.ar/product/vieja"),
                STATUS_DUPLICATE,
                "provider_source_url",
            ),
            (
                ListingHit(url="https://nissiedenim.com.ar/productos/from-run"),
                STATUS_DUPLICATE,
                "import_run",
            ),
            (
                ListingHit(url="https://laslocas.com/ficha-99-nueva", cod_product="BSPOR"),
                STATUS_DUPLICATE,
                "cod_product",
            ),
            (
                ListingHit(
                    url="https://sochic.com.ar/product/vieja",
                    cod_product="BSPOR",
                ),
                STATUS_DUPLICATE,
                "provider_source_url",
            ),
            (
                ListingHit(url="https://sochic.com.ar/product/nueva/", title="Nueva"),
                STATUS_NEW,
                None,
            ),
            (
                ListingHit(url="https://nissiedenim.com.ar/productos/failed/"),
                STATUS_NEW,
                None,
            ),
        ]
        for hit, status, match in cases:
            got_status, got_match = classify_listing_hit(hit, index)
            self.assertEqual(got_status, status, hit.url)
            self.assertEqual(got_match, match, hit.url)

    def test_dedup_index_uses_the_same_rows_as_skip_existing(self):
        session = self.Session()
        session.add(
            Products(
                item_title="Stored",
                price=1000,
                cod_product="sochic-1-stored",
                name="Stored",
                provider="sochic",
                provider_source_url="https://www.sochic.com.ar/product/stored/?ref=1",
            )
        )
        session.add(
            Products(
                item_title="From run",
                price=1000,
                cod_product="nissie-9",
                name="From run",
                provider="nissie",
            )
        )
        session.add(
            Products(
                item_title="Codigo",
                price=1000,
                cod_product="BSPOR",
                name="Codigo",
                provider="laslocas",
            )
        )
        run = ProviderImportRun(provider="nissie", status="completed", phase="completed")
        session.add(run)
        session.flush()
        session.add(
            ProviderImportRunItem(
                run_id=run.run_id,
                source_url="https://nissiedenim.com.ar/productos/from-run/",
                cod_product="nissie-9",
                status="created",
            )
        )
        session.add(
            ProviderImportRunItem(
                run_id=run.run_id,
                source_url="https://nissiedenim.com.ar/productos/failed/",
                cod_product="nissie-9",
                status="failed",
            )
        )
        session.add(
            ProviderImportRunItem(
                run_id=run.run_id,
                source_url="https://nissiedenim.com.ar/productos/deleted/",
                cod_product="nissie-missing",
                status="skipped",
            )
        )
        session.commit()

        index = load_dedup_index(session)
        known = load_known_source_urls(session)
        self.assertEqual(known, set(index.product_urls) | set(index.run_urls))
        self.assertIn("https://sochic.com.ar/product/stored", index.product_urls)
        self.assertIn("https://nissiedenim.com.ar/productos/from-run", index.run_urls)
        self.assertNotIn("https://nissiedenim.com.ar/productos/failed", known)
        self.assertNotIn("https://nissiedenim.com.ar/productos/deleted", known)
        self.assertIn("BSPOR", index.cod_products)
        self.assertIn("nissie-9", index.cod_products)

        duplicate, match = classify_listing_hit(
            ListingHit(url="http://sochic.com.ar/product/stored"),
            index,
        )
        self.assertEqual((duplicate, match), (STATUS_DUPLICATE, "provider_source_url"))
        by_run, run_match = classify_listing_hit(
            ListingHit(url="https://www.nissiedenim.com.ar/productos/from-run/"),
            index,
        )
        self.assertEqual((by_run, run_match), (STATUS_DUPLICATE, "import_run"))
        by_code, code_match = classify_listing_hit(
            ListingHit(url="https://laslocas.com/ficha-1-otra", cod_product="BSPOR"),
            index,
        )
        self.assertEqual((by_code, code_match), (STATUS_DUPLICATE, "cod_product"))
        fresh, fresh_match = classify_listing_hit(
            ListingHit(url="https://nissiedenim.com.ar/productos/failed/"),
            index,
        )
        self.assertEqual((fresh, fresh_match), (STATUS_NEW, None))
        session.close()


class ScanWatchTest(unittest.TestCase):
    def test_limit_and_provider_guards(self):
        self.assertEqual(normalize_watch_limit(5), 5)
        self.assertEqual(normalize_watch_limit(10), 10)
        with self.assertRaises(WatchRequestError):
            normalize_watch_limit(50)
        with self.assertRaises(WatchRequestError):
            normalize_watch_limit(True)
        self.assertEqual(
            normalize_watch_providers(None),
            ["laslocas", "nissie", "sochic"],
        )
        self.assertEqual(
            normalize_watch_providers(["sochic", "sochic", "holic"]),
            ["sochic", "holic"],
        )
        with self.assertRaises(WatchRequestError):
            normalize_watch_providers(["otro"])

    def test_scan_classifies_without_walking_the_catalog(self):
        index = DedupIndex(
            product_urls=frozenset({canonical_source_url("https://sochic.com.ar/product/vieja/")}),
            run_urls=frozenset({canonical_source_url("https://nissiedenim.com.ar/productos/from-run/")}),
            cod_products=frozenset({"BSPOR"}),
        )
        seen = []

        def fetch(*, provider, limit, laslocas_category, session=None):
            seen.append((provider, limit, laslocas_category))
            if provider == "nissie":
                return ListingPage(
                    hits=(
                        ListingHit(
                            url="https://nissiedenim.com.ar/productos/from-run/",
                            title="Ya corrida",
                            price=10000,
                        ),
                        ListingHit(
                            url="https://nissiedenim.com.ar/productos/nueva/",
                            title="Nueva",
                            price=12000,
                        ),
                    ),
                    discovered=2,
                )
            if provider == "sochic":
                return ListingPage(
                    hits=(
                        ListingHit(url="https://www.sochic.com.ar/product/vieja/?utm=1", title="Vieja", price=29000),
                        ListingHit(url="https://sochic.com.ar/product/nueva/", title="Nueva So"),
                    ),
                    discovered=9,
                )
            if provider == "laslocas":
                return ListingPage(
                    hits=(
                        ListingHit(
                            url="https://laslocas.com/ficha-99-nueva",
                            title="Repetida",
                            price=15000,
                            cod_product="BSPOR",
                        ),
                    ),
                    discovered=1,
                )
            raise AssertionError(provider)

        slept = []
        saved_email = os.environ.get("LOGIN_EMAIL")
        saved_pass = os.environ.get("LOGIN_PASS")
        os.environ["LOGIN_EMAIL"] = "ada@example.com"
        os.environ["LOGIN_PASS"] = "s3cret-locas-pass"
        try:
            report = scan_watch(
                providers=["laslocas", "nissie", "sochic"],
                limit=5,
                index=index,
                laslocas_category="denim",
                fetch=fetch,
                sleep=slept.append,
            )
        finally:
            if saved_email is None:
                os.environ.pop("LOGIN_EMAIL", None)
            else:
                os.environ["LOGIN_EMAIL"] = saved_email
            if saved_pass is None:
                os.environ.pop("LOGIN_PASS", None)
            else:
                os.environ["LOGIN_PASS"] = saved_pass

        self.assertEqual(seen[0][0], "laslocas")
        self.assertEqual(seen[0][1], 5)
        self.assertEqual([item.status for item in report.items], [
            STATUS_DUPLICATE,
            STATUS_DUPLICATE,
            STATUS_NEW,
            STATUS_DUPLICATE,
            STATUS_NEW,
        ])
        self.assertEqual(
            [item.match for item in report.items],
            ["cod_product", "import_run", None, "provider_source_url", None],
        )
        self.assertGreaterEqual(slept[0], 1.5)
        self.assertGreaterEqual(slept[1], 5.0)
        self.assertGreaterEqual(slept[1], get_brand("sochic").default_delay_ms / 1000)
        self.assertTrue(report.to_dict()["imports"] is False)
        self.assertTrue(report.to_dict()["publishes_meta"] is False)
        self.assertIn("No publica a Meta", report.to_dict()["notice"])
        self.assertIn("No importa todo solo", report.to_dict()["notice"])
        blob = str(report.to_dict())
        self.assertNotIn("s3cret-locas-pass", blob)
        self.assertNotIn("ada@example.com", blob)
        command = cli_dry_run_command("sochic", 5, "denim")
        self.assertIn("--dry-run", command)
        self.assertIn("--delay-ms 5000", command)
        self.assertNotIn("--status-active", command)

    def test_missing_login_does_not_fetch_or_print_secrets(self):
        saved_email = os.environ.pop("LOGIN_EMAIL", None)
        saved_pass = os.environ.pop("LOGIN_PASS", None)
        called = []
        try:
            report = scan_watch(
                providers=["laslocas"],
                limit=5,
                index=DedupIndex(frozenset(), frozenset(), frozenset()),
                fetch=lambda **kwargs: called.append(kwargs),
                sleep=lambda _seconds: None,
            )
        finally:
            if saved_email is not None:
                os.environ["LOGIN_EMAIL"] = saved_email
            if saved_pass is not None:
                os.environ["LOGIN_PASS"] = saved_pass
        self.assertEqual(called, [])
        error = report.providers[0].error or ""
        self.assertIn("LOGIN_EMAIL", error)
        self.assertIn("LOGIN_PASS", error)
        self.assertNotIn("=", error)

    def test_fetcher_errors_are_redacted(self):
        saved_email = os.environ.get("LOGIN_EMAIL")
        saved_pass = os.environ.get("LOGIN_PASS")
        os.environ["LOGIN_PASS"] = "s3cret-locas-pass"
        os.environ["LOGIN_EMAIL"] = "ada@example.com"

        def fetch(*, provider, limit, laslocas_category, session=None):
            raise RuntimeError("falló ada@example.com s3cret-locas-pass")

        try:
            report = scan_watch(
                providers=["nissie"],
                limit=10,
                index=DedupIndex(frozenset(), frozenset(), frozenset()),
                fetch=fetch,
                sleep=lambda _seconds: None,
            )
        finally:
            _restore_env("LOGIN_EMAIL", saved_email)
            _restore_env("LOGIN_PASS", saved_pass)
        error = report.providers[0].error or ""
        self.assertNotIn("s3cret-locas-pass", error)
        self.assertNotIn("ada@example.com", error)
        self.assertIn("••••", error)

    def test_sochic_alone_does_not_sleep_before_the_only_request(self):
        slept = []
        scan_watch(
            providers=["sochic"],
            limit=5,
            index=DedupIndex(frozenset(), frozenset(), frozenset()),
            fetch=lambda **kwargs: ListingPage(hits=(), discovered=0),
            sleep=slept.append,
        )
        self.assertEqual(slept, [])

    def test_modules_do_not_schedule_or_walk_full_catalogs(self):
        import provider_importers.bulk.watch as watch
        import provider_importers.bulk.watch_listings as listings

        source = inspect.getsource(watch) + "\n" + inspect.getsource(listings)
        for name in (
            "discover_nissie_product_urls",
            "discover_sochic_product_urls",
            "discover_laslocas_product_urls",
            "discover_holic_product_urls",
            "BackgroundTasks",
            "CloudScheduler",
        ):
            self.assertNotIn(name, source)
        self.assertNotIn("novedades", PathRead(".github/workflows/tests.yml"))


def _restore_env(name: str, previous: str | None) -> None:
    if previous is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = previous


def PathRead(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class WatchEndpointTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)
        session = self.SessionLocal()
        session.add(
            Products(
                item_title="Vieja",
                price=29000,
                cod_product="sochic-1-vieja",
                name="Vieja",
                provider="sochic",
                provider_source_url="https://sochic.com.ar/product/vieja/",
            )
        )
        session.commit()
        session.close()

        def override_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        main.app.dependency_overrides[main.get_db_fastApi] = override_db
        main.app.dependency_overrides[main.get_current_user] = lambda: {"sub": "admin"}
        self.client = TestClient(main.app)
        self._k_service = os.environ.pop("K_SERVICE", None)

    def tearDown(self):
        main.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        if self._k_service is not None:
            os.environ["K_SERVICE"] = self._k_service
        else:
            os.environ.pop("K_SERVICE", None)

    def test_endpoint_classifies_and_does_not_import(self):
        def fetch(*, provider, limit, laslocas_category, session=None):
            self.assertIn(limit, (5, 10))
            if provider == "sochic":
                return ListingPage(
                    hits=(
                        ListingHit(url="https://sochic.com.ar/product/vieja/", title="Vieja", price=29000),
                        ListingHit(url="https://sochic.com.ar/product/nueva/", title="Nueva", price=31000),
                    ),
                    discovered=2,
                )
            return ListingPage(hits=(), discovered=0)

        with patch("services.provider_watch.time.sleep") as slept, patch(
            "provider_importers.bulk.watch.fetch_provider_listing",
            side_effect=fetch,
        ), patch("main.fetch_product", side_effect=AssertionError("no bajar fichas")):
            response = self.client.post(
                "/api/proveedores/novedades",
                json={"providers": ["nissie", "sochic"], "limit": 5},
            )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertFalse(body["imports"])
        self.assertFalse(body["publishes_meta"])
        self.assertTrue(body["notebook_only"])
        by_url = {item["url"]: item for item in body["items"]}
        self.assertEqual(by_url["https://sochic.com.ar/product/vieja/"]["status"], "posible_duplicado")
        self.assertEqual(by_url["https://sochic.com.ar/product/vieja/"]["status_label"], "posible duplicado")
        self.assertEqual(by_url["https://sochic.com.ar/product/nueva/"]["status"], "nuevo")
        self.assertEqual(by_url["https://sochic.com.ar/product/nueva/"]["price"], 31000)
        self.assertIn("--dry-run", body["providers"][1]["cli_dry_run"])
        slept.assert_called()
        session = self.SessionLocal()
        self.assertEqual(session.query(Products).count(), 1)
        session.close()

    def test_cloud_run_is_rejected_before_fetch(self):
        os.environ["K_SERVICE"] = "daniebot"
        with patch(
            "provider_importers.bulk.watch.fetch_provider_listing",
            side_effect=AssertionError("no listar en cloud"),
        ):
            response = self.client.post(
                "/api/proveedores/novedades",
                json={"providers": ["nissie"], "limit": 5},
            )
        self.assertEqual(response.status_code, 403)
        detail = response.json()["detail"]
        self.assertIn("PC", detail)
        self.assertIn("Cloud Run", detail)

    def test_oversized_limit_does_not_fetch(self):
        with patch(
            "provider_importers.bulk.watch.fetch_provider_listing",
            side_effect=AssertionError("no listar"),
        ):
            response = self.client.post(
                "/api/proveedores/novedades",
                json={"providers": ["nissie"], "limit": 50},
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("5 o 10", response.json()["detail"])

    def test_redacts_login_values_in_the_http_body(self):
        saved_email = os.environ.get("LOGIN_EMAIL")
        saved_pass = os.environ.get("LOGIN_PASS")
        os.environ["LOGIN_EMAIL"] = "ada@example.com"
        os.environ["LOGIN_PASS"] = "s3cret-locas-pass"

        def fetch(*, provider, limit, laslocas_category, session=None):
            raise RuntimeError("auth ada@example.com s3cret-locas-pass")

        try:
            with patch("services.provider_watch.time.sleep"), patch(
                "provider_importers.bulk.watch.fetch_provider_listing",
                side_effect=fetch,
            ):
                response = self.client.post(
                    "/api/proveedores/novedades",
                    json={"providers": ["nissie"], "limit": 5},
                )
        finally:
            _restore_env("LOGIN_EMAIL", saved_email)
            _restore_env("LOGIN_PASS", saved_pass)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("s3cret-locas-pass", response.text)
        self.assertNotIn("ada@example.com", response.text)


class RedactTest(unittest.TestCase):
    def test_redact_replaces_values_not_names(self):
        os.environ["LOGIN_PASS"] = "s3cret-locas-pass"
        try:
            text = redact_secrets("Faltan LOGIN_PASS. Detalle s3cret-locas-pass")
        finally:
            os.environ.pop("LOGIN_PASS", None)
        self.assertIn("LOGIN_PASS", text)
        self.assertNotIn("s3cret-locas-pass", text)


if __name__ == "__main__":
    unittest.main()
