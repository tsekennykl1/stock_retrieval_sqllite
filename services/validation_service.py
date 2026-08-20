"""Centralized validation rules for each resource."""

VALIDATION_RULES = {
    "transaction": {
        "type": lambda v: v.upper() in ("BUY", "SELL"),
        "quantity": lambda v: float(v) > 0,
        "price": lambda v: float(v) > 0,
    },
    "ledger": {
        "type": lambda v: v.upper() in ("I", "E"),
        "amount": lambda v: float(v) != 0,
    },
    "monthly_pnl": {
        "open_bal": lambda v: isinstance(v, (int, float)),
    },
}


def validate_payload(resource: str, payload: dict) -> list:
    """Returns a list of validation error strings, empty if all OK."""
    rules = VALIDATION_RULES.get(resource, {})
    errors = []
    for field, rule_fn in rules.items():
        if field in payload:
            try:
                if not rule_fn(payload[field]):
                    errors.append(f"Field '{field}' has invalid value: {payload[field]}")
            except (ValueError, TypeError) as e:
                errors.append(f"Field '{field}' validation error: {e}")
    return errors