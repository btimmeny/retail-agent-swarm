# test_logistics_features.py
"""
Feature tests for logistics, provider, and distribution center data/agent layers.
Covers:
- Pagination and filtering in logistics data
- Input validation in provider data
- LRU cache in distribution center
- Agent tool handler correctness
- Edge cases and error handling
"""

import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

import data.logistics as logistics
import data.provider as provider
import data.distribution_center as dc
import agents.logistics_agent as logistics_agent
import agents.provider_agent as provider_agent
import agents.distribution_agent as distribution_agent

# --- Fixtures ---
@pytest.fixture(autouse=True)
def reset_provider_orders():
    # Reset PENDING_PURCHASE_ORDERS before each test
    provider.PENDING_PURCHASE_ORDERS.clear()
    provider.PENDING_PURCHASE_ORDERS.extend([
        {
            "po_id": "PO-8001",
            "supplier_id": "SUP-002",
            "sku": "SKU-1002",
            "qty": 500,
            "status": "confirmed",
            "ordered_at": (datetime.utcnow() - timedelta(days=3)).isoformat(),
            "expected_delivery": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            "destination_dc": "DC-EAST-01",
        },
        {
            "po_id": "PO-8002",
            "supplier_id": "SUP-003",
            "sku": "SKU-1006",
            "qty": 100,
            "status": "pending_confirmation",
            "ordered_at": (datetime.utcnow() - timedelta(days=1)).isoformat(),
            "expected_delivery": (datetime.utcnow() + timedelta(days=13)).isoformat(),
            "destination_dc": "DC-WEST-01",
        },
    ])

@pytest.fixture(autouse=True)
def reset_dc_inventory():
    # Reset DC_INVENTORY before each test
    dc.DC_INVENTORY["DC-EAST-01"]["SKU-1001"]["allocated"] = 200
    dc.DC_INVENTORY["DC-EAST-01"]["SKU-1001"]["on_hand"] = 2400
    dc.DC_INVENTORY["DC-WEST-01"]["SKU-1001"]["allocated"] = 150
    dc.DC_INVENTORY["DC-WEST-01"]["SKU-1001"]["on_hand"] = 1800

# --- Logistics Data Layer ---
def test_get_inbound_for_store_pagination_and_filtering():
    """
    get_inbound_for_store should support limit, offset, and status filtering.
    """
    # Patch the underlying shipment data
    shipments = [
        {"shipment_id": f"SHIP-{i}", "store_id": "store-101", "status": "in_transit" if i % 2 == 0 else "delivered"}
        for i in range(10)
    ]
    with patch("data.logistics.INBOUND_SHIPMENTS", shipments):
        # No filters
        results = logistics.get_inbound_for_store("store-101")
        assert len(results) == 10
        # Limit
        results = logistics.get_inbound_for_store("store-101", limit=3)
        assert len(results) == 3
        # Offset
        results = logistics.get_inbound_for_store("store-101", offset=8)
        assert len(results) == 2
        # Status filter
        results = logistics.get_inbound_for_store("store-101", status="in_transit")
        assert all(r["status"] == "in_transit" for r in results)
        # Combined
        results = logistics.get_inbound_for_store("store-101", status="delivered", limit=2, offset=1)
        delivered = [s for s in shipments if s["status"] == "delivered"]
        assert results == delivered[1:3]

def test_get_inbound_for_sku_pagination_and_filtering():
    """
    get_inbound_for_sku should support limit, offset, status filtering, and only return shipments with the SKU.
    """
    shipments = [
        {"shipment_id": f"SHIP-{i}", "store_id": "store-101", "status": "in_transit", "items": [
            {"sku": "SKU-1001"}, {"sku": "SKU-1002"} if i % 2 == 0 else {"sku": "SKU-1003"}
        ]}
        for i in range(6)
    ]
    with patch("data.logistics.INBOUND_SHIPMENTS", shipments):
        # Only shipments with SKU-1002
        results = logistics.get_inbound_for_sku("store-101", "SKU-1002")
        assert all(any(item["sku"] == "SKU-1002" for item in s["items"]) for s in results)
        # Pagination
        results = logistics.get_inbound_for_sku("store-101", "SKU-1001", limit=2)
        assert len(results) == 2
        # Status filter (all in_transit)
        results = logistics.get_inbound_for_sku("store-101", "SKU-1001", status="in_transit")
        assert all(s["status"] == "in_transit" for s in results)

def test_get_next_arrival_for_sku_status_filter():
    """
    get_next_arrival_for_sku should return the soonest ETA for a given SKU and status.
    """
    now = datetime.utcnow()
    shipments = [
        {"shipment_id": "S1", "store_id": "store-101", "status": "in_transit", "eta": (now + timedelta(days=2)).isoformat(), "items": [{"sku": "SKU-1002"}]},
        {"shipment_id": "S2", "store_id": "store-101", "status": "delivered", "eta": (now + timedelta(days=1)).isoformat(), "items": [{"sku": "SKU-1002"}]},
        {"shipment_id": "S3", "store_id": "store-101", "status": "in_transit", "eta": (now + timedelta(days=1)).isoformat(), "items": [{"sku": "SKU-1002"}]},
    ]
    with patch("data.logistics.INBOUND_SHIPMENTS", shipments):
        result = logistics.get_next_arrival_for_sku("store-101", "SKU-1002", status="in_transit")
        assert result["shipment_id"] == "S3"
        assert result["status"] == "in_transit"

def test_get_inbound_for_store_invalid_store():
    """
    get_inbound_for_store should return empty list for unknown store.
    """
    with patch("data.logistics.INBOUND_SHIPMENTS", []):
        results = logistics.get_inbound_for_store("unknown-store")
        assert results == []

