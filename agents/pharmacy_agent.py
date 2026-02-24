"""Pharmacy Agent — manages prescriptions, refills, drug interactions, and pharmacist alerts."""

from __future__ import annotations

from agents.base import Agent
from data.pharmacy import (
    get_prescriptions,
    get_upcoming_refills,
    get_pharmacy_alerts,
    check_drug_interaction,
)

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
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_prescriptions",
            "description": "Get all active prescriptions for a customer",
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
            "name": "get_upcoming_refills",
            "description": "Get prescriptions due for refill within N days",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer identifier"},
                    "within_days": {"type": "integer", "description": "Number of days to look ahead", "default": 7},
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pharmacy_alerts",
            "description": "Get pharmacist alerts for a customer",
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
            "name": "check_drug_interaction",
            "description": "Check if a new OTC item might interact with existing prescriptions",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer identifier"},
                    "new_sku": {"type": "string", "description": "The SKU of the OTC item being ordered"},
                },
                "required": ["customer_id", "new_sku"],
            },
        },
    },
]

TOOL_HANDLERS = {
    "get_prescriptions": get_prescriptions,
    "get_upcoming_refills": get_upcoming_refills,
    "get_pharmacy_alerts": get_pharmacy_alerts,
    "check_drug_interaction": check_drug_interaction,
}


def create() -> Agent:
    return Agent(
        name="PharmacyAgent",
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_handlers=TOOL_HANDLERS,
    )
