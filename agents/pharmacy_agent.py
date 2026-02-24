"""Pharmacy Agent  manages prescriptions, refills, drug interactions, and pharmacist alerts. Implements HIPAA-compliant access controls and PHI redaction."""

from __future__ import annotations

from agents.base import Agent
from data.pharmacy import (
    get_prescriptions,
    get_upcoming_refills,
    get_pharmacy_alerts,
    check_drug_interaction,
)
from utils.auth import require_authentication, require_role  # New import for access control
from utils.phi import redact_phi  # New import for PHI redaction
import logging

SYSTEM_PROMPT = """\
You are the Pharmacy Agent for a retail pharmacy chain.
Your job is to provide pharmacy-related context for customer orders.
When consulted:
- Check for active prescriptions and upcoming refills
- Check for drug interactions between OTC items being ordered and active prescriptions
- Surface any pharmacist alerts (allergy warnings, refill reminders)
- Flag any items that might require pharmacist consultation

CRITICAL GUARDRAILS:
- Never provide medical advice or dosage recommendations
- Always recommend consulting with the pharmacist for any drug interaction concerns
- Flag high-severity alerts prominently
- If an interaction is detected, the order should include a pharmacist review step

HIPAA GUARDRAILS:
- Enforce authentication and role-based access controls before returning any prescription or alert data
- Redact or summarize PHI in all responses and logs
- Only disclose the minimum necessary information
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_prescriptions",
            "description": "Get all active prescriptions for a customer (requires authentication and pharmacist or provider role)",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer identifier"},
                    "user": {"type": "object", "description": "The requesting user context (must be provided)", "properties": {}, "required": []},
                },
                "required": ["customer_id", "user"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_refills",
            "description": "Get prescriptions due for refill within N days (requires authentication and pharmacist or provider role)",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer identifier"},
                    "within_days": {"type": "integer", "description": "Number of days to look ahead", "default": 7},
                    "user": {"type": "object", "description": "The requesting user context (must be provided)", "properties": {}, "required": []},
                },
                "required": ["customer_id", "user"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pharmacy_alerts",
            "description": "Get pharmacist alerts for a customer (requires authentication and pharmacist or provider role)",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer identifier"},
                    "user": {"type": "object", "description": "The requesting user context (must be provided)", "properties": {}, "required": []},
                },
                "required": ["customer_id", "user"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_drug_interaction",
            "description": "Check if a new OTC item might interact with existing prescriptions (requires authentication and pharmacist or provider role)",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer identifier"},
                    "new_sku": {"type": "string", "description": "The SKU of the OTC item being ordered"},
                    "user": {"type": "object", "description": "The requesting user context (must be provided)", "properties": {}, "required": []},
                },
                "required": ["customer_id", "new_sku", "user"],
            },
        },
    },
]

def _secure_handler(handler, min_role: str = "pharmacist"):
    """
    Decorator to enforce authentication, role-based access, and PHI redaction on handler functions.
    """
    def wrapper(*args, **kwargs):
        user = kwargs.get("user")
        require_authentication(user)
        require_role(user, min_role)
        # Call the original handler
        result = handler(*args, **{k: v for k, v in kwargs.items() if k != "user"})
        # Redact PHI before returning or logging
        redacted_result = redact_phi(result)
        # Log access (audit trail)
        logging.info(f"{handler.__name__} accessed by user {user.get('id', 'unknown')} (role: {user.get('role', 'unknown')}) for customer {kwargs.get('customer_id', 'unknown')}")
        return redacted_result
    return wrapper

TOOL_HANDLERS = {
    "get_prescriptions": _secure_handler(get_prescriptions, min_role="pharmacist"),
    "get_upcoming_refills": _secure_handler(get_upcoming_refills, min_role="pharmacist"),
    "get_pharmacy_alerts": _secure_handler(get_pharmacy_alerts, min_role="pharmacist"),
    "check_drug_interaction": _secure_handler(check_drug_interaction, min_role="pharmacist"),
}


def create() -> Agent:
    return Agent(
        name="PharmacyAgent",
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_handlers=TOOL_HANDLERS,
    )

