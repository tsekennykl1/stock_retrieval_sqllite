# services/transaction_service.py
"""
Transaction Service
───────────────────
Orchestrates all transaction-related business logic:
  • Inserts/updates transaction records via CRUD
  • Retrieves the latest portfolio state for the symbol
  • Recalculates quantity & average buy price
  • Inserts a NEW portfolio row reflecting the updated position
  • Auto-creates stock records from price service if not found locally
"""

from datetime import datetime
from crud_db import (
    insert_transaction as crud_insert_transaction,
    update_transaction as crud_update_transaction,
    get_transactions as crud_get_transactions,
    get_latest_portfolio,
    insert_portfolio,
    get_stock,
    insert_stock,
    normalize_date,
    get_month_str,
)
from services.price_service import get_stock_info


# ══════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════
def process_transaction(symbol, type, quantity, price, notes=None, transaction_date=None, stock_name=None):

    """
    Full transaction workflow:
      1. Validate the stock exists — if not, fetch from price service and auto-create
      2. Check portfolio for current holding position
      3. For SELL: validate quantity does not exceed current holding
      4. Insert the transaction record
      5. Calculate new quantity and weighted-average price
      6. Insert a new portfolio row with the updated position

    Returns:
        dict with transaction details and updated portfolio state, or None on failure.
    """
    symbol = symbol.upper()
    quantity = float(quantity)
    price = float(price)

    # ── Step 1: Validate stock exists; auto-create if not found ──
    stock = get_stock(symbol)
    if not stock:
        print(f"ℹ️  Stock '{symbol}' not found locally. Fetching from price service...")
        stock_info = get_stock_info(symbol)
        stock_name = stock_info.get("name", symbol) if stock_info else None

        if not stock_info:
            print(f"⚠️  Could not retrieve info for '{symbol}' from price service!")
            return {
                "error": f"Stock '{symbol}' not found locally or via price service.",
                "symbol": symbol,
            }

        # Insert the newly fetched stock into the database
        insert_stock(
            symbol=symbol,
            name=stock_name,
            sector=stock_info.get("sector"),
            currency=stock_info.get("currency", "HKD"),
        )
        print(f"✅ Stock '{symbol}' ({stock_info.get('name', symbol)}) auto-created from price service.")

    # ── Step 2: Check current portfolio holding ──
    portfolio_entries = get_latest_portfolio()
    current_entry = next(
        (p for p in portfolio_entries if p["stock_symbol"] == symbol),
        None,
    )
    current_quantity = float(current_entry["quantity"]) if current_entry else 0.0

    # ── Step 3: For SELL — validate quantity ≤ current holding ──
    if type.upper() == "SELL":
        if quantity > current_quantity:
            print(
                f"⚠️  Cannot SELL {quantity} of '{symbol}' — "
                f"current holding is only {current_quantity}!"
            )
            return {
                "error": (
                    f"Insufficient holding: trying to sell {quantity} shares of "
                    f"'{symbol}', but current position is {current_quantity}."
                ),
                "symbol": symbol,
                "requested_quantity": quantity,
                "current_holding": current_quantity,
            }

    # ── Step 4: Insert the transaction record ──
    transaction_result = crud_insert_transaction(
        symbol=symbol,
        stock_name=stock_name,
        type=type,
        quantity=quantity,
        price=price,
        notes=notes,
        transaction_date=transaction_date,
    )

    if transaction_result is None:
        return None

    # ── Step 5: Adjust portfolio ──
    portfolio_result = _adjust_portfolio_after_transaction(
        symbol=symbol,
        stock_name=stock_name,
        type=type,
        quantity=quantity,
        price=price,
        transaction_date=transaction_date,
        transaction_id=transaction_result.get("transaction_id"),
    )

    return {
        **transaction_result,
        "portfolio_update": portfolio_result,
    }


