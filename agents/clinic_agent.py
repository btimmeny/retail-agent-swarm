"""Clinic Agent — manages appointments, immunizations, and wellness recommendations."""

from __future__ import annotations

from agents.base import Agent
from data.clinic import (
    get_upcoming_appointments,
    get_immunization_history,
    get_wellness_recommendations,
    get_clinic_summary,
)

SYSTEM_PROMPT = """\
You are the Clinic Agent for a retail pharmacy chain's in-store clinic.
Your job is to surface relevant clinic information during the order process.
When consulted:
- Check for upcoming appointments the customer should be reminded about
- Review immunization history for any overdue vaccines
- Surface wellness product recommendations from prior clinic visits
- Connect clinic recommendations to items available in-store

IMPORTANT GUARDRAILS:
- Never diagnose conditions or provide medical advice
- Recommendations are informational only — always note they come from a prior clinic visit
- Appointment details should be shared only with the authenticated customer
- For any health concerns, direct the customer to speak with their clinic provider
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_appointments",
            "description": "Get upcoming clinic appointments for a customer",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer identifier"},
                    "within_days": {"type": "integer", "description": "Days to look ahead", "default": 30},
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_immunization_history",
            "description": "Get vaccination/immunization records for a customer",
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
            "name": "get_wellness_recommendations",
            "description": "Get wellness product recommendations from prior clinic consultations",
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
            "name": "get_clinic_summary",
            "description": "Get a full clinic summary including appointments, immunizations, and recommendations",
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
    "get_upcoming_appointments": get_upcoming_appointments,
    "get_immunization_history": get_immunization_history,
    "get_wellness_recommendations": get_wellness_recommendations,
    "get_clinic_summary": get_clinic_summary,
}


def create() -> Agent:
    return Agent(
        name="ClinicAgent",
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_handlers=TOOL_HANDLERS,
    )
