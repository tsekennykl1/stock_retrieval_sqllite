# services/portfolio_service.py
import json

from crud_db import get_latest_portfolio, get_all_portfolio_entries
from services.price_service import fetch_current_prices, fetch_current_prices_lambda


def get_portfolio_holdings_json(print_html: bool = False) -> str:
    """
    Returns the same structure you used in lambda_portfolio_performance.get_holding()
    but implemented as a reusable service.
    """
    holdings = get_latest_portfolio()

    all_entries = get_all_portfolio_entries()
    print(f"Retrieved {len(all_entries)} portfolio entries from the database.\n")
    print(f"{all_entries}")

    if not holdings:
        return json.dumps({"message": "Portfolio is empty.", "holdings": [], "summary": {}})

    symbols = [h["stock_symbol"] for h in holdings]
    quotes = fetch_current_prices_lambda(symbols)

    prices = {}
    for symbol in symbols:
        info = quotes.get(symbol, {})
        if isinstance(info, dict):
            prices[symbol] = float(info.get("price", 0.0))
        else:
            try:
                prices[symbol] = float(info)
            except (TypeError, ValueError):
                prices[symbol] = 0.0

    total_invested_portfolio = 0.0
    total_current_value_portfolio = 0.0

    result = {"holdings": [], "summary": {}}

    if print_html:
        print("\n" + "=" * 95)
        print(f"{'Symbol':<10} | {'Qty':<10} | {'Avg Price':<10} | {'Curr Price':<10} | {'Invested':<12} | {'Curr Value':<12} | {'G/L ($)':<10} | {'G/L (%)':<8}")
        print("-" * 95)

    for item in holdings:
        symbol = item["stock_symbol"]
        qty = float(item["quantity"])
        avg_price = float(item["average_price"])
        invested = float(item["total_invested"])

        curr_price = float(prices.get(symbol, 0.0))
        curr_value = qty * curr_price

        gl_amount = curr_value - invested
        gl_pct = (gl_amount / invested * 100) if invested > 0 else 0.0

        total_invested_portfolio += invested
        total_current_value_portfolio += curr_value

        if print_html:
            print(f"{symbol:<10} | {qty:<10.2f} | {avg_price:<10.2f} | {curr_price:<10.2f} | {invested:<12.2f} | {curr_value:<12.2f} | {gl_amount:<10.2f} | {gl_pct:>7.2f}%")

        result["holdings"].append({
            "symbol": symbol,
            "shortName_en": (quotes.get(symbol, {}) or {}).get("shortName_en", item.get("stock_name", "")),
            "quantity": round(qty, 2),
            "avg_price": round(avg_price, 2),
            "current_price": round(curr_price, 2),
            "total_invested": round(invested, 2),
            "current_value": round(curr_value, 2),
            "gain_loss_amount": round(gl_amount, 2),
            "gain_loss_percentage": round(gl_pct, 2),
        })

    portfolio_gl_amount = total_current_value_portfolio - total_invested_portfolio
    portfolio_gl_pct = (portfolio_gl_amount / total_invested_portfolio * 100) if total_invested_portfolio > 0 else 0.0

    if print_html:
        print("-" * 95)
        print(f"{'TOTALS':<48} | {total_invested_portfolio:<12.2f} | {total_current_value_portfolio:<12.2f} | {portfolio_gl_amount:<10.2f} | {portfolio_gl_pct:>7.2f}%")
        print("=" * 95 + "\n")

    result["summary"] = {
        "total_invested": round(total_invested_portfolio, 2),
        "total_current_value": round(total_current_value_portfolio, 2),
        "total_gain_loss_amount": round(portfolio_gl_amount, 2),
        "total_gain_loss_percentage": round(portfolio_gl_pct, 2),
    }

    return json.dumps(result, indent=4)