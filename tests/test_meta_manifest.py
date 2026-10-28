import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("JWT_SECRET_KEY", "ci-test-jwt-secret-not-for-prod")
os.environ.setdefault("ADMIN_USERNAME", "ci-admin")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.models  # noqa: F401
from database.init_db import Base
from database.models.Category import Category
from database.models.ProductImages import ProductImages
from database.models.ProductVariant import ProductVariant
from database.models.Products import Products
from database.models.Size import Size
from services.meta_manifest import (
    build_caption,
    build_manifest_item,
    channel_gap_ids,
    format_ar_price,
    ids_published_on,
    load_products,
    main,
    manifest_id,
    parse_exclude_tokens,
    published_index,
    read_exclude_file,
    render_manifest,
    select_products,
    strip_provider_suffix,
)


def _size(code, label, order):
    return SimpleNamespace(code=code, label=label, sort_order=order)


def _variant(size, *, activo=True):
    return SimpleNamespace(size=size, activo=activo)


def _image(url, *, is_main=False, image_id=0):
    return SimpleNamespace(url=url, is_main=is_main, image_id=image_id, filename="x.jpg")


def _product(**overrides):
    fields = dict(
        product_id=300,
        provider="sochic",
        item_title="Campera friza - Sochic",
        name="Campera friza - Sochic",
        description="Friza con cierre. Colores proveedor: negro.",
        price=28500,
        is_sale=False,
        discount_percent=None,
        status=False,
        cod_product="sochic-3515-campera-friza",
        category=SimpleNamespace(slug="camperas"),
        variants=[
            _variant(_size("UNICO", "Único", 0)),
            _variant(_size("M", "M", 20)),
            _variant(_size("S", "S", 10)),
            _variant(_size("XL", "XL", 40), activo=False),
        ],
        images=[
            _image("http://cdn.example/skip.jpg", image_id=1),
            _image("https://cdn.example/side.jpg", is_main=False, image_id=2),
            _image("https://cdn.example/main.jpg", is_main=True, image_id=3),
            _image("https://cdn.example/side.jpg", is_main=False, image_id=4),
            _image("/local/foto.jpg", image_id=5),
        ],
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


class PriceAndTitleTest(unittest.TestCase):
    def test_ar_thousands_dot(self):
        self.assertEqual(format_ar_price(28500), "$28.500")
        self.assertEqual(format_ar_price(999), "$999")
        self.assertEqual(format_ar_price(1000), "$1.000")
        self.assertEqual(format_ar_price(1_000_000), "$1.000.000")
        self.assertEqual(format_ar_price(0), "$0")

    def test_strips_provider_suffix(self):
        self.assertEqual(strip_provider_suffix("Campera friza - Sochic"), "Campera friza")
        self.assertEqual(strip_provider_suffix("  Jean   -   So Chic  "), "Jean")
        self.assertEqual(strip_provider_suffix("Pollera — Las Locas"), "Pollera")
        self.assertEqual(strip_provider_suffix("Remera | HOLIC"), "Remera")
        self.assertEqual(strip_provider_suffix("Vestido - Nissie Denim"), "Vestido")
        self.assertEqual(strip_provider_suffix("Nissie Denim Jacket"), "Nissie Denim Jacket")

    def test_slug_uses_provider_then_category(self):
        self.assertEqual(manifest_id(_product()), "sochic-300")
        denim = _product(
            product_id=292,
            provider=None,
            category=SimpleNamespace(slug="denim"),
            item_title="Jean mom",
        )
        self.assertEqual(manifest_id(denim), "denim-292")
        self.assertEqual(
            manifest_id(_product(product_id=12, provider="", category=None)),
            "producto-12",
        )
        both = _product(product_id=300, provider="sochic", category=SimpleNamespace(slug="denim"))
        self.assertEqual(manifest_id(both), "sochic-300")


class CaptionAndImagesTest(unittest.TestCase):
    def test_caption_joins_title_price_sizes_and_short_desc(self):
        caption = build_caption(
            title="Campera friza",
            price=28500,
            description="Friza con cierre.",
            sizes=["S", "M"],
        )
        self.assertEqual(
            caption,
            "Campera friza\n$28.500\nTalles: S, M\nFriza con cierre.",
        )

    def test_sale_price_and_https_images_main_first(self):
        product = _product(price=30000, is_sale=True, discount_percent=5, status=False)
        item = build_manifest_item(product)
        self.assertEqual(item["id"], "sochic-300")
        self.assertEqual(item["title"], "Campera friza")
        self.assertEqual(item["price"], 28500)
        self.assertIn("$28.500", item["caption"])
        self.assertIn("Talles: S, M", item["caption"])
        self.assertNotIn("XL", item["caption"])
        self.assertNotIn("Único", item["caption"])
        self.assertNotIn("Sochic", item["title"])
        self.assertEqual(item["message"], item["caption"])
        self.assertEqual(
            item["images"],
            ["https://cdn.example/main.jpg", "https://cdn.example/side.jpg"],
        )
        self.assertFalse(product.status)

    def test_image_cap_and_boilerplate_description(self):
        images = [_image(f"https://cdn.example/{idx}.jpg", is_main=(idx == 7), image_id=idx) for idx in range(12)]
        product = _product(
            description="Producto importado desde So Chic.",
            images=images,
            variants=[],
        )
        item = build_manifest_item(product)
        self.assertEqual(len(item["images"]), 10)
        self.assertEqual(item["images"][0], "https://cdn.example/7.jpg")
        self.assertEqual(item["caption"], "Campera friza\n$28.500")

    def test_select_keeps_inactive_and_honors_exclude_and_limit(self):
        older = _product(product_id=292, provider=None, category=SimpleNamespace(slug="denim"), item_title="Jean")
        newer = _product(product_id=300, status=False)
        other = _product(product_id=301, provider="nissie", item_title="Wide")
        rows = [newer, other, older]
        picked = select_products(rows, provider="sochic", exclude={"sochic-300"}, limit=5)
        self.assertEqual(picked, [])
        kept = select_products(rows, exclude={"300", "nissie-301"}, limit=1)
        self.assertEqual([row.product_id for row in kept], [292])
        self.assertEqual(select_products([newer], exclude={"Sochic-300"}), [])
        self.assertFalse(newer.status)

    def test_exclude_file_tokens(self):
        self.assertEqual(
            parse_exclude_tokens("# ya publicados\nsochic-300\n\ndenin-292, 301\n"),
            ["sochic-300", "denin-292", "301"],
        )
        self.assertEqual(parse_exclude_tokens('[{"id": "sochic-300"}, 292]'), ["sochic-300", "292"])
        self.assertEqual(
            parse_exclude_tokens("# ledger\nsochic-300:page\nsochic-292:ig, 3515:page\n"),
            ["sochic-300:page", "sochic-292:ig", "3515:page"],
        )
        self.assertEqual(
            parse_exclude_tokens('[{"id": "sochic-300:page"}, {"id": "denim-292:ig"}]'),
            ["sochic-300:page", "denim-292:ig"],
        )

    def test_read_exclude_file_one_id_per_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ya-publicados.txt"
            path.write_text(
                "# publicados en Graph\nsochic-300\n\ndenim-292\n3515\n",
                encoding="utf-8",
            )
            self.assertEqual(
                read_exclude_file(str(path)),
                ["sochic-300", "denim-292", "3515"],
            )


class ChannelLedgerTest(unittest.TestCase):
    def test_bare_id_is_both_channels_and_suffixes_merge(self):
        index = published_index(
            ["Sochic-300:PAGE", "sochic-300:ig", "denim-292", "3515:ig", "  "]
        )
        self.assertEqual(
            index,
            {
                "sochic-300": frozenset({"page", "ig"}),
                "denim-292": frozenset({"page", "ig"}),
                "3515": frozenset({"ig"}),
            },
        )
        self.assertEqual(
            ids_published_on(["sochic-300:page", "denim-292", "3515:ig"], "ig"),
            ["3515", "denim-292"],
        )
        self.assertEqual(
            ids_published_on(["sochic-300:page", "denim-292", "3515:ig"], "PAGE"),
            ["denim-292", "sochic-300"],
        )

    def test_page_ok_ig_pending_exports_only_on_ig_wave(self):
        page_done = _product()
        ig_done = _product(product_id=292, provider=None, category=SimpleNamespace(slug="denim"), item_title="Jean")
        fresh = _product(product_id=301, provider="nissie", item_title="Wide")
        rows = [page_done, ig_done, fresh]
        ledger = {"sochic-300:page", "denim-292:ig", "JEAN292"}
        self.assertEqual(
            [row.product_id for row in select_products(rows, exclude=ledger)],
            [301],
        )
        self.assertEqual(
            [row.product_id for row in select_products(rows, exclude=ledger, channel="ig")],
            [300, 301],
        )
        self.assertEqual(
            [row.product_id for row in select_products(rows, exclude=ledger, channel="page")],
            [292, 301],
        )
        self.assertEqual(select_products([page_done], exclude={"sochic-300"}, channel="ig"), [])
        self.assertEqual(select_products([page_done], exclude={"sochic-300"}, channel="page"), [])
        self.assertEqual(
            select_products([page_done], exclude={"Sochic-300:Page"}, channel="IG"),
            [page_done],
        )
        self.assertEqual(select_products([page_done], exclude={"Sochic-300:Page"}, channel="page"), [])
        self.assertEqual(
            [row.product_id for row in select_products(rows, exclude={"300:page", "nissie-301:ig"}, channel="ig")],
            [300, 292],
        )
        both = {"sochic-300:page", "sochic-300:ig"}
        self.assertEqual(select_products([page_done], exclude=both, channel="ig"), [])
        self.assertEqual(select_products([page_done], exclude=both, channel="page"), [])
        gaps = channel_gap_ids([page_done, fresh], {"sochic-300:page", "999:ig"}, "ig")
        self.assertEqual(gaps, ["sochic-300"])
        self.assertEqual(channel_gap_ids([ig_done], {"denim-292:ig"}, "page"), ["denim-292"])

    def test_same_garment_marked_on_different_keys_counts_as_both(self):
        product = _product()
        ledger = {"sochic-300:page", "300:ig"}
        self.assertEqual(select_products([product], exclude=ledger, channel="ig"), [])
        self.assertEqual(select_products([product], exclude=ledger, channel="page"), [])
        cod_only = {"sochic-3515-campera-friza:ig"}
        self.assertEqual(select_products([product], exclude=cod_only, channel="page"), [product])
        self.assertEqual(select_products([product], exclude=cod_only, channel="ig"), [])

    def test_unknown_channel_suffix_is_rejected(self):
        with self.assertRaises(ValueError):
            published_index(["sochic-300:both"])
        with self.assertRaises(ValueError):
            published_index([":page"])
        with self.assertRaises(ValueError):
            select_products([_product()], channel="feed")

    def test_ops_doc_describes_the_shared_ledger(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/ops/meta-garments-manifest.md").read_text(encoding="utf-8")
        self.assertIn("ya-publicados.txt", text)
        self.assertIn("un id por línea", text)
        self.assertIn("sochic-300", text)
        self.assertIn("id:page", text)
        self.assertIn("id:ig", text)
        self.assertIn("--channel ig", text)
        self.assertIn("MARKET_OPS_EXCLUDE_FILE", text)
        self.assertIn("sin sidecar", text)
        self.assertNotIn("graph.facebook.com", text)


class ManifestBytesTest(unittest.TestCase):
    def test_utf8_without_bom(self):
        item = build_manifest_item(_product(item_title="Campera niño - Sochic"))
        data = render_manifest([item])
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
        text = data.decode("utf-8")
        self.assertIn("Campera niño", text)
        parsed = json.loads(text)
        self.assertEqual(parsed[0]["price"], 28500)
        self.assertEqual(parsed[0]["id"], "sochic-300")


class CliDryRunTest(unittest.TestCase):
    def test_dry_run_prints_summary_and_does_not_write(self):
        product = _product()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "sochic-meta.json"
            output.write_text("keep", encoding="utf-8")
            buf = io.StringIO()
            with patch("services.meta_manifest.fetch_products", return_value=[product]) as fetch:
                with redirect_stdout(buf):
                    code = main(
                        [
                            "--provider",
                            "sochic",
                            "--limit",
                            "5",
                            "--output",
                            str(output),
                            "--dry-run",
                        ]
                    )
            self.assertEqual(code, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep")
            summary = buf.getvalue()
            self.assertIn("dry-run", summary)
            self.assertIn("sochic-300", summary)
            self.assertIn("Campera friza", summary)
            self.assertIn("imágenes=2", summary)
            self.assertIn(str(output), summary)
            self.assertNotIn("DATABASE_URL", summary)
            fetch.assert_called_once()
            self.assertEqual(fetch.call_args.kwargs["provider"], "sochic")
            self.assertEqual(fetch.call_args.kwargs["limit"], 5)

    def test_db_error_does_not_print_the_url(self):
        err = io.StringIO()
        with patch(
            "services.meta_manifest.fetch_products",
            side_effect=RuntimeError("postgresql://user:secret@db.example/app"),
        ):
            with redirect_stderr(err):
                code = main(["--provider", "sochic", "--limit", "1", "--dry-run"])
        self.assertEqual(code, 1)
        text = err.getvalue()
        self.assertNotIn("postgresql", text)
        self.assertNotIn("secret", text)
        self.assertNotIn("DATABASE_URL", text)
        self.assertIn(".env", text)

    def test_write_requires_output(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(["--provider", "sochic"])

    def test_write_utf8_file_without_bom(self):
        product = _product()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "nested" / "lote.json"
            skip = Path(tmp) / "ya.txt"
            skip.write_text("# publicados\n", encoding="utf-8")
            buf = io.StringIO()
            with patch("services.meta_manifest.fetch_products", return_value=[product]) as fetch:
                with redirect_stdout(buf):
                    code = main(
                        [
                            "--product-id",
                            "300",
                            "--exclude-id",
                            "denim-292,otro",
                            "--exclude-file",
                            str(skip),
                            "--output",
                            str(output),
                        ]
                    )
            self.assertEqual(code, 0)
            self.assertEqual(fetch.call_args.kwargs["product_ids"], {300})
            self.assertEqual(fetch.call_args.kwargs["exclude"], {"denim-292", "otro"})
            data = output.read_bytes()
            self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
            parsed = json.loads(data.decode("utf-8"))
            self.assertEqual(parsed[0]["id"], "sochic-300")
            self.assertIn("escrito:", buf.getvalue())
            self.assertIn("imágenes=2", buf.getvalue())

    def test_exclude_file_one_id_per_line_reaches_the_query(self):
        product = _product()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "lote.json"
            published = Path(tmp) / "ya-publicados.txt"
            published.write_text(
                "# ya publicados\nsochic-300\ndenim-292\n\n3515\n",
                encoding="utf-8",
            )
            with patch("services.meta_manifest.fetch_products", return_value=[product]) as fetch:
                with redirect_stdout(io.StringIO()):
                    code = main(
                        [
                            "--provider",
                            "sochic",
                            "--exclude-file",
                            str(published),
                            "--output",
                            str(output),
                            "--dry-run",
                        ]
                    )
            self.assertEqual(code, 0)
            self.assertEqual(
                fetch.call_args.kwargs["exclude"],
                {"sochic-300", "denim-292", "3515"},
            )
            self.assertIsNone(fetch.call_args.kwargs["channel"])

    def test_ig_channel_keeps_page_only_marks_and_names_them(self):
        product = _product()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "lote.json"
            published = Path(tmp) / "ya-publicados.txt"
            published.write_text(
                "# robotRZ ledger\nsochic-300:page\ndenim-292\n3515:ig\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch("services.meta_manifest.fetch_products", return_value=[product]) as fetch:
                with redirect_stdout(buf):
                    code = main(
                        [
                            "--provider",
                            "sochic",
                            "--channel",
                            "IG",
                            "--exclude-file",
                            str(published),
                            "--output",
                            str(output),
                            "--dry-run",
                        ]
                    )
            self.assertEqual(code, 0)
            self.assertEqual(output.exists(), False)
            self.assertEqual(
                fetch.call_args.kwargs["exclude"],
                {"sochic-300:page", "denim-292", "3515:ig"},
            )
            self.assertEqual(fetch.call_args.kwargs["channel"], "ig")
            summary = buf.getvalue()
            self.assertIn("canal=ig", summary)
            self.assertIn("ya en page, pendientes de ig: 1", summary)
            self.assertIn("sochic-300", summary)
            self.assertNotIn("graph.facebook", summary)

    def test_bad_channel_suffix_does_not_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            published = Path(tmp) / "ya-publicados.txt"
            published.write_text("sochic-300:facebook\n", encoding="utf-8")
            with patch(
                "services.meta_manifest.fetch_products",
                side_effect=AssertionError("no debería leer la base"),
            ):
                with self.assertRaises(SystemExit) as caught:
                    main(
                        [
                            "--channel",
                            "ig",
                            "--exclude-file",
                            str(published),
                            "--dry-run",
                        ]
                    )
            self.assertIn("Canal desconocido", str(caught.exception))


class SqliteLoadTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)
        session = self.Session()
        denim = Category(slug="denim", name="Denim", sort_order=1, activo=True, size_group="letter")
        session.add(denim)
        session.flush()
        size_s = Size(code="S", label="S", sort_order=1, size_group="letter")
        size_m = Size(code="M", label="M", sort_order=2, size_group="letter")
        session.add_all([size_s, size_m])
        session.flush()
        older = Products(
            product_id=292,
            item_title="Jean mom - Las Locas",
            name="Jean mom",
            price=15000,
            status=False,
            provider=None,
            category_id=denim.category_id,
            cod_product="JEAN292",
            description="Mom fit.",
        )
        newer = Products(
            product_id=300,
            item_title="Campera - Sochic",
            name="Campera",
            price=28500,
            status=False,
            provider="sochic",
            category_id=denim.category_id,
            cod_product="sochic-3515-campera",
            description="Friza.",
        )
        session.add_all([older, newer])
        session.flush()
        session.add_all(
            [
                ProductImages(
                    product_id=300,
                    filename="side.jpg",
                    url="https://cdn.example/side.jpg",
                    is_main=False,
                ),
                ProductImages(
                    product_id=300,
                    filename="main.jpg",
                    url="https://cdn.example/main.jpg",
                    is_main=True,
                ),
                ProductImages(
                    product_id=300,
                    filename="http.jpg",
                    url="http://cdn.example/nope.jpg",
                    is_main=False,
                ),
            ]
        )
        session.add(ProductVariant(product_id=300, size_id=size_m.size_id, activo=True))
        session.add(ProductVariant(product_id=300, size_id=size_s.size_id, activo=True))
        session.commit()
        session.close()

    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    def test_newest_first_includes_inactive_and_builds_manifest(self):
        session = self.Session()
        rows = load_products(session, limit=0)
        self.assertEqual([row.product_id for row in rows], [300, 292])
        self.assertFalse(rows[0].status)
        item = build_manifest_item(rows[0])
        self.assertEqual(item["id"], "sochic-300")
        self.assertEqual(item["images"][0], "https://cdn.example/main.jpg")
        self.assertNotIn("http://", " ".join(item["images"]))
        self.assertIn("Talles: S, M", item["caption"])
        only_denim = load_products(session, exclude={"sochic-300"})
        self.assertEqual([row.product_id for row in only_denim], [292])
        self.assertEqual(manifest_id(only_denim[0]), "denim-292")
        limited = load_products(session, provider="sochic", limit=1)
        self.assertEqual([row.product_id for row in limited], [300])
        page_only = load_products(session, exclude={"sochic-300:page", "denim-292"}, channel="ig")
        self.assertEqual([row.product_id for row in page_only], [300])
        ig_only = load_products(session, exclude={"sochic-300:page", "JEAN292:ig"}, channel="page")
        self.assertEqual([row.product_id for row in ig_only], [292])
        no_target = load_products(session, exclude={"sochic-300:page"})
        self.assertEqual([row.product_id for row in no_target], [292])
        session.close()


if __name__ == "__main__":
    unittest.main()
