import os
import json

os.environ["LOCAL_DEV"] = "1"
os.environ.setdefault("AWS_REGION", "ap-east-1")

from lambda_crud_handler import lambda_handler


def test_crud():
    """Run a series of CRUD tests locally."""

    tests = [
        # ── Portfolio ─────────────────────────────────────
        {
            "resource_name": "portfolio",
            "action": "get",
            "payload": {}
        },
        {
            "resource_name": "portfolio",
            "action": "insert",
            "payload": {
                "symbol": "9988.HK",
                "stock_name": "Alibaba Group Holding Limited",
                "quantity": 100,
                "avg_buy_price": 82.50,
                "trading_date": "2026-08-20"
            }
        },
        {
            "resource_name": "portfolio",
            "action": "update",
            "payload": {
                "portfolio_id": 1,
                "stock_name": "HSBC Holdings plc"
            }
        },
        # ── Transaction ───────────────────────────────────
        {
            "resource_name": "transaction",
            "action": "insert",
            "payload": {
                "symbol": "9988.HK",
                "type": "BUY",
                "quantity": 100,
                "price": 82.50,
                "notes": "Initial position",
                "transaction_date": "2026-08-20"
            }
        },
        {
            "resource_name": "transaction",
            "action": "get",
            "payload": {
                "year_month": "2026-08"
            }
        },
        # ── Ledger ────────────────────────────────────────
        {
            "resource_name": "ledger",
            "action": "insert",
            "payload": {
                "type": "I",
                "category": "Salary",
                "amount": 45000.00,
                "ledger_datetime": "2026-08-01",
                "comment": "August salary"
            }
        },
        {
            "resource_name": "ledger",
            "action": "get",
            "payload": {
                "month_str": "2026-08"
            }
        },
        # ── Monthly PnL ──────────────────────────────────
        {
            "resource_name": "monthly_pnl",
            "action": "get",
            "payload": {}
        },
        # ── Dividend ──────────────────────────────────────
        {
            "resource_name": "dividend",
            "action": "insert",
            "payload": {
                "symbol": "0005.HK",
                "amount_per_share": 0.30,
                "quantity": 1000,
                "payment_date": "2026-08-15"
            }
        },
        # ── Snapshot ──────────────────────────────────────
        {
            "resource_name": "snapshot",
            "action": "insert",
            "payload": {
                "stock_symbol": "9988.HK",
                "start_quantity": 100,
                "start_price": 82.50,
                "year_month": "2026-08"
            }
        },
        {
            "resource_name": "snapshot",
            "action": "generate",
            "payload": {
                "debug_mode": True
            }
        }
    ]

    for i, evt in enumerate(tests, 1):
        print(f"\n{'━'*60}")
        print(f"  TEST {i}: {evt['resource_name']}/{evt['action']}")
        print(f"{'━'*60}")
        resp = lambda_handler(evt, None)
        print(f"  Status: {resp['statusCode']}")
        body = json.loads(resp['body'])
        print(f"  Result: {json.dumps(body, indent=2, default=str)[:500]}")


if __name__ == "__main__":
    test_crud()