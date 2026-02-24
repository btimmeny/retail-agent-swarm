"""
Simulated provider / supplier management.
Tracks supplier relationships, lead times, and pending purchase orders.
"""

from __future__ import annotations
from datetime import datetime, timedelta

_now = datetime.utcnow

SUPPLIERS: dict[str, dict] = {
    "SUP-001": {
        "name": "PharmaCorp Inc.",
        "skus": ["SKU-1001", "SKU-1005"],
        "lead_time_days": 7,
        "min_order_qty": 500,
        "reliability_score": 0.96,
        "contact": "orders@pharmacorp.example.com",
    },
    "SUP-002": {
        "name": "VitaHealth Supply",
        "skus": ["SKU-1002", "SKU-1007"],
        "lead_time_days": 10,
        "min_order_qty": 200,
        "reliability_score": 0.91,
        "contact": "supply@vitahealth.example.com",
    },
    "SUP-003": {
        "name": "MedDevice Global",
        "skus": ["SKU-1004", "SKU-1006"],
        "lead_time_days": 14,
        "min_order_qty": 50,
        "reliability_score": 0.88,
        "contact": "b2b@meddevice.example.com",
    },
    "SUP-004": {
        "name": "CleanCare Products",
        "skus": ["SKU-1003"],
        "lead_time_days": 5,
        "min_order_qty": 1000,
        "reliability_score": 0.99,
        "contact": "wholesale@cleancare.example.com",
    },
}

PENDING_PURCHASE_ORDERS: list[dict] = [
    {
        "po_id": "PO-8001",
        "supplier_id": "SUP-002",
        "sku": "SKU-1002",
        "qty": 500,
        "status": "confirmed",
        "ordered_at": (_now() - timedelta(days=3)).isoformat(),
        "expected_delivery": (_now() + timedelta(days=7)).isoformat(),
        "destination_dc": "DC-EAST-01",
    },
    {
        "po_id": "PO-8002",
        "supplier_id": "SUP-003",
        "sku": "SKU-1006",
        "qty": 100,
        "status": "pending_confirmation",
        "ordered_at": (_now() - timedelta(days=1)).isoformat(),
        "expected_delivery": (_now() + timedelta(days=13)).isoformat(),
        "destination_dc": "DC-WEST-01",
    },
]


def get_supplier_for_sku(sku: str) -> dict | None:
    """Find the supplier responsible for a given SKU."""
    for sup_id, sup in SUPPLIERS.items():
        if sku in sup["skus"]:
            return {"supplier_id": sup_id, **sup}
    return None


def get_pending_orders_for_sku(sku: str) -> list[dict]:
    """Get all pending purchase orders for a SKU."""
    return [po for po in PENDING_PURCHASE_ORDERS if po["sku"] == sku]


def create_restock_order(sku: str, qty: int, destination_dc: str) -> dict:
    """Create a new purchase order with the appropriate supplier."""
    supplier = get_supplier_for_sku(sku)
    if not supplier:
        return {"created": False, "error": f"No supplier found for {sku}"}
    actual_qty = max(qty, supplier["min_order_qty"])
    po = {
        "po_id": f"PO-{8100 + len(PENDING_PURCHASE_ORDERS)}",
        "supplier_id": supplier["supplier_id"],
        "supplier_name": supplier["name"],
        "sku": sku,
        "qty": actual_qty,
        "status": "pending_confirmation",
        "ordered_at": _now().isoformat(),
        "expected_delivery": (_now() + timedelta(days=supplier["lead_time_days"])).isoformat(),
        "destination_dc": destination_dc,
        "lead_time_days": supplier["lead_time_days"],
    }
    PENDING_PURCHASE_ORDERS.append(po)
    return {"created": True, **po}
