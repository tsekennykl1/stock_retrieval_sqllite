import requests
import json
from crud_db import get_latest_portfolio

API_URL = "https://z35lnmmzgi.execute-api.ap-east-1.amazonaws.com/prod/stock?stocks="

def fetch_current_prices(symbols):
    """Fetch current stock prices from the API."""
    if not symbols:
        return {}
    
    symbol_string = ",".join(symbols)
    url = f"{API_URL}{symbol_string}"
    
    print(f"Fetching prices from API: {url}...")
    try:
        response = requests.get(url, timeout=(3, 10))
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching prices: {e}")
        return {}
    
    if response.status_code == 200:
        data = response.json()
        prices = {}
        for key, val in data.items():
            if isinstance(val, dict):
                # Cleanly grab price from new format
                price = float(val.get('price', 0.0))
                short_name = val.get('shortName_en', '') # Safe if API stops sending it
                prices[key] = {'price': price, 'shortName_en': short_name}
            else:
                try:
                    price = float(val)
                except (TypeError, ValueError):
                    price = 0.0
                prices[key] = {'price': price, 'shortName_en': ''}
        return prices
    else:
        print(f"Failed to fetch prices. Status Code: {response.status_code}")
        return {}
    
def snapshot_beginning_of_month(year_month):
    holdings = get_portfolio()
    if not holdings:
        print("Portfolio is empty, nothing to snapshot.")
        return {"message": "empty"}

    symbols = [h["stock_symbol"] for h in holdings]
    prices = fetch_current_prices(symbols)

    for h in holdings:
        symbol = h["stock_symbol"]
        qty = float(h["quantity"])
        price = float(prices.get(symbol, 0.0))
        insert_monthly_snapshot(stock_symbol=symbol, start_quantity=qty, start_price=price, year_month=year_month)

    return {"message": "snapshot_saved", "year_month": year_month}

def get_portfolio_performance_json(print_html=False):
    holdings = get_latest_portfolio()

    if not holdings:
        return json.dumps({"message": "Portfolio is empty.", "holdings": [], "summary": {}})

    # Extract symbols for API call
    symbols = [holding['stock_symbol'] for holding in holdings]
    prices = fetch_current_prices(symbols)

        
    total_invested_portfolio = 0.0
    total_current_value_portfolio = 0.0
    
    result = {
        "holdings": [],
        "summary": {}
    }

    if print_html:
        print("\n" + "="*95)
        print(f"{'Symbol':<10} | {'Qty':<10} | {'Avg Price':<10} | {'Curr Price':<10} | {'Invested':<12} | {'Curr Value':<12} | {'G/L ($)':<10} | {'G/L (%)':<8}")
        print("-" * 95)


    for item in holdings:
        symbol = item['stock_symbol']
        stock_name = item.get('stock_name', '')
        qty = float(item['total_quantity'])
        avg_price = float(item['average_price'])

        invested = float(item['total_invested'])
        
        # ✅ Fetch stock_data dictionary instead of just a float
        stock_data = prices.get(symbol, {})
        curr_price = stock_data.get('price', 0.0)
        
        curr_value = qty * curr_price
        
        gl_amount = curr_value - invested
        gl_pct = (gl_amount / invested * 100) if invested > 0 else 0.0

        total_invested_portfolio += invested
        total_current_value_portfolio += curr_value

        if print_html:
            print(f"{symbol:<10} | {qty:<10.2f} | {avg_price:<10.2f} | {curr_price:<10.2f} | {invested:<12.2f} | {curr_value:<12.2f} | {gl_amount:<10.2f} | {gl_pct:>7.2f}%")

        result["holdings"].append({
            "symbol": symbol,
            "stock_name": stock_name,
            "quantity": round(qty, 2),
            "avg_price": round(avg_price, 2),
            "current_price": round(curr_price, 2),
            "total_invested": round(invested, 2),
            "current_value": round(curr_value, 2),
            "gain_loss_amount": round(gl_amount, 2),
            "gain_loss_percentage": round(gl_pct, 2)
        })

    portfolio_gl_amount = total_current_value_portfolio - total_invested_portfolio


    portfolio_gl_pct = (portfolio_gl_amount / total_invested_portfolio * 100) if total_invested_portfolio > 0 else 0.0


    if print_html:
        print("-" * 95)
        print(f"{'TOTALS':<48} | {total_invested_portfolio:<12.2f} | {total_current_value_portfolio:<12.2f} | {portfolio_gl_amount:<10.2f} | {portfolio_gl_pct:>7.2f}%")
        print("="*95 + "\n")

    result["summary"] = {
        "total_invested": round(total_invested_portfolio, 2),
        "total_current_value": round(total_current_value_portfolio, 2),
        "total_gain_loss_amount": round(portfolio_gl_amount, 2),
        "total_gain_loss_percentage": round(portfolio_gl_pct, 2)
    }

    return json.dumps(result, indent=4)

if __name__ == "__main__":
    print(get_portfolio_performance_json(True))

