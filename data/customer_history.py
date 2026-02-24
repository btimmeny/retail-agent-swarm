"""
Simulated customer purchase history and profile database.
Tracks past orders, preferences, and loyalty info.
"""

from __future__ import annotations
from datetime import datetime, timedelta

_now = datetime.utcnow

CUSTOMERS: dict[str, dict] = {
    "CUST-2001": {
        "name": "Maria Johnson",
        "email": "maria.j@example.com",
        "phone": "+1-555-0142",
        "loyalty_tier": "Gold",
        "loyalty_points": 4820,
        "preferred_store": "store-101",
        "allergies": ["penicillin", "sulfa"],
        "created_at": "2021-03-15T00:00:00",
    },
    "CUST-2002": {
        "name": "James Chen",
        "email": "jchen@example.com",
        "phone": "+1-555-0198",
        "loyalty_tier": "Platinum",
        "loyalty_points": 12350,
        "preferred_store": "store-101",
        "allergies": [],
        "created_at": "2019-08-22T00:00:00",
    },
    "CUST-2003": {
        "name": "Sarah Williams",
        "email": "swilliams@example.com",
        "phone": "+1-555-0267",
        "loyalty_tier": "Silver",
        "loyalty_points": 1540,
        "preferred_store": "store-101",
        "allergies": ["latex"],
        "created_at": "2023-01-10T00:00:00",
    },
}

ORDER_HISTORY: dict[str, list[dict]] = {
    "CUST-2001": [
        {
            "order_id": "ORD-9001",
            "date": (_now() - timedelta(days=14)).isoformat(),
            "store_id": "store-101",
            "items": [
                {"sku": "SKU-1001", "name": "Ibuprofen 200mg 100ct", "qty": 1, "price": 8.99},
                {"sku": "SKU-1002", "name": "Vitamin D3 2000IU 90ct", "qty": 2, "price": 12.49},
            ],
            "total": 33.97,
            "status": "delivered",
        },
        {
            "order_id": "ORD-9005",
            "date": (_now() - timedelta(days=45)).isoformat(),
            "store_id": "store-101",
            "items": [
                {"sku": "SKU-1005", "name": "Allergy Relief 24hr 30ct", "qty": 1, "price": 14.99},
                {"sku": "SKU-1003", "name": "Hand Sanitizer 8oz", "qty": 3, "price": 3.99},
            ],
            "total": 26.96,
            "status": "delivered",
        },
    ],
    "CUST-2002": [
        {
            "order_id": "ORD-9002",
            "date": (_now() - timedelta(days=7)).isoformat(),
            "store_id": "store-101",
            "items": [
                {"sku": "SKU-1004", "name": "Blood Pressure Monitor", "qty": 1, "price": 49.99},
            ],
            "total": 49.99,
            "status": "delivered",
        },
        {
            "order_id": "ORD-9006",
            "date": (_now() - timedelta(days=30)).isoformat(),
            "store_id": "store-101",
            "items": [
                {"sku": "SKU-1001", "name": "Ibuprofen 200mg 100ct", "qty": 2, "price": 8.99},
                {"sku": "SKU-1007", "name": "Protein Bars Variety 12pk", "qty": 1, "price": 19.99},
            ],
            "total": 37.97,
            "status": "delivered",
        },
    ],
    "CUST-2003": [
        {
            "order_id": "ORD-9003",
            "date": (_now() - timedelta(days=3)).isoformat(),
            "store_id": "store-101",
            "items": [
                {"sku": "SKU-1006", "name": "First Aid Kit Deluxe", "qty": 1, "price": 24.99},
            ],
            "total": 24.99,
            "status": "processing",
        },
    ],
}


def get_customer(customer_id: str) -> dict | None:
    """Retrieve customer profile."""
    return CUSTOMERS.get(customer_id)


def get_order_history(customer_id: str) -> list[dict]:
    """Get full order history for a customer."""
    return ORDER_HISTORY.get(customer_id, [])


def get_recent_orders(customer_id: str, limit: int = 5) -> list[dict]:
    """Get most recent orders for a customer."""
    history = ORDER_HISTORY.get(customer_id, [])
    return sorted(history, key=lambda x: x["date"], reverse=True)[:limit]


def get_frequently_purchased(customer_id: str) -> list[dict]:
    """Determine frequently purchased items from history."""
    sku_counts: dict[str, dict] = {}
    for order in ORDER_HISTORY.get(customer_id, []):
        for item in order["items"]:
            sku = item["sku"]
            if sku not in sku_counts:
                sku_counts[sku] = {"sku": sku, "name": item["name"], "total_qty": 0, "order_count": 0}
            sku_counts[sku]["total_qty"] += item["qty"]
            sku_counts[sku]["order_count"] += 1
    return sorted(sku_counts.values(), key=lambda x: x["order_count"], reverse=True)
