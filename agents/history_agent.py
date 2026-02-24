"""Customer History Agent — looks up customer profiles, past orders, and purchasing patterns."""

from __future__ import annotations

from agents.base import Agent
from data.customer_history import (
    get_customer,
    get_order_history,
    get_recent_orders,
    get_frequently_purchased,
)

SYSTEM_PROMPT = """\
You are the Customer History Agent for a retail pharmacy chain.
Your job is to provide insights about a customer's profile and purchasing behavior.
When consulted:
- Look up the customer profile (loyalty tier, allergies, preferences)
- Review their recent order history
- Identify frequently purchased items that may be relevant to the current order
- Flag any known allergies that could affect product recommendations

You provide context to help other agents personalize the experience. Never share
raw customer data externally — summarize relevant insights only.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_customer",
            "description": "Retrieve customer profile by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer identifier"},
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_orders",
            "description": "Get the most recent orders for a customer",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer identifier"},
                    "limit": {"type": "integer", "description": "Max number of orders to return", "default": 5},
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_frequently_purchased",
            "description": "Get frequently purchased items for a customer",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer identifier"},
                },
                "required": ["customer_id"],
            },
        },
    },
]

TOOL_HANDLERS = {
    "get_customer": get_customer,
    "get_recent_orders": get_recent_orders,
    "get_frequently_purchased": get_frequently_purchased,
}


def create() -> Agent:
    return Agent(
        name="CustomerHistoryAgent",
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_handlers=TOOL_HANDLERS,
    )
