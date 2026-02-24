"""
Simulated pharmacy department database.
Tracks prescriptions, refill schedules, and pharmacist consultations.
"""

from __future__ import annotations
from datetime import datetime, timedelta

_now = datetime.utcnow

PRESCRIPTIONS: dict[str, list[dict]] = {
    "CUST-2001": [
        {
            "rx_id": "RX-3001",
            "medication": "Lisinopril 10mg",
            "prescriber": "Dr. Angela Park",
            "status": "active",
            "refills_remaining": 3,
            "last_filled": (_now() - timedelta(days=28)).isoformat(),
            "next_refill_due": (_now() + timedelta(days=2)).isoformat(),
            "days_supply": 30,
            "auto_refill": True,
            "notes": "Take once daily. Monitor blood pressure.",
        },
        {
            "rx_id": "RX-3002",
            "medication": "Metformin 500mg",
            "prescriber": "Dr. Angela Park",
            "status": "active",
            "refills_remaining": 5,
            "last_filled": (_now() - timedelta(days=15)).isoformat(),
            "next_refill_due": (_now() + timedelta(days=15)).isoformat(),
            "days_supply": 30,
            "auto_refill": True,
            "notes": "Take twice daily with meals.",
        },
    ],
    "CUST-2002": [
        {
            "rx_id": "RX-3003",
            "medication": "Atorvastatin 20mg",
            "prescriber": "Dr. Robert Kim",
            "status": "active",
            "refills_remaining": 2,
            "last_filled": (_now() - timedelta(days=20)).isoformat(),
            "next_refill_due": (_now() + timedelta(days=10)).isoformat(),
            "days_supply": 30,
            "auto_refill": False,
            "notes": "Take at bedtime.",
        },
    ],
    "CUST-2003": [],
}

PHARMACIST_ALERTS: dict[str, list[dict]] = {
    "CUST-2001": [
        {
            "alert_type": "interaction_warning",
            "message": "Customer has penicillin allergy — verify any new antibiotic orders.",
            "severity": "high",
        },
        {
            "alert_type": "refill_reminder",
            "message": "Lisinopril 10mg refill due in 2 days. Auto-refill is enabled.",
            "severity": "info",
        },
    ],
    "CUST-2002": [
        {
            "alert_type": "refill_reminder",
            "message": "Atorvastatin 20mg refill due in 10 days. Auto-refill is OFF — customer may need a reminder.",
            "severity": "medium",
        },
    ],
}


def get_prescriptions(customer_id: str) -> list[dict]:
    """Get all active prescriptions for a customer."""
    return [rx for rx in PRESCRIPTIONS.get(customer_id, []) if rx["status"] == "active"]


def get_upcoming_refills(customer_id: str, within_days: int = 7) -> list[dict]:
    """Get prescriptions due for refill within N days."""
    cutoff = (_now() + timedelta(days=within_days)).isoformat()
    results = []
    for rx in PRESCRIPTIONS.get(customer_id, []):
        if rx["status"] == "active" and rx["next_refill_due"] <= cutoff:
            results.append(rx)
    return results


def get_pharmacy_alerts(customer_id: str) -> list[dict]:
    """Get pharmacist alerts for a customer."""
    return PHARMACIST_ALERTS.get(customer_id, [])


def check_drug_interaction(customer_id: str, new_sku: str) -> dict:
    """Check if a new OTC item might interact with existing prescriptions.
    Simplified simulation — in reality this would query a drug interaction DB.
    """
    OTC_INTERACTION_MAP = {
        "SKU-1001": {  # Ibuprofen
            "interacts_with": ["Lisinopril"],
            "warning": "NSAIDs like ibuprofen may reduce the effectiveness of ACE inhibitors (Lisinopril). "
                       "Consider acetaminophen as an alternative.",
            "severity": "moderate",
        },
    }
    interaction = OTC_INTERACTION_MAP.get(new_sku)
    if not interaction:
        return {"has_interaction": False}

    active_meds = [rx["medication"] for rx in get_prescriptions(customer_id)]
    for med in active_meds:
        for interacting_drug in interaction["interacts_with"]:
            if interacting_drug.lower() in med.lower():
                return {
                    "has_interaction": True,
                    "sku": new_sku,
                    "conflicting_medication": med,
                    "warning": interaction["warning"],
                    "severity": interaction["severity"],
                }
    return {"has_interaction": False}
