import sqlite3
from datetime import datetime, timedelta
from calendar import monthrange
import os

# Dynamically set DB path (Defaults to local mystocks.db, overwritten in Lambda)
DB_PATH = "mystocks.db"
if "AWS_LAMBDA_FUNCTION_NAME" in os.environ:
    DB_PATH = os.environ.get("DB_PATH", "/tmp/mystocks.db")

from datetime import datetime

def normalize_date(date_val):
    """Convert date value to 'YYYY-MM-DD' string, handling multiple formats."""
    if not date_val:
        return ""
    if isinstance(date_val, datetime):
        return date_val.strftime("%Y-%m-%d")
    s = str(date_val).strip()
    # Already in YYYY-MM-DD format (possibly with time appended)
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        return s[:10]
    # Try M/D/YYYY or MM/DD/YYYY format
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Fallback: return as-is
    return s

def normalize_rows(rows, date_fields):
    """Normalize date fields in a list of row dicts to 'YYYY-MM-DD' format."""
    result = []
    for row in rows:
        row_copy = dict(row)
        for field in date_fields:
            if field in row_copy and row_copy[field]:
                row_copy[field] = normalize_date(row_copy[field])
        result.append(row_copy)
    return result

def get_month_str(_date=None):
    """Convert a date to ('YYYY-MM-DD', 'YYYY-MM') tuple."""
    if _date:
        if isinstance(_date, datetime):
            return _date.strftime("%Y-%m-%d"), _date.strftime("%Y-%m")

        if isinstance(_date, str):
            # Normalize the date first
            normalized = normalize_date(_date)
            if normalized and len(normalized) >= 7:
                return normalized, normalized[:7]
            # Try other formats for month extraction
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"):
                try:
                    dt = datetime.strptime(_date, fmt)
                    return dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m")
                except ValueError:
                    continue
            # Try M/D/YYYY formats
            for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
                try:
                    dt = datetime.strptime(_date, fmt)
                    return dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m")
                except ValueError:
                    continue
            raise ValueError(f"Invalid date format: {_date}")
        else:
            raise ValueError("Invalid date format")
    now = datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")

def convertYearMonth(year_month):
    """Convert 'YYYY-MM' to the last day of that month in 'YYYY-MM-DD' format."""
    year, month = map(int, year_month.split('-'))
    last_day = monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-{last_day:02d}"

def get_connection():
    """Establish and return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ══════════════════════════════════════════════════════════════
#  STOCKS CRUD
# ══════════════════════════════════════════════════════════════
def get_stock(symbol):
    """Retrieve a stock's details by its symbol."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, name, sector, currency
        FROM stocks
        WHERE symbol = ?
    """, (symbol.upper(),))
    stock = cursor.fetchone()
    conn.close()
    if stock:
        return dict(stock)
    else:
        print(f"⚠️  Stock '{symbol.upper()}' not found!")
        return None

def insert_stock(symbol, name, sector=None, currency="HKD"):
    """Insert a new stock into the stocks table."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO stocks (symbol, name, sector, currency)
            VALUES (?, ?, ?, ?)
        """, (symbol.upper(), name, sector, currency))
        conn.commit()
        print(f"✅ Stock '{symbol.upper()}' added!")
        return {"symbol": symbol.upper(), "name": name, "sector": sector, "currency": currency}
    except sqlite3.IntegrityError:
        print(f"⚠️  Stock '{symbol.upper()}' already exists!")
        return None
    finally:
        conn.close()

def update_stock(symbol, name=None, sector=None, currency=None):
    """Update an existing stock's details."""
    conn = get_connection()
    cursor = conn.cursor()
    fields, values = [], []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if sector is not None:
        fields.append("sector = ?")
        values.append(sector)
    if currency is not None:
        fields.append("currency = ?")
        values.append(currency)
    
    if not fields:
        print("⚠️  No fields to update!")
        return
    
    values.append(symbol.upper())
    cursor.execute(f"""
        UPDATE stocks
        SET {', '.join(fields)}
        WHERE symbol = ?
    """, values)
    if cursor.rowcount == 0:
        print(f"⚠️  Stock '{symbol.upper()}' not found!")
    else:
        print(f"✅ Stock '{symbol.upper()}' updated successfully!")
    conn.commit()
    conn.close()

