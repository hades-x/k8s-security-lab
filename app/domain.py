"""Pure order validation; callers supply trusted identity/environment."""
def normalize_order(payload, order_id, environment):
    item = payload.get("item")
    quantity = payload.get("quantity", 1)
    if not isinstance(item, str) or not item.strip() or len(item.strip()) > 200:
        raise ValueError("item must contain 1..200 characters")
    if type(quantity) is not int or not 1 <= quantity <= 1000:
        raise ValueError("quantity must be an integer from 1 to 1000")
    return {"id": order_id, "item": item.strip(), "quantity": quantity, "environment": environment}
