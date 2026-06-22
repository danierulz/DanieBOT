# Logo de marca

## Archivos

- `logo-source.png` — referencia oficial (PNG transparente)
- `logo-extracted.json` — geometría extraída (depuración)
- `logo-meta.json` — conteos y `stem_length` para animación CSS
- `logo-calibration.json` — offsets finos letters/jasmine (dev)
- SVG animado en [`templates/partials/brand_logo.html`](../../templates/partials/brand_logo.html)
- Preview dev: [`templates/dev-brand-logo.html`](../../templates/dev-brand-logo.html) (solo `APP_DEBUG=true`)

## Regenerar SVG desde PNG

```powershell
cd C:\Projects\DanieBOT
pip install -r requirements-dev.txt
python scripts/build_brand_logo_from_png.py --write-html
```

Solo JSON intermedio:

```powershell
python scripts/build_brand_logo_from_png.py --json-only
```

El generador lee `logo-calibration.json` y aplica `transform` a los grupos `brand-logo__letters` y `brand-logo__jasmine`.

## Colores (env opcionales)

| Variable | Default |
|----------|---------|
| `SITE_BRAND_LOGO_LETTER` | `#111111` |
| `SITE_BRAND_LOGO_STEM` | `#3D6B4F` |
| `SITE_BRAND_LOGO_LEAF` | `#2F5A40` |
| `SITE_BRAND_LOGO_PETAL` | `#FAFAF8` |
| `SITE_BRAND_LOGO_PETAL_CENTER` | `#E8C547` |
| `SITE_BRAND_LOGO_BUD` | `#F5F5F0` |
| `SITE_BRAND_LOGO_ANIMATED` | `true` |

## Preview local y validación

```powershell
cd C:\Projects\DanieBOT
$env:APP_DEBUG = "true"
python main.py
```

- Tienda: http://localhost:8080/
- Comparador PNG/SVG: http://localhost:8080/dev/brand-logo  
  Modos: superpuesto (opacidad 50% recomendada), solo SVG, solo PNG, lado a lado.
- Sliders **letters / jasmine** → **Exportar calibración** guarda `logo-calibration.json`. Luego ejecutá el comando de regeneración.

Criterio de aceptación: en modo superpuesto al 50% o **Diff (desvío)**, la silueta de O+J y el jazmín coinciden visiblemente con el PNG.

El preview dev incluye toggles por capa (letras, tallo, hojas, flor) y conteos desde `logo-meta.json`.

Para repetir la animación en la tienda: DevTools → Session Storage → borrar `outfitJazminesLogoPlayed`.

## Clases CSS obligatorias por capa

Conservá estas clases (disparan la animación vía `--leaf-delay`, `--petal-delay`, etc.):

| Clase | Elemento |
|-------|----------|
| `brand-logo__letter-o` | Contorno/relleno de la O |
| `brand-logo__letter-j` | J interior |
| `brand-logo__stem` | Tallo (`pathLength` + `--logo-stem-length`) |
| `brand-logo__leaf--1` … `--N` | Hojas |
| `brand-logo__bud--top`, `brand-logo__bud--mid` | Capullos |
| `brand-logo__petal--1` … `--N` | Pétalos |
| `brand-logo__flower-center` | Centro amarillo |

Orden en SVG: grupo `brand-logo__letters` primero, `brand-logo__jasmine` después (jazmín encima del borde izquierdo de la O).

`viewBox` debe coincidir con el PNG (`0 0 666 714`).

## Scripts de ayuda

```powershell
python scripts/analyze_logo_png.py   # bounding boxes por color
python scripts/build_brand_logo_from_png.py --write-html
```
