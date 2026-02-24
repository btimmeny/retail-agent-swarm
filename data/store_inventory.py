"""
Simulated store-level inventory database.
Each store has SKUs with on-hand quantities, aisle locations, and reorder thresholds.
"""

from __future__ import annotations
from datetime import datetime

STORE_INVENTORY: dict[str, dict[str, dict]] = {
    "store-101": {
        "SKU-1001": {
            "name": "Ibuprofen 200mg 100ct",
            "on_hand": 24,
            "aisle": "Pharmacy-A3",
            "reorder_threshold": 10,
            "price": 8.99,
            "category": "OTC Medicine",
        },
        "SKU-1002": {
            "name": "Vitamin D3 2000IU 90ct",
            "on_hand": 0,
            "aisle": "Wellness-B1",
            "reorder_threshold": 15,
            "price": 12.49,
            "category": "Vitamins",
        },
        "SKU-1003": {
            "name": "Hand Sanitizer 8oz",
            "on_hand": 56,
            "aisle": "Personal Care-C2",
            "reorder_threshold": 20,
            "price": 3.99,
            "category": "Personal Care",
        },
        "SKU-1004": {
            "name": "Blood Pressure Monitor",
            "on_hand": 3,
            "aisle": "Health Devices-D1",
            "reorder_threshold": 5,
            "price": 49.99,
            "category": "Health Devices",
        },
        "SKU-1005": {
            "name": "Allergy Relief 24hr 30ct",
            "on_hand": 42,
            "aisle": "Pharmacy-A5",
            "reorder_threshold": 12,
            "price": 14.99,
            "category": "OTC Medicine",
        },
        "SKU-1006": {
            "name": "First Aid Kit Deluxe",
            "on_hand": 1,
            "aisle": "Health Devices-D3",
            "reorder_threshold": 4,
            "price": 24.99,
            "category": "First Aid",
        },
        "SKU-1007": {
            "name": "Protein Bars Variety 12pk",
            "on_hand": 18,
            "aisle": "Nutrition-E2",
            "reorder_threshold": 8,
            "price": 19.99,
            "category": "Nutrition",
        },
    },
}


def check_stock(store_id: str, sku: str) -> dict:
    """Check if a specific SKU is in stock at a given store."""
    store = STORE_INVENTORY.get(store_id)
    if not store:
        return {"found": False, "error": f"Store {store_id} not found"}
    item = store.get(sku)
    if not item:
        return {"found": False, "error": f"SKU {sku} not carried at {store_id}"}
    return {
        "found": True,
        "sku": sku,
        "store_id": store_id,
        "name": item["name"],
        "in_stock": item["on_hand"] > 0,
        "on_hand": item["on_hand"],
        "aisle": item["aisle"],
        "price": item["price"],
        "needs_reorder": item["on_hand"] <= item["reorder_threshold"],
    }


def check_multiple(store_id: str, skus: list[str]) -> list[dict]:
    """Check stock for multiple SKUs at once."""
    return [check_stock(store_id, sku) for sku in skus]


def reserve_stock(store_id: str, sku: str, qty: int) -> dict:
    """Attempt to reserve stock for an order. Decrements on_hand."""
    store = STORE_INVENTORY.get(store_id)
    if not store or sku not in store:
        return {"reserved": False, "error": "Item not found"}
    item = store[sku]
    if item["on_hand"] < qty:
        return {
            "reserved": False,
            "available": item["on_hand"],
            "requested": qty,
            "shortfall": qty - item["on_hand"],
        }
    item["on_hand"] -= qty
    return {
        "reserved": True,
        "sku": sku,
        "qty_reserved": qty,
        "remaining_on_hand": item["on_hand"],
        "needs_reorder": item["on_hand"] <= item["reorder_threshold"],
    }
