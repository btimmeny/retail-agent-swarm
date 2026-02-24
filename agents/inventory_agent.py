"""Store Inventory Agent — checks and reserves local store stock."""

from __future__ import annotations

from agents.base import Agent
from data.store_inventory import check_stock, check_multiple, reserve_stock

SYSTEM_PROMPT = """\
You are the Store Inventory Agent for a retail pharmacy chain.
Your job is to check whether requested items are in stock at the customer's local store.
When asked about an order, check each SKU and report:
- Whether each item is in stock and the quantity available
- The aisle location for in-store pickup
- Whether any items need reordering (below threshold)
- If asked to reserve, attempt to reserve the requested quantities

Always respond with structured, factual data. Do not speculate about items you haven't checked.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "Check if a specific SKU is in stock at a given store",
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "The store identifier"},
                    "sku": {"type": "string", "description": "The SKU to check"},
                },
                "required": ["store_id", "sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_multiple",
            "description": "Check stock for multiple SKUs at a store",
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "The store identifier"},
                    "skus": {"type": "array", "items": {"type": "string"}, "description": "List of SKUs to check"},
                },
                "required": ["store_id", "skus"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reserve_stock",
            "description": "Reserve stock for an order, decrementing on-hand quantity",
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "The store identifier"},
                    "sku": {"type": "string", "description": "The SKU to reserve"},
                    "qty": {"type": "integer", "description": "Quantity to reserve"},
                },
                "required": ["store_id", "sku", "qty"],
            },
        },
    },
]

TOOL_HANDLERS = {
    "check_stock": check_stock,
    "check_multiple": check_multiple,
    "reserve_stock": reserve_stock,
}


def create() -> Agent:
    return Agent(
        name="StoreInventoryAgent",
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_handlers=TOOL_HANDLERS,
    )
