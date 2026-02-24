"""Clinic Agent  manages appointments, immunizations, and wellness recommendations."""

from __future__ import annotations

from agents.base import Agent
from data.clinic import (
    get_upcoming_appointments,
    get_immunization_history,
    get_wellness_recommendations,
    get_clinic_summary,
)
from utils.auth import is_authenticated, is_authorized  # NEW: Import authentication utilities
from utils.phi import redact_phi  # NEW: Import PHI redaction utility
import logging  # NEW: For audit logging

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
- Recommendations are informational only  always note they come from a prior clinic visit
- Appointment details should be shared only with the authenticated customer
- For any health concerns, direct the customer to speak with their clinic provider
"""

def _audit_log(event: str, user_id: str, customer_id: str, action: str, allowed: bool):
    logging.info(f"[AUDIT] event={event} user_id={user_id} customer_id={customer_id} action={action} allowed={allowed}")

# Wrapper functions to enforce access control and PHI redaction

def _secure_get_upcoming_appointments(user, customer_id, within_days=30):
    allowed = is_authenticated(user) and (user.id == customer_id or is_authorized(user, 'view_appointments'))
    _audit_log('get_upcoming_appointments', getattr(user, 'id', 'unknown'), customer_id, 'view_appointments', allowed)
    if not allowed:
        return {"error": "Access denied. You are not authorized to view these appointments."}
    appts = get_upcoming_appointments(customer_id=customer_id, within_days=within_days)
    # Redact PHI fields not necessary for the purpose
    return [redact_phi(a, context='appointment', user=user) for a in appts]

def _secure_get_immunization_history(user, customer_id):
    allowed = is_authenticated(user) and (user.id == customer_id or is_authorized(user, 'view_immunizations'))
    _audit_log('get_immunization_history', getattr(user, 'id', 'unknown'), customer_id, 'view_immunizations', allowed)
    if not allowed:
        return {"error": "Access denied. You are not authorized to view immunization history."}
    records = get_immunization_history(customer_id=customer_id)
    return [redact_phi(r, context='immunization', user=user) for r in records]

def _secure_get_wellness_recommendations(user, customer_id):
    allowed = is_authenticated(user) and (user.id == customer_id or is_authorized(user, 'view_recommendations'))
    _audit_log('get_wellness_recommendations', getattr(user, 'id', 'unknown'), customer_id, 'view_recommendations', allowed)
    if not allowed:
        return {"error": "Access denied. You are not authorized to view recommendations."}
    recs = get_wellness_recommendations(customer_id=customer_id)
    return [redact_phi(r, context='recommendation', user=user) for r in recs]

def _secure_get_clinic_summary(user, customer_id):
    allowed = is_authenticated(user) and (user.id == customer_id or is_authorized(user, 'view_clinic_summary'))
    _audit_log('get_clinic_summary', getattr(user, 'id', 'unknown'), customer_id, 'view_clinic_summary', allowed)
    if not allowed:
        return {"error": "Access denied. You are not authorized to view this clinic summary."}
    summary = get_clinic_summary(customer_id=customer_id)
    # Redact PHI in all nested fields
    if 'appointments' in summary:
        summary['appointments'] = [redact_phi(a, context='appointment', user=user) for a in summary['appointments']]
    if 'immunizations' in summary:
        summary['immunizations'] = [redact_phi(i, context='immunization', user=user) for i in summary['immunizations']]
    if 'recommendations' in summary:
        summary['recommendations'] = [redact_phi(r, context='recommendation', user=user) for r in summary['recommendations']]
    return summary

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

# The agent must be passed a user context for each tool handler call
TOOL_HANDLERS = {
    "get_upcoming_appointments": lambda params, user=None: _secure_get_upcoming_appointments(user, params["customer_id"], params.get("within_days", 30)),
    "get_immunization_history": lambda params, user=None: _secure_get_immunization_history(user, params["customer_id"]),
    "get_wellness_recommendations": lambda params, user=None: _secure_get_wellness_recommendations(user, params["customer_id"]),
    "get_clinic_summary": lambda params, user=None: _secure_get_clinic_summary(user, params["customer_id"]),
}


def create() -> Agent:
    return Agent(
        name="ClinicAgent",
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        tool_handlers=TOOL_HANDLERS,
    )

