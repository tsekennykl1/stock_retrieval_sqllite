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
        Main entry point. Validates timing, builds monthly report first
        (to ensure holdings and prices are ready), then inserts monthly snapshots
        with per-stock realised PnL and net diff.

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

        # Step 2: Build monthly report FIRST
        # This fetches current prices, computes per-stock performance
        # (realised PnL, net diff), and ensures portfolio holdings are up to date.
        monthly_report = build_monthly_report(year_month)

        if self.debug_mode:
            print(f"🐛 [DEBUG] Monthly report: {json.dumps(monthly_report, indent=2, default=str)}")

        if not monthly_report:
            return {
                "status": "error",
                "reason": "build_monthly_report returned empty or None.",
                "year_month": year_month,
            }

        # Step 3: Extract per-stock performance data from the report
        # Build a lookup: symbol → { monthly_realised_pnl, monthly_net_diff }
        stock_performance = self._extract_stock_performance(monthly_report)

        if self.debug_mode:
            print(f"🐛 [DEBUG] Stock performance lookup: {json.dumps(stock_performance, indent=2, default=str)}")

        # Step 4: Get current portfolio holdings (quantity > 0)
        holdings = get_latest_portfolio()
        if not holdings:
            return {
                "status": "skipped",
                "reason": "Portfolio is empty — no holdings with quantity > 0.",
                "year_month": year_month,
                "monthly_report": monthly_report,
            }

        symbols = [h["stock_symbol"] for h in holdings]

        if self.debug_mode:
            print(f"🐛 [DEBUG] Portfolio symbols: {symbols}")

        # Step 5: Fetch current stock prices (report already fetched them,
        # but we still need the price dict for snapshot insertion)
        prices = self._fetch_prices(symbols)
        snapshot_date = prices.get("snapshot_date") or self.now.strftime("%Y-%m-%d")

        if self.debug_mode:
            print(f"🐛 [DEBUG] Prices fetched: {json.dumps(prices, indent=2, default=str)}")

        # Step 6: Insert snapshot for each holding (with realised PnL & net diff)
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

            # Get per-stock PnL fields from the monthly report
            perf = stock_performance.get(symbol, {})
            monthly_realised_pnl = perf.get("monthly_realised_pnl", 0)
            monthly_net_diff = perf.get("monthly_net_diff", 0)

            insert_monthly_snapshot(
                stock_symbol=symbol,
                start_quantity=quantity,
                start_price=current_price,
                year_month=year_month,
                snapshot_date=snapshot_date,
                monthly_realised_pnl=monthly_realised_pnl,
                monthly_net_diff=monthly_net_diff,
            )

            inserted.append({
                "symbol": symbol,
                "quantity": quantity,
                "price": current_price,
                "monthly_realised_pnl": monthly_realised_pnl,
                "monthly_net_diff": monthly_net_diff,
            })

        result = {
            "status": "success",
            "year_month": year_month,
            "snapshot_date": snapshot_date,
            "total_inserted": len(inserted),
            "snapshots": inserted,
            "monthly_report": monthly_report,
        }

        if skipped:
            result["skipped"] = skipped

        if self.debug_mode:
            result["debug_mode"] = True

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

    def _extract_stock_performance(self, monthly_report: dict) -> dict:
        """
        Extract per-stock monthly_realised_pnl and monthly_net_diff
        from the build_monthly_report response.

        Returns:
            dict keyed by symbol, e.g.:
            {
                "0005.HK": {"monthly_realised_pnl": 500.0, "monthly_net_diff": 200.0},
                "0011.HK": {"monthly_realised_pnl": 0, "monthly_net_diff": -100.0},
            }

        Adjust the field names below if your build_monthly_report
        uses different keys (e.g. "realised_pnl", "net_diff", "pnl", etc.)
        """
        lookup = {}

        # Try list-based structure: report["stocks"] or report["holdings"]
        stock_list = (
            monthly_report.get("stocks")
            or monthly_report.get("holdings")
            or monthly_report.get("performance")
            or []
        )

        if isinstance(stock_list, list):
            for item in stock_list:
                symbol = (
                    item.get("stock_symbol")
                    or item.get("symbol")
                    or ""
                )
                if symbol:
                    lookup[symbol] = {
                        "monthly_realised_pnl": float(
                            item.get("monthly_realised_pnl")
                            or item.get("realised_pnl")
                            or item.get("realized_pnl")
                            or 0
                        ),
                        "monthly_net_diff": float(
                            item.get("monthly_net_diff")
                            or item.get("net_diff")
                            or item.get("unrealised_pnl")
                            or 0
                        ),
                    }

        elif isinstance(stock_list, dict):
            # Dict-based structure: report["stocks"]["0005.HK"] = {...}
            for symbol, item in stock_list.items():
                if isinstance(item, dict):
                    lookup[symbol] = {
                        "monthly_realised_pnl": float(
                            item.get("monthly_realised_pnl")
                            or item.get("realised_pnl")
                            or item.get("realized_pnl")
                            or 0
                        ),
                        "monthly_net_diff": float(
                            item.get("monthly_net_diff")
                            or item.get("net_diff")
                            or item.get("unrealised_pnl")
                            or 0
                        ),
                    }

        return lookup


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