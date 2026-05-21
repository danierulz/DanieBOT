-- Pedidos, clientes y eventos (bases existentes)

CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    wa_id VARCHAR(32) UNIQUE,
    phone VARCHAR(50),
    display_name VARCHAR(200),
    email VARCHAR(255),
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    marketing_email_consent BOOLEAN NOT NULL DEFAULT FALSE,
    marketing_email_consent_at TIMESTAMP,
    marketing_whatsapp_consent BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS ix_customers_wa_id ON customers (wa_id);

ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_code VARCHAR(32) UNIQUE;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_id INTEGER REFERENCES customers(customer_id);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS whatsapp_wa_id VARCHAR(32);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS source VARCHAR(32) DEFAULT 'web';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS channel VARCHAR(32) DEFAULT 'wa_me';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS cart_snapshot JSONB;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_orders_order_code ON orders (order_code);
CREATE INDEX IF NOT EXISTS ix_orders_whatsapp_wa_id ON orders (whatsapp_wa_id);

ALTER TABLE order_items ADD COLUMN IF NOT EXISTS title_snapshot VARCHAR(255);

CREATE TABLE IF NOT EXISTS order_events (
    event_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS ix_order_events_order_id ON order_events (order_id);