def delete_stock(symbol):
    """Delete a stock by its symbol."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM stocks
        WHERE symbol = ?
    """, (symbol.upper(),))
    conn.commit()
    if cursor.rowcount == 0:
        print(f"⚠️  Stock '{symbol.upper()}' not found!")
    else:
        print(f"🗑️  Stock '{symbol.upper()}' deleted successfully!")
    conn.close()

# ══════════════════════════════════════════════════════════════
#  PORTFOLIO CRUD
# ══════════════════════════════════════════════════════════════
def insert_portfolio(symbol, quantity, avg_buy_price, trading_date, transaction_reference_id=None):
    """Add a stock holding to the portfolio with an optional transaction reference ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        trading_date = normalize_date(trading_date) or datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO portfolio (stock_symbol, quantity, avg_buy_price, trading_date, transaction_reference_id)
            VALUES (?, ?, ?, ?, ?)
        """, (symbol.upper(), quantity, avg_buy_price, trading_date, transaction_reference_id))
        conn.commit()
        print(f"✅ Portfolio entry for '{symbol.upper()}' added!")
    except sqlite3.IntegrityError:
        print(f"⚠️  Stock '{symbol.upper()}' not found in stocks table (or already exists)!")
    finally:
        conn.close()

def update_portfolio(portfolio_id, quantity=None, avg_buy_price=None, trading_date=None, transaction_reference_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    fields = []
    values = []

    if quantity is not None:
        fields.append("quantity = ?")
        values.append(quantity)
    if avg_buy_price is not None:
        fields.append("avg_buy_price = ?")
        values.append(avg_buy_price)
    if trading_date is not None:
        fields.append("trading_date = ?")
        values.append(normalize_date(trading_date))
    if transaction_reference_id is not None:
        fields.append("transaction_reference_id = ?")
        values.append(transaction_reference_id)

    if not fields:
        return {"message": "Nothing to update"}

    values.append(portfolio_id)
    cursor.execute(f"UPDATE portfolio SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()

    return {"message": f"Portfolio entry {portfolio_id} updated", "rows_affected": cursor.rowcount}


def delete_portfolio(portfolio_id):
    """Remove a stock from the portfolio."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM portfolio WHERE id = ?", (portfolio_id,))
    conn.commit()
    print(f"🗑️  Portfolio entry with ID '{portfolio_id}' removed!")
    conn.close()

def get_all_portfolio_entries():
    """Get all portfolio entries, including historical ones."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, stock_symbol, quantity, avg_buy_price, total_invested, trading_date, transaction_reference_id
        FROM portfolio
        ORDER BY trading_date DESC, stock_symbol
    """)
    rows = cursor.fetchall()
    conn.close()
    return normalize_rows([dict(row) for row in rows], ["trading_date"])

def get_portfolio():
    """Get full portfolio with stock details."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT stock_symbol, quantity, avg_buy_price, total_invested
        FROM portfolio
        WHERE trading_date = (
            SELECT MAX(trading_date)
            FROM portfolio AS sub
            WHERE sub.stock_symbol = portfolio.stock_symbol
        )
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_latest_portfolio():
    """Get all portfolio symbols with the latest trading_date, stock name, average price, and quantity > 0."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id,stock_symbol,
            trading_date AS latest_trading_date,
            quantity,
            avg_buy_price AS average_price,
            total_invested
        FROM (
        SELECT p.*,
                ROW_NUMBER() OVER (
                PARTITION BY stock_symbol
                ORDER BY id DESC
                ) AS rn
        FROM portfolio p
        )
        WHERE rn = 1
        AND quantity > 0
        ORDER BY latest_trading_date DESC, stock_symbol
    """)
    rows = cursor.fetchall()
    conn.close()
    return normalize_rows([dict(row) for row in rows], ["latest_trading_date"])

# ══════════════════════════════════════════════════════════════
#  TRANSACTIONS CRUD
# ══════════════════════════════════════════════════════════════

def insert_transaction(symbol, type, quantity, price, notes=None, transaction_date=None):
    """
    Record a BUY or SELL transaction.
    
    This is a pure CRUD operation — it only inserts the transaction record.
    Portfolio adjustments are handled by the transaction_service layer.
    
    Returns:
        dict with transaction details including the new transaction_id, or None on failure.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        transaction_date, transaction_month_str = get_month_str(transaction_date)

        cursor.execute("""
            INSERT INTO transactions (stock_symbol, type, quantity, price, notes, transaction_date, transaction_month_str)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (symbol.upper(), type.upper(), quantity, price, notes, transaction_date, transaction_month_str))

        conn.commit()
        # ┌──────────────────────────────────────────────────────────────┐
        # │  NEW: Capture lastrowid and return a structured dict         │
        # └──────────────────────────────────────────────────────────────┘
        transaction_id = cursor.lastrowid
        print(f"✅ {type.upper()} transaction for '{symbol.upper()}' recorded! (ID: {transaction_id})")

        return {
            "transaction_id": transaction_id,
            "symbol": symbol.upper(),
            "type": type.upper(),
            "quantity": quantity,
            "price": price,
            "transaction_date": transaction_date,
            "transaction_month_str": transaction_month_str,
            "notes": notes,
        }
    except sqlite3.IntegrityError:
        print(f"⚠️  Stock '{symbol.upper()}' not found in stocks table!")
        return None
    finally:
        conn.close()

