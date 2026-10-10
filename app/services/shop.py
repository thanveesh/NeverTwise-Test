import sqlite3

from app.models import Order, OrderCreate, Product, ProductCreate, ProductUpdate


class ShopError(Exception):
    status_code = 400


class ProductNotFound(ShopError):
    status_code = 404


class InsufficientInventory(ShopError):
    status_code = 409


def _product(row: sqlite3.Row) -> Product:
    return Product(**dict(row))


def create_product(connection: sqlite3.Connection, payload: ProductCreate) -> Product:
    cursor = connection.execute(
        "INSERT INTO products (name, description, price_cents, quantity) VALUES (?, ?, ?, ?)",
        (payload.name, payload.description, payload.price_cents, payload.quantity),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM products WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return _product(row)


def list_products(connection: sqlite3.Connection) -> list[Product]:
    rows = connection.execute("SELECT * FROM products ORDER BY id").fetchall()
    return [_product(row) for row in rows]


def get_product(connection: sqlite3.Connection, product_id: int) -> Product:
    row = connection.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if row is None:
        raise ProductNotFound(f"Product {product_id} was not found")
    return _product(row)


def update_product(
    connection: sqlite3.Connection, product_id: int, payload: ProductUpdate
) -> Product:
    get_product(connection, product_id)
    values = payload.model_dump(exclude_unset=True)
    if values:
        assignments = ", ".join(f"{key} = ?" for key in values)
        connection.execute(
            f"UPDATE products SET {assignments} WHERE id = ?",
            (*values.values(), product_id),
        )
        connection.commit()
    return get_product(connection, product_id)


def create_order(connection: sqlite3.Connection, payload: OrderCreate) -> Order:
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM products WHERE id = ?", (payload.product_id,)
        ).fetchone()
        if row is None:
            raise ProductNotFound(f"Product {payload.product_id} was not found")

        connection.execute(
            "UPDATE products SET quantity = quantity - ? WHERE id = ?",
            (payload.quantity, payload.product_id),
        )
        cursor = connection.execute(
            "INSERT INTO orders (product_id, quantity, total_cents) VALUES (?, ?, ?)",
            (payload.product_id, payload.quantity, payload.quantity * row["price_cents"]),
        )
        connection.commit()
        return Order(
            id=cursor.lastrowid,
            product_id=payload.product_id,
            quantity=payload.quantity,
            total_cents=payload.quantity * row["price_cents"],
        )
    except Exception:
        connection.rollback()
        raise
