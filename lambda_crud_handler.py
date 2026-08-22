import json
import os
from s3_db_sync import s3_db_wrapper
from crud_db import (
    # Stocks
    get_stock, insert_stock, update_stock, delete_stock,
    # Portfolio
    insert_portfolio, update_portfolio, delete_portfolio,
    get_portfolio, get_latest_portfolio, get_all_portfolio_entries,
    # Transactions
    insert_transaction, update_transaction, delete_transaction, get_transactions,
    # Watchlist
    insert_watchlist, update_watchlist, delete_watchlist, get_watchlist,
    # Dividends
    insert_dividend, update_dividend, delete_dividend, get_dividends,
    # Monthly Snapshots
    insert_monthly_snapshot, update_monthly_snapshot, delete_monthly_snapshot, get_monthly_snapshots,
    # Monthly PnL
    insert_monthly_pnl, update_monthly_pnl, delete_monthly_pnl, get_monthly_pnl,
    # Mortgage
    insert_mortgage_monthly, update_mortgage_monthly, delete_mortgage_monthly, get_mortgage_monthly,
    # Ledger
    insert_ledger_entry, update_ledger_entry, delete_ledger_entry, get_ledger_entries,
)
from services.validation_service import validate_payload
from services.transaction_service import process_transaction, process_transaction_update
from services.monthly_snapshot_service import generate_monthly_snapshot

LOCAL_DEV = os.environ.get("LOCAL_DEV") == "1"


# ══════════════════════════════════════════════════════════════
#  ROUTE REGISTRY
# ══════════════════════════════════════════════════════════════

