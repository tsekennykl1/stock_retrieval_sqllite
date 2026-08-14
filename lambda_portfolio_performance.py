import json
from crud_db import get_latest_portfolio
import boto3

lambda_client = boto3.client('lambda', region_name='ap-east-1')


def invoke_stock_retrieval(stocks: list) -> dict:
    payload = {                                     # ✅ build correct payload
        "queryStringParameters": {
            "stocks": ",".join(stocks)              # ✅ e.g. "0700.HK,9988.HK,0005.HK"
        }
    }
    response = lambda_client.invoke(
        FunctionName='stock_retrieval_lambda',
        InvocationType='RequestResponse',
        Payload=json.dumps(payload).encode()        # ✅ send stocks in payload
    )
    result = json.loads(response['Payload'].read())
    if response.get('FunctionError'):               # ✅ catch Lambda-level errors
        raise Exception(f"stock_retrieval_lambda error: {result}")
    if 'body' in result:                            # ✅ unwrap API Gateway response format
        return json.loads(result['body'])
    return result





def get_holding(print_html=False):
    holdings = get_latest_portfolio()

    if not holdings:
        return json.dumps({"message": "Portfolio is empty.", "holdings": [], "summary": {}})

    symbols = [holding['stock_symbol'] for holding in holdings]
    prices_dict = invoke_stock_retrieval(symbols)   # ✅ direct Lambda invoke, no internet

    prices = {}
    for symbol in symbols:
        price_info = prices_dict.get(symbol, {})
        if isinstance(price_info, dict):
            prices[symbol] = float(price_info.get('price', 0.0))
        else:
            try:
                prices[symbol] = float(price_info)
            except (TypeError, ValueError):
                prices[symbol] = 0.0

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
        qty = float(item['total_quantity'])
        avg_price = float(item['average_price'])
        invested = float(item['total_invested'])
        
        curr_price = prices.get(symbol, 0.0)
        curr_value = qty * curr_price
        
        gl_amount = curr_value - invested
        gl_pct = (gl_amount / invested * 100) if invested > 0 else 0.0

        total_invested_portfolio += invested
        total_current_value_portfolio += curr_value

        if print_html:
            print(f"{symbol:<10} | {qty:<10.2f} | {avg_price:<10.2f} | {curr_price:<10.2f} | {invested:<12.2f} | {curr_value:<12.2f} | {gl_amount:<10.2f} | {gl_pct:>7.2f}%")

        result["holdings"].append({
            "symbol": symbol,
            "shortName_en": prices_dict.get(symbol, {}).get('shortName_en', item.get('shortName_en', '')),
            "quantity": round(qty, 2),
            "avg_price": round(avg_price, 2),
            "current_price": round(curr_price, 2),
            "total_invested": round(invested, 2),
            "current_value": round(curr_value, 2),
            "gain_loss_amount": round(gl_amount, 2),
            "gain_loss_percentage": round(gl_pct, 2),
            "last_updated": item.get('last_updated', '')   #,
            #"sector": item.get('sector', ''),
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


def lambda_handler(event, context):
    """AWS Lambda handler to retrieve portfolio performance."""
    try:
        performance_data = get_holding(print_html=False)
        return {
            "statusCode": 200,
            "body": performance_data,
            "headers": {
                "Content-Type": "application/json"
            }
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {
                "Content-Type": "application/json"
            }
        }
