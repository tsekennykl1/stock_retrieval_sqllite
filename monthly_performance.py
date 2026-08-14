import requests
import json
from datetime import datetime, timedelta
from s3_db_sync import s3_db_wrapper

# Import CRUD functions from your existing create_db.py
from crud_db import (
    get_portfolio,
    insert_monthly_snapshot,
    get_monthly_snapshots,
    get_transactions, get_dividends,
    insert_monthly_pnl,get_monthly_pnl,update_monthly_pnl
)
from portfolio_performance import get_portfolio_performance_json
from monthly_ledger import get_monthly_ledger

API_URL = "https://z35lnmmzgi.execute-api.ap-east-1.amazonaws.com/prod/stocks?stocks="

def fetch_current_prices(symbols):
    """Fetch current stock prices from the API."""
    if not symbols: return {}
    response = requests.get(f"{API_URL}{','.join(symbols)}", timeout=(3, 10))
    prices = {}
    if response.status_code == 200:
        data = response.json()
        for key, val in data.items():
            if isinstance(val, dict) and 'price' in val: prices[key] = float(val['price'])
            elif isinstance(val, dict) and 'regularMarketPrice' in val: prices[key] = float(val['regularMarketPrice'])
            else:
                try: prices[key] = float(val)
                except (TypeError, ValueError): prices[key] = 0.0
    return prices


def calculate_monthly_performance(year_month, print_table=False):
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
    current_prices = fetch_current_prices(list(symbols_to_fetch))
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
        curr_price = current_prices.get(sym, 0.0)
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

def calculate_monthly_dividends(year_month,print_table=False):
    """Calculate total dividends received for the given month."""

    dividends = get_dividends(year_month=year_month)
    total_dividends = 0.0
    if print_table:
        print(f"Retrieved {len(dividends)} dividend records for {year_month}.")
        print(f"\n💰 Dividend Report for {year_month}")
        print("=" * 50)
        print(f"{'Symbol':<10} | {'Dividend':<10}")
        print("-" * 50)

    for d in dividends:
        # Use .get() to prevent KeyError if keys are slightly different
        symbol = d.get('symbol', 'UNKNOWN')
        # Fallback to other common key names if 'amount' is not found
        amount = d.get('total_dividend', 0.0)
        
        total_dividends += float(amount)
        if print_table:
            print(f"{symbol:<10} | {amount:<10.2f}")
    if print_table:
        print("-" * 50)
        print(f"{'TOTAL':<10} | {total_dividends:<10.2f}")
        print("=" * 50 + "\n")

    return total_dividends


def value_fresh(current_month):

    portfolio = get_portfolio_performance_json(print_html=False)
    print(f"\n--- Portfolio Performance for {current_month} ---")
    print(portfolio)
    monthly_performance = calculate_monthly_performance(current_month, print_table=False)
    if not monthly_performance:
        raise Exception("Monthly performance is empty (missing snapshots?)")
    print(f"\n--- Monthly Performance for {current_month} ---")
    print(json.dumps(monthly_performance, indent=4))
    dividends = calculate_monthly_dividends(current_month)  
    print(f"\n--- Total Dividends for {current_month}: {dividends:.2f} ---")
    

    # When you call the function, it returns a JSON string
    ledger_json_string = get_monthly_ledger(current_month)

    # Convert the JSON string back into a Python dictionary
    monthly_ledger = json.loads(ledger_json_string)

    last_month = (datetime.strptime(current_month, '%Y-%m') - timedelta(days=1)).strftime('%Y-%m')
    print(f"\n✅ Monthly P&L entry for {current_month} inserted successfully. Previous month: {last_month}")

    last_month_pnl = get_monthly_pnl(year_month=last_month)
    print(f"\n--- Last Month ({last_month}) P&L Summary ---")
    print(json.dumps(last_month_pnl, indent=4))
    open_balance_this_month = last_month_pnl[0]['close_bal'] if last_month_pnl else 0.0
    print(f"\n--- Open Balance for {current_month}: {open_balance_this_month:.2f} ---")
    
    insert_monthly_pnl(year_month=current_month,
        open_bal=open_balance_this_month,
        income=monthly_ledger['Total_Income'],
        expenses=monthly_ledger['Total_Expense'],
        stock_pnl=monthly_performance['totals']['total_net_diff'],
        dividend=dividends
    )

    print(f"\n--- Last Month ({last_month}) P&L Summary ---")
    print(json.dumps(last_month_pnl, indent=4))
    print("\n--- Portfolio Performance JSON ---")
    print(portfolio)
    print("\n--- Monthly Performance JSON ---")
    print(json.dumps(monthly_performance, indent=4))
    print("\n--- Total Dividends for the Month ---")
    print(f"Total Dividends: {dividends:.2f}")  
    print("\n--- Monthly Ledger JSON ---")
    print(json.dumps(monthly_ledger, indent=4))
    print("\n✅ Monthly P&L entry inserted successfully.")
    print("\n--- Monthly P&L Summary ---")
    monthly_pnl = get_monthly_pnl(year_month=current_month)
    # Round all floating numbers to 2 decimal places
    for entry in monthly_pnl:
        for key, value in entry.items():
            if isinstance(value, float):
                entry[key] = round(value, 2)
    print(json.dumps(monthly_pnl, indent=4))
    print("\n✅ Monthly P&L summary retrieved successfully.")
    
def lambda_handler(event=None, context=None):
    """AWS Lambda Entry Point"""

    event = event or {}
    action = event.get("action", "value_fresh")  # default action

    with s3_db_wrapper():
        current_month = datetime.now().strftime('%Y-%m')

        try:
            if action == "portfolio":
                body = json.loads(get_portfolio_performance_json(print_html=False))
                return {"statusCode": 200, "body": json.dumps(body)}

            elif action == "monthly":
                perf = calculate_monthly_performance(current_month, print_table=False)
                return {"statusCode": 200, "body": json.dumps(perf)}

            elif action == "value_fresh":
                # your existing function prints + inserts pnl
                value_fresh(current_month=current_month)
                return {"statusCode": 200, "body": json.dumps({"message": "value_fresh completed", "year_month": current_month})}

            else:
                return {"statusCode": 400, "body": json.dumps({"error": f"Unknown action '{action}'"})}

        except Exception as e:
            print(f"lambda_handler error: {e}")
            return {"statusCode": 500, "body": json.dumps({"error": str(e)})}



if __name__ == "__main__":
    current_month = datetime.now().strftime('%Y-%m')
    
 #   print("1. Take/Update Snapshot for this month")
 #   print("2. View Monthly Performance")
 #   choice = input("Select an option (1/2): ")
    
 #   if choice == '1':
 #       snapshot_beginning_of_month(current_month)
 #   elif choice == '2':

    value_fresh(current_month=current_month)