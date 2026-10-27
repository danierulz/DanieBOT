"""Brand registry for notebook bulk catalog imports.

The CLI reads this file for ``--provider`` / ``--list-brands``. Discovery
functions stay in code; the file is the operator-facing contract.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

BRANDS_FILE = Path(__file__).with_name("brands.json")
BRAND_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
MODES = frozenset({"categories", "catalog", "urls_only"})

NOTEBOOK_BANNER = (
    "Alta masiva solo en notebook (PC local). "
    "No agendar en Cloud Run, Cloud Scheduler ni GitHub Actions."
)


class BrandConfigError(ValueError):
    """brands.json is missing fields or contradicts the notebook-only rule."""


@dataclass(frozen=True)
class BrandConfig:
    id: str
    display_name: str
    mode: str
    requires_login: bool
    login_env: tuple[str, ...]
    default_delay_ms: int
    notes: str


@dataclass(frozen=True)
class BrandRegistry:
    notebook_only: bool
    do_not_schedule: tuple[str, ...]
    brands: tuple[BrandConfig, ...]

    def get(self, brand_id: str) -> BrandConfig:
        for brand in self.brands:
            if brand.id == brand_id:
                return brand
        raise BrandConfigError(f"Marca desconocida: {brand_id}")

    def ids(self) -> list[str]:
        return [brand.id for brand in self.brands]


def load_brand_registry(path: Path | None = None) -> BrandRegistry:
    file = path or BRANDS_FILE
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrandConfigError(f"No se pudo leer {file.name}: {exc}") from exc
    if not isinstance(raw, dict):
        raise BrandConfigError("brands.json debe ser un objeto.")
    if raw.get("notebook_only") is not True:
        raise BrandConfigError(
            "brands.json debe declarar notebook_only=true. "
            "La alta masiva no se agenda en Cloud Run ni Cloud Scheduler."
        )
    schedule = raw.get("do_not_schedule") or []
    if not isinstance(schedule, list) or not all(isinstance(item, str) and item.strip() for item in schedule):
        raise BrandConfigError("do_not_schedule debe ser una lista de strings.")
    rows = raw.get("brands")
    if not isinstance(rows, list) or not rows:
        raise BrandConfigError("brands debe ser una lista con al menos una marca.")
    brands: list[BrandConfig] = []
    seen: set[str] = set()
    for row in rows:
        brand = _parse_brand(row)
        if brand.id in seen:
            raise BrandConfigError(f"Id de marca duplicado: {brand.id}")
        seen.add(brand.id)
        brands.append(brand)
    return BrandRegistry(
        notebook_only=True,
        do_not_schedule=tuple(item.strip() for item in schedule),
        brands=tuple(brands),
    )


def _parse_brand(row: object) -> BrandConfig:
    if not isinstance(row, dict):
        raise BrandConfigError("Cada marca debe ser un objeto.")
    brand_id = _require_str(row, "id")
    if not BRAND_ID_RE.match(brand_id):
        raise BrandConfigError(f"Id de marca inválido: {brand_id}")
    mode = _require_str(row, "mode")
    if mode not in MODES:
        raise BrandConfigError(f"Modo desconocido para {brand_id}: {mode}")
    requires_login = row.get("requires_login")
    if not isinstance(requires_login, bool):
        raise BrandConfigError(f"{brand_id}: requires_login debe ser bool.")
    login_env_raw = row.get("login_env", [])
    if not isinstance(login_env_raw, list) or not all(
        isinstance(item, str) and item.strip() for item in login_env_raw
    ):
        raise BrandConfigError(f"{brand_id}: login_env debe ser una lista de nombres de variables.")
    login_env = tuple(item.strip() for item in login_env_raw)
    if requires_login and not login_env:
        raise BrandConfigError(f"{brand_id}: requires_login exige login_env.")
    if not requires_login and login_env:
        raise BrandConfigError(f"{brand_id}: login_env debe estar vacío si no hay login.")
    delay = row.get("default_delay_ms")
    if isinstance(delay, bool) or not isinstance(delay, int) or delay < 0:
        raise BrandConfigError(f"{brand_id}: default_delay_ms debe ser un entero >= 0.")
    return BrandConfig(
        id=brand_id,
        display_name=_require_str(row, "display_name"),
        mode=mode,
        requires_login=requires_login,
        login_env=login_env,
        default_delay_ms=delay,
        notes=_require_str(row, "notes"),
    )


def _require_str(row: dict, field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise BrandConfigError(f"Campo obligatorio vacío o inválido: {field}")
    return value.strip()


def load_brands(path: Path | None = None) -> list[BrandConfig]:
    return list(load_brand_registry(path).brands)


def get_brand(brand_id: str, path: Path | None = None) -> BrandConfig:
    return load_brand_registry(path).get(brand_id)


def missing_login_env(brand: BrandConfig) -> list[str]:
    """Names of required login variables that are unset. Values are never returned."""
    if not brand.requires_login:
        return []
    return [name for name in brand.login_env if not os.getenv(name, "").strip()]


def format_brand_list(path: Path | None = None) -> str:
    registry = load_brand_registry(path)
    lines = [
        "Alta masiva: solo notebook (PC local).",
        "No agendar en Cloud Run, Cloud Scheduler ni GitHub Actions.",
        "do_not_schedule: " + ", ".join(registry.do_not_schedule),
        f"config: {path or BRANDS_FILE}",
        "",
    ]
    for brand in registry.brands:
        login = ", ".join(brand.login_env) if brand.requires_login else "no"
        lines.append(f"{brand.display_name} ({brand.id})")
        lines.append(f"  mode: {brand.mode}")
        lines.append(f"  login: {login}")
        lines.append(f"  default_delay_ms: {brand.default_delay_ms}")
        lines.append(f"  notes: {brand.notes}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
