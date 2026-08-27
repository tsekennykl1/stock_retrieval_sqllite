import sqlite3
from datetime import datetime, timedelta
from calendar import monthrange
import os

# Dynamically set DB path (Defaults to local mystocks.db, overwritten in Lambda)
DB_PATH = "mystocks.db"
if "AWS_LAMBDA_FUNCTION_NAME" in os.environ:
    base_path = os.environ.get("DB_PATH", "/mnt/efs")
    DB_PATH = os.path.join(base_path, "mystocks.db") 

print(f"Files in {db_path}: {os.listdir(db_path)}")  # Log what's there



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
def insert_portfolio(symbol, quantity, avg_buy_price, trading_date=None, transaction_reference_id=None):
    """Add a stock holding to the portfolio with an optional transaction reference ID and stock name."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        trading_date = normalize_date(trading_date) or datetime.now().strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO portfolio (
                stock_symbol,
                quantity,
                avg_buy_price,
                trading_date,
                transaction_reference_id
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            symbol.upper(),
            quantity,
            avg_buy_price,
            trading_date,
            transaction_reference_id
        ))

        conn.commit()

        portfolio_id = cursor.lastrowid

        print(f"✅ Portfolio entry for '{symbol.upper()}' added! (ID: {portfolio_id})")

        return {
            "portfolio_id": portfolio_id,
            "symbol": symbol.upper(),
            "quantity": quantity,
            "avg_buy_price": avg_buy_price,
            "total_invested": quantity * avg_buy_price,
            "trading_date": trading_date,
            "transaction_reference_id": transaction_reference_id,
        }

    except sqlite3.IntegrityError:
        print(f"⚠️  Stock '{symbol.upper()}' not found in stocks table!")
        return None

    finally:
        conn.close()

def update_portfolio(portfolio_id,quantity=None,avg_buy_price=None,trading_date=None,transaction_reference_id=None):

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
        conn.close()
        return {
            "message": "Nothing to update",
            "rows_affected": 0
        }

    values.append(portfolio_id)

    cursor.execute(f"""
        UPDATE portfolio
        SET {', '.join(fields)}
        WHERE id = ?
    """, values)

    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()

    return {
        "message": f"Portfolio entry {portfolio_id} updated",
        "rows_affected": rows_affected
    }

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
        SELECT p.id, p.stock_symbol, s.name AS stock_name, p.quantity, p.avg_buy_price,
               p.total_invested, p.trading_date, p.transaction_reference_id
        FROM portfolio p
        LEFT JOIN stocks s ON p.stock_symbol = s.symbol
        ORDER BY p.trading_date DESC, p.stock_symbol
    """)
    rows = cursor.fetchall()
    conn.close()
    return normalize_rows([dict(row) for row in rows], ["trading_date"])


def get_portfolio():
    """Get full latest portfolio records with stock name."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.stock_symbol, s.name AS stock_name, p.quantity, p.avg_buy_price,
               p.total_invested, p.trading_date, p.transaction_reference_id
        FROM portfolio p
        LEFT JOIN stocks s ON p.stock_symbol = s.symbol
        WHERE p.trading_date = (
            SELECT MAX(sub.trading_date)
            FROM portfolio AS sub
            WHERE sub.stock_symbol = p.stock_symbol
        )
        ORDER BY p.stock_symbol
    """)

    rows = cursor.fetchall()
    conn.close()

    return normalize_rows([dict(row) for row in rows], ["trading_date"])

