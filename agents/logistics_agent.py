"""Logistics Agent — tracks inbound shipments and delivery ETAs."""

from __future__ import annotations

from agents.base import Agent
from data.logistics import get_inbound_for_store, get_inbound_for_sku, get_next_arrival_for_sku

SYSTEM_PROMPT = """\
You are the Logistics Agent for a retail pharmacy chain.
Your job is to track inbound shipments heading to stores.
When asked about a product that may be out of stock or running low, check:
- Whether any shipments containing that SKU are en route
- The carrier, status, and ETA of each shipment
- The quantity arriving in each shipment

Provide precise ETAs and shipment details. If no shipments are found for a SKU,
clearly state that no inbound stock is expected.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_inbound_for_store",
            "description": "Get all inbound shipments heading to a specific store",
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "The store identifier"},
                },
                "required": ["store_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inbound_for_sku",
            "description": "Find inbound shipments containing a specific SKU for a store",
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "The store identifier"},
                    "sku": {"type": "string", "description": "The SKU to search for"},
                },
                "required": ["store_id", "sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_next_arrival_for_sku",
            "description": "Get the soonest arriving shipment containing a specific SKU",
            "parameters": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "The store identifier"},
                    "sku": {"type": "string", "description": "The SKU to search for"},
                },
                "required": ["store_id", "sku"],
            },
        },
    },
]

TOOL_HANDLERS = {
    "get_inbound_for_store": get_inbound_for_store,
    "get_inbound_for_sku": get_inbound_for_sku,
    "get_next_arrival_for_sku": get_next_arrival_for_sku,
}


def create() -> Agent:
    return Agent(
        name="LogisticsAgent",
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_handlers=TOOL_HANDLERS,
    )