def process_transaction_update(transaction_id, symbol, type=None, quantity=None, price=None, notes=None, transaction_date=None, stock_name=None):
    """
    Update a transaction and recalculate the portfolio position.

    After updating the transaction fields, if quantity/price/type changed,
    a new portfolio row is inserted reflecting the NET adjustment.

    For SELL updates: validates that new sell quantity does not exceed current holding.

    Args:
        transaction_id: ID of the transaction to update
        symbol: Stock symbol (required to locate the portfolio entry)
        type, quantity, price, notes, transaction_date: Fields to update

    Returns:
        dict with update confirmation and portfolio adjustment details.
    """
    # ── For SELL updates, validate against current holding ──
    if symbol and type and type.upper() == "SELL" and quantity is not None:
        portfolio_entries = get_latest_portfolio()
        current_entry = next(
            (p for p in portfolio_entries if p["stock_symbol"] == symbol.upper()),
            None,
        )
        current_quantity = float(current_entry["quantity"]) if current_entry else 0.0

        if float(quantity) > current_quantity:
            return {
                "error": (
                    f"Insufficient holding: trying to sell {quantity} shares of "
                    f"'{symbol.upper()}', but current position is {current_quantity}."
                ),
                "symbol": symbol.upper(),
                "requested_quantity": float(quantity),
                "current_holding": current_quantity,
            }

    # Step 1: Update the transaction record
    crud_update_transaction(
        transaction_id=transaction_id,
        stock_name=stock_name,  # Stock name is not updated here
        type=type,
        quantity=quantity,
        price=price,
        notes=notes,
        transaction_date=transaction_date,
    )

    portfolio_result = None

    # Step 2: If position-affecting fields changed, adjust portfolio
    if symbol and type and quantity is not None and price is not None:
        portfolio_result = _adjust_portfolio_after_transaction(
            symbol=symbol.upper(),
            stock_name=stock_name,
            type=type,
            quantity=float(quantity),
            price=float(price),
            transaction_date=transaction_date,
            transaction_id=transaction_id,
        )

    return {
        "message": f"Transaction {transaction_id} updated",
        "transaction_id": transaction_id,
        "portfolio_update": portfolio_result,
    }


def get_monthly_transactions(year_month, symbol=None):
    """
    Retrieve and format transactions for a given month.

    Returns a list of dicts sorted by date, with normalized fields
    suitable for reports and API responses.
    """
    transactions = crud_get_transactions(year_month=year_month, symbol=symbol)

    formatted = sorted([
        {
            "date": normalize_date(t["transaction_date"]),
            "type": t["type"],
            "symbol": t.get("symbol", t.get("stock_symbol")),
            "stock_name": t.get("stock_name", ""),
            "quantity": t["quantity"],
            "price": t["price"],
            "total": round(float(t["total_amount"]), 2),
            "notes": t.get("notes", ""),
        }
        for t in transactions
    ], key=lambda x: x["date"])

    return formatted


# ══════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════

def _adjust_portfolio_after_transaction(symbol, type, quantity, price, transaction_date=None, transaction_id=None,stock_name=None):
    """
    Core portfolio adjustment logic:
      • Retrieves the latest portfolio row for the given symbol
      • Computes new quantity and weighted-average buy price
      • Inserts a NEW portfolio row (preserving history)

    BUY:  new_avg = (old_qty * old_avg + buy_qty * buy_price) / new_qty
    SELL: new_avg = old_avg (unchanged), new_qty = old_qty - sell_qty

    Returns:
        dict describing the portfolio adjustment made.
    """
    symbol = symbol.upper()
    quantity = float(quantity)
    price = float(price)

    # Get current portfolio state for this symbol
    portfolio_entries = get_latest_portfolio()
    current_entry = next(
        (p for p in portfolio_entries if p["stock_symbol"] == symbol),
        None,
    )

    current_quantity = float(current_entry["quantity"]) if current_entry else 0.0
    current_avg_price = float(current_entry["average_price"]) if current_entry else 0.0

    # Calculate new values based on transaction type
    if type.upper() == "BUY":
        new_quantity = current_quantity + quantity
        if new_quantity > 0:
            new_avg_price = (
                (current_quantity * current_avg_price) + (quantity * price)
            ) / new_quantity
        else:
            new_avg_price = price

    elif type.upper() == "SELL":
        new_quantity = current_quantity - quantity
        new_avg_price = current_avg_price  # Average cost basis unchanged on sell

    else:
        print(f"⚠️  Invalid transaction type '{type.upper()}'!")
        return None

    # Resolve trading date
    if transaction_date:
        trading_date = normalize_date(transaction_date)
    else:
        trading_date = datetime.now().strftime("%Y-%m-%d")

    # Insert a new portfolio row (preserves full history)
    insert_portfolio(
        symbol=symbol,
        stock_name=stock_name,
        quantity=round(new_quantity, 4),
        avg_buy_price=round(new_avg_price, 4),
        trading_date=trading_date,
        transaction_reference_id=transaction_id,
    )

    return {
        "symbol": symbol,
        "stock_name": stock_name,
        "previous_quantity": current_quantity,
        "previous_avg_price": current_avg_price,
        "new_quantity": round(new_quantity, 4),
        "new_avg_price": round(new_avg_price, 4),
        "trading_date": trading_date,
        "transaction_reference_id": transaction_id,
    }