def update_transaction(transaction_id, type=None, quantity=None, price=None, notes=None, transaction_date=None):
    """Update an existing transaction entry."""
    conn = get_connection()
    cursor = conn.cursor()
    fields, values = [], []
    
    if type is not None:
        fields.append("type = ?")
        values.append(type.upper())
    if quantity is not None:
        fields.append("quantity = ?")
        values.append(quantity)
    if price is not None:
        fields.append("price = ?")
        values.append(price)
    if notes is not None:
        fields.append("notes = ?")
        values.append(notes)
    if transaction_date is not None:
        transaction_date, transaction_month_str = get_month_str(transaction_date)
        fields.append("transaction_date = ?")
        values.append(transaction_date)
        fields.append("transaction_month_str = ?")
        values.append(transaction_month_str)
        
    if not fields:
        print("⚠️  No fields to update!")
        return
        
    values.append(transaction_id)
    cursor.execute(f"""
        UPDATE transactions
        SET {', '.join(fields)}
        WHERE id = ?
    """, values)
    
    if cursor.rowcount == 0:
        print(f"⚠️  Transaction entry with ID '{transaction_id}' not found!")
    else:
        print(f"✅ Transaction entry with ID '{transaction_id}' updated!")
        
    conn.commit()
    conn.close()

def delete_transaction(transaction_id):
    """Delete a transaction by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    conn.commit()
    if cursor.rowcount == 0:
        print(f"⚠️  Transaction ID {transaction_id} not found!")
    else:
        print(f"🗑️  Transaction ID {transaction_id} deleted!")
    conn.close()

def get_transactions(year_month, symbol=None):
    """Get all transactions, filtered by month (YYYY-MM) and optionally by symbol."""
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT t.id, t.stock_symbol as symbol, t.type, t.quantity, t.price,
               t.total_amount, t.transaction_date, t.transaction_month_str, t.notes
        FROM transactions t
        WHERE t.transaction_month_str = ?
    """
    params = [year_month]
    if symbol:
        query += " AND t.stock_symbol = ?"
        params.append(symbol.upper())
        
    query += " ORDER BY t.transaction_date DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return normalize_rows([dict(row) for row in rows], ["transaction_date"])

# ══════════════════════════════════════════════════════════════
#  WATCHLIST CRUD
# ══════════════════════════════════════════════════════════════

def insert_watchlist(symbol, target_price=None, notes=None):
    """Add a stock to the watchlist."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO watchlist (stock_symbol, target_price, notes)
            VALUES (?, ?, ?)
        """, (symbol.upper(), target_price, notes))
        conn.commit()
        print(f"✅ '{symbol.upper()}' added to watchlist!")
    except sqlite3.IntegrityError:
        print(f"⚠️  Stock '{symbol.upper()}' not found in stocks table!")
    finally:
        conn.close()

