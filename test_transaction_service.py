# test_local.py
import sys
import os

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(__file__))

from services.transaction_service import process_transaction, get_monthly_transactions

# --- Test process_transaction ---
result = process_transaction(
    symbol="0700.HK",
    type="SELL",
    quantity=100000,
    price=350.0,
    notes="Test buy",
    transaction_date="2025-03-15"
)
print("Insert result:", result)

# --- Test get_monthly_transactions ---
txns = get_monthly_transactions(year_month="2025-03")
print("Monthly transactions:", txns)


