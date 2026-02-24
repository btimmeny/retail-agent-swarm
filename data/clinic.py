"""
Simulated in-store clinic database.
Tracks appointments, health screenings, immunizations, and wellness programs.
"""

from __future__ import annotations
from datetime import datetime, timedelta
import logging

_now = datetime.utcnow

# Audit log setup (could be replaced with a more robust system)
def audit_log(customer_id: str, function: str, timestamp: str) -> None:
    """Log access to sensitive data for audit trail compliance."""
    logging.info(f"AUDIT_LOG | customer_id={customer_id} | function={function} | timestamp={timestamp}")

APPOINTMENTS: dict[str, list[dict]] = {
    "CUST-2001": [
        {
            "appt_id": "APPT-4001",
            "type": "Annual Flu Shot",
            "provider": "NP Linda Torres",
            "scheduled_at": (_now() + timedelta(days=5, hours=10)).isoformat(),
            "status": "confirmed",
            "location": "store-101 Clinic Room A",
            "notes": "Patient allergic to penicillin \u0014 documented. Standard flu vaccine OK.",
        },
        {
            "appt_id": "APPT-4003",
            "type": "Blood Pressure Check",
            "provider": "NP Linda Torres",
            "scheduled_at": (_now() + timedelta(days=12, hours=14)).isoformat(),
            "status": "confirmed",
            "location": "store-101 Clinic Room A",
            "notes": "Follow-up for Lisinopril therapy monitoring.",
        },
    ],
    "CUST-2002": [
        {
            "appt_id": "APPT-4002",
            "type": "Cholesterol Screening",
            "provider": "NP Marcus Reed",
            "scheduled_at": (_now() + timedelta(days=8, hours=9)).isoformat(),
            "status": "confirmed",
            "location": "store-101 Clinic Room B",
            "notes": "Fasting required. Patient on Atorvastatin \u0014 check lipid panel.",
        },
    ],
    "CUST-2003": [],
}

IMMUNIZATION_RECORDS: dict[str, list[dict]] = {
    "CUST-2001": [
        {"vaccine": "COVID-19 Booster (Moderna)", "date": (_now() - timedelta(days=180)).isoformat(), "provider": "store-101 Clinic"},
        {"vaccine": "Flu Shot 2024-2025", "date": (_now() - timedelta(days=365)).isoformat(), "provider": "store-101 Clinic"},
    ],
    "CUST-2002": [
        {"vaccine": "Shingles (Shingrix Dose 1)", "date": (_now() - timedelta(days=60)).isoformat(), "provider": "store-101 Clinic"},
    ],
    "CUST-2003": [],
}

WELLNESS_RECOMMENDATIONS: dict[str, list[dict]] = {
    "CUST-2001": [
        {
            "recommendation": "Vitamin D supplementation",
            "reason": "Based on blood work from last clinic visit \u0014 low Vitamin D levels.",
            "suggested_sku": "SKU-1002",
            "priority": "recommended",
        },
        {
            "recommendation": "Blood pressure home monitoring",
            "reason": "Currently on Lisinopril \u0014 regular home monitoring advised.",
            "suggested_sku": "SKU-1004",
            "priority": "advised",
        },
    ],
    "CUST-2002": [
        {
            "recommendation": "Protein supplementation",
            "reason": "Discussed during last wellness check \u0014 patient interested in fitness nutrition.",
            "suggested_sku": "SKU-1007",
            "priority": "optional",
        },
    ],
}

def _validate_customer_id(customer_id: str) -> None:
    """Validate the format of customer_id."""
    if not isinstance(customer_id, str) or not customer_id.startswith('CUST-') or not customer_id[5:].isdigit():
        raise ValueError('Invalid customer_id')

def get_upcoming_appointments(customer_id: str, within_days: int = 30) -> list[dict]:
    """Get upcoming clinic appointments for a customer."""
    _validate_customer_id(customer_id)
    # Audit log for access to appointment data
    audit_log(customer_id, 'get_upcoming_appointments', datetime.utcnow().isoformat())
    cutoff = (_now() + timedelta(days=within_days)).isoformat()
    return [
        appt for appt in APPOINTMENTS.get(customer_id, [])
        if appt["status"] == "confirmed" and appt["scheduled_at"] <= cutoff
    ]


def get_immunization_history(customer_id: str) -> list[dict]:
    """Get vaccination/immunization records."""
    _validate_customer_id(customer_id)
    # Audit log for access to immunization data
    audit_log(customer_id, 'get_immunization_history', datetime.utcnow().isoformat())
    return IMMUNIZATION_RECORDS.get(customer_id, [])


def get_wellness_recommendations(customer_id: str) -> list[dict]:
    """Get wellness product recommendations from clinic consultations."""
    _validate_customer_id(customer_id)
    # Audit log for access to wellness data
    audit_log(customer_id, 'get_wellness_recommendations', datetime.utcnow().isoformat())
    return WELLNESS_RECOMMENDATIONS.get(customer_id, [])


def get_clinic_summary(customer_id: str) -> dict:
    """Get a full clinic summary for a customer."""
    _validate_customer_id(customer_id)
    # Audit log for access to all sensitive clinic data at summary level
    audit_log(customer_id, 'get_clinic_summary', datetime.utcnow().isoformat())
    return {
        "upcoming_appointments": get_upcoming_appointments(customer_id),
        "immunization_history": get_immunization_history(customer_id),
        "wellness_recommendations": get_wellness_recommendations(customer_id),
    }