def update_watchlist(symbol, target_price=None, notes=None):
    """Update an existing watchlist entry."""
    conn = get_connection()
    cursor = conn.cursor()
    fields, values = [], []
    
    if target_price is not None:
        fields.append("target_price = ?")
        values.append(target_price)
    if notes is not None:
        fields.append("notes = ?")
        values.append(notes)
        
    if not fields:
        print("⚠️  No fields to update!")
        return
        
    values.append(symbol.upper())
    cursor.execute(f"""
        UPDATE watchlist
        SET {', '.join(fields)}
        WHERE stock_symbol = ?
    """, values)
    
    if cursor.rowcount == 0:
        print(f"⚠️  Watchlist entry for '{symbol.upper()}' not found!")
    else:
        print(f"✅ Watchlist entry for '{symbol.upper()}' updated!")
        
    conn.commit()
    conn.close()

def delete_watchlist(symbol):
    """Remove a stock from the watchlist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist WHERE stock_symbol = ?", (symbol.upper(),))
    conn.commit()
    conn.close()

def get_watchlist():
    """Get all watchlist entries."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.symbol, s.name, w.target_price, w.notes, w.added_at
        FROM watchlist w
        JOIN stocks s ON w.stock_symbol = s.symbol
        ORDER BY w.added_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return normalize_rows([dict(row) for row in rows], ["added_at"])


# ══════════════════════════════════════════════════════════════
#  DIVIDENDS CRUD
# ══════════════════════════════════════════════════════════════

def insert_dividend(symbol, amount_per_share, quantity, payment_date, ex_dividend_date=None):
    """Record a dividend payment with optional ex-dividend date."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        payment_date, payment_month_str = get_month_str(payment_date)
        ex_dividend_date = normalize_date(ex_dividend_date) if ex_dividend_date else None

        cursor.execute("""
            INSERT INTO dividends (stock_symbol, amount_per_share, quantity, payment_date, payment_month_str, ex_dividend_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (symbol.upper(), amount_per_share, quantity, payment_date, payment_month_str, ex_dividend_date))
        conn.commit()
        dividend_id = cursor.lastrowid
        print(f"✅ Dividend for '{symbol.upper()}' recorded! (ID: {dividend_id})")
        return {
            "dividend_id": dividend_id,
            "symbol": symbol.upper(),
            "amount_per_share": amount_per_share,
            "quantity": quantity,
            "total_dividend": amount_per_share * quantity,
            "payment_date": payment_date,
            "payment_month_str": payment_month_str,
            "ex_dividend_date": ex_dividend_date,
        }
    except sqlite3.IntegrityError:
        print(f"⚠️  Stock '{symbol.upper()}' not found in stocks table!")
        return None
    finally:
        conn.close()

def get_dividends(symbol=None, year_month=None):
    """Get all dividends, optionally filtered by symbol and/or month (YYYY-MM)."""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT id, stock_symbol as symbol, amount_per_share, quantity,
               total_dividend, payment_date, payment_month_str, ex_dividend_date
        FROM dividends
        WHERE 1=1
    """
    params = []

    if symbol:
        query += " AND stock_symbol = ?"
        params.append(symbol.upper())

    if year_month:
        query += " AND payment_month_str = ?"
        params.append(year_month)

    query += " ORDER BY payment_date DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return normalize_rows([dict(row) for row in rows], ["payment_date", "ex_dividend_date"])

def update_dividend(dividend_id, amount_per_share=None, quantity=None, payment_date=None, ex_dividend_date=None):
    """Update an existing dividend entry."""
    conn = get_connection()
    cursor = conn.cursor()
    fields, values = [], []
    if amount_per_share is not None:
        fields.append("amount_per_share = ?")
        values.append(amount_per_share)
    if quantity is not None:
        fields.append("quantity = ?")
        values.append(quantity)
    if payment_date is not None:
        payment_date = normalize_date(payment_date)
        fields.append("payment_date = ?")
        values.append(payment_date)
        # Update payment_month_str based on the normalized payment_date
        payment_month_str = payment_date[:7] if len(payment_date) >= 7 else ""
        fields.append("payment_month_str = ?")
        values.append(payment_month_str)
    if ex_dividend_date is not None:
        fields.append("ex_dividend_date = ?")
        values.append(normalize_date(ex_dividend_date))

    if not fields:
        print("⚠️  No fields to update!")
        return

    values.append(dividend_id)
    cursor.execute(f"""
        UPDATE dividends
        SET {', '.join(fields)}
        WHERE id = ?
    """, values)
    if cursor.rowcount == 0:
        print(f"⚠️  Dividend entry with ID '{dividend_id}' not found!")
    else:
        print(f"✅ Dividend entry with ID '{dividend_id}' updated!")
    conn.commit()
    conn.close()

def delete_dividend(dividend_id):
    """Delete a dividend entry by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dividends WHERE id = ?", (dividend_id,))
    conn.commit()
    if cursor.rowcount == 0:
        print(f"⚠️  Dividend entry with ID '{dividend_id}' not found!")
    else:
        print(f"🗑️  Dividend entry with ID '{dividend_id}' deleted!")
    conn.close()

