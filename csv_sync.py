import sqlite3
import csv
import os
import re
from pathlib import Path
from datetime import datetime

DB_NAME = "mystocks.db"

# ─── Date Parsing Formats ────────────────────────────────────────────────────

DATE_FORMATS_FULL = [
    "%Y-%m-%d",           # 2024-01-15
    "%Y-%m-%d %H:%M:%S",  # 2024-01-15 10:30:00
    "%d/%m/%Y",           # 15/01/2024
    "%m/%d/%Y",           # 01/15/2024
    "%d-%m-%Y",           # 15-01-2024
    "%Y/%m/%d",           # 2024/01/15
    "%d %b %Y",           # 15 Jan 2024
    "%d %B %Y",           # 15 January 2024
    "%b %d, %Y",          # Jan 15, 2024
    "%B %d, %Y",          # January 15, 2024
    "%Y%m%d",             # 20240115
]

DATE_FORMATS_MONTH = [
    "%Y-%m",              # 2024-01
    "%m/%Y",              # 01/2024
    "%m-%Y",              # 01-2024
    "%Y/%m",              # 2024/01
    "%b %Y",              # Jan 2024
    "%B %Y",              # January 2024
    "%Y%m",              # 202401
]

# ─── Column Classification Based on Schema ───────────────────────────────────

# Columns that should be formatted as yyyy-mm-dd (DATETIME fields)
FULL_DATE_COLUMNS = {
    'created_at',
    'trading_date',
    'transaction_date',
    'added_at',
    'ex_dividend_date',
    'payment_date',
    'snapshot_date',
    'pnl_date',
    'period',
    'datetime',
}

# Columns that should be formatted as yyyy-mm (month-only TEXT fields)
MONTH_COLUMNS = {
    'year_month',
    'month_str',
    'transaction_month_str',
    'payment_month_str',
}

# All date-related columns combined
ALL_DATE_COLUMNS = FULL_DATE_COLUMNS | MONTH_COLUMNS


# ─── Database Helpers ─────────────────────────────────────────────────────────

def get_connection():
    """Establish and return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_tables():
    """Retrieve all table names from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return [table for table in tables if table not in ('sqlite_sequence', 'sqlite_stat1')]


def get_generated_columns(cursor, table):
    """
    Dynamically detect GENERATED (virtual/stored) columns using PRAGMA table_xinfo.
    Returns a set of column names that are generated and should NOT be imported.
    
    table_xinfo columns: cid, name, type, notnull, dflt_value, pk, hidden
    hidden = 0: normal column
    hidden = 2: virtual generated column
    hidden = 3: stored generated column
    """
    try:
        cursor.execute(f"PRAGMA table_xinfo({table})")
        columns_info = cursor.fetchall()
        generated = set()
        for col in columns_info:
            # col index: 0=cid, 1=name, 2=type, 3=notnull, 4=dflt_value, 5=pk, 6=hidden
            col_name = col[1]
            hidden_flag = col[6]
            if hidden_flag in (2, 3):  # 2=virtual generated, 3=stored generated
                generated.add(col_name)
        return generated
    except Exception:
        # Fallback: if PRAGMA table_xinfo is not available (older SQLite)
        return get_generated_columns_fallback(cursor, table)


def get_generated_columns_fallback(cursor, table):
    """
    Fallback: parse CREATE TABLE SQL to find GENERATED ALWAYS AS columns.
    Used when PRAGMA table_xinfo is not available.
    """
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
    row = cursor.fetchone()
    if not row:
        return set()

    create_sql = row[0]
    generated = set()
    # Match pattern: column_name TYPE GENERATED ALWAYS AS (...)
    pattern = r'(\w+)\s+\w+.*?GENERATED\s+ALWAYS\s+AS'
    matches = re.findall(pattern, create_sql, re.IGNORECASE)
    for col_name in matches:
        generated.add(col_name)
    return generated


