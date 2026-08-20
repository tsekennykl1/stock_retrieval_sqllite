import sqlite3
import csv
import os
from pathlib import Path

DB_NAME = "mystocks.db"

def get_connection():
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

TABLES = get_all_tables()

def export_to_csv(target_table=None):
    """Export tables from the database to individual CSV files."""
    conn = get_connection()
    cursor = conn.cursor()

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

            with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(col_names)  # Write headers
                writer.writerows(rows)      # Write data

            print(f"✅ Exported '{table}' to {csv_filename} ({len(rows)} rows)")
        except sqlite3.OperationalError as e:
            print(f"❌ Error exporting '{table}': {e}")
            
    conn.close()

def import_from_csv(target_table=None):
    """Dynamically import CSV files matching table names into the database."""
    conn = get_connection()
    cursor = conn.cursor()

    tables_to_import = [target_table] if target_table else TABLES

    # Set of SQL generated (virtual/non-writable) columns to exclude
    virtual_cols = {
        'total_dividend', 
        'monthly_gl', 
        'total_amount', 
        'total_invested', 
        'close_bal', 
        #'month_str',
        #'transaction_month_str',
        #'payment_month_str',
        'total_payment'

    }

    for table in tables_to_import:
        csv_filename = os.path.join("csv", f"{table}.csv")
        
        
        if not os.path.exists(csv_filename):
            print(f"⚠️  File '{csv_filename}' not found. Skipping import for '{table}'.")
            continue

        try:
            with open(csv_filename, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                raw_headers = next(reader, None)
                
                if not raw_headers:
                    print(f"⚠️  File '{csv_filename}' is empty.")
                    continue

                # ✅ Strip whitespace and completely filter out empty/blank headers (removes trailing commas)
                headers = [h.strip() for h in raw_headers if h and h.strip()]

                # Remove virtual generated columns from headers if present
                db_headers = [h for h in headers if h not in virtual_cols]
                
                if not db_headers:
                    print(f"⚠️  No writable columns found for table '{table}'. Skipping.")
                    continue

                # Indexes of columns to import
                import_indices = [headers.index(h) for h in db_headers]

                # Dynamically construct INSERT statement using CSV headers
                placeholders = ", ".join(["?"] * len(db_headers))
                columns = ", ".join(db_headers) # ✅ No trailing comma is produced now
                sql = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
                
                row_count = 0
                for row_data in reader:
                    # ✅ Pad row if it has fewer columns than headers (some writers omit trailing empty cells)
                    if len(row_data) < len(headers):
                        row_data += [""] * (len(headers) - len(row_data))
                    
                    # ✅ Aligned to clean headers & converted blank strings to None (fixed the '02' typo to 'None')
                    clean_row = [row_data[i].strip() if row_data[i].strip() != "" else 0 for i in import_indices]
                    print(f"Debug: Cleaned row for table '{table}': {clean_row}")
                    if all(value in (0, 0.0, '0', '0.0',"",None) for value in clean_row):
                        print(f"⚠️  Skipping row with all 0 values for table '{table}'.")
                    else:
                        print(f"Importing row into '{table}': {clean_row}")
                        print(f"Executing SQL: {sql} with values: {clean_row}")
                        cursor.execute(sql, clean_row)
                        row_count += 1

        except Exception as e:
            print(f"❌ Error importing '{table}': {e}")
    conn.commit()
    conn.close()

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