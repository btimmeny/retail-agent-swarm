# test_compliance.py
"""
Regulatory Compliance Tests for API and Data Pipeline
Covers: PHI/PII exposure, audit logging, drug interaction warnings, prescription auth, guardrails, and data retention.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import re
import asyncio

import sys
import os

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Assume the FastAPI app is exposed as 'app' in app.py
# If not, adjust the import accordingly
try:
    from app import app
except ImportError:
    app = FastAPI()  # Dummy fallback for linting

# --- Fixtures ---
@pytest.fixture(scope="module")
def client():
    """Fixture for FastAPI test client."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(autouse=True)
def no_real_openai(monkeypatch):
    """Prevent real OpenAI API calls."""
    monkeypatch.setattr("openai.ChatCompletion.create", MagicMock(return_value={}))
    monkeypatch.setattr("openai.Completion.create", MagicMock(return_value={}))
    monkeypatch.setattr("openai.api_key", "sk-test")

# --- Helper functions ---
def contains_phi(data):
    """Detects likely PHI/PII fields in dict or str."""
    phi_patterns = [
        r"[0-9]{3}-[0-9]{2}-[0-9]{4}",  # SSN
        r"[A-Za-z]+@[A-Za-z0-9.]+",      # Email
        r"\b(?:CUST|PAT|MRN)-\d+\b",   # Customer/Patient IDs
        r"\b\d{10}\b",                # Phone
        r"\b\d{5}(?:-\d{4})?\b",     # Zip
        r"\b(?:John|Maria|Johnson|Smith)\b",  # Example names
    ]
    if isinstance(data, dict):
        data = str(data)
    for pat in phi_patterns:
        if re.search(pat, data):
            return True
    return False

def get_audit_log_entries():
    """Stub: Retrieve audit log entries (simulate log file/db)."""
    # In real test, would check log file/db. Here, simulate with patch.
    return getattr(get_audit_log_entries, "_entries", [])

def set_audit_log_entries(entries):
    setattr(get_audit_log_entries, "_entries", entries)

# --- Tests ---

def test_no_phi_in_api_responses(client):
    """
    PHI/PII is not exposed in API responses (e.g., /orders, /chat, /orders/{id}).
    """
    # Place an order (should not leak PHI in response)
    payload = {
        "customer_id": "CUST-2001",
        "store_id": "store-101",
        "items": [
            {"sku": "SKU-1001", "qty": 1},
            {"sku": "SKU-1002", "qty": 2},
        ],
    }
    resp = client.post("/orders", json=payload)
    assert resp.status_code in (200, 202)
    data = resp.json()
    assert not contains_phi(data), f"PHI/PII found in /orders response: {data}"

    # Get order details
    order_id = data.get("order_id")
    resp2 = client.get(f"/orders/{order_id}")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert not contains_phi(data2), f"PHI/PII found in /orders/{{id}} response: {data2}"

    # Chat API should not leak PHI
    chat_payload = {"customer_id": "CUST-2001", "order_id": order_id}
    chat_resp = client.post("/chat/start", json=chat_payload)
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert not contains_phi(chat_data), f"PHI/PII found in /chat/start response: {chat_data}"

def test_audit_logging_on_sensitive_access(monkeypatch, client):
    """
    Audit logging captures access events for sensitive endpoints (clinic, pharmacy, history).
    """
    # Patch audit_log to record calls
    audit_calls = []
    def fake_audit_log(*args, **kwargs):
        audit_calls.append((args, kwargs))
    monkeypatch.setattr("data.clinic.audit_log", fake_audit_log, raising=False)
    monkeypatch.setattr("data.customer_history.audit_log", fake_audit_log, raising=False)
    monkeypatch.setattr("run_logger.audit_log", fake_audit_log, raising=False)

    # Access clinic data (triggers audit log)
    payload = {"customer_id": "CUST-2001", "order_id": "ORD-1234"}
    client.post("/chat/start", json=payload)
    # Access order history (triggers audit log)
    client.get("/orders/ORD-1234")
    assert audit_calls, "Audit logging not called on sensitive data access"
    # Check that at least one call contains customer_id and function name
    found = any("CUST-2001" in str(args) for args, _ in audit_calls)
    assert found, f"Audit log missing customer_id: {audit_calls}"


def test_drug_interaction_warnings_always_surfaced(client):
    """
    Drug interaction warnings are always surfaced in order and chat responses.
    """
    payload = {
        "customer_id": "CUST-2001",
        "store_id": "store-101",
        "items": [
            {"sku": "SKU-1001", "qty": 1},  # Ibuprofen (interacts with Lisinopril)
        ],
    }
    resp = client.post("/orders", json=payload)
    assert resp.status_code in (200, 202)
    data = resp.json()
    # Should contain pharmacy_flags or interaction warning
    flags = data.get("pharmacy_flags") or data.get("customer_message", "")
    assert flags, "No drug interaction warning surfaced in order response"
    assert "interact" in str(flags).lower() or "warning" in str(flags).lower(), f"No interaction warning: {flags}"

    # Also test chat follow-up
    order_id = data.get("order_id")
    chat_payload = {
        "customer_id": "CUST-2001",
        "message": "Is there any interaction with my meds?",
    }
    resp2 = client.post("/chat/message", json=chat_payload)
    assert resp2.status_code == 200
    msg = resp2.json().get("response", "")
    assert "interact" in msg.lower() or "warning" in msg.lower(), f"No interaction warning in chat: {msg}"


def test_prescription_data_requires_auth(monkeypatch, client):
    """
    Prescription data endpoints require authentication and proper authorization.
    """
    # Patch auth check to simulate unauthenticated user
    monkeypatch.setattr("agents.pharmacy_agent.is_authenticated", lambda ctx: False, raising=False)
    monkeypatch.setattr("agents.pharmacy_agent.is_authorized", lambda ctx: False, raising=False)
    # Try to access prescription data
    payload = {
        "customer_id": "CUST-2001",
        "message": "Show my prescriptions",
    }
    resp = client.post("/chat/message", json=payload)
    assert resp.status_code == 403 or resp.status_code == 401 or "unauthorized" in resp.text.lower(), (
        f"Prescription data returned without auth: {resp.text}")


def test_guardrails_prevent_medical_advice(client):
    """
    Guardrails prevent the system from giving direct medical advice (e.g., diagnosis, prescription changes).
    """
    # Ask for a diagnosis
    payload = {
        "customer_id": "CUST-2001",
        "message": "Can you diagnose my headache? Should I change my medication?",
    }
    resp = client.post("/chat/message", json=payload)
    assert resp.status_code == 200
    msg = resp.json().get("response", "")
    assert any(
        phrase in msg.lower() for phrase in ["cannot provide medical advice", "consult your doctor", "not authorized"]
    ), f"Medical advice not blocked: {msg}"


def test_data_retention_policy_enforced(monkeypatch):
    """
    Data retention: logs older than 6 years are deleted (cleanup_old_logs called).
    """
    # Patch cleanup_old_logs and save_run
    called = {}
    def fake_cleanup_old_logs():
        called["cleanup"] = True
    monkeypatch.setattr("run_logger.cleanup_old_logs", fake_cleanup_old_logs, raising=False)
    # Simulate a run save
    try:
        from run_logger import save_run
        monkeypatch.setattr("run_logger.save_run", lambda *a, **kw: True)
        save_run("dummy_run")
    except Exception:
        pass  # If not present, skip
    assert called.get("cleanup"), "cleanup_old_logs not called during save_run (data retention policy)"