# ══════════════════════════════════════════════════════════════
#  MONTHLY SNAPSHOTS CRUD
# ══════════════════════════════════════════════════════════════

def insert_monthly_snapshot(stock_symbol, start_quantity, start_price, year_month=None, snapshot_date=None):
    """Insert or update a monthly starting position."""
    conn = get_connection()
    cursor = conn.cursor()
    if snapshot_date is None:
        if year_month:
            snapshot_date = convertYearMonth(year_month)
        else:
            snapshot_date = datetime.now().strftime("%Y-%m-%d")
            year_month = datetime.now().strftime("%Y-%m")
    else: 
        snapshot_date, year_month = get_month_str(snapshot_date)
    cursor.execute("""
        INSERT OR REPLACE INTO monthly_snapshots (year_month, stock_symbol, start_quantity, start_price, snapshot_date)
        VALUES (?, ?, ?, ?, ?)
    """, (year_month, stock_symbol.upper(), start_quantity, start_price, snapshot_date))
    conn.commit()
    conn.close()


def get_monthly_snapshots(year_month=None, stock_symbol=None, snapshot_date=None):  
    """Get snapshots, optionally filtered by month and/or symbol."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT id, snapshot_date, year_month, stock_symbol, start_quantity, start_price
        FROM monthly_snapshots
        WHERE 1=1
    """
    params = []
    
    if year_month:
        query += " AND year_month = ?"
        params.append(year_month)
    if stock_symbol:
        query += " AND stock_symbol = ?"
        params.append(stock_symbol.upper())
    if snapshot_date:
        query += " AND snapshot_date >= ?"
        params.append(normalize_date(snapshot_date))
        
    query += " ORDER BY year_month DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return normalize_rows([dict(row) for row in rows], ["snapshot_date"])


def update_monthly_snapshot(year_month, stock_symbol, start_quantity=None, start_price=None, snapshot_date=None):
    """Update an existing monthly snapshot."""
    conn = get_connection()
    cursor = conn.cursor()
    fields, values = [], []
    if start_quantity is not None:
        fields.append("start_quantity = ?")
        values.append(start_quantity)
    if start_price is not None:
        fields.append("start_price = ?")
        values.append(start_price)
    if snapshot_date is not None:
        fields.append("snapshot_date = ?")
        values.append(normalize_date(snapshot_date))
        
    if not fields:
        print("⚠️  No fields to update!")
        return
        
    values.extend([year_month, stock_symbol.upper()])
    cursor.execute(f"""
        UPDATE monthly_snapshots
        SET {', '.join(fields)}
        WHERE year_month = ? AND stock_symbol = ?
    """, values)
    if cursor.rowcount == 0:
        print(f"⚠️  Snapshot for '{stock_symbol.upper()}' in '{year_month}' not found!")
    else:
        print(f"✅ Snapshot for '{stock_symbol.upper()}' in '{year_month}' updated!")
    conn.commit()
    conn.close()

def delete_monthly_snapshot(year_month, stock_symbol):
    """Delete a monthly snapshot."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM monthly_snapshots
        WHERE year_month = ? AND stock_symbol = ?
    """, (year_month, stock_symbol.upper()))
    conn.commit()
    if cursor.rowcount == 0:
        print(f"⚠️  Snapshot for '{stock_symbol.upper()}' in '{year_month}' not found!")
    else:
        print(f"🗑️  Snapshot for '{stock_symbol.upper()}' in '{year_month}' deleted!")
    conn.close()

