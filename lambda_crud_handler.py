import json
import os
from crud_db import (
    # S3 sync
    upload_db_to_s3,
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
    insert_dividend, update_dividend, delete_dividend, get_dividends, get_all_dividends_from,
    # Monthly Snapshots
    insert_monthly_snapshot, update_monthly_snapshot, delete_monthly_snapshot, get_monthly_snapshots,
    # Monthly PnL
    insert_monthly_pnl, update_monthly_pnl, delete_monthly_pnl, get_monthly_pnl,
    # Mortgage
    insert_mortgage_monthly, update_mortgage_monthly, delete_mortgage_monthly, get_mortgage_monthly,
    # Ledger
    insert_ledger_entry, update_ledger_entry, delete_ledger_entry, get_ledger_entries, get_ledger_entry_by_id,
)
from services.validation_service import validate_payload
from services.transaction_service import process_transaction, process_transaction_update
from services.monthly_snapshot_service import generate_monthly_snapshot

LOCAL_DEV = os.environ.get("LOCAL_DEV") == "1"

# Actions that modify the database → require S3 upload after execution
WRITE_ACTIONS = {"insert", "update", "delete", "generate"}

# Allowed CORS origins
ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "*")


# ══════════════════════════════════════════════════════════════
#  CORS HELPER
# ══════════════════════════════════════════════════════════════

def get_cors_headers(event=None):
    """Return CORS headers. Supports wildcard or specific origin matching."""
    origin = "*"
    if event and ALLOWED_ORIGINS != "*":
        request_origin = (event.get("headers") or {}).get("origin", "")
        allowed_list = [o.strip() for o in ALLOWED_ORIGINS.split(",")]
        if request_origin in allowed_list:
            origin = request_origin

    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, GET, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token",
        "Access-Control-Max-Age": "86400",
    }


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
        # accept either id or entry_id (backward compatible)
        "handler": lambda p: update_ledger_entry(
            entry_id=p.get("id") if p.get("id") is not None else p.get("entry_id"),
            ledger_datetime=p.get("ledger_datetime"),
            type=p.get("type"),
            category=p.get("category"),
            amount=p.get("amount"),
            comment=p.get("comment"),
        ),
        "required": [],  # validated in lambda_handler for id/entry_id
    },
    ("ledger", "delete"): {
        "handler": lambda p: delete_ledger_entry(
            entry_id=p.get("id") if p.get("id") is not None else p.get("entry_id")
        ),
        "required": [],  # validated in lambda_handler for id/entry_id
    },
    ("ledger", "get_by_id"): {
        "handler": lambda p: get_ledger_entry_by_id(entry_id=p["id"]),
        "required": ["id"],
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
        "required": ["year_month"],
    },
    ("dividend", "get_all"): {
        "handler": lambda p: get_all_dividends_from(
            symbol=p.get("symbol"),
            year_month=p.get("year_month"),
        ),
        "required": ["year_month"],
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
    body = event.get("body")
    if body:
        try:
            return json.loads(body) if isinstance(body, str) else body
        except (json.JSONDecodeError, TypeError):
            return {}
    return event


def extract_route(event: dict, parsed_body: dict = None) -> tuple:
    if parsed_body is None:
        parsed_body = {}

    path_params = event.get("pathParameters") or {}
    resource = path_params.get("resource")
    action = path_params.get("action")

    if resource and action:
        return resource.lower(), action.lower()

    resource = parsed_body.get("resource_name") or parsed_body.get("resource")
    action = parsed_body.get("action")

    if resource and action:
        return resource.lower(), action.lower()

    resource = event.get("resource_name") or event.get("resource")
    action = event.get("action")

    if resource and action:
        return resource.lower(), action.lower()

    return None, None


# ══════════════════════════════════════════════════════════════
#  LAMBDA HANDLER
# ══════════════════════════════════════════════════════════════

def lambda_handler(event, context):

    http_method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if not http_method:
        http_method = event.get("httpMethod", "")

    if http_method.upper() == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": get_cors_headers(event),
            "body": "",
        }

    try:
        parsed_body = extract_payload(event)
        resource, action = extract_route(event, parsed_body)

        payload = parsed_body.get("payload") if isinstance(parsed_body.get("payload"), dict) else {}
        if not payload:
            payload = {k: v for k, v in parsed_body.items()
                       if k not in ("resource_name", "resource", "action", "operation", "payload")}

        if not resource or not action:
            return _response(400, {"error": "Missing 'resource_name' and/or 'action' in the request."}, event)

        route_key = (resource, action)
        route = ROUTE_MAP.get(route_key)

        if not route:
            supported = sorted(set(k[0] for k in ROUTE_MAP.keys()))
            return _response(400, {
                "error": f"Unknown route: resource='{resource}', action='{action}'",
                "supported_resources": supported,
                "hint": "Valid actions are typically: insert, update, delete, get"
            }, event)

        # Special-case ledger update/delete: allow either id or entry_id
        if resource == "ledger" and action in ("update", "delete"):
            if payload.get("id") is None and payload.get("entry_id") is None:
                return _response(400, {
                    "error": f"Missing required fields for {resource}/{action}",
                    "missing_fields": ["id (or entry_id)"],
                }, event)

        missing = [f for f in route["required"] if f not in payload or payload[f] is None]
        if missing:
            return _response(400, {
                "error": f"Missing required fields for {resource}/{action}",
                "missing_fields": missing,
            }, event)

        errors = validate_payload(resource, payload)
        if errors:
            return _response(400, {"error": "Validation failed", "details": errors}, event)

        result = route["handler"](payload)

        if action in WRITE_ACTIONS:
            try:
                upload_db_to_s3()
            except Exception as s3_err:
                print(f"⚠️  S3 upload failed (data saved locally): {s3_err}")

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

        return _response(200, response_body, event)

    except Exception as e:
        print(f"❌ CRUD Lambda error: {e}")
        import traceback
        traceback.print_exc()
        return _response(500, {"error": str(e)}, event)


def _response(status_code: int, body: dict, event: dict = None) -> dict:
    return {
        "statusCode": status_code,
        "headers": get_cors_headers(event),
        "body": json.dumps(body, indent=2, default=str),
    }


if __name__ == "__main__":
    os.environ["LOCAL_DEV"] = "1"
    print("🚀 Running CRUD Lambda locally...\n")

    test_event_1 = {
        "resource_name": "transaction",
        "action": "insert",
        "payload": {
            "symbol": "2318.HK",
            "type": "SELL",
            "quantity": 6000,
            "price": 56.8,
            "notes": "",
            "transaction_date": "2026-09-01"
        }
    }

    resp = lambda_handler(test_event_1, None)
    print(f"Status: {resp['statusCode']}")
    print(f"Body: {resp['body']}")