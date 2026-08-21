# services/monthly_report_service.py
import json
from datetime import datetime, timedelta

from crud_db import get_monthly_pnl, insert_monthly_pnl, get_transactions, get_monthly_snapshots, get_all_portfolio_entries, normalize_date
from services.monthly_ledger_service import retrieve_monthly_ledger
from services.monthly_dividend_service import calculate_monthly_dividends
from services.portfolio_service import get_portfolio_holdings_json
from services.price_service import fetch_current_prices, fetch_current_prices_lambda 


def get_monthly_performance(year_month,  print_table=False, current_prices=None,):
    """Calculate performance against the monthly snapshot, factoring in transactions."""
    
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
            'start_value': float(s['start_quantity']) * float(s['start_price']),
            'running_qty': float(s['start_quantity']),
            'running_cb': float(s['start_price']), # Running cost basis
            'buy_qty': 0, 'buy_value': 0.0,
            'sell_qty': 0, 'sell_value': 0.0,
            'realized_gl': 0.0
        }
        symbols_to_fetch.add(sym)
    
    # 2. Get Transactions for the month via create_db CRUD
    transactions = get_transactions(year_month=year_month)

    for t in transactions:
        sym = t.get('symbol', t.get('stock_symbol'))
        symbols_to_fetch.add(sym)
        
        if sym not in performance:
            # Stock bought this month (not in snapshot)
            performance[sym] = {
                'start_qty': 0, 'start_price': 0.0, 'start_value': 0.0,
                'running_qty': 0, 'running_cb': 0.0,
                'buy_qty': 0, 'buy_value': 0.0, 'sell_qty': 0, 'sell_value': 0.0,
                'realized_gl': 0.0
            }
        
        qty = float(t['quantity'])
        price = float(t['price'])
  
        if t['type'].upper() == 'BUY':
            performance[sym]['buy_qty'] += qty
            performance[sym]['buy_value'] += (qty * price)
            
            # Recalculate average cost basis
            total_cost = (performance[sym]['running_qty'] * performance[sym]['running_cb']) + (qty * price)
            performance[sym]['running_qty'] += qty
            if performance[sym]['running_qty'] > 0:
                performance[sym]['running_cb'] = total_cost / performance[sym]['running_qty']
                
        elif t['type'].upper() == 'SELL':
            performance[sym]['sell_qty'] += qty
            performance[sym]['sell_value'] += (qty * price)
            
            # Realized G/L based on the running cost basis at the time of sale
            performance[sym]['realized_gl'] += round((price - performance[sym]['running_cb']) * qty, 2)
            performance[sym]['running_qty'] -= qty

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

    # ✅ Add missing for-loop and accurately output the adjusted data
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
    
    # Prepare JSON result
  
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

    #format the transaction dates to 'YYYY-MM-DD' for consistency and sort the transactions by date
    transactions = sorted([{
        "date": normalize_date(t['transaction_date']),
        "type": t['type'],
        "symbol": t.get('symbol', t.get('stock_symbol')),
        "quantity": t['quantity'],
        "price": t['price'],
        "total": round(t['total_amount'], 2),
        "notes": t.get('notes', '')
    } for t in transactions], key=lambda x: x['date'])

    # Ledger
    ledger = json.loads(retrieve_monthly_ledger(year_month))
    ledger_entries = ledger.get("Ledger_entries", [])
    income = float(ledger.get("Income_total", -0.01) or -0.01)
    expenses = float(ledger.get("Expenses_total", -0.01) or -0.01)
    
    # Dividends total
    dividend_data = calculate_monthly_dividends(year_month)
    dividends_total = float(dividend_data.get("total_dividends", 0.0))
    
    # Open balance from previous month close
    last_month = (datetime.strptime(year_month, "%Y-%m") - timedelta(days=1)).strftime("%Y-%m")
    last_month_rows = get_monthly_pnl(year_month=last_month)
    open_bal = float(last_month_rows[0]["close_bal"]) if last_month_rows else 0.0
    stock_pnl = float(monthly_perf["totals"]["total_net_diff"])
     
    # Insert/update current month PnL
    insert_monthly_pnl(
        year_month=year_month,
        open_bal=open_bal,
        income=income,
        expenses=expenses,
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
        "stock_pnl": float(row["stock_pnl"]),
        "dividend": float(row["dividend"]),
        "close_bal": float(row["close_bal"])
    } for row in all_pnl], key=lambda x: x['pnl_date'], reverse=True)
    
    return {
        "year_month": year_month,
        "previous_month": last_month,
        "portfolio_performance": holdings,
        "market_data": market_data,              # ← NEW: current stock prices
        "monthly_performance": monthly_perf,
        "transactions": transactions,            # ← NEW: month's transactions
        "monthly_ledger": ledger,
        "dividends": dividend_data,
        "all_monthly_pnl": all_pnl,
    }
if __name__ == "__main__":
    current_month = datetime.now().strftime('%Y-%m')
    #print(json.dumps(build_monthly_report(current_month)["all_monthly_pnl"][0]))
    print(json.dumps(build_monthly_report(current_month), indent=4))