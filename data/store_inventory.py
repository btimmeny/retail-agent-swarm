"""
Simulated store-level inventory database.
Each store has SKUs with on-hand quantities, aisle locations, and reorder thresholds.
"""

from __future__ import annotations
from datetime import datetime
import threading
import requests
import re

# --- OpenTelemetry Tracing Integration ---
from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer(__name__)

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

# --- Webhook mechanism ---
_WEBHOOKS: dict[str, set[str]] = {}
_WEBHOOKS_LOCK = threading.Lock()

def register_webhook(event: str, url: str):
    """Register a webhook URL for a given event."""
    with _WEBHOOKS_LOCK:
        if event not in _WEBHOOKS:
            _WEBHOOKS[event] = set()
        _WEBHOOKS[event].add(url)

def unregister_webhook(event: str, url: str):
    """Unregister a webhook URL for a given event."""
    with _WEBHOOKS_LOCK:
        if event in _WEBHOOKS and url in _WEBHOOKS[event]:
            _WEBHOOKS[event].remove(url)
            if not _WEBHOOKS[event]:
                del _WEBHOOKS[event]

def _trigger_webhook(event: str, payload: dict):
    """Trigger all registered webhooks for an event with the given payload."""
    with _WEBHOOKS_LOCK:
        urls = list(_WEBHOOKS.get(event, set()))
    for url in urls:
        # Send asynchronously to avoid blocking
        threading.Thread(target=_send_webhook, args=(url, payload)).start()

def _send_webhook(url: str, payload: dict):
    try:
        requests.post(url, json=payload, timeout=3)
    except Exception:
        pass  # Optionally log failures

# --- Input validation helpers ---

def _validate_store_id(store_id: str):
    if not isinstance(store_id, str):
        raise ValueError('Invalid store_id: not a string')
    # Allow alphanumeric, dash, and underscore
    if not re.fullmatch(r'[\w\-]+', store_id):
        raise ValueError('Invalid store_id: must be alphanumeric, dash or underscore')


def _validate_sku(sku: str):
    if not isinstance(sku, str):
        raise ValueError('Invalid sku: not a string')
    # Allow alphanumeric, dash, and underscore
    if not re.fullmatch(r'[\w\-]+', sku):
        raise ValueError('Invalid sku: must be alphanumeric, dash or underscore')


def _validate_qty(qty):
    if not isinstance(qty, int):
        raise ValueError('Invalid qty: not an integer')
    if qty <= 0:
        raise ValueError('Invalid qty: must be positive')

# --- Inventory functions ---

def check_stock(store_id: str, sku: str) -> dict:
    """Check if a specific SKU is in stock at a given store."""
    with tracer.start_as_current_span('check_stock', kind=SpanKind.INTERNAL) as span:
        try:
            _validate_store_id(store_id)
            _validate_sku(sku)
        except ValueError as ve:
            if span is not None:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(ve))
            return {"found": False, "error": str(ve)}
        store = STORE_INVENTORY.get(store_id)
        if not store:
            if span is not None:
                span.set_attribute("error", True)
                span.set_attribute("error.message", f"Store {store_id} not found")
            return {"found": False, "error": f"Store {store_id} not found"}
        item = store.get(sku)
        if not item:
            if span is not None:
                span.set_attribute("error", True)
                span.set_attribute("error.message", f"SKU {sku} not carried at {store_id}")
            return {"found": False, "error": f"SKU {sku} not carried at {store_id}"}
        if span is not None:
            span.set_attribute("store_id", store_id)
            span.set_attribute("sku", sku)
            span.set_attribute("on_hand", item["on_hand"])
            span.set_attribute("needs_reorder", item["on_hand"] <= item["reorder_threshold"])
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
    with tracer.start_as_current_span('check_multiple', kind=SpanKind.INTERNAL) as span:
        try:
            _validate_store_id(store_id)
            if not isinstance(skus, list):
                raise ValueError('Invalid skus: not a list')
            for sku in skus:
                _validate_sku(sku)
        except ValueError as ve:
            if span is not None:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(ve))
            # Return a single error dict for all if input is invalid
            return [{"found": False, "error": str(ve)}]
        if span is not None:
            span.set_attribute("store_id", store_id)
            span.set_attribute("sku_count", len(skus))
        results = [check_stock(store_id, sku) for sku in skus]
        return results


def reserve_stock(store_id: str, sku: str, qty: int) -> dict:
    """Attempt to reserve stock for an order. Decrements on_hand."""
    with tracer.start_as_current_span('reserve_stock', kind=SpanKind.INTERNAL) as span:
        try:
            _validate_store_id(store_id)
            _validate_sku(sku)
            _validate_qty(qty)
        except ValueError as ve:
            if span is not None:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(ve))
            return {"reserved": False, "error": str(ve)}
        store = STORE_INVENTORY.get(store_id)
        if not store or sku not in store:
            if span is not None:
                span.set_attribute("error", True)
                span.set_attribute("error.message", "Item not found")
            return {"reserved": False, "error": "Item not found"}
        item = store[sku]
        if item["on_hand"] < qty:
            if span is not None:
                span.set_attribute("error", True)
                span.set_attribute("error.message", "Insufficient stock")
                span.set_attribute("available", item["on_hand"])
                span.set_attribute("requested", qty)
            return {
                "reserved": False,
                "available": item["on_hand"],
                "requested": qty,
                "shortfall": qty - item["on_hand"],
            }
        item["on_hand"] -= qty
        result = {
            "reserved": True,
            "sku": sku,
            "qty_reserved": qty,
            "remaining_on_hand": item["on_hand"],
            "needs_reorder": item["on_hand"] <= item["reorder_threshold"],
        }
        if span is not None:
            span.set_attribute("store_id", store_id)
            span.set_attribute("sku", sku)
            span.set_attribute("qty_reserved", qty)
            span.set_attribute("remaining_on_hand", item["on_hand"])
            span.set_attribute("needs_reorder", item["on_hand"] <= item["reorder_threshold"])
        # Trigger webhook for stock reserved
        _trigger_webhook(
            "stock_reserved",
            {
                "event": "stock_reserved",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "store_id": store_id,
                "sku": sku,
                "qty_reserved": qty,
                "remaining_on_hand": item["on_hand"],
            },
        )
        # If stock now below or at reorder threshold, trigger low inventory webhook
        if item["on_hand"] <= item["reorder_threshold"]:
            _trigger_webhook(
                "inventory_low",
                {
                    "event": "inventory_low",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "store_id": store_id,
                    "sku": sku,
                    "on_hand": item["on_hand"],
                    "reorder_threshold": item["reorder_threshold"],
                },
            )
        return result