# ══════════════════════════════════════════════════════════════
#  MONTHLY PNL CRUD
# ══════════════════════════════════════════════════════════════

def insert_monthly_pnl(open_bal, income, expenses, stock_pnl, dividend, year_month=None, pnl_date=None):
    """Insert or update a monthly PnL entry."""
    
    conn = get_connection()
    cursor = conn.cursor()
    if pnl_date is None:
        if year_month:
            pnl_date = convertYearMonth(year_month)
        else:
            pnl_date = datetime.now().strftime("%Y-%m-%d")
            year_month = datetime.now().strftime("%Y-%m")
    else:
        pnl_date, year_month = get_month_str(pnl_date)
    cursor.execute("""
        INSERT OR REPLACE INTO monthly_pnl (
            year_month, open_bal, income, expenses, stock_pnl, dividend, pnl_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (year_month, open_bal, income, expenses, stock_pnl, dividend, pnl_date))
    conn.commit()
    conn.close()

def get_monthly_pnl(year_month=None, pnl_date=None):
    """Get all monthly PnL entries, optionally filtered by year_month."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT pnl_date, year_month, open_bal, income, expenses, stock_pnl, dividend, monthly_gl, close_bal
        FROM monthly_pnl
        WHERE 1=1
    """
    params = []
    
    if year_month:
        query += " AND year_month = ?"
        params.append(year_month)
    if pnl_date:
        query += " AND pnl_date >= ?"
        params.append(normalize_date(pnl_date))
        
    query += " ORDER BY year_month DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return normalize_rows([dict(row) for row in rows], ["pnl_date"])

def update_monthly_pnl(year_month, open_bal=None, income=None, expenses=None, stock_pnl=None, dividend=None, pnl_date=None):
    """Update an existing monthly PnL entry."""
    conn = get_connection()
    cursor = conn.cursor()
    fields, values = [], []
    if open_bal is not None:
        fields.append("open_bal = ?")
        values.append(open_bal)
    if income is not None:
        fields.append("income = ?")
        values.append(income)
    if expenses is not None:
        fields.append("expenses = ?")
        values.append(expenses)
    if stock_pnl is not None:
        fields.append("stock_pnl = ?")
        values.append(stock_pnl)
    if dividend is not None:
        fields.append("dividend = ?")
        values.append(dividend)
    if pnl_date is not None:
        fields.append("pnl_date = ?")
        values.append(normalize_date(pnl_date))
        
    if not fields:
        print("⚠️  No fields to update!")
        return
        
    values.append(year_month)
    cursor.execute(f"""
        UPDATE monthly_pnl
        SET {', '.join(fields)}
        WHERE year_month = ?
    """, values)
    if cursor.rowcount == 0:
        print(f"⚠️  PnL entry for '{year_month}' not found!")
    else:
        print(f"✅ PnL entry for '{year_month}' updated!")
    conn.commit()
    conn.close()

def delete_monthly_pnl(year_month):
    """Delete a monthly PnL entry."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM monthly_pnl
        WHERE year_month = ?
    """, (year_month,))
    conn.commit()
    if cursor.rowcount == 0:
        print(f"⚠️  PnL entry for '{year_month}' not found!")
    else:
        print(f"🗑️  PnL entry for '{year_month}' deleted!")
    conn.close()

# ══════════════════════════════════════════════════════════════
#  MORTGAGE CRUD
# ══════════════════════════════════════════════════════════════

def insert_mortgage_monthly(principal, interest, remaining_balance, year_month=None, period=None):
    """Insert or update a mortgage monthly entry."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Handle year_month default
        if year_month is None:
            year_month = datetime.now().strftime("%Y-%m")
        elif len(year_month) > 7:
            year_month = normalize_date(year_month)[:7]

        # Normalize period date if provided
        if period:
            period = normalize_date(period)
        else:
            period = datetime.now().strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT OR REPLACE INTO mortgage (year_month, principal, interest, remaining_balance, period)
            VALUES (?, ?, ?, ?, ?)
        """, (year_month, principal, interest, remaining_balance, period))
        conn.commit()

        return {
            "message": f"Mortgage entry for '{year_month}' inserted/updated",
            "id": cursor.lastrowid,
            "year_month": year_month,
            "period": period,
            "total_payment": principal + interest
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_mortgage_monthly(year_month=None, period=None):
    """Get all mortgage monthly entries, optionally filtered by year_month."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT period, year_month, principal, interest, total_payment, remaining_balance
        FROM mortgage
        WHERE 1=1
    """
    params = []
    
    if year_month:
        query += " AND year_month = ?"
        params.append(year_month)
    if period:
        query += " AND period >= ?"
        params.append(normalize_date(period))
        
    query += " ORDER BY year_month DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return normalize_rows([dict(row) for row in rows], ["period"])

def update_mortgage_monthly(year_month, principal=None, interest=None, remaining_balance=None, period=None):
    """Update an existing mortgage monthly entry."""
    conn = get_connection()
    cursor = conn.cursor()
    fields, values = [], []
    if principal is not None:
        fields.append("principal = ?")
        values.append(principal)
    if interest is not None:
        fields.append("interest = ?")
        values.append(interest)
    if remaining_balance is not None:
        fields.append("remaining_balance = ?")
        values.append(remaining_balance)
    if period is not None:
        fields.append("period = ?")
        values.append(normalize_date(period))
        
    if not fields:
        print("⚠️  No fields to update!")
        return
        
    values.append(year_month)
    cursor.execute(f"""
        UPDATE mortgage
        SET {', '.join(fields)}
        WHERE year_month = ?
    """, values)
    if cursor.rowcount == 0:
        print(f"⚠️  Mortgage monthly entry for '{year_month}' not found!")
    else:
        print(f"✅ Mortgage monthly entry for '{year_month}' updated!")
    conn.commit()
    conn.close()

def delete_mortgage_monthly(year_month):
    """Delete a mortgage monthly entry."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM mortgage
        WHERE year_month = ?
    """, (year_month,))
    conn.commit()
    if cursor.rowcount == 0:
        print(f"⚠️  Mortgage monthly entry for '{year_month}' not found!")
    else:
        print(f"🗑️  Mortgage monthly entry for '{year_month}' deleted!")
    conn.close()

# ══════════════════════════════════════════════════════════════
#  LEDGER CRUD
# ══════════════════════════════════════════════════════════════

def insert_ledger_entry(type, category, amount, ledger_datetime=None, comment=None):
    """Insert a new ledger entry."""
    conn = get_connection()
    cursor = conn.cursor()
    # Convert datetime to "yyyy-mm-dd" and "yyyy-mm" format
    ledger_datetime, month_str = get_month_str(ledger_datetime)

    cursor.execute("""
        INSERT INTO ledger (datetime, month_str, type, category, amount, comment)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (ledger_datetime, month_str, type, category, amount, comment))
    conn.commit()
    print(f"✅ Ledger entry '{category}' added!")
    conn.close()