def get_table_columns(cursor, table):
    """Get all column names for a table (excluding generated columns)."""
    cursor.execute(f"PRAGMA table_info({table})")
    return [col[1] for col in cursor.fetchall()]


TABLES = get_all_tables()


# ─── Date Normalization ───────────────────────────────────────────────────────

def normalize_to_full_date(value):
    """
    Normalize a value to yyyy-mm-dd format.
    Returns normalized string or original value if parsing fails.
    """
    if value is None or str(value).strip() == "":
        return value

    val = str(value).strip()

    # Already in correct format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', val):
        return val

    # If it has time component, try to extract just the date
    if re.match(r'^\d{4}-\d{2}-\d{2}\s', val):
        return val[:10]

    # Try full date formats
    for fmt in DATE_FORMATS_FULL:
        try:
            parsed = datetime.strptime(val, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # If it's a month-only format, append -01
    for fmt in DATE_FORMATS_MONTH:
        try:
            parsed = datetime.strptime(val, fmt)
            return parsed.strftime("%Y-%m-01")
        except ValueError:
            continue

    return value


def normalize_to_month(value):
    """
    Normalize a value to yyyy-mm format.
    Returns normalized string or original value if parsing fails.
    """
    if value is None or str(value).strip() == "":
        return value

    val = str(value).strip()

    # Already in correct format
    if re.match(r'^\d{4}-\d{2}$', val):
        return val

    # Try month-only formats first
    for fmt in DATE_FORMATS_MONTH:
        try:
            parsed = datetime.strptime(val, fmt)
            return parsed.strftime("%Y-%m")
        except ValueError:
            continue

    # Try full date formats and extract year-month
    for fmt in DATE_FORMATS_FULL:
        try:
            parsed = datetime.strptime(val, fmt)
            return parsed.strftime("%Y-%m")
        except ValueError:
            continue

    return value


def normalize_date_value(value, col_name):
    """
    Normalize a date value based on the column name.
    Uses full date format (yyyy-mm-dd) for DATETIME columns,
    and month format (yyyy-mm) for month-only columns.
    """
    if col_name in FULL_DATE_COLUMNS:
        return normalize_to_full_date(value)
    elif col_name in MONTH_COLUMNS:
        return normalize_to_month(value)
    return value


# ─── Export Function ──────────────────────────────────────────────────────────

def export_to_csv(target_table=None):
    """Export tables from the database to individual CSV files with normalized date formats."""
    conn = get_connection()
    cursor = conn.cursor()

    # Ensure csv directory exists
    os.makedirs("csv", exist_ok=True)

    tables_to_export = [target_table] if target_table else TABLES

    for table in tables_to_export:
        csv_filename = os.path.join("csv", f"{table}.csv")
        try:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()

            if not rows:
                print(f"⚠️  Table '{table}' is empty. Skipping export.")
                continue

            # Get column headers
            col_names = [description[0] for description in cursor.description]

            # Get generated columns to exclude from export (optional: keep them for reference)
            generated_cols = get_generated_columns(cursor, table)

            # Identify date column indices
            date_col_indices = {
                i: col for i, col in enumerate(col_names)
                if col in ALL_DATE_COLUMNS
            }

            with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(col_names)  # Write headers (including generated for visibility)

                for row in rows:
                    row_list = list(row)
                    # Normalize date fields
                    for idx, col_name in date_col_indices.items():
                        row_list[idx] = normalize_date_value(row_list[idx], col_name)
                    writer.writerow(row_list)

            print(f"✅ Exported '{table}' to {csv_filename} ({len(rows)} rows)")
        except sqlite3.OperationalError as e:
            print(f"❌ Error exporting '{table}': {e}")

    conn.close()


# ─── Import Function ─────────────────────────────────────────────────────────

def import_from_csv(target_table=None):
    """Dynamically import CSV files matching table names into the database with normalized dates."""
    conn = get_connection()
    cursor = conn.cursor()

    tables_to_import = [target_table] if target_table else TABLES

    for table in tables_to_import:
        csv_filename = os.path.join("csv", f"{table}.csv")

        if not os.path.exists(csv_filename):
            print(f"⚠️  File '{csv_filename}' not found. Skipping import for '{table}'.")
            continue

        try:
            # Dynamically detect generated columns from schema (no hardcoding!)
            generated_cols = get_generated_columns(cursor, table)
            if generated_cols:
                print(f"ℹ️  Table '{table}' generated columns (auto-excluded): {generated_cols}")

            with open(csv_filename, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                raw_headers = next(reader, None)

                if not raw_headers:
                    print(f"⚠️  File '{csv_filename}' is empty.")
                    continue

                # Strip whitespace and filter out empty/blank headers (trailing commas)
                headers = [h.strip() for h in raw_headers if h and h.strip()]

                # Remove generated columns from headers dynamically
                db_headers = [h for h in headers if h not in generated_cols]

                if not db_headers:
                    print(f"⚠️  No writable columns found for table '{table}'. Skipping.")
                    continue

                # Indexes of columns to import (mapped back to CSV column positions)
                import_indices = [headers.index(h) for h in db_headers]

                # Identify which db_headers are date columns
                date_headers = {h for h in db_headers if h in ALL_DATE_COLUMNS}

                # Dynamically construct INSERT statement
                placeholders = ", ".join(["?"] * len(db_headers))
                columns = ", ".join(db_headers)
                sql = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"

                row_count = 0
                for row_data in reader:
                    # Pad row if it has fewer columns than headers
                    if len(row_data) < len(headers):
                        row_data += [""] * (len(headers) - len(row_data))

                    # Clean and normalize row values
                    clean_row = []
                    for i, idx in enumerate(import_indices):
                        raw_val = row_data[idx].strip()
                        col_name = db_headers[i]

                        if raw_val == "":
                            # For date columns, keep as None; for others, use 0
                            if col_name in date_headers:
                                clean_row.append(None)
                            else:
                                clean_row.append(0)
                        elif col_name in date_headers:
                            # Normalize date value
                            clean_row.append(normalize_date_value(raw_val, col_name))
                        else:
                            clean_row.append(raw_val)

                    # Skip rows where all values are empty/zero
                    if all(value in (0, 0.0, '0', '0.0', "", None) for value in clean_row):
                        print(f"⚠️  Skipping empty row for table '{table}'.")
                    else:
                        print(f"Importing row into '{table}': {clean_row}")
                        cursor.execute(sql, clean_row)
                        row_count += 1

            print(f"✅ Imported {row_count} rows into '{table}'")

        except Exception as e:
            print(f"❌ Error importing '{table}': {e}")

    conn.commit()
    conn.close()


# ─── Interactive Menu ─────────────────────────────────────────────────────────

def select_table_menu(action_name):
    """Display table selection list."""
    print(f"\nSelect Table to {action_name}:")
    print("0. All Tables")
    for idx, table in enumerate(TABLES, 1):
        print(f"{idx}. {table}")

    try:
        choice = int(input(f"Enter choice (0-{len(TABLES)}): "))
        if choice == 0:
            return None
        elif 1 <= choice <= len(TABLES):
            return TABLES[choice - 1]
        else:
            print("⚠️  Invalid index. Defaulting to all tables.")
            return None
    except ValueError:
        print("⚠️  Invalid input. Defaulting to all tables.")
        return None


if __name__ == "__main__":
    print("--- 📂 SQLite to CSV Sync Utility ---")
    print(f"📊 Database: {DB_NAME}")
    print(f"📋 Tables found: {', '.join(TABLES)}\n")
    print("1. Export Database to CSVs")
    print("2. Import CSVs to Database")
    main_choice = input("Enter choice (1 or 2): ")

    if main_choice == '1':
        selected_table = select_table_menu("Export")
        export_to_csv(selected_table)
    elif main_choice == '2':
        selected_table = select_table_menu("Import")
        import_from_csv(selected_table)
    else:
        print("Invalid choice.")