-- Ejecutar contra una base existente si ya tenías tablas sin estas columnas/tablas.
-- Instalaciones nuevas: SQLAlchemy create_all crea el esquema desde los modelos.

CREATE TABLE IF NOT EXISTS sizes (
    size_id SERIAL PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    label VARCHAR(64) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_sizes_code ON sizes (code);

CREATE TABLE IF NOT EXISTS product_variants (
    variant_id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    size_id INTEGER NOT NULL REFERENCES sizes(size_id),
    qty_stock_local INTEGER NOT NULL DEFAULT 0,
    encargo_habilitado BOOLEAN NOT NULL DEFAULT FALSE,
    dias_encargo_estimados INTEGER,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_product_variants_product_size UNIQUE (product_id, size_id)
);

CREATE INDEX IF NOT EXISTS ix_product_variants_product_id ON product_variants (product_id);
CREATE INDEX IF NOT EXISTS ix_product_variants_size_id ON product_variants (size_id);

ALTER TABLE order_items ADD COLUMN IF NOT EXISTS variant_id INTEGER REFERENCES product_variants(variant_id) ON DELETE SET NULL;
