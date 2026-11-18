-- Relational schema for hijab retail transactions (PostgreSQL)

CREATE TABLE customers (
    customer_id  INTEGER PRIMARY KEY,
    signup_date  DATE NOT NULL,
    region       TEXT NOT NULL
);

CREATE TABLE products (
    product_id   INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    fabric       TEXT NOT NULL,
    colour       TEXT NOT NULL,
    unit_price   NUMERIC(10, 2) NOT NULL
);

CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date   DATE NOT NULL,
    order_month  TEXT NOT NULL,         -- 'YYYY-MM', kept for portable monthly grouping
    collection   TEXT NOT NULL          -- seasonal collection the order falls in
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id),
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    sale_price    NUMERIC(10, 2) NOT NULL, -- price paid per unit after discount
    returned_quantity INTEGER NOT NULL DEFAULT 0
        CHECK (returned_quantity BETWEEN 0 AND quantity)
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_items_order     ON order_items(order_id);
CREATE INDEX idx_items_product   ON order_items(product_id);
