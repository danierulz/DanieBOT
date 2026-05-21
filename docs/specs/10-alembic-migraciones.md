# Alembic — migraciones de base de datos

## Qué resuelve

- Un solo historial versionado de cambios de esquema (tablas, columnas, índices).
- La tabla `alembic_version` registra qué revisión tiene cada entorno.
- Deja de depender de `create_all` + SQL sueltos en `database/migrations/` + `_migrate_*()` en el arranque.

## Comandos (desde la raíz del repo)

```bash
# Aplicar migraciones pendientes
python -m alembic upgrade head

# Ver revisión actual
python -m alembic current

# Historial
python -m alembic history

# Nueva migración (después de cambiar modelos en database/models/)
python -m alembic revision --autogenerate -m "descripcion del cambio"
# Revisar el archivo generado en alembic/versions/ antes de commitear
```

Variables de entorno: las mismas que la app (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`) o `DATABASE_URL` completa.

## Producción (Cloud SQL ya con tablas y datos)

**No ejecutar** `upgrade head` si la base ya tiene todas las tablas creadas a mano, salvo que falten columnas y exista una migración incremental que solo agregue lo faltante.

### Primera vez — marcar baseline sin recrear tablas

1. Verificar que el esquema coincide con los modelos (pedidos, customers, order_events, etc.).
2. Si falta algo, aplicar el SQL pendiente o `python -m alembic upgrade head` solo si la migración es segura (ALTER ADD).
3. Marcar la revisión actual sin ejecutar CREATE:

```bash
python -m alembic stamp 20260520_0001
# o, si esa es la única revisión:
python -m alembic stamp head
```

4. Confirmar: `python -m alembic current` debe mostrar `20260520_0001 (head)`.

### Deploys siguientes

Antes o durante el deploy de la app:

```bash
python -m alembic upgrade head
```

## Base de datos nueva (vacía)

```bash
python -m alembic upgrade head
python -c "from database.init_db import seed_reference_data; seed_reference_data()"
```

### En Docker (desarrollo local)

```powershell
.\scripts\dev-init.ps1
```

Equivalente a `upgrade head` + seeds contra Postgres en `docker-compose` (`DB_HOST=db`). Ver [11-desarrollo-local.md](./11-desarrollo-local.md).

## Seeds (datos, no esquema)

Talles y categorías base: [`database/init_db.py`](../database/init_db.py) → `seed_reference_data()`.

No usar `RUN_DB_CREATE_ALL`; el esquema es responsabilidad de Alembic.

## Archivos legacy

- `database/migrations/*.sql` — histórico; no usar para cambios nuevos.
- Migraciones manuales `_migrate_*` — eliminadas de `initialize_database()`.

## CI / Cloud Build (opcional)

Añadir un paso antes del deploy:

```yaml
# ejemplo
- name: migrate
  run: python -m alembic upgrade head
```

Requiere acceso de red a Cloud SQL (VPC connector) y las mismas variables `DB_*`.

## Troubleshooting

| Síntoma | Acción |
|---------|--------|
| `relation already exists` en upgrade | La base ya tenía tablas: usar `stamp head`, no `upgrade` en baseline. |
| App falla por columna faltante | `alembic current`; generar migración nueva; `upgrade head` en prod. |
| Autogenerate propone DROP | Revisar siempre el .py generado; quitar drops accidentales. |
