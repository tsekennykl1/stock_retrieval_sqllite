import sqlite3
print(sqlite3.sqlite_version)  # Should be 3.31.0+ for generated columns

def get_connection():
    """Establish and return a connection to the SQLite database."""
    conn = sqlite3.connect("mystocks.db")
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    """Create all stock portfolio tables."""
    conn = get_connection()
    
    # Enable foreign keys for SQLite
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # ── Table 1: Stocks (Master list of stocks) ──────────────────---────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            symbol      TEXT PRIMARY KEY,        -- e.g. AAPL, TSLA (Now the PK)
            name        TEXT NOT NULL,           -- e.g. Apple Inc.
            sector      TEXT,                    -- e.g. Technology
            currency    TEXT DEFAULT 'HKD',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Table 2: Portfolio (Your holdings) ───────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trading_date   DATETIME DEFAULT CURRENT_TIMESTAMP,
            stock_symbol    TEXT NOT NULL,
            quantity        REAL NOT NULL,
            avg_buy_price   REAL NOT NULL,
            total_invested  REAL GENERATED ALWAYS AS (quantity * avg_buy_price) VIRTUAL,
            transaction_reference_id INTEGER,
            FOREIGN KEY (stock_symbol) REFERENCES stocks(symbol) ON DELETE CASCADE,
            FOREIGN KEY (transaction_reference_id) REFERENCES transactions(id) ON DELETE CASCADE
        )
    """)

    # ── Table 3: Transactions (Buy/Sell history) ──────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_symbol    TEXT NOT NULL,
            type            TEXT NOT NULL CHECK(type IN ('BUY', 'SELL')),
            quantity        REAL NOT NULL,
            price           REAL NOT NULL,
            total_amount    REAL GENERATED ALWAYS AS (quantity * price) VIRTUAL,
            transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            transaction_month_str  TEXT,
            notes           TEXT,
            FOREIGN KEY (stock_symbol) REFERENCES stocks(symbol) ON DELETE CASCADE
        )
    """)

    # ── Table 4: Watchlist (Stocks you are watching) ─────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_symbol TEXT NOT NULL UNIQUE,
            target_price REAL,
            notes       TEXT,
            added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stock_symbol) REFERENCES stocks(symbol) ON DELETE CASCADE
        )
    """)


    # ── Table 5: Dividends (Dividend income tracking) ────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dividends (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_symbol    TEXT NOT NULL,
            amount_per_share REAL NOT NULL,
            quantity        REAL NOT NULL,
            total_dividend  REAL GENERATED ALWAYS AS (amount_per_share * quantity) VIRTUAL,
            ex_dividend_date DATETIME,
            payment_date    DATETIME DEFAULT CURRENT_TIMESTAMP,
            payment_month_str  TEXT,
            FOREIGN KEY (stock_symbol) REFERENCES stocks(symbol) ON DELETE CASCADE
        )
    """)

    # ── Table 6: Monthly performance  ────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            year_month TEXT NOT NULL,
            stock_symbol TEXT NOT NULL,
            start_quantity REAL NOT NULL,
            start_price REAL NOT NULL,
            FOREIGN KEY (stock_symbol) REFERENCES stocks(symbol) ON DELETE CASCADE,
            UNIQUE(year_month, stock_symbol)
        )
    """)

    # ── Table 7: Monthly P&L table  ────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_pnl (
            pnl_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            year_month TEXT NOT NULL PRIMARY KEY,
            open_bal REAL NOT NULL DEFAULT 0,
            income REAL DEFAULT 0,
            expenses REAL DEFAULT 0,
            stock_pnl REAL DEFAULT 0,
            dividend REAL DEFAULT 0,
            monthly_gl REAL GENERATED ALWAYS AS (income + expenses + stock_pnl + dividend) VIRTUAL,
            close_bal REAL GENERATED ALWAYS AS (open_bal + monthly_gl) VIRTUAL
        )
    """)
    
    # ── Table 8: Mortgage Monthly Table ────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mortgage (
            period DATETIME DEFAULT CURRENT_TIMESTAMP,
            year_month TEXT NOT NULL PRIMARY KEY,
            principal REAL NOT NULL,
            interest REAL NOT NULL,
            total_payment REAL GENERATED ALWAYS AS (principal + interest) VIRTUAL,
            remaining_balance REAL NOT NULL
        )
    """)
    
    # ── Table 9: Ledger (Income/Expense tracking) ────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime    DATETIME DEFAULT CURRENT_TIMESTAMP,
            month_str   TEXT,
            type        TEXT NOT NULL CHECK(type IN ('I', 'E')),  -- I: Income, E: Expense
            category    TEXT NOT NULL,
            amount      REAL NOT NULL,
            comment     TEXT
        )
    """)


    conn.commit()
    conn.close()
    print("✅ All tables created successfully!")

if __name__ == "__main__":
    create_tables()
    #conn = sqlite3.connect("your_database.db")
    #cursor = conn.cursor()
    #cursor.execute("SELECT sql FROM sqlite_master WHERE name = 'mortgage';")
    #print(cursor.fetchone())

    print("\n🎉 Database setup complete!")
    