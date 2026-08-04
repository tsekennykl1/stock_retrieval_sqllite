import sqlite3
import os

DB_NAME = "mystocks.db"

def get_connection():
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def create_tables():
    """Create all stock portfolio tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # ── Table 1: Stocks (Master list of stocks) ──────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT NOT NULL UNIQUE,   -- e.g. AAPL, TSLA
            name        TEXT NOT NULL,           -- e.g. Apple Inc.
            exchange    TEXT,                    -- e.g. NASDAQ, NYSE
            sector      TEXT,                    -- e.g. Technology
            currency    TEXT DEFAULT 'USD',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Table 2: Portfolio (Your holdings) ───────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id        INTEGER NOT NULL,
            quantity        REAL NOT NULL,
            avg_buy_price   REAL NOT NULL,
            total_invested  REAL GENERATED ALWAYS AS (quantity * avg_buy_price) VIRTUAL,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stock_id) REFERENCES stocks(id)
        )
    """)

    # ── Table 3: Transactions (Buy/Sell history) ──────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id        INTEGER NOT NULL,
            type            TEXT NOT NULL CHECK(type IN ('BUY', 'SELL')),
            quantity        REAL NOT NULL,
            price           REAL NOT NULL,
            total_amount    REAL GENERATED ALWAYS AS (quantity * price) VIRTUAL,
            transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes           TEXT,
            FOREIGN KEY (stock_id) REFERENCES stocks(id)
        )
    """)

    # ── Table 4: Watchlist (Stocks you are watching) ─────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id    INTEGER NOT NULL UNIQUE,
            target_price REAL,
            notes       TEXT,
            added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stock_id) REFERENCES stocks(id)
        )
    """)

    # ── Table 5: Dividends (Dividend income tracking) ────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dividends (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id        INTEGER NOT NULL,
            amount_per_share REAL NOT NULL,
            quantity        REAL NOT NULL,
            total_dividend  REAL GENERATED ALWAYS AS (amount_per_share * quantity) VIRTUAL,
            payment_date    DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stock_id) REFERENCES stocks(id)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ All tables created successfully!")


# ══════════════════════════════════════════════════════════════
#  STOCKS CRUD
# ══════════════════════════════════════════════════════════════

def insert_stock(symbol, name, exchange=None, sector=None, currency='USD'):
    """Insert a new stock into the stocks table."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO stocks (symbol, name, exchange, sector, currency)
            VALUES (?, ?, ?, ?, ?)
        """, (symbol.upper(), name, exchange, sector, currency))
        conn.commit()
        print(f"✅ Stock '{symbol.upper()}' inserted successfully!")
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        print(f"⚠️  Stock '{symbol.upper()}' already exists!")
        return None
    finally:
        conn.close()

def update_stock(symbol, name=None, exchange=None, sector=None, currency=None):
    """Update an existing stock's details."""
    conn = get_connection()
    cursor = conn.cursor()
    fields, values = [], []
    if name:     fields.append("name = ?");     values.append(name)
    if exchange: fields.append("exchange = ?"); values.append(exchange)
    if sector:   fields.append("sector = ?");   values.append(sector)
    if currency: fields.append("currency = ?"); values.append(currency)
    if not fields:
        print("⚠️  No fields to update!")
        return
    values.append(symbol.upper())
    cursor.execute(f"UPDATE stocks SET {', '.join(fields)} WHERE symbol = ?", values)
    conn.commit()
    print(f"✅ Stock '{symbol.upper()}' updated successfully!")
    conn.close()

def delete_stock(symbol):
    """Delete a stock by symbol."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stocks WHERE symbol = ?", (symbol.upper(),))
    conn.commit()
    print(f"🗑️  Stock '{symbol.upper()}' deleted!")
    conn.close()

def get_all_stocks():
    """Retrieve all stocks."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stocks")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ══════════════════════════════════════════════════════════════
#  PORTFOLIO CRUD
# ══════════════════════════════════════════════════════════════

