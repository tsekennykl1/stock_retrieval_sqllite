import json
from datetime import datetime, timedelta

from crud_db import get_monthly_pnl, insert_monthly_pnl, get_transactions, get_monthly_snapshots, get_all_portfolio_entries, normalize_date
from services.monthly_ledger_service import retrieve_monthly_ledger
from services.monthly_dividend_service import calculate_monthly_dividends, calculate_all_dividends_from
from services.portfolio_service import get_portfolio_holdings_json
from services.price_service import fetch_current_prices, fetch_current_prices_lambda 
from services.transaction_service import get_monthly_transactions
import os
from services.monthly_mortgage_service import calculate_monthly_mortgage

# ── Constants ──────────────────────────────────────────────────
SUMMARY_START = "2025-01"

# ── Special Costs — one-time adjustments deducted from period G/L ──
# Key = quarter key (e.g. "2025-Q2"), Value = amount (negative)
QUARTERLY_SPECIAL_COSTS: dict[str, float] = {
    "2025-Q2": -109400.0,
    "2025-Q3": -3134000.0,
}


# ══════════════════════════════════════════════════════════════
#  GENERIC PERIOD PnL SUMMARY (quarterly / annual / any bucket)
# ══════════════════════════════════════════════════════════════

def _to_quarter_key(year_month: str) -> str:
    """'2025-03' → '2025-Q1'"""
    year, month = year_month.split("-")
    quarter = (int(month) - 1) // 3 + 1
    return f"{year}-Q{quarter}"


def _to_year_key(year_month: str) -> str:
    """'2025-03' → '2025'"""
    return year_month[:4]


def _get_special_cost(period_type: str, period_key: str) -> float:
    """
    Returns the special cost adjustment for the given period.

    - QUARTERLY: direct lookup from QUARTERLY_SPECIAL_COSTS
    - ANNUAL:    sum of all quarterly special costs belonging to that year

    Returns the special cost (negative = deduction), or 0.0 if none.
    """
    if period_type == "QUARTERLY":
        return QUARTERLY_SPECIAL_COSTS.get(period_key, 0.0)

    if period_type == "ANNUAL":
        # period_key is just the year, e.g. "2025"
        return sum(
            cost for qk, cost in QUARTERLY_SPECIAL_COSTS.items()
            if qk.startswith(f"{period_key}-")
        )

    return 0.0


def build_period_summary(all_monthly_pnl: list, period_type: str, key_extractor) -> list:
    """
    Generic aggregation: groups monthly PnL records by a key derived from
    year_month, sums stock_pnl, dividend, and monthly_gl, applies special
    cost deductions, and returns sorted summaries with
    period_gl = monthly_gl + special_cost.

    Args:
        all_monthly_pnl:  the full list of monthly PnL dicts
        period_type:      "QUARTERLY" or "ANNUAL" — stamped on each result
        key_extractor:    callable that converts a year_month string
                          (e.g. "2025-03") to a bucket key
                          (e.g. "2025-Q1" for quarterly, "2025" for annual)

    Returns:
        sorted list of dicts with keys:
        type, period, stock_pnl, dividend, special_cost, period_gl
    """
    buckets: dict[str, list] = {}

    for pnl in all_monthly_pnl:
        ym = pnl.get("year_month", "")
        if not ym or ym < SUMMARY_START:
            continue

        bucket_key = key_extractor(ym)
        if bucket_key not in buckets:
            buckets[bucket_key] = [0.0, 0.0, 0.0]  # [stock_pnl, dividend, monthly_gl]

        sums = buckets[bucket_key]
        sums[0] += float(pnl.get("stock_pnl", 0.0) or 0.0)
        sums[1] += float(pnl.get("dividend", 0.0) or 0.0)
        sums[2] += float(pnl.get("monthly_gl", 0.0) or 0.0)

    result = []
    for key, sums in sorted(buckets.items()):
        special_cost = _get_special_cost(period_type, key)
        period_gl = sums[2] + special_cost
        result.append({
            "type": period_type,
            "period": key,
            "stock_pnl": round(sums[0], 2),
            "dividend": round(sums[1], 2),
            "special_cost": round(special_cost, 2),
            "period_gl": round(period_gl, 2),
        })

    return result