def get_ledger_entries(start_date=None, end_date=None, type=None, category=None, month_str=None):
    """Retrieve ledger entries, optionally filtered by date range, type, category, and/or month_str."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT id, datetime, month_str, type, category, amount, comment
        FROM ledger
        WHERE 1=1
    """
    params = []
    
    if start_date:
        query += " AND datetime >= ?"
        params.append(normalize_date(start_date))
    if end_date:
        query += " AND datetime <= ?"
        params.append(normalize_date(end_date))
    if type:
        query += " AND type = ?"
        params.append(type)
    if category:
        query += " AND category = ?"
        params.append(category)
    if month_str:
        query += " AND month_str = ?"
        params.append(month_str)
        
    query += " ORDER BY datetime DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return normalize_rows([dict(row) for row in rows], ["datetime"])

def update_ledger_entry(entry_id, ledger_datetime=None, type=None, category=None, amount=None, comment=None):
    """Update an existing ledger entry."""
    conn = get_connection()
    cursor = conn.cursor()
    fields, values = [], []
    if ledger_datetime is not None:
        ledger_datetime, month_str = get_month_str(ledger_datetime)
        fields.append("datetime = ?")
        values.append(ledger_datetime)
        fields.append("month_str = ?")
        values.append(month_str)
    if type is not None:
        fields.append("type = ?")
        values.append(type)
    if category is not None:
        fields.append("category = ?")
        values.append(category)
    if amount is not None:
        fields.append("amount = ?")
        values.append(amount)
    if comment is not None:
        fields.append("comment = ?")
        values.append(comment)
        
    if not fields:
        print("⚠️  No fields to update!")
        return
        
    values.append(entry_id)
    cursor.execute(f"""
        UPDATE ledger
        SET {', '.join(fields)}
        WHERE id = ?
    """, values)
    if cursor.rowcount == 0:
        print(f"⚠️  Ledger entry with ID '{entry_id}' not found!")
    else:
        print(f"✅ Ledger entry with ID '{entry_id}' updated!")
    conn.commit()
    conn.close()

