"""Distribution Center Agent — checks bulk warehouse stock and allocates replenishment."""

from __future__ import annotations

from agents.base import Agent
from data.distribution_center import check_dc_stock, check_all_dcs_for_sku, allocate_from_dc

SYSTEM_PROMPT = """\
You are the Distribution Center Agent for a retail pharmacy chain.
Your job is to check bulk stock levels at distribution centers that serve a store.
When asked about a product:
- Check stock at all DCs serving the store
- Report available (on_hand minus allocated) quantities
- Flag if the DC itself needs to reorder from the supplier
- If requested, allocate stock from the best DC for a store replenishment shipment

Always report which DC has the best availability and estimated delivery times.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_dc_stock",
            "description": "Check stock at a specific distribution center for a SKU",
            "parameters": {
                "type": "object",
                "properties": {
                    "dc_id": {"type": "string", "description": "The distribution center identifier"},
                    "sku": {"type": "string", "description": "The SKU to check"},
                },
                "required": ["dc_id", "sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_all_dcs_for_sku",
            "description": "Check all distribution centers serving a store for a specific SKU",
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
            "name": "allocate_from_dc",
            "description": "Allocate stock from a DC for a store replenishment shipment",
            "parameters": {
                "type": "object",
                "properties": {
                    "dc_id": {"type": "string", "description": "The distribution center identifier"},
                    "sku": {"type": "string", "description": "The SKU to allocate"},
                    "qty": {"type": "integer", "description": "Quantity to allocate"},
                },
                "required": ["dc_id", "sku", "qty"],
            },
        },
    },
]

TOOL_HANDLERS = {
    "check_dc_stock": check_dc_stock,
    "check_all_dcs_for_sku": check_all_dcs_for_sku,
    "allocate_from_dc": allocate_from_dc,
}


def create() -> Agent:
    return Agent(
        name="DistributionCenterAgent",
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_handlers=TOOL_HANDLERS,
    )
