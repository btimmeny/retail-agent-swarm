"""
Simulated distribution center inventory.
DCs hold bulk stock and fulfill store replenishment orders.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from functools import lru_cache

_now = datetime.utcnow

DC_INVENTORY: dict[str, dict[str, dict]] = {
    "DC-EAST-01": {
        "SKU-1001": {"name": "Ibuprofen 200mg 100ct", "on_hand": 2400, "allocated": 200, "reorder_point": 500},
        "SKU-1002": {"name": "Vitamin D3 2000IU 90ct", "on_hand": 1800, "allocated": 60, "reorder_point": 400},
        "SKU-1003": {"name": "Hand Sanitizer 8oz", "on_hand": 5000, "allocated": 300, "reorder_point": 1000},
        "SKU-1004": {"name": "Blood Pressure Monitor", "on_hand": 150, "allocated": 12, "reorder_point": 50},
        "SKU-1005": {"name": "Allergy Relief 24hr 30ct", "on_hand": 3200, "allocated": 180, "reorder_point": 600},
        "SKU-1006": {"name": "First Aid Kit Deluxe", "on_hand": 420, "allocated": 20, "reorder_point": 100},
        "SKU-1007": {"name": "Protein Bars Variety 12pk", "on_hand": 960, "allocated": 50, "reorder_point": 200},
    },
    "DC-WEST-01": {
        "SKU-1001": {"name": "Ibuprofen 200mg 100ct", "on_hand": 1800, "allocated": 150, "reorder_point": 500},
        "SKU-1002": {"name": "Vitamin D3 2000IU 90ct", "on_hand": 900, "allocated": 0, "reorder_point": 400},
        "SKU-1003": {"name": "Hand Sanitizer 8oz", "on_hand": 3500, "allocated": 100, "reorder_point": 1000},
        "SKU-1004": {"name": "Blood Pressure Monitor", "on_hand": 80, "allocated": 5, "reorder_point": 50},
        "SKU-1005": {"name": "Allergy Relief 24hr 30ct", "on_hand": 2100, "allocated": 100, "reorder_point": 600},
        "SKU-1006": {"name": "First Aid Kit Deluxe", "on_hand": 15, "allocated": 0, "reorder_point": 100},
        "SKU-1007": {"name": "Protein Bars Variety 12pk", "on_hand": 720, "allocated": 24, "reorder_point": 200},
    },
}

# Maps stores to their primary and secondary DCs
STORE_DC_MAP: dict[str, list[str]] = {
    "store-101": ["DC-EAST-01", "DC-WEST-01"],
}


def check_dc_stock(dc_id: str, sku: str) -> dict:
    """Check stock at a specific distribution center."""
    dc = DC_INVENTORY.get(dc_id)
    if not dc:
        return {"found": False, "error": f"DC {dc_id} not found"}
    item = dc.get(sku)
    if not item:
        return {"found": False, "error": f"SKU {sku} not in DC {dc_id}"}
    available = item["on_hand"] - item["allocated"]
    return {
        "found": True,
        "dc_id": dc_id,
        "sku": sku,
        "name": item["name"],
        "on_hand": item["on_hand"],
        "allocated": item["allocated"],
        "available": available,
        "needs_reorder": available <= item["reorder_point"],
    }


@lru_cache(maxsize=128)
def check_all_dcs_for_sku(store_id: str, sku: str) -> list[dict]:
    """Check all DCs serving a store for a specific SKU. Cached for performance."""
    dc_ids = STORE_DC_MAP.get(store_id, [])
    return [check_dc_stock(dc_id, sku) for dc_id in dc_ids]


def allocate_from_dc(dc_id: str, sku: str, qty: int) -> dict:
    """Allocate stock from a DC for a store replenishment shipment."""
    dc = DC_INVENTORY.get(dc_id)
    if not dc or sku not in dc:
        return {"allocated": False, "error": "Not found"}
    item = dc[sku]
    available = item["on_hand"] - item["allocated"]
    if available < qty:
        return {"allocated": False, "available": available, "requested": qty}
    item["allocated"] += qty
    return {
        "allocated": True,
        "dc_id": dc_id,
        "sku": sku,
        "qty_allocated": qty,
        "estimated_ship_date": (_now() + timedelta(days=1)).isoformat(),
        "estimated_delivery": (_now() + timedelta(days=3)).isoformat(),
    }