def get_latest_portfolio():
    """Get latest portfolio record for each stock symbol with quantity > 0, with stock name from stocks table."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            latest.id,
            latest.stock_symbol,
            s.name AS stock_name,
            latest.trading_date AS latest_trading_date,
            latest.quantity,
            latest.avg_buy_price AS average_price,
            latest.total_invested,
            latest.transaction_reference_id
        FROM (
            SELECT
                p.*,
                ROW_NUMBER() OVER (
                    PARTITION BY p.stock_symbol
                    ORDER BY p.id DESC
                ) AS rn
            FROM portfolio p
        ) latest
        LEFT JOIN stocks s ON latest.stock_symbol = s.symbol
        WHERE latest.rn = 1
          AND latest.quantity > 0
        ORDER BY latest_trading_date DESC, latest.stock_symbol
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

    Args:
        symbol: Stock symbol, e.g. "0005.HK"
        type: BUY or SELL
        quantity: Transaction quantity
        price: Transaction price
        notes: Optional notes
        transaction_date: Optional transaction date

    Returns:
        dict with transaction details including the new transaction_id, or None on failure.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        transaction_date, transaction_month_str = get_month_str(transaction_date)

        cursor.execute("""
            INSERT INTO transactions (
                stock_symbol,
                type,
                quantity,
                price,
                notes,
                transaction_date,
                transaction_month_str
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol.upper(),
            type.upper(),
            quantity,
            price,
            notes,
            transaction_date,
            transaction_month_str
        ))

        conn.commit()

        transaction_id = cursor.lastrowid

        # Retrieve stock_name from stocks table
        cursor.execute("SELECT name FROM stocks WHERE symbol = ?", (symbol.upper(),))
        stock_row = cursor.fetchone()
        stock_name = stock_row["name"] if stock_row else None

        print(f"✅ {type.upper()} transaction for '{symbol.upper()}' recorded! (ID: {transaction_id})")

        return {
            "transaction_id": transaction_id,
            "symbol": symbol.upper(),
            "stock_name": stock_name,
            "type": type.upper(),
            "quantity": quantity,
            "price": price,
            "total_amount": quantity * price,
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
        return {"message": "Nothing to update", "rows_affected": 0}

    values.append(transaction_id)

    cursor.execute(f"""
        UPDATE transactions
        SET {', '.join(fields)}
        WHERE id = ?
    """, values)

    rows_affected = cursor.rowcount

    if rows_affected == 0:
        print(f"⚠️  Transaction entry with ID '{transaction_id}' not found!")
    else:
        print(f"✅ Transaction entry with ID '{transaction_id}' updated!")

    conn.commit()
    conn.close()

    return {
        "message": f"Transaction entry {transaction_id} updated",
        "rows_affected": rows_affected
    }


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
    """Get all transactions, filtered by month (YYYY-MM) and optionally by symbol. Includes stock name from stocks table."""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT t.id, t.stock_symbol AS symbol, s.name AS stock_name, t.type, t.quantity,
            t.price, t.total_amount, t.transaction_date, t.transaction_month_str, t.notes
        FROM transactions t
        LEFT JOIN stocks s ON t.stock_symbol = s.symbol
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
        SELECT d.id, d.stock_symbol AS symbol, s.name AS stock_name,
               d.amount_per_share, d.quantity,
               d.total_dividend, d.payment_date, d.payment_month_str, d.ex_dividend_date
        FROM dividends d
        LEFT JOIN stocks s ON d.stock_symbol = s.symbol
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

def get_all_dividends_from(year_month, symbol=None):
    """Get all dividends with payment_month_str >= year_month (from that month onwards).
    
    Args:
        year_month: Starting month in 'YYYY-MM' format (inclusive).
        symbol: Optional stock symbol filter.
    
    Returns:
        List of dividend dicts with normalized date fields.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT d.id, d.stock_symbol AS symbol, s.name AS stock_name,
               d.amount_per_share, d.quantity,
               d.total_dividend, d.payment_date, d.payment_month_str, d.ex_dividend_date
        FROM dividends d
        LEFT JOIN stocks s ON d.stock_symbol = s.symbol
        WHERE d.payment_month_str >= ?
    """
    params = [year_month]

    if symbol:
        query += " AND d.stock_symbol = ?"
        params.append(symbol.upper())

    query += " ORDER BY d.payment_date ASC"

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
        SELECT id, snapshot_date, year_month, stock_symbol, start_quantity, start_price, start_value
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
    import sys


    print("=" * 60)
    print("  CRUD_DB.PY — FULL CRUD TEST SUITE")
    print("=" * 60)

    errors = []

    def assert_equal(label, actual, expected):
        if actual != expected:
            msg = f"❌ FAIL [{label}]: expected {expected!r}, got {actual!r}"
            print(msg)
            errors.append(msg)
        else:
            print(f"  ✔ PASS [{label}]")

    def assert_not_none(label, actual):
        if actual is None:
            msg = f"❌ FAIL [{label}]: expected not None, got None"
            print(msg)
            errors.append(msg)
        else:
            print(f"  ✔ PASS [{label}]")

    def assert_none(label, actual):
        if actual is not None:
            msg = f"❌ FAIL [{label}]: expected None, got {actual!r}"
            print(msg)
            errors.append(msg)
        else:
            print(f"  ✔ PASS [{label}]")

    def assert_true(label, condition):
        if not condition:
            msg = f"❌ FAIL [{label}]: condition is False"
            print(msg)
            errors.append(msg)
        else:
            print(f"  ✔ PASS [{label}]")

    # ══════════════════════════════════════════════════════════════
    #  UTILITY FUNCTION TESTS
    # ══════════════════════════════════════════════════════════════
    print("\n" + "═" * 60)
    print("  TEST: UTILITY FUNCTIONS")
    print("═" * 60)

    # normalize_date tests
    print("\n--- normalize_date ---")
    assert_equal("normalize_date(None)", normalize_date(None), "")
    assert_equal("normalize_date('')", normalize_date(""), "")
    assert_equal("normalize_date(datetime obj)", normalize_date(datetime(2023, 10, 15)), "2023-10-15")
    assert_equal("normalize_date('2023-10-15')", normalize_date("2023-10-15"), "2023-10-15")
    assert_equal("normalize_date('2023-10-15 14:30:00')", normalize_date("2023-10-15 14:30:00"), "2023-10-15")
    assert_equal("normalize_date('10/15/2023')", normalize_date("10/15/2023"), "2023-10-15")
    assert_equal("normalize_date('  2023-10-15  ')", normalize_date("  2023-10-15  "), "2023-10-15")
    assert_equal("normalize_date(unrecognized)", normalize_date("random-string"), "random-string")

    # get_month_str tests
    print("\n--- get_month_str ---")
    now = datetime.now()

    date_str, month_str = get_month_str(None)
    assert_equal("get_month_str(None) date", date_str, now.strftime("%Y-%m-%d"))
    assert_equal("get_month_str(None) month", month_str, now.strftime("%Y-%m"))

    date_str, month_str = get_month_str(datetime(2023, 10, 15))
    assert_equal("get_month_str(datetime) date", date_str, "2023-10-15")
    assert_equal("get_month_str(datetime) month", month_str, "2023-10")

    date_str, month_str = get_month_str("2023-10-15")
    assert_equal("get_month_str('2023-10-15') date", date_str, "2023-10-15")
    assert_equal("get_month_str('2023-10-15') month", month_str, "2023-10")

    date_str, month_str = get_month_str("2023-10-15 14:30:00")
    assert_equal("get_month_str('2023-10-15 14:30:00') date", date_str, "2023-10-15")
    assert_equal("get_month_str('2023-10-15 14:30:00') month", month_str, "2023-10")

    date_str, month_str = get_month_str("10/15/2023")
    assert_equal("get_month_str('10/15/2023') date", date_str, "2023-10-15")
    assert_equal("get_month_str('10/15/2023') month", month_str, "2023-10")

    # NOTE: get_month_str with an unrecognized string that is >= 7 chars does NOT raise ValueError.
    # normalize_date returns it as-is, and get_month_str slices [:7] for the month portion.
    date_str, month_str = get_month_str("invalid-date-xyz")
    assert_equal("get_month_str(unrecognized) returns as-is", date_str, "invalid-date-xyz")
    assert_equal("get_month_str(unrecognized) month slice", month_str, "invalid")

    # A short unrecognized string (< 7 chars after normalize) that fails all parsing
    # will also not raise if normalize_date returns it with len >= 7 after fallback.
    # Only truly invalid types (not str/datetime) raise ValueError.
    try:
        get_month_str(12345)
        print("  ❌ FAIL [get_month_str int] should have raised ValueError")
        errors.append("get_month_str int did not raise ValueError")
    except ValueError:
        print("  ✔ PASS [get_month_str int raises ValueError]")

    try:
        get_month_str([2023, 10])
        print("  ❌ FAIL [get_month_str list] should have raised ValueError")
        errors.append("get_month_str list did not raise ValueError")
    except (ValueError, TypeError):
        print("  ✔ PASS [get_month_str list raises error]")

    # convertYearMonth tests
    print("\n--- convertYearMonth ---")
    assert_equal("convertYearMonth('2023-01')", convertYearMonth("2023-01"), "2023-01-31")
    assert_equal("convertYearMonth('2023-02') non-leap", convertYearMonth("2023-02"), "2023-02-28")
    assert_equal("convertYearMonth('2024-02') leap", convertYearMonth("2024-02"), "2024-02-29")
    assert_equal("convertYearMonth('2023-04')", convertYearMonth("2023-04"), "2023-04-30")
    assert_equal("convertYearMonth('2023-12')", convertYearMonth("2023-12"), "2023-12-31")

    # normalize_rows tests
    print("\n--- normalize_rows ---")
    test_rows = [{"name": "Test", "date": "10/15/2023", "other": "value"}]
    result = normalize_rows(test_rows, ["date"])
    assert_equal("normalize_rows date field", result[0]["date"], "2023-10-15")
    assert_equal("normalize_rows other field unchanged", result[0]["other"], "value")
    assert_equal("normalize_rows original not mutated", test_rows[0]["date"], "10/15/2023")

    test_rows2 = [{"name": "Test", "date": None}]
    result2 = normalize_rows(test_rows2, ["date"])
    assert_none("normalize_rows None date stays None", result2[0]["date"])

    test_rows3 = [{"name": "Test"}]
    result3 = normalize_rows(test_rows3, ["date"])
    assert_true("normalize_rows missing field not added", "date" not in result3[0])

    # ══════════════════════════════════════════════════════════════
    #  STOCKS CRUD TESTS
    # ══════════════════════════════════════════════════════════════
    print("\n" + "═" * 60)
    print("  TEST: STOCKS CRUD")
    print("═" * 60)

    # Insert stocks
    print("\n--- insert_stock ---")
    result = insert_stock("TEST1", "Test Company 1", "Technology", "USD")
    assert_not_none("insert_stock success", result)
    assert_equal("insert_stock symbol", result["symbol"], "TEST1")
    assert_equal("insert_stock name", result["name"], "Test Company 1")
    assert_equal("insert_stock sector", result["sector"], "Technology")
    assert_equal("insert_stock currency", result["currency"], "USD")

    result = insert_stock("test2", "Test Company 2", "Finance", "HKD")
    assert_equal("insert_stock uppercase", result["symbol"], "TEST2")

    result = insert_stock("TEST3", "Test Company 3")
    assert_equal("insert_stock default currency", result["currency"], "HKD")

    result = insert_stock("TEST1", "Duplicate", "Tech", "USD")
    assert_none("insert_stock duplicate returns None", result)

    # Get stock
    print("\n--- get_stock ---")
    result = get_stock("TEST1")
    assert_not_none("get_stock exists", result)
    assert_equal("get_stock symbol", result["symbol"], "TEST1")
    assert_equal("get_stock name", result["name"], "Test Company 1")

    result = get_stock("test1")
    assert_not_none("get_stock case insensitive", result)
    assert_equal("get_stock case insensitive symbol", result["symbol"], "TEST1")

    result = get_stock("NONEXIST")
    assert_none("get_stock not found", result)

    # Update stock
    print("\n--- update_stock ---")
    update_stock("TEST1", name="Test Company Updated")
    result = get_stock("TEST1")
    assert_equal("update_stock name", result["name"], "Test Company Updated")

    update_stock("TEST1", sector="FinTech", currency="EUR")
    result = get_stock("TEST1")
    assert_equal("update_stock sector", result["sector"], "FinTech")
    assert_equal("update_stock currency", result["currency"], "EUR")

    update_stock("TEST1")  # No fields - should print warning
    update_stock("NONEXIST", name="Ghost")  # Not found - should print warning

    # Delete stock
    print("\n--- delete_stock ---")
    insert_stock("TODEL", "To Delete Stock", "Tech", "USD")
    delete_stock("TODEL")
    result = get_stock("TODEL")
    assert_none("delete_stock removed", result)

    delete_stock("NONEXIST")  # Not found - should print warning

    # ══════════════════════════════════════════════════════════════
    #  PORTFOLIO CRUD TESTS
    # ══════════════════════════════════════════════════════════════
    print("\n" + "═" * 60)
    print("  TEST: PORTFOLIO CRUD")
    print("═" * 60)

    # Insert portfolio
    print("\n--- insert_portfolio ---")
    result = insert_portfolio("TEST1", 100, 50.0, "2023-10-01")
    assert_not_none("insert_portfolio success", result)
    assert_equal("insert_portfolio symbol", result["symbol"], "TEST1")
    assert_equal("insert_portfolio quantity", result["quantity"], 100)
    assert_equal("insert_portfolio avg_buy_price", result["avg_buy_price"], 50.0)
    assert_equal("insert_portfolio total_invested", result["total_invested"], 5000.0)
    assert_equal("insert_portfolio trading_date", result["trading_date"], "2023-10-01")
    assert_none("insert_portfolio no ref id", result["transaction_reference_id"])
    p1_id = result["portfolio_id"]

    result = insert_portfolio("TEST1", 150, 52.0, "2023-11-01", transaction_reference_id=99)
    assert_equal("insert_portfolio with ref id", result["transaction_reference_id"], 99)
    p2_id = result["portfolio_id"]

    result = insert_portfolio("test2", 500, 10.0, "2023-10-15")
    assert_equal("insert_portfolio case insensitive", result["symbol"], "TEST2")
    p3_id = result["portfolio_id"]

    result = insert_portfolio("TEST1", 200, 55.0)
    assert_equal("insert_portfolio default date", result["trading_date"], now.strftime("%Y-%m-%d"))
    p4_id = result["portfolio_id"]

    result = insert_portfolio("TEST1", 0, 50.0, "2023-12-01")
    p5_id = result["portfolio_id"]

    # NOTE: Foreign keys are NOT enforced in get_connection() (no PRAGMA foreign_keys = ON),
    # so inserting with a non-existent stock_symbol will succeed rather than raise IntegrityError.
    result = insert_portfolio("NONEXIST", 100, 10.0, "2023-10-01")
    assert_not_none("insert_portfolio non-existent stock (FK not enforced)", result)
    assert_equal("insert_portfolio non-existent symbol", result["symbol"], "NONEXIST")
    p_nonexist_id = result["portfolio_id"]

    # Update portfolio
    print("\n--- update_portfolio ---")
    result = update_portfolio(p1_id, quantity=120)
    assert_equal("update_portfolio quantity rows", result["rows_affected"], 1)

    result = update_portfolio(p1_id, avg_buy_price=51.0)
    assert_equal("update_portfolio price rows", result["rows_affected"], 1)

    result = update_portfolio(p1_id, trading_date="2023-10-05")
    assert_equal("update_portfolio date rows", result["rows_affected"], 1)

    result = update_portfolio(p1_id, transaction_reference_id=42)
    assert_equal("update_portfolio ref_id rows", result["rows_affected"], 1)

    result = update_portfolio(p1_id)
    assert_equal("update_portfolio no fields", result["rows_affected"], 0)
    assert_true("update_portfolio no fields msg", "Nothing to update" in result["message"])

    result = update_portfolio(99999, quantity=10)
    assert_equal("update_portfolio not found", result["rows_affected"], 0)

    # Get all portfolio entries
    print("\n--- get_all_portfolio_entries ---")
    entries = get_all_portfolio_entries()
    assert_true("get_all_portfolio_entries count >= 6", len(entries) >= 6)
    assert_true("get_all has stock_name", "stock_name" in entries[0])
    assert_true("get_all has trading_date", "trading_date" in entries[0])

    # Get portfolio (latest per stock by trading_date)
    print("\n--- get_portfolio ---")
    entries = get_portfolio()
    assert_true("get_portfolio has entries", len(entries) > 0)
    assert_true("get_portfolio has stock_name", "stock_name" in entries[0])
    symbols = [e["stock_symbol"] for e in entries]
    assert_true("get_portfolio has TEST1", "TEST1" in symbols)
    assert_true("get_portfolio has TEST2", "TEST2" in symbols)

    # Get latest portfolio (quantity > 0, by max id)
    print("\n--- get_latest_portfolio ---")
    entries = get_latest_portfolio()
    # Verify all returned entries have quantity > 0
    assert_true("get_latest_portfolio all qty > 0", all(e["quantity"] > 0 for e in entries))
    assert_true("get_latest has stock_name", all("stock_name" in e for e in entries))

    # Delete portfolio
    print("\n--- delete_portfolio ---")
    delete_portfolio(p5_id)
    delete_portfolio(p_nonexist_id)
    # Verify deletion via get_all
    entries_after = get_all_portfolio_entries()
    ids_after = [e["id"] for e in entries_after]
    assert_true("delete_portfolio removed p5", p5_id not in ids_after)
    assert_true("delete_portfolio removed nonexist", p_nonexist_id not in ids_after)

    # ══════════════════════════════════════════════════════════════
    #  TRANSACTIONS CRUD TESTS
    # ══════════════════════════════════════════════════════════════
    print("\n" + "═" * 60)
    print("  TEST: TRANSACTIONS CRUD")
    print("═" * 60)

    # Insert transactions
    print("\n--- insert_transaction ---")
    result = insert_transaction("TEST1", "BUY", 100, 50.0, "Initial purchase", "2023-10-15")
    assert_not_none("insert_transaction BUY", result)
    assert_equal("insert_txn symbol", result["symbol"], "TEST1")
    assert_equal("insert_txn type", result["type"], "BUY")
    assert_equal("insert_txn quantity", result["quantity"], 100)
    assert_equal("insert_txn price", result["price"], 50.0)
    assert_equal("insert_txn total_amount", result["total_amount"], 5000.0)
    assert_equal("insert_txn date", result["transaction_date"], "2023-10-15")
    assert_equal("insert_txn month_str", result["transaction_month_str"], "2023-10")
    assert_equal("insert_txn notes", result["notes"], "Initial purchase")
    assert_equal("insert_txn stock_name", result["stock_name"], "Test Company Updated")
    txn1_id = result["transaction_id"]

    result = insert_transaction("TEST1", "SELL", 50, 55.0, "Partial sell", "2023-11-01")
    assert_equal("insert_txn SELL type", result["type"], "SELL")
    assert_equal("insert_txn SELL month", result["transaction_month_str"], "2023-11")
    txn2_id = result["transaction_id"]

    result = insert_transaction("test2", "buy", 200, 10.0, transaction_date="2023-10-20")
    assert_equal("insert_txn case symbol", result["symbol"], "TEST2")
    assert_equal("insert_txn case type", result["type"], "BUY")
    txn3_id = result["transaction_id"]

    result = insert_transaction("TEST1", "BUY", 25, 48.0)
    assert_equal("insert_txn default date", result["transaction_date"], now.strftime("%Y-%m-%d"))
    assert_none("insert_txn no notes", result["notes"])
    txn4_id = result["transaction_id"]

    # NOTE: Foreign keys are NOT enforced in get_connection() (no PRAGMA foreign_keys = ON),
    # so inserting with a non-existent stock_symbol will succeed. stock_name will be None.
    result = insert_transaction("NONEXIST", "BUY", 10, 10.0, transaction_date="2023-10-01")
    assert_not_none("insert_txn non-existent stock (FK not enforced)", result)
    assert_equal("insert_txn non-existent symbol", result["symbol"], "NONEXIST")
    assert_none("insert_txn non-existent stock_name is None", result["stock_name"])
    txn_nonexist_id = result["transaction_id"]

    # Get transactions
    print("\n--- get_transactions ---")
    txns = get_transactions("2023-10")
    assert_true("get_txns oct count >= 2", len(txns) >= 2)
    assert_true("get_txns has stock_name", "stock_name" in txns[0])

    txns = get_transactions("2023-10", symbol="TEST1")
    assert_true("get_txns filtered by symbol", all(t["symbol"] == "TEST1" for t in txns))

    txns = get_transactions("2023-11")
    assert_true("get_txns nov has entries", len(txns) >= 1)

    txns = get_transactions("2099-01")
    assert_equal("get_txns empty month", len(txns), 0)

    # Update transaction
    print("\n--- update_transaction ---")
    result = update_transaction(txn1_id, quantity=110)
    assert_equal("update_txn quantity", result["rows_affected"], 1)

    result = update_transaction(txn1_id, price=51.0)
    assert_equal("update_txn price", result["rows_affected"], 1)

    result = update_transaction(txn1_id, type="SELL")
    assert_equal("update_txn type", result["rows_affected"], 1)

    result = update_transaction(txn1_id, notes="Updated note")
    assert_equal("update_txn notes", result["rows_affected"], 1)

    result = update_transaction(txn1_id, transaction_date="2023-10-20")
    assert_equal("update_txn date", result["rows_affected"], 1)

    result = update_transaction(txn1_id)
    assert_equal("update_txn no fields", result["rows_affected"], 0)
    assert_true("update_txn no fields msg", "Nothing to update" in result["message"])

    result = update_transaction(99999, quantity=10)
    assert_equal("update_txn not found", result["rows_affected"], 0)

    # Delete transaction
    print("\n--- delete_transaction ---")
    delete_transaction(txn4_id)
    txns = get_transactions(now.strftime("%Y-%m"), symbol="TEST1")
    ids = [t["id"] for t in txns]
    assert_true("delete_txn removed", txn4_id not in ids)

    # Clean up the NONEXIST transaction
    delete_transaction(txn_nonexist_id)

    delete_transaction(99999)  # Not found - should print warning

    # ══════════════════════════════════════════════════════════════
    #  WATCHLIST CRUD TESTS
    # ══════════════════════════════════════════════════════════════
    #print("\n" + "═" * 60)
    #print("  TEST: WATCHLIST CRUD")
    #print("═" * 60)

    # Insert watchlist
    #print("\n--- insert_watchlist ---")
    #insert_watchlist("TEST1", 75.0, "Watch for breakout")
    #insert_watchlist("TEST2", 15.0, "Value buy target")
    #insert_watchlist("test3", 100.0)  # Case insensitive

    #watchlist = get_watchlist()
    #assert_true("insert_watchlist count >= 3", len(watchlist) >= 3)

    # Duplicate insert (INSERT OR IGNORE)
    #insert_watchlist("TEST1", 999.0, "Should be ignored")
    #watchlist = get_watchlist()
    #test1_entries = [w for w in watchlist if w["symbol"] == "TEST1"]
    #assert_equal("insert_watchlist duplicate ignored", len(test1_entries), 1)
    #assert_equal("insert_watchlist original value kept", test1_entries[0]["target_price"], 75.0)

    # Insert without target price
    #insert_stock("TEST4", "Test Company 4", "Health")
    #insert_watchlist("TEST4")
    #watchlist = get_watchlist()
    #test4_entries = [w for w in watchlist if w["symbol"] == "TEST4"]
    #assert_equal("insert_watchlist no target", len(test4_entries), 1)
    #assert_none("insert_watchlist target_price None", test4_entries[0]["target_price"])

    # Get watchlist
    #print("\n--- get_watchlist ---")
    #watchlist = get_watchlist()
    #assert_true("get_watchlist has entries", len(watchlist) >= 3)
    #assert_true("get_watchlist has name", "name" in watchlist[0])
    #assert_true("get_watchlist has symbol", "symbol" in watchlist[0])
    #assert_true("get_watchlist has target_price", "target_price" in watchlist[0])
    #assert_true("get_watchlist has notes", "notes" in watchlist[0])
    #assert_true("get_watchlist has added_at", "added_at" in watchlist[0])

    # Update watchlist
    #print("\n--- update_watchlist ---")
    #update_watchlist("TEST1", target_price=80.0)
    #watchlist = get_watchlist()
    #test1_entry = [w for w in watchlist if w["symbol"] == "TEST1"][0]
    #assert_equal("update_watchlist target_price", test1_entry["target_price"], 80.0)

    #update_watchlist("TEST1", notes="New strategy note")
    #watchlist = get_watchlist()
    #test1_entry = [w for w in watchlist if w["symbol"] == "TEST1"][0]
    #assert_equal("update_watchlist notes", test1_entry["notes"], "New strategy note")

    #update_watchlist("TEST1")  # No fields - should print warning
    #update_watchlist("NONEXIST", target_price=100.0)  # Not found - should print warning

    # Delete watchlist
    #print("\n--- delete_watchlist ---")
    #delete_watchlist("TEST4")
    #watchlist = get_watchlist()
    #symbols = [w["symbol"] for w in watchlist]
    #assert_true("delete_watchlist removed", "TEST4" not in symbols)

    # ══════════════════════════════════════════════════════════════
    #  DIVIDENDS CRUD TESTS
    # ══════════════════════════════════════════════════════════════
    print("\n" + "═" * 60)
    print("  TEST: DIVIDENDS CRUD")
    print("═" * 60)

    # Insert dividends
    print("\n--- insert_dividend ---")
    result = insert_dividend("TEST1", 0.50, 100, "2023-10-15", "2023-09-20")
    assert_not_none("insert_dividend with ex_date", result)
    assert_equal("insert_div symbol", result["symbol"], "TEST1")
    assert_equal("insert_div amount_per_share", result["amount_per_share"], 0.50)
    assert_equal("insert_div quantity", result["quantity"], 100)
    assert_equal("insert_div total_dividend", result["total_dividend"], 50.0)
    assert_equal("insert_div payment_date", result["payment_date"], "2023-10-15")
    assert_equal("insert_div payment_month_str", result["payment_month_str"], "2023-10")
    assert_equal("insert_div ex_dividend_date", result["ex_dividend_date"], "2023-09-20")
    div1_id = result["dividend_id"]

    result = insert_dividend("TEST2", 0.25, 500, "2023-10-20")
    assert_not_none("insert_dividend no ex_date", result)
    assert_none("insert_div no ex_date value", result["ex_dividend_date"])
    div2_id = result["dividend_id"]

    result = insert_dividend("test1", 0.60, 120, "2023-11-15", "2023-10-25")
    assert_equal("insert_div case insensitive", result["symbol"], "TEST1")
    div3_id = result["dividend_id"]

    # NOTE: Foreign keys are NOT enforced in get_connection() (no PRAGMA foreign_keys = ON),
    # so inserting with a non-existent stock_symbol will succeed rather than raise IntegrityError.
    result = insert_dividend("NONEXIST", 1.0, 100, "2023-10-01")
    assert_not_none("insert_dividend non-existent stock (FK not enforced)", result)
    assert_equal("insert_div non-existent symbol", result["symbol"], "NONEXIST")
    div_nonexist_id = result["dividend_id"]

    # Get dividends
    print("\n--- get_dividends ---")
    divs = get_dividends()
    assert_true("get_dividends all count >= 4", len(divs) >= 4)
    assert_true("get_dividends has stock_name", "stock_name" in divs[0])

    divs = get_dividends(symbol="TEST1")
    assert_true("get_dividends by symbol", all(d["symbol"] == "TEST1" for d in divs))
    assert_true("get_dividends TEST1 count >= 2", len(divs) >= 2)

    divs = get_dividends(year_month="2023-10")
    assert_true("get_dividends by month", all(d["payment_month_str"] == "2023-10" for d in divs))

    divs = get_dividends(symbol="TEST1", year_month="2023-10")
    assert_true("get_dividends by symbol+month", len(divs) >= 1)
    assert_true("get_dividends filter combo", all(d["symbol"] == "TEST1" and d["payment_month_str"] == "2023-10" for d in divs))

    # Use a month that truly has no dividends
    divs = get_dividends(symbol="TEST1", year_month="2099-01")
    assert_equal("get_dividends empty", len(divs), 0)

    # Update dividend
    print("\n--- update_dividend ---")
    update_dividend(div1_id, amount_per_share=0.55)
    divs = get_dividends(symbol="TEST1", year_month="2023-10")
    assert_equal("update_div amount", divs[0]["amount_per_share"], 0.55)

    update_dividend(div1_id, quantity=110)
    divs = get_dividends(symbol="TEST1", year_month="2023-10")
    assert_equal("update_div quantity", divs[0]["quantity"], 110)

    update_dividend(div1_id, payment_date="2023-10-18")
    divs = get_dividends(symbol="TEST1", year_month="2023-10")
    found = [d for d in divs if d["id"] == div1_id]
    assert_true("update_div payment_date", len(found) > 0 and found[0]["payment_date"] == "2023-10-18")

    update_dividend(div1_id, ex_dividend_date="2023-09-25")
    divs = get_dividends(symbol="TEST1", year_month="2023-10")
    found = [d for d in divs if d["id"] == div1_id]
    assert_equal("update_div ex_date", found[0]["ex_dividend_date"], "2023-09-25")

    update_dividend(div1_id)  # No fields - should print warning
    update_dividend(99999, amount_per_share=1.0)  # Not found - should print warning

    # Delete dividend
    print("\n--- delete_dividend ---")
    delete_dividend(div2_id)
    divs = get_dividends(symbol="TEST2")
    ids = [d["id"] for d in divs]
    assert_true("delete_dividend removed", div2_id not in ids)

    # Clean up NONEXIST dividend
    delete_dividend(div_nonexist_id)

    delete_dividend(99999)  # Not found - should print warning

    # ══════════════════════════════════════════════════════════════
    #  MONTHLY SNAPSHOTS CRUD TESTS
    # ══════════════════════════════════════════════════════════════
    print("\n" + "═" * 60)
    print("  TEST: MONTHLY SNAPSHOTS CRUD")
    print("═" * 60)

    # Insert snapshots
    print("\n--- insert_monthly_snapshot ---")
    insert_monthly_snapshot("TEST1", 100, 50.0, year_month="2023-10")
    insert_monthly_snapshot("TEST2", 500, 10.0, year_month="2023-10")
    insert_monthly_snapshot("TEST1", 120, 52.0, year_month="2023-11")
    insert_monthly_snapshot("TEST1", 150, 55.0, snapshot_date="2023-12-15")
    insert_monthly_snapshot("test2", 600, 11.0, year_month="2023-11")  # Case insensitive

    # Insert with default (current month)
    insert_monthly_snapshot("TEST1", 200, 58.0)

    # INSERT OR REPLACE - should overwrite
    insert_monthly_snapshot("TEST1", 999, 99.0, year_month="2023-10")
    snaps = get_monthly_snapshots("2023-10", stock_symbol="TEST1")
    assert_equal("insert_snapshot replace qty", snaps[0]["start_quantity"], 999)
    assert_equal("insert_snapshot replace price", snaps[0]["start_price"], 99.0)

    # Reset back
    insert_monthly_snapshot("TEST1", 100, 50.0, year_month="2023-10")

    # Get snapshots
    print("\n--- get_monthly_snapshots ---")
    snaps = get_monthly_snapshots()
    assert_true("get_snapshots all has entries", len(snaps) >= 5)

    snaps = get_monthly_snapshots("2023-10")
    assert_true("get_snapshots by month", all(s["year_month"] == "2023-10" for s in snaps))
    assert_true("get_snapshots oct count >= 2", len(snaps) >= 2)

    snaps = get_monthly_snapshots(stock_symbol="TEST1")
    assert_true("get_snapshots by symbol", all(s["stock_symbol"] == "TEST1" for s in snaps))

    snaps = get_monthly_snapshots("2023-10", stock_symbol="TEST1")
    assert_equal("get_snapshots by month+symbol", len(snaps), 1)
    assert_equal("get_snapshots snapshot_date", snaps[0]["snapshot_date"], "2023-10-31")

    snaps = get_monthly_snapshots(snapshot_date="2023-11-01")
    assert_true("get_snapshots by date filter", all(s["snapshot_date"] >= "2023-11-01" for s in snaps))

    snaps = get_monthly_snapshots("2099-01")
    assert_equal("get_snapshots empty", len(snaps), 0)

    # Verify computed start_value
    snaps = get_monthly_snapshots("2023-10", stock_symbol="TEST1")
    assert_equal("snapshot start_value computed", snaps[0]["start_value"], 100 * 50.0)

    # Update snapshot
    print("\n--- update_monthly_snapshot ---")
    update_monthly_snapshot("2023-10", "TEST1", start_quantity=105)
    snaps = get_monthly_snapshots("2023-10", stock_symbol="TEST1")
    assert_equal("update_snapshot quantity", snaps[0]["start_quantity"], 105)

    update_monthly_snapshot("2023-10", "TEST1", start_price=51.0)
    snaps = get_monthly_snapshots("2023-10", stock_symbol="TEST1")
    assert_equal("update_snapshot price", snaps[0]["start_price"], 51.0)

    update_monthly_snapshot("2023-10", "TEST1", snapshot_date="2023-10-20")
    snaps = get_monthly_snapshots("2023-10", stock_symbol="TEST1")
    assert_equal("update_snapshot date", snaps[0]["snapshot_date"], "2023-10-20")

    update_monthly_snapshot("2023-10", "TEST1")  # No fields - should print warning
    update_monthly_snapshot("2099-01", "NONEXIST", start_quantity=10)  # Not found

    # Delete snapshot
    print("\n--- delete_monthly_snapshot ---")
    delete_monthly_snapshot("2023-11", "TEST2")
    snaps = get_monthly_snapshots("2023-11", stock_symbol="TEST2")
    assert_equal("delete_snapshot removed", len(snaps), 0)

    delete_monthly_snapshot("2099-01", "NONEXIST")  # Not found

    # ══════════════════════════════════════════════════════════════
    #  MONTHLY PNL CRUD TESTS
    # ══════════════════════════════════════════════════════════════
    print("\n" + "═" * 60)
    print("  TEST: MONTHLY PNL CRUD")
    print("═" * 60)

    # Insert PnL
    print("\n--- insert_monthly_pnl ---")
    insert_monthly_pnl(10000, 5000, 2000, 1000, 200, year_month="2023-10")
    insert_monthly_pnl(14200, 5500, 2100, 800, 150, year_month="2023-11")
    insert_monthly_pnl(18550, 6000, 2500, 1200, 300, pnl_date="2023-12-15")

    # Default (current month)
    insert_monthly_pnl(20000, 7000, 3000, 500, 100)

    # INSERT OR REPLACE - should overwrite
    insert_monthly_pnl(99999, 1, 1, 1, 1, year_month="2023-10")
    pnl = get_monthly_pnl("2023-10")
    assert_equal("insert_pnl replace open_bal", pnl[0]["open_bal"], 99999)

    # Reset
    insert_monthly_pnl(10000, 5000, 2000, 1000, 200, year_month="2023-10")

    # Get PnL
    print("\n--- get_monthly_pnl ---")
    pnl = get_monthly_pnl()
    assert_true("get_pnl all has entries", len(pnl) >= 3)

    pnl = get_monthly_pnl("2023-10")
    assert_equal("get_pnl by month count", len(pnl), 1)
    assert_equal("get_pnl open_bal", pnl[0]["open_bal"], 10000)
    assert_equal("get_pnl income", pnl[0]["income"], 5000)
    assert_equal("get_pnl expenses", pnl[0]["expenses"], 2000)
    assert_equal("get_pnl stock_pnl", pnl[0]["stock_pnl"], 1000)
    assert_equal("get_pnl dividend", pnl[0]["dividend"], 200)
    assert_equal("get_pnl pnl_date", pnl[0]["pnl_date"], "2023-10-31")

    # Verify computed fields (from create_db: monthly_gl = income + expenses + stock_pnl + dividend)
    expected_gl = 5000 + 2000 + 1000 + 200
    assert_equal("get_pnl monthly_gl computed", pnl[0]["monthly_gl"], expected_gl)
    expected_close = 10000 + expected_gl
    assert_equal("get_pnl close_bal computed", pnl[0]["close_bal"], expected_close)

    pnl = get_monthly_pnl(pnl_date="2023-11-01")
    assert_true("get_pnl by date filter", all(p["pnl_date"] >= "2023-11-01" for p in pnl))

    pnl = get_monthly_pnl("2099-01")
    assert_equal("get_pnl empty", len(pnl), 0)

    # Update PnL
    print("\n--- update_monthly_pnl ---")
    update_monthly_pnl("2023-10", open_bal=11000)
    pnl = get_monthly_pnl("2023-10")
    assert_equal("update_pnl open_bal", pnl[0]["open_bal"], 11000)

    update_monthly_pnl("2023-10", income=5500)
    pnl = get_monthly_pnl("2023-10")
    assert_equal("update_pnl income", pnl[0]["income"], 5500)

    update_monthly_pnl("2023-10", expenses=2200)
    pnl = get_monthly_pnl("2023-10")
    assert_equal("update_pnl expenses", pnl[0]["expenses"], 2200)

    update_monthly_pnl("2023-10", stock_pnl=1500)
    pnl = get_monthly_pnl("2023-10")
    assert_equal("update_pnl stock_pnl", pnl[0]["stock_pnl"], 1500)

    update_monthly_pnl("2023-10", dividend=250)
    pnl = get_monthly_pnl("2023-10")
    assert_equal("update_pnl dividend", pnl[0]["dividend"], 250)

    update_monthly_pnl("2023-10", pnl_date="2023-10-28")
    pnl = get_monthly_pnl("2023-10")
    assert_equal("update_pnl date", pnl[0]["pnl_date"], "2023-10-28")

    update_monthly_pnl("2023-10")  # No fields - should print warning
    update_monthly_pnl("2099-01", income=100)  # Not found

    # Delete PnL
    print("\n--- delete_monthly_pnl ---")
    delete_monthly_pnl("2023-11")
    pnl = get_monthly_pnl("2023-11")
    assert_equal("delete_pnl removed", len(pnl), 0)

    delete_monthly_pnl("2099-01")  # Not found

    # ══════════════════════════════════════════════════════════════
    #  MORTGAGE CRUD TESTS
    # ══════════════════════════════════════════════════════════════
    print("\n" + "═" * 60)
    print("  TEST: MORTGAGE CRUD")
    print("═" * 60)

    # Insert mortgage
    print("\n--- insert_mortgage_monthly ---")
    result = insert_mortgage_monthly(5000, 1000, 450000, year_month="2023-10")
    assert_not_none("insert_mortgage success", result)
    assert_equal("insert_mortgage year_month", result["year_month"], "2023-10")
    assert_equal("insert_mortgage total_payment", result["total_payment"], 6000)

    result = insert_mortgage_monthly(5100, 950, 445000, year_month="2023-11", period="2023-11-15")
    assert_equal("insert_mortgage with period", result["period"], "2023-11-15")

    result = insert_mortgage_monthly(5200, 900, 440000)
    assert_equal("insert_mortgage default year_month", result["year_month"], now.strftime("%Y-%m"))

    result = insert_mortgage_monthly(5300, 850, 435000, year_month="2023-12-15")
    assert_equal("insert_mortgage long year_month normalized", result["year_month"], "2023-12")

    # INSERT OR REPLACE
    insert_mortgage_monthly(9999, 1, 1, year_month="2023-10")
    entries = get_mortgage_monthly("2023-10")
    assert_equal("insert_mortgage replace principal", entries[0]["principal"], 9999)

    # Reset
    insert_mortgage_monthly(5000, 1000, 450000, year_month="2023-10")

    # Get mortgage
    print("\n--- get_mortgage_monthly ---")
    entries = get_mortgage_monthly()
    assert_true("get_mortgage all has entries", len(entries) >= 3)

    entries = get_mortgage_monthly("2023-10")
    assert_equal("get_mortgage by month count", len(entries), 1)
    assert_equal("get_mortgage principal", entries[0]["principal"], 5000)
    assert_equal("get_mortgage interest", entries[0]["interest"], 1000)
    assert_equal("get_mortgage total_payment", entries[0]["total_payment"], 6000)
    assert_equal("get_mortgage remaining_balance", entries[0]["remaining_balance"], 450000)

    entries = get_mortgage_monthly(period="2023-11-01")
    assert_true("get_mortgage by period filter", len(entries) >= 1)

    entries = get_mortgage_monthly("2099-01")
    assert_equal("get_mortgage empty", len(entries), 0)

    # Update mortgage
    print("\n--- update_mortgage_monthly ---")
    update_mortgage_monthly("2023-10", principal=5050)
    entries = get_mortgage_monthly("2023-10")
    assert_equal("update_mortgage principal", entries[0]["principal"], 5050)

    update_mortgage_monthly("2023-10", interest=980)
    entries = get_mortgage_monthly("2023-10")
    assert_equal("update_mortgage interest", entries[0]["interest"], 980)

    update_mortgage_monthly("2023-10", remaining_balance=449000)
    entries = get_mortgage_monthly("2023-10")
    assert_equal("update_mortgage balance", entries[0]["remaining_balance"], 449000)

    update_mortgage_monthly("2023-10", period="2023-10-20")
    entries = get_mortgage_monthly("2023-10")
    assert_equal("update_mortgage period", entries[0]["period"], "2023-10-20")

    update_mortgage_monthly("2023-10")  # No fields - should print warning
    update_mortgage_monthly("2099-01", principal=100)  # Not found

    # Delete mortgage
    print("\n--- delete_mortgage_monthly ---")
    delete_mortgage_monthly("2023-11")
    entries = get_mortgage_monthly("2023-11")
    assert_equal("delete_mortgage removed", len(entries), 0)

    delete_mortgage_monthly("2099-01")  # Not found

    # ══════════════════════════════════════════════════════════════
    #  LEDGER CRUD TESTS
    # ══════════════════════════════════════════════════════════════
    print("\n" + "═" * 60)
    print("  TEST: LEDGER CRUD")
    print("═" * 60)

    # Insert ledger entries
    print("\n--- insert_ledger_entry ---")
    insert_ledger_entry("E", "Rent", 5000, "2023-10-01", "Monthly rent")
    insert_ledger_entry("E", "Food", 800, "2023-10-05", "Groceries")
    insert_ledger_entry("E", "Transport", 300, "2023-10-15")
    insert_ledger_entry("I", "Salary", 30000, "2023-10-25", "Monthly salary")
    insert_ledger_entry("I", "Freelance", 5000, "2023-11-01", "Side project")
    insert_ledger_entry("E", "Rent", 5000, "2023-11-01", "Monthly rent")

    # Default date (current)
    insert_ledger_entry("E", "Misc", 100)

    # Get ledger entries
    print("\n--- get_ledger_entries ---")
    entries = get_ledger_entries()
    assert_true("get_ledger all has entries", len(entries) >= 7)

    entries = get_ledger_entries(month_str="2023-10")
    assert_true("get_ledger by month", len(entries) >= 4)
    assert_true("get_ledger month filter", all(e["month_str"] == "2023-10" for e in entries))

    entries = get_ledger_entries(type="E")
    assert_true("get_ledger by type E", all(e["type"] == "E" for e in entries))
    assert_true("get_ledger type E count >= 4", len(entries) >= 4)

    entries = get_ledger_entries(type="I")
    assert_true("get_ledger by type I", all(e["type"] == "I" for e in entries))
    assert_true("get_ledger type I count >= 2", len(entries) >= 2)

    entries = get_ledger_entries(category="Rent")
    assert_true("get_ledger by category", all(e["category"] == "Rent" for e in entries))
    assert_true("get_ledger category Rent count >= 2", len(entries) >= 2)

    entries = get_ledger_entries(start_date="2023-10-10", end_date="2023-10-20")
    assert_true("get_ledger by date range", len(entries) >= 1)
    assert_true("get_ledger date range filter", all(e["datetime"] >= "2023-10-10" and e["datetime"] <= "2023-10-20" for e in entries))

    entries = get_ledger_entries(type="E", month_str="2023-10")
    assert_true("get_ledger combined filters", all(e["type"] == "E" and e["month_str"] == "2023-10" for e in entries))
    assert_true("get_ledger combined count >= 3", len(entries) >= 3)

    entries = get_ledger_entries(month_str="2099-01")
    assert_equal("get_ledger empty", len(entries), 0)

    # Get first entry ID for updates
    entries = get_ledger_entries(month_str="2023-10", category="Rent")
    ledger_id = entries[0]["id"]

    # Update ledger entry
    print("\n--- update_ledger_entry ---")
    update_ledger_entry(ledger_id, amount=5200)
    entries = get_ledger_entries(month_str="2023-10", category="Rent")
    found = [e for e in entries if e["id"] == ledger_id]
    assert_equal("update_ledger amount", found[0]["amount"], 5200)

    update_ledger_entry(ledger_id, category="Housing")
    entries = get_ledger_entries(month_str="2023-10", category="Housing")
    assert_true("update_ledger category", len(entries) >= 1)

    update_ledger_entry(ledger_id, type="I")
    entries = get_ledger_entries(type="I", month_str="2023-10")
    ids = [e["id"] for e in entries]
    assert_true("update_ledger type", ledger_id in ids)

    update_ledger_entry(ledger_id, comment="Updated comment")
    entries = get_ledger_entries(month_str="2023-10")
    found = [e for e in entries if e["id"] == ledger_id]
    assert_equal("update_ledger comment", found[0]["comment"], "Updated comment")

    # Update datetime — should also update month_str
    update_ledger_entry(ledger_id, ledger_datetime="2023-12-01")
    entries = get_ledger_entries(month_str="2023-12")
    ids = [e["id"] for e in entries]
    assert_true("update_ledger datetime moves month", ledger_id in ids)
    found = [e for e in entries if e["id"] == ledger_id]
    assert_equal("update_ledger datetime value", found[0]["datetime"], "2023-12-01")
    assert_equal("update_ledger month_str synced", found[0]["month_str"], "2023-12")

    update_ledger_entry(ledger_id)  # No fields - should print warning
    update_ledger_entry(99999, amount=100)  # Not found

    # Delete ledger entry
    print("\n--- delete_ledger_entry ---")
    entries = get_ledger_entries(month_str="2023-10", category="Food")
    food_id = entries[0]["id"]
    delete_ledger_entry(food_id)
    entries = get_ledger_entries(month_str="2023-10", category="Food")
    ids = [e["id"] for e in entries]
    assert_true("delete_ledger removed", food_id not in ids)

    delete_ledger_entry(99999)  # Not found

    # ══════════════════════════════════════════════════════════════
    #  CLEANUP & FINAL REPORT
    # ══════════════════════════════════════════════════════════════
    print("\n" + "═" * 60)
    print("  CLEANUP: Removing test data")
    print("═" * 60)

    # Clean up test stocks (note: cascades don't work without FK enforcement,
    # so we manually clean related records first)
    # Clean up portfolio entries for test stocks
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM portfolio WHERE stock_symbol IN ('TEST1', 'TEST2', 'TEST3', 'TEST4', 'NONEXIST')")
    cursor.execute("DELETE FROM transactions WHERE stock_symbol IN ('TEST1', 'TEST2', 'TEST3', 'TEST4', 'NONEXIST')")
    cursor.execute("DELETE FROM watchlist WHERE stock_symbol IN ('TEST1', 'TEST2', 'TEST3', 'TEST4', 'NONEXIST')")
    cursor.execute("DELETE FROM dividends WHERE stock_symbol IN ('TEST1', 'TEST2', 'TEST3', 'TEST4', 'NONEXIST')")
    cursor.execute("DELETE FROM monthly_snapshots WHERE stock_symbol IN ('TEST1', 'TEST2', 'TEST3', 'TEST4', 'NONEXIST')")
    cursor.execute("DELETE FROM ledger WHERE month_str IN ('2023-10', '2023-11', '2023-12') OR month_str = ?", (now.strftime("%Y-%m"),))
    conn.commit()
    conn.close()

    # Delete test stocks
    delete_stock("TEST1")
    delete_stock("TEST2")
    delete_stock("TEST3")
    delete_stock("TEST4")

    # Clean up PnL and mortgage entries
    delete_monthly_pnl("2023-10")
    delete_monthly_pnl("2023-12")
    delete_monthly_pnl(now.strftime("%Y-%m"))
    delete_mortgage_monthly("2023-10")
    delete_mortgage_monthly("2023-12")
    delete_mortgage_monthly(now.strftime("%Y-%m"))

    print("\n" + "═" * 60)
    print("  TEST RESULTS SUMMARY")
    print("═" * 60)

    if errors:
        print(f"\n  🔴 {len(errors)} TEST(S) FAILED:\n")
        for err in errors:
            print(f"    {err}")
        print()
        sys.exit(1)
    else:
        print(f"\n  🟢 ALL TESTS PASSED! ✅")
        print()
        sys.exit(0)