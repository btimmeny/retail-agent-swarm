"""Shared pytest fixtures for retail-agent-swarm tests."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the repo root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Environment ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Ensure OPENAI_API_KEY is set for all tests (never calls the real API)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-for-testing-only")


# ── Mock OpenAI Client ───────────────────────────────────────────────

@pytest.fixture
def mock_openai_client():
    """Return a mocked OpenAI client that returns a canned chat response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"response": "test response"}'
    mock_response.choices[0].message.tool_calls = None
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# ── Sample Data ──────────────────────────────────────────────────────

@pytest.fixture
def sample_order_items():
    """Sample order items for testing."""
    return [
        {"sku": "ASPIRIN-100", "qty": 2},
        {"sku": "BANDAGE-LG", "qty": 1},
    ]


@pytest.fixture
def sample_order_request(sample_order_items):
    """Sample order request dict."""
    return {
        "customer_id": "CUST-001",
        "store_id": "STORE-ATL-01",
        "items": sample_order_items,
    }


@pytest.fixture
def sample_inventory():
    """Sample inventory data for testing."""
    return {
        "ASPIRIN-100": {"name": "Aspirin 100mg", "qty_available": 50, "price": 9.99},
        "BANDAGE-LG": {"name": "Large Bandage", "qty_available": 25, "price": 4.99},
        "INSULIN-PEN": {"name": "Insulin Pen", "qty_available": 0, "price": 89.99},
    }


@pytest.fixture
def sample_customer_history():
    """Sample customer history for testing."""
    return {
        "customer_id": "CUST-001",
        "name": "Jane Doe",
        "orders": [
            {"order_id": "ORD-100", "date": "2026-01-15", "total": 29.97},
        ],
        "allergies": ["penicillin"],
        "prescriptions": ["metformin"],
    }


@pytest.fixture
def sample_final_decision():
    """Sample orchestrator final decision for testing."""
    return {
        "can_fulfill": True,
        "customer_message": "Your order has been processed successfully.",
        "pharmacy_flags": [],
        "clinic_reminders": ["Annual checkup due in 30 days"],
    }


# ── FastAPI Test Client ──────────────────────────────────────────────

@pytest.fixture
def test_client(mock_openai_client):
    """FastAPI TestClient with mocked OpenAI."""
    with patch("agents.base.get_client", return_value=mock_openai_client):
        from fastapi.testclient import TestClient
        from app import app
        with TestClient(app) as client:
            yield client
