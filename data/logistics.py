"""
Simulated logistics / inbound shipment tracking.
Tracks shipments en route to stores with ETAs, carriers, and contents.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any
import logging

logger = logging.getLogger(__name__)

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

def get_inbound_for_store(
    store_id: str,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    carrier: str | None = None,
    origin: str | None = None,
) -> list[dict]:
    """Get inbound shipments heading to a store, with optional filtering and pagination."""
    try:
        shipments = [
            s for s in INBOUND_SHIPMENTS if s["destination_store"] == store_id
        ]
        if status is not None:
            shipments = [s for s in shipments if s["status"] == status]
        if carrier is not None:
            shipments = [s for s in shipments if s["carrier"] == carrier]
        if origin is not None:
            shipments = [s for s in shipments if s["origin"] == origin]
        # Pagination
        result = shipments[offset : offset + limit]
        if not result:
            logger.warning(f"No inbound shipments found for store_id={store_id} with the given filters.")
        return result
    except Exception as e:
        logger.error(f"Error in get_inbound_for_store: {e}", exc_info=True)
        raise

def get_inbound_for_sku(
    store_id: str,
    sku: str,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    carrier: str | None = None,
    origin: str | None = None,
) -> list[dict]:
    """Find inbound shipments containing a specific SKU for a store, with filtering and pagination."""
    try:
        results = []
        for shipment in INBOUND_SHIPMENTS:
            if shipment["destination_store"] != store_id:
                continue
            if status is not None and shipment["status"] != status:
                continue
            if carrier is not None and shipment["carrier"] != carrier:
                continue
            if origin is not None and shipment["origin"] != origin:
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
        paginated = results[offset : offset + limit]
        if not paginated:
            logger.warning(f"No inbound shipments found for store_id={store_id}, sku={sku} with the given filters.")
        return paginated
    except Exception as e:
        logger.error(f"Error in get_inbound_for_sku: {e}", exc_info=True)
        raise

def get_next_arrival_for_sku(store_id: str, sku: str) -> dict | None:
    """Get the soonest arriving shipment containing a specific SKU."""
    try:
        inbound = get_inbound_for_sku(store_id, sku)
        if not inbound:
            logger.info(f"No upcoming arrivals for SKU {sku} at store {store_id}.")
            return None
        next_arrival = sorted(inbound, key=lambda x: x["eta"])[0]
        return next_arrival
    except Exception as e:
        logger.error(f"Error in get_next_arrival_for_sku: {e}", exc_info=True)
        raise