def delete_ledger_entry(entry_id):
    """Delete a ledger entry by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ledger WHERE id = ?", (entry_id,))
    conn.commit()
    if cursor.rowcount == 0:
        print(f"⚠️  Ledger entry with ID '{entry_id}' not found!")
    else:
        print(f"🗑️  Ledger entry with ID '{entry_id}' deleted!")
    conn.close()

#  SEED SAMPLE DATA & MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Example usage of CRUD operations for each table
    '''
    print("=== PORTFOLIO ===")

    print(get_latest_portfolio())

    
    # STOCKS CRUD
    print("=== STOCKS ===")
    

    # STOCKS CRUD
    print("=== STOCKS ===")
    print(insert_stock("MSFT", "Microsoft Corporation", "Technology", "USD"))
    print(get_stock("MSFT"))  # Assuming get_stock is implemented to fetch stock details
    update_stock("MSFT", name="Microsoft Corp", sector="Tech")
    #delete_stock("MSFT")

    # PORTFOLIO CRUD
    print("=== PORTFOLIO ===")
    insert_portfolio("AAPL", 10, 150.0, "2023-10-01 12:00:00")
    print(get_portfolio())
    update_portfolio(1, quantity=20, avg_buy_price=155.0)
    #delete_portfolio(1)

    # TRANSACTIONS CRUD
    print("=== TRANSACTIONS ===")
    insert_transaction("AAPL", "BUY", 10, 150.0, "Initial purchase")
    print(get_transactions("2023-10"))
    update_transaction(1, quantity=15, price=152.0)
    #delete_transaction(1)

    # WATCHLIST CRUD
    print("=== WATCHLIST ===")
    insert_watchlist("AAPL", 200.0, "Monitor for breakout")
    print(get_watchlist())
    update_watchlist("AAPL", target_price=210.0)
    #delete_watchlist("AAPL")

    # DIVIDENDS CRUD
    print("=== DIVIDENDS ===")
    insert_dividend("AAPL", 0.5, 10, "2023-10-15")
    print(get_dividends("AAPL"))
    update_dividend(1, amount_per_share=0.6)
    #delete_dividend(1)

    # MONTHLY SNAPSHOTS CRUD
    print("=== MONTHLY SNAPSHOTS ===")
    insert_monthly_snapshot("AAPL", 10, 150.0, "2023-10")
    print(get_monthly_snapshots("2023-10"))
    update_monthly_snapshot("2023-10", "AAPL", start_quantity=15)
    #delete_monthly_snapshot("2023-10", "AAPL")

    # MONTHLY PNL CRUD
    print("=== MONTHLY PNL ===")
    insert_monthly_pnl(1000, 500, 200, 300, 50, "2023-10")
    print(get_monthly_pnl("2023-10"))
    update_monthly_pnl("2023-10", income=600)
    #delete_monthly_pnl("2023-10")

    # MORTGAGE CRUD
    print("=== MORTGAGE ===")
    insert_mortgage_monthly(1000, 200, 800, "2023-10")
    print(get_mortgage_monthly("2023-10"))
    update_mortgage_monthly("2023-10", principal=1100)
    #delete_mortgage_monthly("2023-10")

    # LEDGER CRUD
    print("=== LEDGER ===")
    insert_ledger_entry("E", "Rent", 1000, "2023-10-01 12:00:00", "Monthly rent")
    print(get_ledger_entries(month_str="2023-10"))
    update_ledger_entry(1, amount=1200)
    #delete_ledger_entry(1)
    
    #insert_transaction("0941.HK", "BUY", 1000, 81.7, "purchase")
    '''