ROUTE_MAP = {
    # ── Portfolio ─────────────────────────────────────────────
    ("portfolio", "insert"): {
        "handler": lambda p: insert_portfolio(
            symbol=p["symbol"],
            quantity=p["quantity"],
            avg_buy_price=p["avg_buy_price"],
            trading_date=p.get("trading_date"),
            transaction_reference_id=p.get("transaction_reference_id"),
        ),
        "required": ["symbol", "quantity", "avg_buy_price"],
    },
    ("portfolio", "update"): {
        "handler": lambda p: update_portfolio(
            portfolio_id=p["portfolio_id"],
            quantity=p.get("quantity"),
            avg_buy_price=p.get("avg_buy_price"),
            trading_date=p.get("trading_date"),
            transaction_reference_id=p.get("transaction_reference_id"),
        ),
        "required": ["portfolio_id"],
    },
    ("portfolio", "delete"): {
        "handler": lambda p: delete_portfolio(portfolio_id=p["portfolio_id"]),
        "required": ["portfolio_id"],
    },
    ("portfolio", "get"): {
        "handler": lambda p: get_latest_portfolio(),
        "required": [],
    },
    ("portfolio", "get_all"): {
        "handler": lambda p: get_all_portfolio_entries(),
        "required": [],
    },

    # ── Transactions ──────────────────────────────────────────
    ("transaction", "insert"): {
        # ┌──────────────────────────────────────────────────────────┐
        # │  CHANGED: Now calls process_transaction (service layer)   │
        # │  which handles BOTH the insert AND portfolio adjustment   │
        # └──────────────────────────────────────────────────────────┘
        "handler": lambda p: process_transaction(
            symbol=p["symbol"],
            type=p["type"],
            quantity=p["quantity"],
            price=p["price"],
            notes=p.get("notes"),
            transaction_date=p.get("transaction_date"),
        ),
        "required": ["symbol", "type", "quantity", "price"],
    },

    ("transaction", "update"): {
        # ┌──────────────────────────────────────────────────────────┐
        # │  CHANGED: Now calls process_transaction_update            │
        # │  which updates the transaction AND adjusts the portfolio  │
        # │  NEW: Also accepts "symbol" to locate portfolio entry     │
        # └──────────────────────────────────────────────────────────┘
        "handler": lambda p: process_transaction_update(
            transaction_id=p["transaction_id"],
            symbol=p.get("symbol"),
            type=p.get("type"),
            quantity=p.get("quantity"),
            price=p.get("price"),
            notes=p.get("notes"),
            transaction_date=p.get("transaction_date"),
        ),
        "required": ["transaction_id"],
    },

    ("transaction", "delete"): {
        "handler": lambda p: delete_transaction(transaction_id=p["transaction_id"]),
        "required": ["transaction_id"],
    },
    ("transaction", "get"): {
        "handler": lambda p: get_transactions(
            year_month=p["year_month"],
            symbol=p.get("symbol"),
        ),
        "required": ["year_month"],
    },

    # ── Ledger ────────────────────────────────────────────────
    ("ledger", "insert"): {
        "handler": lambda p: insert_ledger_entry(
            type=p["type"],
            category=p["category"],
            amount=p["amount"],
            ledger_datetime=p.get("ledger_datetime"),
            comment=p.get("comment"),
        ),
        "required": ["type", "category", "amount"],
    },
    ("ledger", "update"): {
        "handler": lambda p: update_ledger_entry(
            entry_id=p["entry_id"],
            ledger_datetime=p.get("ledger_datetime"),
            type=p.get("type"),
            category=p.get("category"),
            amount=p.get("amount"),
            comment=p.get("comment"),
        ),
        "required": ["entry_id"],
    },
    ("ledger", "delete"): {
        "handler": lambda p: delete_ledger_entry(entry_id=p["entry_id"]),
        "required": ["entry_id"],
    },
    ("ledger", "get"): {
        "handler": lambda p: get_ledger_entries(
            start_date=p.get("start_date"),
            end_date=p.get("end_date"),
            type=p.get("type"),
            category=p.get("category"),
            month_str=p.get("month_str"),
        ),
        "required": [],
    },

    # ── Monthly PnL ──────────────────────────────────────────
    ("monthly_pnl", "insert"): {
        "handler": lambda p: insert_monthly_pnl(
            open_bal=p["open_bal"],
            income=p["income"],
            expenses=p["expenses"],
            stock_pnl=p["stock_pnl"],
            dividend=p["dividend"],
            year_month=p.get("year_month"),
            pnl_date=p.get("pnl_date"),
        ),
        "required": ["open_bal", "income", "expenses", "stock_pnl", "dividend"],
    },
    ("monthly_pnl", "update"): {
        "handler": lambda p: update_monthly_pnl(
            year_month=p["year_month"],
            open_bal=p.get("open_bal"),
            income=p.get("income"),
            expenses=p.get("expenses"),
            stock_pnl=p.get("stock_pnl"),
            dividend=p.get("dividend"),
            pnl_date=p.get("pnl_date"),
        ),
        "required": ["year_month"],
    },
    ("monthly_pnl", "delete"): {
        "handler": lambda p: delete_monthly_pnl(year_month=p["year_month"]),
        "required": ["year_month"],
    },
    ("monthly_pnl", "get"): {
        "handler": lambda p: get_monthly_pnl(
            year_month=p.get("year_month"),
            pnl_date=p.get("pnl_date"),
        ),
        "required": [],
    },

    # ── Dividends ─────────────────────────────────────────────
    ("dividend", "insert"): {
        "handler": lambda p: insert_dividend(
            symbol=p["symbol"],
            amount_per_share=p["amount_per_share"],
            quantity=p["quantity"],
            payment_date=p.get("payment_date"),
        ),
        "required": ["symbol", "amount_per_share", "quantity"],
    },
    ("dividend", "update"): {
        "handler": lambda p: update_dividend(
            dividend_id=p["dividend_id"],
            amount_per_share=p.get("amount_per_share"),
            quantity=p.get("quantity"),
            payment_date=p.get("payment_date"),
        ),
        "required": ["dividend_id"],
    },
    ("dividend", "delete"): {
        "handler": lambda p: delete_dividend(dividend_id=p["dividend_id"]),
        "required": ["dividend_id"],
    },
    ("dividend", "get"): {
        "handler": lambda p: get_dividends(
            symbol=p.get("symbol"),
            year_month=p.get("year_month"),
        ),
        "required": [],
    },

        # ── Monthly Snapshots ─────────────────────────────────────
    ("snapshot", "generate"): {
        "handler": lambda p: generate_monthly_snapshot(debug_mode=p.get("debug_mode", False)),
        "required": [],
    },
    ("snapshot", "insert"): {
        "handler": lambda p: insert_monthly_snapshot(
            stock_symbol=p["stock_symbol"],
            start_quantity=p["start_quantity"],
            start_price=p["start_price"],
            year_month=p.get("year_month"),
            snapshot_date=p.get("snapshot_date"),
        ),
        "required": ["stock_symbol", "start_quantity", "start_price"],
    },
    ("snapshot", "update"): {
        "handler": lambda p: update_monthly_snapshot(
            year_month=p["year_month"],
            stock_symbol=p["stock_symbol"],
            start_quantity=p.get("start_quantity"),
            start_price=p.get("start_price"),
            snapshot_date=p.get("snapshot_date"),
        ),
        "required": ["year_month", "stock_symbol"],
    },
    ("snapshot", "delete"): {
        "handler": lambda p: delete_monthly_snapshot(
            year_month=p["year_month"],
            stock_symbol=p["stock_symbol"],
        ),
        "required": ["year_month", "stock_symbol"],
    },
    ("snapshot", "get"): {
        "handler": lambda p: get_monthly_snapshots(
            year_month=p.get("year_month"),
            stock_symbol=p.get("stock_symbol"),
        ),
        "required": [],
    },

    # ── Mortgage ──────────────────────────────────────────────
    ("mortgage", "insert"): {
        "handler": lambda p: insert_mortgage_monthly(
            principal=p["principal"],
            interest=p["interest"],
            remaining_balance=p["remaining_balance"],
            year_month=p.get("year_month"),
            period=p.get("period"),
        ),
        "required": ["principal", "interest", "remaining_balance"],
    },
    ("mortgage", "update"): {
        "handler": lambda p: update_mortgage_monthly(
            year_month=p["year_month"],
            principal=p.get("principal"),
            interest=p.get("interest"),
            remaining_balance=p.get("remaining_balance"),
            period=p.get("period"),
        ),
        "required": ["year_month"],
    },
    ("mortgage", "delete"): {
        "handler": lambda p: delete_mortgage_monthly(year_month=p["year_month"]),
        "required": ["year_month"],
    },
    ("mortgage", "get"): {
        "handler": lambda p: get_mortgage_monthly(
            year_month=p.get("year_month"),
            period=p.get("period"),
        ),
        "required": [],
    },

    # ── Stock (master) ────────────────────────────────────────
    ("stock", "get"): {
        "handler": lambda p: get_stock(symbol=p["symbol"]),
        "required": ["symbol"],
    },
    ("stock", "insert"): {
        "handler": lambda p: insert_stock(
            symbol=p["symbol"],
            name=p["name"],
            sector=p.get("sector"),
            currency=p.get("currency", "HKD"),
        ),
        "required": ["symbol", "name"],
    },
    ("stock", "update"): {
        "handler": lambda p: update_stock(
            symbol=p["symbol"],
            name=p.get("name"),
            sector=p.get("sector"),
            currency=p.get("currency"),
        ),
        "required": ["symbol"],
    },
    ("stock", "delete"): {
        "handler": lambda p: delete_stock(symbol=p["symbol"]),
        "required": ["symbol"],
    },

    # ── Watchlist ─────────────────────────────────────────────
    ("watchlist", "insert"): {
        "handler": lambda p: insert_watchlist(
            symbol=p["symbol"],
            target_price=p.get("target_price"),
            notes=p.get("notes"),
        ),
        "required": ["symbol"],
    },
    ("watchlist", "update"): {
        "handler": lambda p: update_watchlist(
            symbol=p["symbol"],
            target_price=p.get("target_price"),
            notes=p.get("notes"),
        ),
        "required": ["symbol"],
    },
    ("watchlist", "delete"): {
        "handler": lambda p: delete_watchlist(symbol=p["symbol"]),
        "required": ["symbol"],
    },
    ("watchlist", "get"): {
        "handler": lambda p: get_watchlist(),
        "required": [],
    },
}


