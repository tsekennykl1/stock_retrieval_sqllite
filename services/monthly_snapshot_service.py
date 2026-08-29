# services/snapshot_service.py
import json
from datetime import datetime, timedelta
from calendar import monthrange

from crud_db import (
    get_latest_portfolio,
    get_monthly_snapshots,
    insert_monthly_snapshot,
)
from services.price_service import fetch_current_prices_lambda, fetch_current_prices
from services.monthly_report_service import get_monthly_performance, build_monthly_report

class SnapshotService:
    """
    Service to generate monthly portfolio snapshots.

    Logic (when debugMode=False):
      - Last week of current month  → year_month = this month
      - First week of current month → year_month = last month (skip if already exists)
      - Otherwise                   → raises an error (not within valid snapshot window)

    When debugMode=True:
      - Always proceeds regardless of current date
      - Uses the same year_month resolution logic but never returns None
    """

    def __init__(self, reference_date: datetime = None, debug_mode: bool = False):
        """
        Args:
            reference_date: Override for testing. Defaults to datetime.now().
            debug_mode: If True, bypasses date validation and always proceeds.
        """
        self.now = reference_date or datetime.now()
        self.debug_mode = debug_mode

    # ──────────────────────────────────────────────────────────
    #  PUBLIC
    # ──────────────────────────────────────────────────────────

    def run(self) -> dict:
        """
        Main entry point. Validates timing, fetches portfolio & prices,
        then inserts monthly snapshots.

        Returns:
            dict with status, year_month, and list of inserted snapshots.
        """
        # Step 1: Determine year_month and validate timing
        year_month = self._resolve_year_month()

        if year_month is None and not self.debug_mode:
            return {
                "status": "skipped",
                "reason": "Current date is not within the first or last week of the month.",
                "date": self.now.strftime("%Y-%m-%d"),
            }

        # In debug mode, force a year_month if resolution returned None
        if year_month is None and self.debug_mode:
            year_month = self.now.strftime("%Y-%m")
            print(f"🐛 [DEBUG] Forcing year_month = '{year_month}' (date check bypassed)")

        # Check if snapshot already exists (skip in debug mode)
        if not self.debug_mode and self._snapshot_already_exists(year_month):
            return {
                "status": "skipped",
                "reason": f"Monthly snapshot for '{year_month}' already exists.",
                "year_month": year_month,
            }

        if self.debug_mode and self._snapshot_already_exists(year_month):
            print(f"🐛 [DEBUG] Snapshot for '{year_month}' already exists — overwriting (debug mode)")

        # Step 2: Get current portfolio holdings (quantity > 0)
        holdings = get_latest_portfolio()
        if not holdings:
            return {
                "status": "skipped",
                "reason": "Portfolio is empty — no holdings with quantity > 0.",
                "year_month": year_month,
            }

        symbols = [h["stock_symbol"] for h in holdings]

        if self.debug_mode:
            print(f"🐛 [DEBUG] Portfolio symbols: {symbols}")

        # Step 3: Fetch current stock prices
        prices = self._fetch_prices(symbols)
        snapshot_date = prices.get("snapshot_date") or self.now.strftime("%Y-%m-%d")
        if self.debug_mode:
            print(f"🐛 [DEBUG] Prices fetched: {json.dumps(prices, indent=2, default=str)}")

        # Step 4: Insert snapshot for each holding
        inserted = []
        skipped = []
        for holding in holdings:
            symbol = holding["stock_symbol"]
            quantity = float(holding["quantity"])
            current_price = self._extract_price(prices, symbol)

            if current_price is None or current_price <= 0:
                print(f"⚠️  Skipping '{symbol}': no valid price returned.")
                skipped.append({"symbol": symbol, "reason": "no valid price"})
                continue

            insert_monthly_snapshot(
                stock_symbol=symbol,
                start_quantity=quantity,
                start_price=current_price,
                year_month=year_month,
                snapshot_date=snapshot_date
            )

            inserted.append({
                "symbol": symbol,
                "quantity": quantity,
                "price": current_price,
            })
        monthly_report = build_monthly_report(year_month)
        result = {
            "status": "success",
            "year_month": year_month,
            "snapshot_date": snapshot_date,
            "total_inserted": len(inserted),
            "snapshots": inserted,
            'monthly_preport': monthly_report
        }

        if skipped:
            result["skipped"] = skipped

        if self.debug_mode:
            result["debug_mode"] = True
        print(get_monthly_performance(year_month,  print_table=False, current_prices=prices))
        return result

    # ──────────────────────────────────────────────────────────
    #  PRIVATE HELPERS
    # ──────────────────────────────────────────────────────────

    def _resolve_year_month(self) -> str | None:
        """
        Determine the target year_month based on current date:
          - Last week of month  → current month (YYYY-MM)
          - First week of month → previous month (YYYY-MM)
          - Otherwise           → None (invalid window) unless debug_mode
        """
        day = self.now.day
        year = self.now.year
        month = self.now.month

        # Last day of current month
        last_day = monthrange(year, month)[1]

        # Last week: day > (last_day - 7)
        if day > last_day - 7:
            return f"{year:04d}-{month:02d}"

        # First week: day <= 7
        if day <= 7:
            # Previous month
            first_of_this_month = datetime(year, month, 1)
            last_month_date = first_of_this_month - timedelta(days=1)
            return last_month_date.strftime("%Y-%m")

        # Not within a valid snapshot window
        # In debug mode, we return None here but the caller will force it
        return None

    def _snapshot_already_exists(self, year_month: str) -> bool:
        """Check if any snapshot records exist for the given year_month."""
        existing = get_monthly_snapshots(year_month=year_month)
        return len(existing) > 0

    def _fetch_prices(self, symbols: list[str]) -> dict:
        """
        Fetch current prices using HTTP API first, fallback to Lambda invocation.
        """
        try:
            prices = fetch_current_prices(symbols)
            if prices and any(s in prices for s in symbols):
                return prices
        except Exception as e:
            print(f"⚠️  HTTP price fetch failed: {e}")

        # Fallback to Lambda invocation
        try:
            prices = fetch_current_prices_lambda(symbols, max_retries=2)
            return prices or {}
        except Exception as e:
            print(f"⚠️  Lambda price fetch also failed: {e}")
            return {}

    def _extract_price(self, prices: dict, symbol: str) -> float | None:
        """
        Extract the numeric price for a symbol from the prices response dict.
        Handles both dict-style ({"symbol": {"price": 123}}) and flat values.
        """
        if not prices or symbol not in prices:
            return None

        info = prices[symbol]

        if isinstance(info, dict):
            raw = info.get("price") or info.get("currentPrice") or info.get("regularMarketPrice")
            if raw is not None:
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    return None
            return None

        # Direct numeric value
        try:
            return float(info)
        except (TypeError, ValueError):
            return None


# ══════════════════════════════════════════════════════════════
#  STANDALONE / LAMBDA ENTRY POINT
# ══════════════════════════════════════════════════════════════

def generate_monthly_snapshot(reference_date: datetime = None, debug_mode: bool = False) -> dict:
    """
    Convenience function to run the snapshot service.
    Can be called from a Lambda handler or scheduled job.

    Args:
        reference_date: Override current date for testing.
        debug_mode: If True, bypasses all date/existence checks.
    """
    service = SnapshotService(reference_date=reference_date, debug_mode=debug_mode)
    return service.run()


# ══════════════════════════════════════════════════════════════
#  LOCAL TESTING
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🚀 Running Monthly Snapshot Service...\n")

    # Normal mode — respects date window
    # result = generate_monthly_snapshot()
    # print(json.dumps(result, indent=2))

    # Debug mode — always proceeds regardless of date
    result = generate_monthly_snapshot(debug_mode=True)
    print(json.dumps(result, indent=2))

    # # Debug mode with a specific reference date (mid-month — would normally be rejected)
    # test_date = datetime(2026, 8, 15)
    # result = generate_monthly_snapshot(reference_date=test_date, debug_mode=True)
    # print(json.dumps(result, indent=2))