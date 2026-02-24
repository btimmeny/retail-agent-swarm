"""Customer History Agent  looks up customer profiles, past orders, and purchasing patterns, with HIPAA-compliant access controls and PHI redaction."""

from __future__ import annotations

import functools
from typing import Callable, Any, Dict

from agents.base import Agent
from data.customer_history import (
    get_customer,
    get_order_history,
    get_recent_orders,
    get_frequently_purchased,
)

# --- Access Control and PHI Redaction Utilities ---

# Example PHI fields to redact
PHI_FIELDS = {"allergies", "prescriptions", "medical_conditions", "dob", "address", "phone", "email"}

# Simulated authentication and authorization check (to be replaced with real implementation)
def is_authenticated(context: dict) -> bool:
    # Placeholder: check for 'user' and 'authenticated' in context
    return context.get("user") is not None and context.get("authenticated", False)

def is_authorized(context: dict, action: str) -> bool:
    # Placeholder: check user role and allowed actions
    user = context.get("user", {})
    roles = user.get("roles", [])
    # Example: only 'pharmacist', 'provider', or 'admin' can access PHI
    if action == "view_phi":
        return any(role in ("pharmacist", "provider", "admin") for role in roles)
    return False

def redact_phi(data: Any) -> Any:
    """Redact PHI fields from dicts or lists of dicts."""
    if isinstance(data, dict):
        return {
            k: ("[REDACTED]" if k in PHI_FIELDS else redact_phi(v))
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [redact_phi(item) for item in data]
    return data

# Decorator for access control and PHI redaction
def hipaa_guard(handler: Callable) -> Callable:
    @functools.wraps(handler)
    def wrapper(*args, **kwargs):
        # Assume context is always passed as a kwarg (enforced by agent)
        context = kwargs.get("context", {})
        # Authentication check
        if not is_authenticated(context):
            return {"error": "Authentication required."}
        # Authorization check
        if not is_authorized(context, action="view_phi"):
            # Redact PHI if not authorized
            result = handler(*args, **kwargs)
            return redact_phi(result)
        # Authorized: return full data
        return handler(*args, **kwargs)
    return wrapper

# --- HIPAA-guarded Tool Handlers ---

TOOL_HANDLERS = {
    "get_customer": hipaa_guard(get_customer),
    "get_recent_orders": hipaa_guard(get_recent_orders),
    "get_frequently_purchased": hipaa_guard(get_frequently_purchased),
}

SYSTEM_PROMPT = """\
You are the Customer History Agent for a retail pharmacy chain.
Your job is to provide insights about a customer's profile and purchasing behavior.
When consulted:
- Look up the customer profile (loyalty tier, allergies, preferences)
- Review their recent order history
- Identify frequently purchased items that may be relevant to the current order
- Flag any known allergies that could affect product recommendations

You provide context to help other agents personalize the experience. Never share
raw customer data externally  summarize relevant insights only.
All access to customer data must be authenticated and authorized. If a request is not
properly authorized, only non-PHI, redacted, or summary information may be returned.
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


def create() -> Agent:
    return Agent(
        name="CustomerHistoryAgent",
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_handlers=TOOL_HANDLERS,
    )