def get_monthly_performance(year_month,  print_table=False, current_prices=None,):
    """Calculate performance against the monthly snapshot, factoring in transactions.
    
    Realized G/L is computed using LIFO (Last In, First Out):
    each sell is matched against the most-recently-acquired cost lot first.
    """
    
    # 1. Get Snapshot via create_db CRUD
    # Calculate the last month in 'YYYY-MM' format
    last_month = (datetime.strptime(year_month, '%Y-%m') - timedelta(days=1)).strftime('%Y-%m')
    snapshots = get_monthly_snapshots(year_month=last_month)

    if not snapshots:
        print(f"No snapshot found for {last_month}. Please take a snapshot first.")
        return

    # Track data per stock
    performance = {}
    symbols_to_fetch = set()

    for s in snapshots:
        sym = s['stock_symbol']
        performance[sym] = {
            'start_qty': float(s['start_quantity']),
            'start_price': float(s['start_price']),
            'start_value': float(s['start_value']),
            'running_qty': float(s['start_quantity']),
            # ── LIFO: cost lot stack [(qty, unit_price), ...] ──
            # The snapshot's opening position is the bottom (oldest) lot
            'cost_lots': [(float(s['start_quantity']), float(s['start_price']))],
            'buy_qty': 0, 'buy_value': 0.0,
            'sell_qty': 0, 'sell_value': 0.0,
            'realized_gl': 0.0
        }
        symbols_to_fetch.add(sym)
    
    transactions = get_monthly_transactions(year_month=year_month)

    for t in transactions:
        sym = t.get('symbol', t.get('stock_symbol'))
        symbols_to_fetch.add(sym)
        
        if sym not in performance:
            # Stock bought this month (not in snapshot)
            performance[sym] = {
                'start_qty': 0, 'start_price': 0.0, 'start_value': 0.0,
                'running_qty': 0,
                'cost_lots': [],
                'buy_qty': 0, 'buy_value': 0.0, 'sell_qty': 0, 'sell_value': 0.0,
                'realized_gl': 0.0
            }
        
        qty = float(t['quantity'])
        price = float(t['price'])
  
        if t['type'].upper() == 'BUY':
            performance[sym]['buy_qty'] += qty
            performance[sym]['buy_value'] += (qty * price)
            performance[sym]['running_qty'] += qty
            # ── LIFO: push new lot onto the top of the stack ──
            performance[sym]['cost_lots'].append((qty, price))
                
        elif t['type'].upper() == 'SELL':
            performance[sym]['sell_qty'] += qty
            performance[sym]['sell_value'] += (qty * price)
            performance[sym]['running_qty'] -= qty
            
            # ── LIFO: consume lots from the top (most recent) first ──
            remaining = qty
            realized = 0.0

            while remaining > 0 and performance[sym]['cost_lots']:
                lot_qty, lot_price = performance[sym]['cost_lots'][-1]
                sell_from_lot = min(remaining, lot_qty)

                realized  += (price - lot_price) * sell_from_lot
                remaining -= sell_from_lot

                if sell_from_lot >= lot_qty:
                    # Entire lot consumed — pop it off the stack
                    performance[sym]['cost_lots'].pop()
                else:
                    # Partial lot consumed — shrink it in place
                    performance[sym]['cost_lots'][-1] = (lot_qty - sell_from_lot, lot_price)

            performance[sym]['realized_gl'] += round(realized, 2)

    # 3. Get Current Prices
    if current_prices is None:
        current_prices = fetch_current_prices_lambda(list(symbols_to_fetch))
    if print_table: 
        print(f"\n📊 Monthly Performance Report for {year_month}")
        print("="*120)
        print(f"{'Symbol':<10} | {'Start Qty':<10} | {'Start Val':<10} | {'Start Price':<11} | {'Adjusted Qty':<12} | {'Curr Price':<10} | {'Curr Val':<10} | {'Realized G/L':<12} | {'Month Net Diff':<12}")
        print("-" * 120)

    total_start_val = 0.0
    total_curr_val = 0.0
    total_realized = 0.0
    total_net_diff = 0.0

    result = {
        "year_month": year_month,
        "performance": []
    }

    for sym, data in performance.items():
        # Adjusted end-of-month quantity
        end_qty = max(0, data['running_qty'])
        stock_data = current_prices.get(sym, {}) or {}
        if isinstance(stock_data, dict):
            curr_price = float(stock_data.get("price", 0.0) or 0.0)
        else:
            # fallback if price service returns raw floats sometimes
            curr_price = float(stock_data or 0.0)
        curr_val = end_qty * curr_price
        
        # Net Difference: (Current Value + Cash Out from Sells) - (Start Value + Cash In for Buys)
        net_diff = round((curr_val + data['sell_value']) - (data['start_value'] + data['buy_value']), 2)

        total_start_val += data['start_value']
        total_curr_val += curr_val
        total_realized += data['realized_gl']
        total_net_diff += net_diff

        result["performance"].append({
            "symbol": sym,
            "start_qty": data['start_qty'],
            "start_value": data['start_value'],
            "start_price": data['start_price'],
            "adjusted_qty": end_qty,
            "current_price": curr_price,
            "current_value": curr_val,
            "realized_gl": data['realized_gl'],
            "month_net_diff": net_diff
        })
        if print_table:
            print(f"{sym:<10} | {data['start_qty']:<10.2f} | {data['start_value']:<10.2f} | {data['start_price']:<11.2f} | {end_qty:<12.2f} | {curr_price:<10.2f} | {curr_val:<10.2f} | {data['realized_gl']:<12.2f} | {net_diff:<12.2f}")
    if print_table:
        print("-" * 120)
        print(f"{'TOTALS':<24} | {total_start_val:<10.2f} | {'':<11} | {'':<12} | {'':<10} | {total_curr_val:<10.2f} | {total_realized:<12.2f} | {total_net_diff:<12.2f}")
        print("="*120 + "\n")
    
    result["totals"] = {
        "total_start_value": total_start_val,
        "total_current_value": total_curr_val,
        "total_realized_gl": total_realized,
        "total_net_diff": total_net_diff
    }

    return result