# ══════════════════════════════════════════════════════════════
#  HELPER: Extract payload from various API Gateway formats
# ══════════════════════════════════════════════════════════════

def extract_payload(event: dict) -> dict:
    """
    Extracts the request body/payload regardless of how the event arrives:
      - Direct invocation (event IS the payload)
      - API Gateway REST (body is JSON string)
      - API Gateway HTTP API v2
    """
    # If body exists (API Gateway), parse it
    body = event.get("body")
    if body:
        try:
            return json.loads(body) if isinstance(body, str) else body
        except (json.JSONDecodeError, TypeError):
            return {}

    # Otherwise assume direct invocation — event itself holds the fields
    return event


def extract_route(event: dict, parsed_body: dict = None) -> tuple:
    """
    Extract (resource, action) from path parameters or from the payload.
    Supports:
      - API Gateway path: /crud/{resource}/{action}
      - JSON body keys: {"resource_name": "...", "action": "..."}
      - Direct event keys: {"resource_name": "...", "action": "..."}
    """
    if parsed_body is None:
        parsed_body = {}

    # 1. Try path parameters first (API Gateway proxy integration)
    path_params = event.get("pathParameters") or {}
    resource = path_params.get("resource")
    action = path_params.get("action")

    if resource and action:
        return resource.lower(), action.lower()

    # 2. Check parsed body (API Gateway POST with JSON body)
    resource = parsed_body.get("resource_name") or parsed_body.get("resource")
    action = parsed_body.get("action")

    if resource and action:
        return resource.lower(), action.lower()

    # 3. Fallback: check top-level event (for Lambda console / direct invoke)
    resource = event.get("resource_name") or event.get("resource")
    action = event.get("action")

    if resource and action:
        return resource.lower(), action.lower()

    return None, None