# --- Provider Data Layer ---
def test_provider_input_validation():
    """
    create_restock_order should reject invalid SKU, qty, or destination_dc.
    """
    # Invalid SKU
    resp = provider.create_restock_order("BADSKU", 100, "DC-EAST-01")
    assert not resp["created"]
    assert "Invalid SKU" in resp["error"]
    # Invalid qty
    resp = provider.create_restock_order("SKU-1001", -5, "DC-EAST-01")
    assert not resp["created"]
    assert "Quantity must be" in resp["error"]
    # Invalid DC
    resp = provider.create_restock_order("SKU-1001", 100, "BAD-DC")
    assert not resp["created"]
    assert "Invalid destination_dc" in resp["error"]

def test_provider_min_order_qty_enforced():
    """
    create_restock_order should use min_order_qty if requested qty is less.
    """
    resp = provider.create_restock_order("SKU-1002", 50, "DC-EAST-01")
    assert resp["created"]
    assert resp["qty"] == provider.SUPPLIERS["SUP-002"]["min_order_qty"]

def test_provider_get_supplier_for_sku_not_found():
    """
    get_supplier_for_sku returns None if SKU not found.
    """
    assert provider.get_supplier_for_sku("SKU-9999") is None

def test_provider_get_pending_orders_for_sku():
    """
    get_pending_orders_for_sku returns only orders for the given SKU.
    """
    orders = provider.get_pending_orders_for_sku("SKU-1002")
    assert all(o["sku"] == "SKU-1002" for o in orders)

# --- Distribution Center Data Layer ---
def test_dc_lru_cache():
    """
    check_all_dcs_for_sku should cache results (lru_cache).
    """
    # Patch check_dc_stock to count calls
    call_count = {}
    orig = dc.check_dc_stock
    def wrapped(dc_id, sku):
        call_count[dc_id] = call_count.get(dc_id, 0) + 1
        return orig(dc_id, sku)
    with patch("data.distribution_center.check_dc_stock", side_effect=wrapped):
        dc.check_all_dcs_for_sku.cache_clear()
        dc.check_all_dcs_for_sku("store-101", "SKU-1001")
        dc.check_all_dcs_for_sku("store-101", "SKU-1001")  # Should hit cache
        assert sum(call_count.values()) == 2  # 2 DCs, only called once each

# --- Agent Tool Handlers ---
def test_logistics_agent_tool_handlers():
    """
    Logistics agent tool handlers should call correct data functions and support filters.
    """
    agent = logistics_agent.create()
    with patch("data.logistics.get_inbound_for_store", return_value=[{"shipment_id": "S1"}]) as m:
        result = agent.tool_handlers["get_inbound_for_store"]("store-101", limit=1)
        m.assert_called_with("store-101", limit=1)
        assert result == [{"shipment_id": "S1"}]
    with patch("data.logistics.get_inbound_for_sku", return_value=[{"shipment_id": "S2"}]) as m:
        result = agent.tool_handlers["get_inbound_for_sku"]("store-101", "SKU-1002", status="in_transit")
        m.assert_called_with("store-101", "SKU-1002", status="in_transit")
        assert result == [{"shipment_id": "S2"}]

# --- Edge Cases ---
def test_allocate_from_dc_insufficient_stock():
    """
    allocate_from_dc should fail if not enough available stock.
    """
    # Set available to 1, request 10
    dc.DC_INVENTORY["DC-EAST-01"]["SKU-1001"]["on_hand"] = 201
    dc.DC_INVENTORY["DC-EAST-01"]["SKU-1001"]["allocated"] = 200
    resp = dc.allocate_from_dc("DC-EAST-01", "SKU-1001", 10)
    assert not resp["allocated"]
    assert resp["available"] == 1
    assert resp["requested"] == 10

def test_allocate_from_dc_success():
    """
    allocate_from_dc should allocate and update allocated count.
    """
    before = dc.DC_INVENTORY["DC-EAST-01"]["SKU-1001"]["allocated"]
    resp = dc.allocate_from_dc("DC-EAST-01", "SKU-1001", 5)
    assert resp["allocated"]
    assert resp["qty_allocated"] == 5
    after = dc.DC_INVENTORY["DC-EAST-01"]["SKU-1001"]["allocated"]
    assert after == before + 5

# --- Distribution Agent Tool Handlers ---
def test_distribution_agent_tool_handlers():
    """
    Distribution agent tool handlers should call correct DC functions.
    """
    agent = distribution_agent.create()
    with patch("data.distribution_center.check_dc_stock", return_value={"found": True}) as m:
        result = agent.tool_handlers["check_dc_stock"]("DC-EAST-01", "SKU-1001")
        m.assert_called_with("DC-EAST-01", "SKU-1001")
        assert result["found"]
    with patch("data.distribution_center.allocate_from_dc", return_value={"allocated": True}) as m:
        result = agent.tool_handlers["allocate_from_dc"]("DC-EAST-01", "SKU-1001", 10)
        m.assert_called_with("DC-EAST-01", "SKU-1001", 10)
        assert result["allocated"]

# --- Provider Agent Tool Handlers ---
def test_provider_agent_tool_handlers():
    """
    Provider agent tool handlers should call correct provider data functions.
    """
    agent = provider_agent.create()
    with patch("data.provider.get_supplier_for_sku", return_value={"supplier_id": "SUP-001"}) as m:
        result = agent.tool_handlers["get_supplier_for_sku"]("SKU-1001")
        m.assert_called_with("SKU-1001")
        assert result["supplier_id"] == "SUP-001"
    with patch("data.provider.create_restock_order", return_value={"created": True}) as m:
        result = agent.tool_handlers["create_restock_order"]("SKU-1001", 100, "DC-EAST-01")
        m.assert_called_with("SKU-1001", 100, "DC-EAST-01")
        assert result["created"]

