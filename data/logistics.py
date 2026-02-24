"""
Simulated logistics / inbound shipment tracking.
Tracks shipments en route to stores with ETAs, carriers, and contents.
"""

from __future__ import annotations
from datetime import datetime, timedelta

_now = datetime.utcnow

INBOUND_SHIPMENTS: list[dict] = [
    {
        "shipment_id": "SHIP-5001",
        "destination_store": "store-101",
        "origin": "DC-EAST-01",
        "carrier": "FedEx Freight",
        "status": "in_transit",
        "eta": (_now() + timedelta(days=2)).isoformat(),
        "items": [
            {"sku": "SKU-1002", "qty": 60, "name": "Vitamin D3 2000IU 90ct"},
            {"sku": "SKU-1004", "qty": 12, "name": "Blood Pressure Monitor"},
        ],
    },
    {
        "shipment_id": "SHIP-5002",
        "destination_store": "store-101",
        "origin": "DC-EAST-01",
        "carrier": "UPS Freight",
        "status": "scheduled",
        "eta": (_now() + timedelta(days=5)).isoformat(),
        "items": [
            {"sku": "SKU-1006", "qty": 20, "name": "First Aid Kit Deluxe"},
        ],
    },
    {
        "shipment_id": "SHIP-5003",
        "destination_store": "store-101",
        "origin": "DC-WEST-01",
        "carrier": "FedEx Freight",
        "status": "in_transit",
        "eta": (_now() + timedelta(hours=18)).isoformat(),
        "items": [
            {"sku": "SKU-1001", "qty": 48, "name": "Ibuprofen 200mg 100ct"},
            {"sku": "SKU-1005", "qty": 36, "name": "Allergy Relief 24hr 30ct"},
            {"sku": "SKU-1007", "qty": 24, "name": "Protein Bars Variety 12pk"},
        ],
    },
]


def get_inbound_for_store(store_id: str) -> list[dict]:
    """Get all inbound shipments heading to a store."""
    return [s for s in INBOUND_SHIPMENTS if s["destination_store"] == store_id]


def get_inbound_for_sku(store_id: str, sku: str) -> list[dict]:
    """Find inbound shipments containing a specific SKU for a store."""
    results = []
    for shipment in INBOUND_SHIPMENTS:
        if shipment["destination_store"] != store_id:
            continue
        for item in shipment["items"]:
            if item["sku"] == sku:
                results.append({
                    "shipment_id": shipment["shipment_id"],
                    "carrier": shipment["carrier"],
                    "status": shipment["status"],
                    "eta": shipment["eta"],
                    "qty_incoming": item["qty"],
                })
    return results


def get_next_arrival_for_sku(store_id: str, sku: str) -> dict | None:
    """Get the soonest arriving shipment containing a specific SKU."""
    inbound = get_inbound_for_sku(store_id, sku)
    if not inbound:
        return None
    return sorted(inbound, key=lambda x: x["eta"])[0]