def insert_portfolio(symbol, quantity, avg_buy_price):
    """Add a stock holding to the portfolio."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM stocks WHERE symbol = ?", (symbol.upper(),))
    stock = cursor.fetchone()
    if not stock:
        print(f"⚠️  Stock '{symbol.upper()}' not found! Please insert it first.")
        conn.close()
        return
    cursor.execute("""
        INSERT INTO portfolio (stock_id, quantity, avg_buy_price)
        VALUES (?, ?, ?)
    """, (stock["id"], quantity, avg_buy_price))
    conn.commit()
    print(f"✅ Portfolio entry for '{symbol.upper()}' added!")
    conn.close()

def update_portfolio(symbol, quantity=None, avg_buy_price=None):
    """Update portfolio holding for a stock."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM stocks WHERE symbol = ?", (symbol.upper(),))
    stock = cursor.fetchone()
    if not stock:
        print(f"⚠️  Stock '{symbol.upper()}' not found!")
        conn.close()
        return
    fields, values = [], []
    if quantity:      fields.append("quantity = ?");      values.append(quantity)
    if avg_buy_price: fields.append("avg_buy_price = ?"); values.append(avg_buy_price)
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(stock["id"])
    cursor.execute(f"UPDATE portfolio SET {', '.join(fields)} WHERE stock_id = ?", values)
    conn.commit()
    print(f"✅ Portfolio for '{symbol.upper()}' updated!")
    conn.close()

def delete_portfolio(symbol):
    """Remove a stock from the portfolio."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM stocks WHERE symbol = ?", (symbol.upper(),))
    stock = cursor.fetchone()
    if not stock:
        print(f"⚠️  Stock '{symbol.upper()}' not found!")
        conn.close()
        return
    cursor.execute("DELETE FROM portfolio WHERE stock_id = ?", (stock["id"],))
    conn.commit()
    print(f"🗑️  '{symbol.upper()}' removed from portfolio!")
    conn.close()

def get_portfolio():
    """Get full portfolio with stock details."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.symbol, s.name, s.sector, p.quantity,
               p.avg_buy_price, p.total_invested, p.updated_at
        FROM portfolio p
        JOIN stocks s ON p.stock_id = s.id
        ORDER BY p.total_invested DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ══════════════════════════════════════════════════════════════
#  TRANSACTIONS CRUD
# ══════════════════════════════════════════════════════════════

def insert_transaction(symbol, type, quantity, price, notes=None):
    """Record a BUY or SELL transaction."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM stocks WHERE symbol = ?", (symbol.upper(),))
    stock = cursor.fetchone()
    if not stock:
        print(f"⚠️  Stock '{symbol.upper()}' not found!")
        conn.close()
        return
    cursor.execute("""
        INSERT INTO transactions (stock_id, type, quantity, price, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (stock["id"], type.upper(), quantity, price, notes))
    conn.commit()
    print(f"✅ {type.upper()} transaction for '{symbol.upper()}' recorded!")
    conn.close()

def delete_transaction(transaction_id):
    """Delete a transaction by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    conn.commit()
    print(f"🗑️  Transaction ID {transaction_id} deleted!")
    conn.close()

def get_transactions(symbol=None):
    """Get all transactions, optionally filtered by stock symbol."""
    conn = get_connection()
    cursor = conn.cursor()
    if symbol:
        cursor.execute("""
            SELECT t.id, s.symbol, t.type, t.quantity, t.price,
                   t.total_amount, t.transaction_date, t.notes
            FROM transactions t
            JOIN stocks s ON t.stock_id = s.id
            WHERE s.symbol = ?
            ORDER BY t.transaction_date DESC
        """, (symbol.upper(),))
    else:
        cursor.execute("""
            SELECT t.id, s.symbol, t.type, t.quantity, t.price,
                   t.total_amount, t.transaction_date, t.notes
            FROM transactions t
            JOIN stocks s ON t.stock_id = s.id
            ORDER BY t.transaction_date DESC
        """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ══════════════════════════════════════════════════════════════
#  WATCHLIST CRUD
# ══════════════════════════════════════════════════════════════

def insert_watchlist(symbol, target_price=None, notes=None):
    """Add a stock to the watchlist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM stocks WHERE symbol = ?", (symbol.upper(),))
    stock = cursor.fetchone()
    if not stock:
        print(f"⚠️  Stock '{symbol.upper()}' not found!")
        conn.close()
        return
    cursor.execute("""
        INSERT OR IGNORE INTO watchlist (stock_id, target_price, notes)
        VALUES (?, ?, ?)
    """, (stock["id"], target_price, notes))
    conn.commit()
    print(f"✅ '{symbol.upper()}' added to watchlist!")
    conn.close()