# ══════════════════════════════════════════════════════════════
#  LAMBDA HANDLER
# ══════════════════════════════════════════════════════════════

def lambda_handler(event, context):
    

    # ─── Handle CORS preflight ─────────────────────────────
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if not http_method:
        http_method = event.get("httpMethod", "")
    
    if http_method.upper() == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": "",
        }
    # ───────────────────────────────────────────────────────

    try:
        # Parse body for API Gateway events
        parsed_body = extract_payload(event)

        # Extract route from path params OR parsed body
        resource, action = extract_route(event, parsed_body)

        # Extract the nested payload (or use the body minus routing keys)
        payload = parsed_body.get("payload") if isinstance(parsed_body.get("payload"), dict) else {}
        if not payload:
            # Fallback: use parsed body but strip routing keys
            payload = {k: v for k, v in parsed_body.items() if k not in ("resource_name", "resource", "action", "operation", "payload")}

        if not resource or not action:
            return _response(400, {"error": "Missing 'resource_name' and/or 'action' in the request."})

        route_key = (resource, action)
        route = ROUTE_MAP.get(route_key)

        if not route:
            supported = sorted(set(k[0] for k in ROUTE_MAP.keys()))
            return _response(400, {
                "error": f"Unknown route: resource='{resource}', action='{action}'",
                "supported_resources": supported,
                "hint": "Valid actions are typically: insert, update, delete, get"
            })

        # Validate required fields
        missing = [f for f in route["required"] if f not in payload or payload[f] is None]
        if missing:
            return _response(400, {
                "error": f"Missing required fields for {resource}/{action}",
                "missing_fields": missing,
            })

        # Validation service
        errors = validate_payload(resource, payload)
        if errors:
            return _response(400, {"error": "Validation failed", "details": errors})

        # Execute within S3 sync wrapper (or locally)
        if LOCAL_DEV:
            result = route["handler"](payload)
        else:
            with s3_db_wrapper():
                result = route["handler"](payload)

        # Format result for response
        response_body = {
            "message": f"{action.capitalize()} on '{resource}' completed successfully.",
            "resource": resource,
            "action": action,
        }

        if result is not None:
            if isinstance(result, list):
                response_body["data"] = result
                response_body["count"] = len(result)
            elif isinstance(result, dict):
                response_body["data"] = result
            else:
                response_body["data"] = str(result)

        return _response(200, response_body)

    except Exception as e:
        print(f"❌ CRUD Lambda error: {e}")
        import traceback
        traceback.print_exc()
        return _response(500, {"error": str(e)})

def _response(status_code: int, body: dict) -> dict:
    """Standard API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body, indent=2, default=str),
    }


# ══════════════════════════════════════════════════════════════
#  LOCAL TESTING
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    os.environ["LOCAL_DEV"] = "1"
    print("🚀 Running CRUD Lambda locally...\n")

    # Example 1: Insert a ledger entry
    test_event_1 = {
        "resource_name": "ledger",
        "action": "insert",
        "payload": {
            "type": "E",
            "category": "Groceries",
            "amount": 350.00,
            "ledger_datetime": "2026-08-15",
            "comment": "Weekly groceries"
        }
    }

    # Example 2: Insert a transaction (BUY)
    test_event_2 = {
        "resource_name": "transaction",
        "action": "insert",
        "payload": {
            "symbol": "0700.HK",
            "type": "BUY",
            "quantity": 400,
            "price": 458.50,
            "notes": "Accumulated Tencent shares",
            "transaction_date": "2026-08-22"
        }
    }

    # Example 3: Get all PnL
    test_event_3 = {
        "resource_name": "monthly_pnl",
        "action": "get",
        "payload": {}
    }

    # Example 4: Insert dividend
    test_event_4 = {
        "resource_name": "dividend",
        "action": "insert",
        "payload": {
            "symbol": "0005.HK",
            "amount_per_share": 0.30,
            "quantity": 400,
            "payment_date": "2026-08-20"
        }
    }

    test_event_5 = {
        "resource_name": "snapshot",
        "action": "generate",
        "payload": {
            "debug_mode": True
        }
    }

    # Run tests
    for i, evt in enumerate([test_event_1, test_event_2, test_event_3, test_event_4, test_event_5], 1):
        print(f"\n{'='*60}")
        print(f"  TEST {i}: {evt['resource_name']}/{evt['action']}")
        print(f"{'='*60}")
        resp = lambda_handler(evt, None)
        print(f"Status: {resp['statusCode']}")
        print(f"Body: {resp['body']}")