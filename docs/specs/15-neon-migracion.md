# Migración PostgreSQL: Cloud SQL → Neon

## Conexión desde la app

Neon expone una URL tipo:

```text
postgresql://USER:PASS@ep-XXXX-pooler.REGION.aws.neon.tech/neondb?sslmode=require
```

En Cloud Run / local, usá el driver SQLAlchemy de la app:

```text
DATABASE_URL=postgresql+psycopg2://USER:PASS@ep-XXXX-pooler.REGION.aws.neon.tech/neondb?sslmode=require
```

- Usá el host **`-pooler`** para Cloud Run (muchas conexiones cortas).
- Con `DATABASE_URL` definida, la app **no** usa `DB_HOST` ni socket Cloud SQL.
- Podés quitar `--vpc-connector` y `--add-cloudsql-instances` del deploy cuando la app apunte solo a Neon.

## Bootstrap de esquema (base vacía)

```bash
export DATABASE_URL='postgresql+psycopg2://...'
python3 -m alembic upgrade head
python3 -c "from database.init_db import seed_reference_data; seed_reference_data()"
```

Revisión Alembic esperada: `20260528_0002` (head).

## Copiar datos desde Cloud SQL

1. Exportar desde GCP (Cloud SQL Auth proxy o IP autorizada):

   ```bash
   pg_dump -h 127.0.0.1 -U TU_USER -d laslocas_dbng -Fc -f laslocas.dump
   ```

2. Importar en Neon (misma URL con `sslmode=require`):

   ```bash
   pg_restore -d "$DATABASE_URL" --no-owner --no-acl -j 4 laslocas.dump
   ```

3. Si la base en Neon ya tiene tablas vacías del paso anterior, usá `--clean` solo si entendés que borra objetos existentes, o restaurá en un branch/proyecto Neon nuevo.

4. Tras importar con datos viejos, alinear Alembic:

   ```bash
   python3 -m alembic stamp head
   ```

## Secret Manager (producción)

Crear o actualizar el secreto `DATABASE_URL` con la URL pooler de Neon. En `cloudbuild.yaml`, inyectar `DATABASE_URL` en Cloud Run y eliminar variables solo-Cloud-SQL si ya no aplican.

## Verificación rápida

```bash
export DATABASE_URL='postgresql+psycopg2://...'
python3 -c "
from sqlalchemy import create_engine, text
from database.db_url import build_database_url
e = create_engine(build_database_url())
with e.connect() as c:
    print(c.execute(text('SELECT version()')).scalar()[:60])
    print('tables', c.execute(text(\"SELECT count(*) FROM information_schema.tables WHERE table_schema='public'\")).scalar())
"
```
