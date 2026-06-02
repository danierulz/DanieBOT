#!/usr/bin/env python3
"""
Copia datos de Cloud SQL (origen) a Neon (destino).

Requiere esquema ya creado en destino (alembic upgrade head).

Variables:
  SOURCE_DATABASE_URL — Cloud SQL (postgresql:// o postgresql+psycopg2://)
  TARGET_DATABASE_URL — Neon pooler (si no está, usa DATABASE_URL)

Uso:
  python3 scripts/migrate_cloudsql_to_neon.py --verify-only
  python3 scripts/migrate_cloudsql_to_neon.py --method pg_dump
  python3 scripts/migrate_cloudsql_to_neon.py --method copy
"""
from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKUPS_DIR = REPO_ROOT / "backups"

DATA_TABLES = [
    "categories",
    "sizes",
    "colors",
    "customers",
    "products",
    "product_images",
    "product_variants",
    "product_colors",
    "home_banners",
    "orders",
    "order_items",
    "order_events",
]

TRUNCATE_TABLES = list(reversed(DATA_TABLES))


def _normalize_url(url: str) -> str:
    return url.replace("postgresql+psycopg2://", "postgresql://").strip()


def _resolve_urls() -> tuple[str, str]:
    source = os.getenv("SOURCE_DATABASE_URL", "").strip()
    target = os.getenv("TARGET_DATABASE_URL", "").strip() or os.getenv(
        "DATABASE_URL", ""
    ).strip()
    if not source:
        user = os.getenv("DB_USER", "")
        password = os.getenv("DB_PASSWORD", "")
        host = os.getenv("DB_HOST", "")
        port = os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME", "")
        if all([user, password, host, name]):
            source = f"postgresql://{user}:{password}@{host}:{port}/{name}"
    if not source or not target:
        print(
            "ERROR: Definí SOURCE_DATABASE_URL y TARGET_DATABASE_URL "
            "(o DATABASE_URL para destino y DB_* / SOURCE_DATABASE_URL para origen).",
            file=sys.stderr,
        )
        sys.exit(1)
    return _normalize_url(source), _normalize_url(target)


def _connect(url: str, *, label: str):
    try:
        return psycopg2.connect(_normalize_url(url), connect_timeout=30)
    except psycopg2.Error as e:
        print(f"ERROR: No se pudo conectar a {label}: {e}", file=sys.stderr)
        sys.exit(2)


def _table_counts(conn) -> dict[str, int]:
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        for table in DATA_TABLES + ["alembic_version"]:
            try:
                cur.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
                )
                counts[table] = int(cur.fetchone()[0])
            except psycopg2.Error:
                conn.rollback()
                counts[table] = -1
    return counts


def verify(source_url: str, target_url: str) -> int:
    src = _connect(source_url, label="origen")
    dst = _connect(target_url, label="destino")
    try:
        src_counts = _table_counts(src)
        dst_counts = _table_counts(dst)
    finally:
        src.close()
        dst.close()

    print(f"{'tabla':<22} {'origen':>10} {'destino':>10} {'ok':>4}")
    print("-" * 50)
    mismatches = 0
    for table in DATA_TABLES + ["alembic_version"]:
        s, d = src_counts.get(table, -1), dst_counts.get(table, -1)
        ok = s == d and s >= 0
        if not ok and table != "alembic_version":
            mismatches += 1
        mark = "yes" if ok else "NO"
        print(f"{table:<22} {s:>10} {d:>10} {mark:>4}")

    try:
        conn = _connect(target_url, label="destino")
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version")
            print(f"\nAlembic destino: {cur.fetchone()[0]}")
        conn.close()
    except psycopg2.Error:
        print("\nAlembic destino: (no legible)")

    return 0 if mismatches == 0 else 1


def _truncate_target(conn) -> None:
    tables_sql = sql.SQL(", ").join(sql.Identifier(t) for t in TRUNCATE_TABLES)
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(tables_sql)
        )
    conn.commit()
    print("Destino vaciado (TRUNCATE ... RESTART IDENTITY CASCADE).")