def delete_watchlist(symbol):
    """Remove a stock from the watchlist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM stocks WHERE symbol = ?", (symbol.upper(),))
    stock = cursor.fetchone()
    if not stock:
        print(f"⚠️  Stock '{symbol.upper()}' not found!")
        conn.close()
        return
    cursor.execute("DELETE FROM watchlist WHERE stock_id = ?", (stock["id"],))
    conn.commit()
    print(f"🗑️  '{symbol.upper()}' removed from watchlist!")
    conn.close()

def get_watchlist():
    """Get all watchlist entries."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.symbol, s.name, w.target_price, w.notes, w.added_at
        FROM watchlist w
        JOIN stocks s ON w.stock_id = s.id
        ORDER BY w.added_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ══════════════════════════════════════════════════════════════
#  DIVIDENDS CRUD
# ══════════════════════════════════════════════════════════════

def insert_dividend(symbol, amount_per_share, quantity):
    """Record a dividend payment."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM stocks WHERE symbol = ?", (symbol.upper(),))
    stock = cursor.fetchone()
    if not stock:
        print(f"⚠️  Stock '{symbol.upper()}' not found!")
        conn.close()
        return
    cursor.execute("""
        INSERT INTO dividends (stock_id, amount_per_share, quantity)
        VALUES (?, ?, ?)
    """, (stock["id"], amount_per_share, quantity))
    conn.commit()
    print(f"✅ Dividend for '{symbol.upper()}' recorded!")
    conn.close()

def get_dividends(symbol=None):
    """Get all dividends, optionally filtered by symbol."""
    conn = get_connection()
    cursor = conn.cursor()
    if symbol:
        cursor.execute("""
            SELECT s.symbol, d.amount_per_share, d.quantity,
                   d.total_dividend, d.payment_date
            FROM dividends d
            JOIN stocks s ON d.stock_id = s.id
            WHERE s.symbol = ?
            ORDER BY d.payment_date DESC
        """, (symbol.upper(),))
    else:
        cursor.execute("""
            SELECT s.symbol, d.amount_per_share, d.quantity,
                   d.total_dividend, d.payment_date
            FROM dividends d
            JOIN stocks s ON d.stock_id = s.id
            ORDER BY d.payment_date DESC
        """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ══════════════════════════════════════════════════════════════
#  SEED SAMPLE DATA & MAIN
# ══════════════════════════════════════════════════════════════

def seed_sample_data():
    """Insert sample data for testing."""
    # Stocks
    insert_stock("AAPL", "Apple Inc.",       "NASDAQ", "Technology")
    insert_stock("TSLA", "Tesla Inc.",        "NASDAQ", "Automotive")
    insert_stock("MSFT", "Microsoft Corp.",   "NASDAQ", "Technology")
    insert_stock("AMZN", "Amazon.com Inc.",   "NASDAQ", "E-Commerce")

    # Portfolio
    insert_portfolio("AAPL", 10, 175.50)
    insert_portfolio("TSLA", 5,  245.00)
    insert_portfolio("MSFT", 8,  415.00)

    # Transactions
    insert_transaction("AAPL", "BUY",  10, 175.50, "Initial purchase")
    insert_transaction("TSLA", "BUY",  5,  245.00, "Initial purchase")
    insert_transaction("MSFT", "SELL", 2,  420.00, "Partial profit taking")

    # Watchlist
    insert_watchlist("AMZN", target_price=180.00, notes="Waiting for dip")

    # Dividends
    insert_dividend("AAPL", 0.24, 10)
    insert_dividend("MSFT", 0.75, 8)

    print("\n✅ Sample data seeded successfully!")


if __name__ == "__main__":
    create_tables()
    seed_sample_data()

    print("\n📊 Portfolio:")
    for row in get_portfolio():
        print(row)

    print("\n📈 Transactions:")
    for row in get_transactions():
        print(row)

    print("\n👀 Watchlist:")
    for row in get_watchlist():
        print(row)

    print("\n💰 Dividends:")
    for row in get_dividends():
        print(row)
