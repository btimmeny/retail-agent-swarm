"""Provider/Supplier Agent — manages supplier relationships and purchase orders."""

from __future__ import annotations

from agents.base import Agent
from data.provider import get_supplier_for_sku, get_pending_orders_for_sku, create_restock_order

SYSTEM_PROMPT = """\
You are the Provider/Supplier Agent for a retail pharmacy chain.
Your job is to manage supplier relationships and ensure long-term stock availability.
When consulted about a product:
- Identify the supplier responsible for that SKU
- Check if there are any pending purchase orders already in the pipeline
- Report supplier lead times and reliability scores
- If stock is critically low at the DC level, recommend or create a new restock order

Always factor in lead times when assessing whether current pipelines are sufficient.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_supplier_for_sku",
            "description": "Find the supplier responsible for a given SKU",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "The SKU to look up"},
                },
                "required": ["sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_orders_for_sku",
            "description": "Get all pending purchase orders for a SKU",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "The SKU to check"},
                },
                "required": ["sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_restock_order",
            "description": "Create a new purchase order with the appropriate supplier",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "The SKU to restock"},
                    "qty": {"type": "integer", "description": "Quantity to order"},
                    "destination_dc": {"type": "string", "description": "DC to ship to"},
                },
                "required": ["sku", "qty", "destination_dc"],
            },
        },
    },
]

TOOL_HANDLERS = {
    "get_supplier_for_sku": get_supplier_for_sku,
    "get_pending_orders_for_sku": get_pending_orders_for_sku,
    "create_restock_order": create_restock_order,
}


def create() -> Agent:
    return Agent(
        name="ProviderAgent",
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_handlers=TOOL_HANDLERS,
    )