def _fix_sequences(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            DO $$
            DECLARE r RECORD;
            BEGIN
              FOR r IN (
                SELECT c.table_schema, c.table_name, c.column_name
                FROM information_schema.columns c
                WHERE c.table_schema = 'public'
                  AND c.column_default LIKE 'nextval%%'
              ) LOOP
                EXECUTE format(
                  'SELECT setval(pg_get_serial_sequence(%L, %L), '
                  'COALESCE((SELECT MAX(%I) FROM %I.%I), 1), true)',
                  r.table_name, r.column_name,
                  r.column_name, r.table_schema, r.table_name
                );
              END LOOP;
            END $$;
            """
        )
    conn.commit()
    print("Secuencias (serial) actualizadas en destino.")


def _copy_alembic_version(src, dst) -> None:
    with src.cursor() as sc, dst.cursor() as dc:
        sc.execute("SELECT version_num FROM alembic_version")
        row = sc.fetchone()
        if not row:
            return
        dc.execute("DELETE FROM alembic_version")
        dc.execute("INSERT INTO alembic_version (version_num) VALUES (%s)", (row[0],))
    dst.commit()
    print(f"alembic_version copiada: {row[0]}")


def migrate_copy(source_url: str, target_url: str) -> None:
    src = _connect(source_url, label="origen")
    dst = _connect(target_url, label="destino")
    try:
        _truncate_target(dst)
        for table in DATA_TABLES:
            buf = io.BytesIO()
            try:
                with src.cursor() as cur:
                    cur.copy_expert(f'COPY "{table}" TO STDOUT', buf)
            except psycopg2.Error as e:
                src.rollback()
                print(f"  {table}: omitida en origen ({e.pgerror or e})")
                continue
            buf.seek(0)
            if buf.getbuffer().nbytes == 0:
                print(f"  {table}: (vacía)")
                continue
            with dst.cursor() as cur:
                cur.copy_expert(f'COPY "{table}" FROM STDIN', buf)
            dst.commit()
            with dst.cursor() as cur:
                cur.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
                )
                n = cur.fetchone()[0]
            print(f"  {table}: {n} filas")
        _copy_alembic_version(src, dst)
        _fix_sequences(dst)
    finally:
        src.close()
        dst.close()


def _parse_pg_url(url: str) -> dict[str, str]:
    from urllib.parse import urlparse, unquote

    u = urlparse(_normalize_url(url))
    return {
        "host": u.hostname or "localhost",
        "port": str(u.port or 5432),
        "user": unquote(u.username or ""),
        "password": unquote(u.password or ""),
        "dbname": (u.path or "/").lstrip("/"),
    }


def migrate_pg_dump(source_url: str, target_url: str, dump_path: Path) -> None:
    src = _parse_pg_url(source_url)
    tgt = _parse_pg_url(target_url)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    dump_path = dump_path.resolve()

    env = os.environ.copy()
    env["PGPASSWORD"] = src["password"]
    print(f"Exportando datos (solo datos) → {dump_path}")
    dump_cmd = subprocess.run(
        [
            "pg_dump",
            "-h",
            src["host"],
            "-p",
            src["port"],
            "-U",
            src["user"],
            "-d",
            src["dbname"],
            "--format=custom",
            "--data-only",
            "--no-owner",
            "--no-acl",
            "-f",
            str(dump_path),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    if dump_cmd.returncode != 0:
        err = (dump_cmd.stderr or "") + (dump_cmd.stdout or "")
        if "version mismatch" in err or "server version" in err:
            raise RuntimeError("pg_dump version mismatch")
        dump_cmd.check_returncode()

    dst_conn = _connect(target_url, label="destino")
    try:
        _truncate_target(dst_conn)
    finally:
        dst_conn.close()

    env["PGPASSWORD"] = tgt["password"]
    if "neon.tech" in tgt["host"]:
        env["PGSSLMODE"] = "require"
    print("Importando en Neon...")
    subprocess.run(
        [
            "pg_restore",
            "-h",
            tgt["host"],
            "-p",
            tgt["port"],
            "-U",
            tgt["user"],
            "-d",
            tgt["dbname"],
            "--data-only",
            "--no-owner",
            "--no-acl",
            "--disable-triggers",
            str(dump_path),
        ],
        env=env,
        check=True,
    )
    print("pg_restore completado.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrar datos Cloud SQL → Neon")
    parser.add_argument(
        "--method",
        choices=("pg_dump", "copy"),
        default="copy",
        help="copy (psycopg2, compatible PG18 en Cloud Shell) o pg_dump",
    )
    parser.add_argument(
        "--dump",
        type=Path,
        default=BACKUPS_DIR / "laslocas_data.dump",
        help="Ruta del dump (solo pg_dump)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Solo comparar conteos origen vs destino",
    )
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass

    source_url, target_url = _resolve_urls()

    if args.verify_only:
        return verify(source_url, target_url)

    print("Origen:", source_url.split("@")[-1])
    print("Destino:", target_url.split("@")[-1])

    if args.method == "pg_dump":
        try:
            migrate_pg_dump(source_url, target_url, args.dump)
        except (subprocess.CalledProcessError, RuntimeError) as e:
            msg = str(e)
            if "version mismatch" in msg or isinstance(e, RuntimeError):
                print(
                    "AVISO: pg_dump no coincide con la versión del servidor "
                    "(p. ej. Cloud SQL PG18 + pg_dump 16). Usando método copy..."
                )
                migrate_copy(source_url, target_url)
            else:
                raise
    else:
        migrate_copy(source_url, target_url)

    print("\nVerificación post-migración:")
    return verify(source_url, target_url)


if __name__ == "__main__":
    sys.exit(main())
