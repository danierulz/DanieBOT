-- Categorías + flags de Sale en products. Idempotente para bases ya creadas.

CREATE TABLE IF NOT EXISTS categories (
    category_id SERIAL PRIMARY KEY,
    slug VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS ix_categories_slug ON categories (slug);

ALTER TABLE products ADD COLUMN IF NOT EXISTS category_id INTEGER
    REFERENCES categories(category_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_products_category_id ON products (category_id);

ALTER TABLE products ADD COLUMN IF NOT EXISTS is_sale BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS discount_percent INTEGER;

INSERT INTO categories (slug, name, sort_order, activo) VALUES
    ('jeans', 'Jeans', 10, TRUE),
    ('pantalones', 'Pantalones', 20, TRUE),
    ('remeras', 'Remeras', 30, TRUE),
    ('camisas', 'Camisas', 40, TRUE),
    ('blusas', 'Blusas', 50, TRUE),
    ('camperas', 'Camperas', 60, TRUE),
    ('vestidos', 'Vestidos', 70, TRUE),
    ('polleras', 'Polleras', 80, TRUE),
    ('buzos', 'Buzos', 90, TRUE),
    ('accesorios', 'Accesorios', 100, TRUE)
ON CONFLICT (slug) DO NOTHING;