def build_monthly_report(year_month: str) -> dict:
    
    if not year_month:
        year_month = datetime.now().strftime("%Y-%m")
    
    # Portfolio holdings (JSON string -> dict)
    holdings = json.loads(get_portfolio_holdings_json(print_html=False))

    # ── Fetch current prices for all portfolio symbols ─────────
    symbols = [h["symbol"] for h in holdings.get("holdings", [])]
    market_data = fetch_current_prices_lambda(symbols) if symbols else {}

    # Monthly performance (pass market_data to avoid duplicate API call)
    monthly_perf = get_monthly_performance(year_month, print_table=False, current_prices=market_data)
    if not monthly_perf:
        raise Exception(f"Monthly performance is empty. Missing snapshot for previous month of {year_month}.")

    # ── Transactions for the month ─────────────────────────────
    transactions = get_transactions(year_month=year_month)

    # Ledger
    ledger = json.loads(retrieve_monthly_ledger(year_month))
    ledger_entries = ledger.get("Ledger_entries", [])
    income = float(ledger.get("Income_total", -0.01) or -0.01)
    expenses = float(ledger.get("Expenses_total", -0.01) or -0.01)
    
    # Determine mortgage amount
    mortgage_amount = float(os.environ.get("MORTGAGE", -0.1))
    if not mortgage_amount or mortgage_amount < 0:
        mortgage_entry = calculate_monthly_mortgage(year_month=year_month)
        mortgage_amount = float(mortgage_entry.get("Total_payment", 0.0))*-1
    # Dividends — use calculate_all_dividends_from to get both current month and all future receivable
    dividend_data = calculate_all_dividends_from(year_month)
    # total_dividend: only the specified year_month's dividends (for PnL calculation)
    dividends_total = float(dividend_data.get("total_dividend", 0.0))
    # total_all_dividend: current month + all future receivable dividends (for display/reference)
    dividends_all_total = float(dividend_data.get("total_all_dividend", 0.0))
    
    # Open balance from previous month close
    last_month = (datetime.strptime(year_month, "%Y-%m") - timedelta(days=1)).strftime("%Y-%m")
    last_month_rows = get_monthly_pnl(year_month=last_month)
    open_bal = float(last_month_rows[0]["close_bal"]) if last_month_rows else 0.0
    stock_pnl = float(monthly_perf["totals"]["total_net_diff"])
     
    # Insert/update current month PnL (uses only current month's dividend total)
    insert_monthly_pnl(
        year_month=year_month,
        open_bal=open_bal,
        income=income,
        expenses=expenses,
        mortgage=mortgage_amount, 
        stock_pnl=stock_pnl,
        dividend=dividends_total,
    )
    
    # Read back computed columns
    all_pnl = get_monthly_pnl()
    all_pnl = sorted([{
        "pnl_date": normalize_date(row["pnl_date"]),
        "year_month": row["year_month"],
        "open_bal": float(row["open_bal"]),
        "income": float(row["income"]),
        "expenses": float(row["expenses"]),
        "mortgage": float(row.get("mortgage", 0.0) or 0.0),
        "stock_pnl": float(row["stock_pnl"]),
        "dividend": float(row["dividend"]),
        "monthly_gl": float(row["monthly_gl"]),
        "close_bal": float(row["close_bal"])
    } for row in all_pnl], key=lambda x: x['pnl_date'], reverse=True)

    # ── Quarterly & Annual PnL summaries (2025 onward) ─────────
    quarterly_pnl_summary = build_period_summary(all_pnl, "QUARTERLY", _to_quarter_key)
    annual_pnl_summary    = build_period_summary(all_pnl, "ANNUAL",    _to_year_key)
    
    return {
        "year_month": year_month,
        "previous_month": last_month,
        "portfolio_performance": holdings,
        "market_data": market_data,
        "monthly_performance": monthly_perf,
        "transactions": transactions,
        "monthly_ledger": ledger,
        "dividends": dividend_data,
        "all_monthly_pnl": all_pnl,
        "quarterly_pnl_summary": quarterly_pnl_summary,
        "annual_pnl_summary": annual_pnl_summary,
    }

if __name__ == "__main__":
    current_month = datetime.now().strftime('%Y-%m')
    print(json.dumps(build_monthly_report(current_month), indent=4))