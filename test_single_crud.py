import os
import json

# ── Must set BEFORE importing the handler ──
os.environ["LOCAL_DEV"] = "1"
os.environ.setdefault("AWS_REGION", "ap-east-1")
os.environ.setdefault("STOCK_RETRIEVAL_FUNCTION_NAME", "getStockData")

from lambda_crud_handler import lambda_handler


def invoke(resource, action, payload=None):
    """Helper to invoke the handler and pretty-print the response."""
    event = {
        "resource_name": resource,
        "action": action,
        "payload": payload or {}
    }
    response = lambda_handler(event, None)
    status = response["statusCode"]
    body = json.loads(response["body"])

    print(f"\n{'─'*50}")
    print(f"  {resource}/{action}  →  HTTP {status}")
    print(f"{'─'*50}")
    print(json.dumps(body, indent=2, default=str))
    return body


def section_header(title):
    """Print a section header for readability."""
    print(f"\n\n{'═'*60}")
    print(f"  📦 {title}")
    print(f"{'═'*60}")


if __name__ == "__main__":

    # ═══════════════════════════════════════════════════════════
    #  1️⃣  PORTFOLIO CRUD
    # ═══════════════════════════════════════════════════════════
    section_header("PORTFOLIO")

    # Insert
    invoke("portfolio", "insert", {
        "symbol": "0005.HK",
        "quantity": 1000,
        "avg_buy_price": 55.20,
        "trading_date": "2026-07-15",
        "transaction_reference_id": None
    })

    invoke("portfolio", "insert", {
        "symbol": "9988.HK",
        "quantity": 200,
        "avg_buy_price": 82.50,
        "trading_date": "2026-08-01"
    })

    invoke("portfolio", "insert", {
        "symbol": "0700.HK",
        "quantity": 100,
        "avg_buy_price": 320.00,
        "trading_date": "2026-08-10"
    })

    # Get latest portfolio
    invoke("portfolio", "get")

    # Get all portfolio entries (history)
    invoke("portfolio", "get_all")

    # Update
    invoke("portfolio", "update", {
        "portfolio_id": 1,
        "quantity": 1400,
        "avg_buy_price": 56.80,
        "trading_date": "2026-08-18"
    })

    # Get after update
    invoke("portfolio", "get")

    # Delete
    invoke("portfolio", "delete", {
        "portfolio_id": 3
    })

    # Get after delete
    invoke("portfolio", "get")

    # ═══════════════════════════════════════════════════════════
    #  2️⃣  TRANSACTIONS CRUD
    # ═══════════════════════════════════════════════════════════
    section_header("TRANSACTIONS")

    # Insert - BUY
    invoke("transaction", "insert", {
        "symbol": "0005.HK",
        "type": "BUY",
        "quantity": 400,
        "price": 58.50,
        "transaction_date": "2026-08-05",
        "notes": "Accumulated HSBC on dip"
    })

    # Insert - BUY another stock
    invoke("transaction", "insert", {
        "symbol": "9988.HK",
        "type": "BUY",
        "quantity": 100,
        "price": 80.00,
        "transaction_date": "2026-08-10",
        "notes": "Initial Alibaba position"
    })

    # Insert - SELL
    invoke("transaction", "insert", {
        "symbol": "0005.HK",
        "type": "SELL",
        "quantity": 200,
        "price": 62.30,
        "transaction_date": "2026-08-15",
        "notes": "Partial profit taking"
    })

    # Insert - BUY in different month
    invoke("transaction", "insert", {
        "symbol": "0700.HK",
        "type": "BUY",
        "quantity": 100,
        "price": 315.00,
        "transaction_date": "2026-07-20",
        "notes": "Tencent July buy"
    })

    # Get - this month
    invoke("transaction", "get", {
        "year_month": "2026-08"
    })

    # Get - previous month
    invoke("transaction", "get", {
        "year_month": "2026-07"
    })

    # Get - filtered by symbol
    invoke("transaction", "get", {
        "year_month": "2026-08",
        "symbol": "0005.HK"
    })

    # Update
    invoke("transaction", "update", {
        "transaction_id": 1,
        "price": 57.90,
        "notes": "Corrected price - was 58.50"
    })

    # Get after update
    invoke("transaction", "get", {
        "year_month": "2026-08",
        "symbol": "0005.HK"
    })

    # Delete
    invoke("transaction", "delete", {
        "transaction_id": 4
    })

    # Verify deletion
    invoke("transaction", "get", {
        "year_month": "2026-07"
    })

    # ═══════════════════════════════════════════════════════════
    #  3️⃣  LEDGER CRUD
    # ═══════════════════════════════════════════════════════════
    section_header("LEDGER")

    # Insert - Income
    invoke("ledger", "insert", {
        "type": "I",
        "category": "Salary",
        "amount": 45000.00,
        "ledger_datetime": "2026-08-01",
        "comment": "August salary"
    })

    # Insert - Income (bonus)
    invoke("ledger", "insert", {
        "type": "I",
        "category": "Bonus",
        "amount": 10000.00,
        "ledger_datetime": "2026-08-15",
        "comment": "Mid-year bonus"
    })

    # Insert - Expense (rent)
    invoke("ledger", "insert", {
        "type": "E",
        "category": "Rent",
        "amount": 15000.00,
        "ledger_datetime": "2026-08-01",
        "comment": "Monthly rent"
    })

    # Insert - Expense (dining)
    invoke("ledger", "insert", {
        "type": "E",
        "category": "Dining",
        "amount": 280.00,
        "ledger_datetime": "2026-08-20",
        "comment": "Dinner with family"
    })

    # Insert - Expense (utilities)
    invoke("ledger", "insert", {
        "type": "E",
        "category": "Utilities",
        "amount": 850.00,
        "ledger_datetime": "2026-08-10",
        "comment": "Electricity + Water"
    })

    # Insert - Expense (transport)
    invoke("ledger", "insert", {
        "type": "E",
        "category": "Transport",
        "amount": 600.00,
        "ledger_datetime": "2026-08-12",
        "comment": "Octopus top-up"
    })

    # Insert - July entry
    invoke("ledger", "insert", {
        "type": "E",
        "category": "Groceries",
        "amount": 1200.00,
        "ledger_datetime": "2026-07-25",
        "comment": "Weekly groceries"
    })

    # Get - by month
    invoke("ledger", "get", {
        "month_str": "2026-08"
    })

    # Get - by type
    invoke("ledger", "get", {
        "month_str": "2026-08",
        "type": "E"
    })

    # Get - by category
    invoke("ledger", "get", {
        "category": "Rent"
    })

    # Get - by date range
    invoke("ledger", "get", {
        "start_date": "2026-08-01",
        "end_date": "2026-08-15"
    })

    # Get - July entries
    invoke("ledger", "get", {
        "month_str": "2026-07"
    })

    # Update
    invoke("ledger", "update", {
        "entry_id": 4,
        "amount": 320.00,
        "comment": "Dinner with family (updated - included drinks)"
    })

    # Get after update
    invoke("ledger", "get", {
        "month_str": "2026-08",
        "category": "Dining"
    })

    # Delete
    invoke("ledger", "delete", {
        "entry_id": 7
    })

    # Verify deletion
    invoke("ledger", "get", {
        "month_str": "2026-07"
    })

    # ═══════════════════════════════════════════════════════════
    #  4️⃣  MONTHLY PNL CRUD
    # ═══════════════════════════════════════════════════════════
    section_header("MONTHLY PNL")

    # Insert - August
    invoke("monthly_pnl", "insert", {
        "open_bal": 150000.00,
        "income": 55000.00,
        "expenses": 22000.00,
        "stock_pnl": 3500.00,
        "dividend": 800.00,
        "year_month": "2026-08",
        "pnl_date": "2026-08-31"
    })

    # Insert - July
    invoke("monthly_pnl", "insert", {
        "open_bal": 125000.00,
        "income": 45000.00,
        "expenses": 20000.00,
        "stock_pnl": -1200.00,
        "dividend": 600.00,
        "year_month": "2026-07",
        "pnl_date": "2026-07-31"
    })

    # Insert - June
    invoke("monthly_pnl", "insert", {
        "open_bal": 110000.00,
        "income": 45000.00,
        "expenses": 30500.00,
        "stock_pnl": 2000.00,
        "dividend": 500.00,
        "year_month": "2026-06",
        "pnl_date": "2026-06-30"
    })

    # Get all
    invoke("monthly_pnl", "get")

    # Get specific month
    invoke("monthly_pnl", "get", {
        "year_month": "2026-08"
    })

    # Update
    invoke("monthly_pnl", "update", {
        "year_month": "2026-08",
        "expenses": 23500.00,
        "stock_pnl": 4200.00
    })

    # Get after update
    invoke("monthly_pnl", "get", {
        "year_month": "2026-08"
    })

    # Delete
    invoke("monthly_pnl", "delete", {
        "year_month": "2026-06"
    })

    # Get all after delete
    invoke("monthly_pnl", "get")

    # ═══════════════════════════════════════════════════════════
    #  5️⃣  DIVIDENDS CRUD
    # ═══════════════════════════════════════════════════════════
    section_header("DIVIDENDS")

    # Insert - HSBC Q3
    invoke("dividend", "insert", {
        "symbol": "0005.HK",
        "amount_per_share": 0.30,
        "quantity": 1000,
        "payment_date": "2026-08-15"
    })

    # Insert - HSBC Q2
    invoke("dividend", "insert", {
        "symbol": "0005.HK",
        "amount_per_share": 0.28,
        "quantity": 1000,
        "payment_date": "2026-05-20"
    })

    # Insert - Tencent
    invoke("dividend", "insert", {
        "symbol": "0700.HK",
        "amount_per_share": 1.60,
        "quantity": 100,
        "payment_date": "2026-08-10"
    })

    # Insert - Alibaba
    invoke("dividend", "insert", {
        "symbol": "9988.HK",
        "amount_per_share": 0.50,
        "quantity": 200,
        "payment_date": "2026-07-30"
    })

    # Get all dividends
    invoke("dividend", "get")

    # Get by symbol
    invoke("dividend", "get", {
        "symbol": "0005.HK"
    })

    # Get by month
    invoke("dividend", "get", {
        "year_month": "2026-08"
    })

    # Update
    invoke("dividend", "update", {
        "dividend_id": 1,
        "amount_per_share": 0.32,
        "quantity": 1400
    })

    # Get after update
    invoke("dividend", "get", {
        "symbol": "0005.HK"
    })

    # Delete
    invoke("dividend", "delete", {
        "dividend_id": 2
    })

    # Get after delete
    invoke("dividend", "get", {
        "symbol": "0005.HK"
    })

    # ═══════════════════════════════════════════════════════════
    #  6️⃣  MONTHLY SNAPSHOTS CRUD
    # ═══════════════════════════════════════════════════════════
    section_header("MONTHLY SNAPSHOTS")

    # Insert - August snapshots
    invoke("snapshot", "insert", {
        "stock_symbol": "0005.HK",
        "start_quantity": 1000,
        "start_price": 55.20,
        "year_month": "2026-08",
        "snapshot_date": "2026-08-01"
    })

    invoke("snapshot", "insert", {
        "stock_symbol": "9988.HK",
        "start_quantity": 200,
        "start_price": 80.00,
        "year_month": "2026-08",
        "snapshot_date": "2026-08-01"
    })

    invoke("snapshot", "insert", {
        "stock_symbol": "0700.HK",
        "start_quantity": 100,
        "start_price": 310.00,
        "year_month": "2026-08",
        "snapshot_date": "2026-08-01"
    })

    # Insert - July snapshot
    invoke("snapshot", "insert", {
        "stock_symbol": "0005.HK",
        "start_quantity": 600,
        "start_price": 52.00,
        "year_month": "2026-07",
        "snapshot_date": "2026-07-01"
    })

    # Get all snapshots
    invoke("snapshot", "get")

    # Get by month
    invoke("snapshot", "get", {
        "year_month": "2026-08"
    })

    # Get by symbol
    invoke("snapshot", "get", {
        "stock_symbol": "0005.HK"
    })

    # Get by month + symbol
    invoke("snapshot", "get", {
        "year_month": "2026-08",
        "stock_symbol": "9988.HK"
    })

    # Update
    invoke("snapshot", "update", {
        "year_month": "2026-08",
        "stock_symbol": "0005.HK",
        "start_quantity": 1000,
        "start_price": 56.00
    })

    # Get after update
    invoke("snapshot", "get", {
        "year_month": "2026-08",
        "stock_symbol": "0005.HK"
    })

    # Delete
    invoke("snapshot", "delete", {
        "year_month": "2026-07",
        "stock_symbol": "0005.HK"
    })

    # Verify deletion
    invoke("snapshot", "get", {
        "year_month": "2026-07"
    })

    # ═══════════════════════════════════════════════════════════
    #  7️⃣  MORTGAGE CRUD
    # ═══════════════════════════════════════════════════════════
    section_header("MORTGAGE")

    # Insert - multiple months
    invoke("mortgage", "insert", {
        "principal": 8500.00,
        "interest": 6200.00,
        "remaining_balance": 2850000.00,
        "year_month": "2026-08",
        "period": 48
    })

    invoke("mortgage", "insert", {
        "principal": 8400.00,
        "interest": 6300.00,
        "remaining_balance": 2858500.00,
        "year_month": "2026-07",
        "period": 47
    })

    invoke("mortgage", "insert", {
        "principal": 8300.00,
        "interest": 6400.00,
        "remaining_balance": 2866900.00,
        "year_month": "2026-06",
        "period": 46
    })

    # Get all
    invoke("mortgage", "get")

    # Get by month
    invoke("mortgage", "get", {
        "year_month": "2026-08"
    })

    # Get by period
    invoke("mortgage", "get", {
        "period": 47
    })

    # Update
    invoke("mortgage", "update", {
        "year_month": "2026-08",
        "principal": 8550.00,
        "interest": 6150.00
    })

    # Get after update
    invoke("mortgage", "get", {
        "year_month": "2026-08"
    })

    # Delete
    invoke("mortgage", "delete", {
        "year_month": "2026-06"
    })

    # Get all after delete
    invoke("mortgage", "get")

    # ═══════════════════════════════════════════════════════════
    #  8️⃣  STOCK (MASTER) CRUD
    # ═══════════════════════════════════════════════════════════
    section_header("STOCK (MASTER)")

    # Get existing stock
    invoke("stock", "get", {
        "symbol": "0005.HK"
    })

    invoke("stock", "get", {
        "symbol": "9988.HK"
    })

    # Update stock details
    invoke("stock", "update", {
        "symbol": "0005.HK",
        "name": "HSBC Holdings plc",
        "sector": "Banking & Finance",
        "currency": "HKD"
    })

    invoke("stock", "update", {
        "symbol": "9988.HK",
        "sector": "E-Commerce & Cloud"
    })

    # Get after update
    invoke("stock", "get", {
        "symbol": "0005.HK"
    })

    invoke("stock", "get", {
        "symbol": "9988.HK"
    })

    # Delete (be careful - FK constraints may apply)
    # Only delete a stock not referenced elsewhere
    invoke("stock", "delete", {
        "symbol": "TEST.HK"
    })

    # ═══════════════════════════════════════════════════════════
    #  9️⃣  WATCHLIST CRUD
    # ═══════════════════════════════════════════════════════════
    section_header("WATCHLIST")

    # Insert
    invoke("watchlist", "insert", {
        "symbol": "1810.HK",
        "target_price": 15.00,
        "notes": "Xiaomi - wait for pullback to $15"
    })

    invoke("watchlist", "insert", {
        "symbol": "2318.HK",
        "target_price": 45.00,
        "notes": "Ping An Insurance - undervalued"
    })

    invoke("watchlist", "insert", {
        "symbol": "3690.HK",
        "target_price": 260.00,
        "notes": "Meituan - watch for earnings"
    })

    invoke("watchlist", "insert", {
        "symbol": "0388.HK",
        "target_price": 280.00,
        "notes": "HKEX - long term hold candidate"
    })

    # Get all
    invoke("watchlist", "get")

    # Update
    invoke("watchlist", "update", {
        "symbol": "1810.HK",
        "target_price": 14.50,
        "notes": "Xiaomi - revised target after earnings miss"
    })

    invoke("watchlist", "update", {
        "symbol": "3690.HK",
        "target_price": 250.00,
        "notes": "Meituan - lowered target, competition concerns"
    })

    # Get after update
    invoke("watchlist", "get")

    # Delete
    invoke("watchlist", "delete", {
        "symbol": "0388.HK"
    })

    # Get after delete
    invoke("watchlist", "get")

    # ═══════════════════════════════════════════════════════════
    #  🚨 ERROR HANDLING TESTS
    # ═══════════════════════════════════════════════════════════
    section_header("ERROR HANDLING")

    # Missing required fields
    invoke("ledger", "insert", {
        "type": "E",
        "category": "Food",
        "amount": 150.00
    })


    print("These are intentional error tests to verify that the handler returns HTTP 400 for invalid requests.\n")
    # Unknown resource
    invoke("unknown_resource", "insert", {
        "foo": "bar"
    })

    # Unknown action
    invoke("portfolio", "unknown_action", {})

    # Missing resource/action entirely
    response = lambda_handler({"some_random_key": "value"}, None)
    print(f"\n{'─'*50}")
    print(f"  (missing resource & action)  →  HTTP {response['statusCode']}")
    print(f"{'─'*50}")
    print(json.dumps(json.loads(response["body"]), indent=2))

    # Invalid portfolio_id for update
    invoke("portfolio", "update", {
        "portfolio_id": 99999,
        "quantity": 500
    })

    # Insert transaction with missing price
    invoke("transaction", "insert", {
        "symbol": "0005.HK",
        "type": "BUY",
        "quantity": 100,
        "price" : 52.35
    })

    # Delete non-existent dividend
    invoke("dividend", "delete", {
        "dividend_id": 99999
    })

    # ═══════════════════════════════════════════════════════════
    #  📊 SUMMARY
    # ═══════════════════════════════════════════════════════════
    section_header("ALL TESTS COMPLETED ✅")
    print("\n  Review output above for any unexpected HTTP 500 errors.")
    print("  HTTP 400 errors in the 'ERROR HANDLING' section are expected.\n")