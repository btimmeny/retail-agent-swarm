# test_integration_ecosystem.py
"""
Integration tests for ecosystem endpoints and cross-cutting concerns.
Covers:
- /health endpoint status
- OpenAPI schema validity
- Structured logging (JSON parseable)
- RFC 7807 error responses
- API versioning headers
- Webhook callback firing

Assumes FastAPI app is exposed as `app` in app.py.
"""
import json
import re
import pytest
import httpx
from fastapi import status
from unittest.mock import patch, MagicMock

# Import the FastAPI app
from app import app

@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="module")
def async_client():
    """Provides an httpx.AsyncClient for the FastAPI app."""
    from fastapi.testclient import TestClient
    client = httpx.AsyncClient(app=app, base_url="http://testserver")
    yield client
    import asyncio
    asyncio.get_event_loop().run_until_complete(client.aclose())

@pytest.fixture(autouse=True)
def mock_openai(monkeypatch):
    """Prevents real OpenAI API calls during tests."""
    monkeypatch.setattr("openai.ChatCompletion.create", lambda *a, **kw: {"choices": [{"message": {"content": "mocked"}}]})
    monkeypatch.setattr("openai.Completion.create", lambda *a, **kw: {"choices": [{"text": "mocked"}]})
    yield

@pytest.fixture
def capture_structured_logs(monkeypatch):
    """Capture structured logs emitted to stdout for parsing tests."""
    logs = []
    def fake_emit(event_dict):
        logs.append(json.dumps(event_dict))
        return event_dict
    try:
        import structlog
        monkeypatch.setattr("structlog.stdlib.ProcessorFormatter", MagicMock())
        monkeypatch.setattr("structlog.processors.JSONRenderer", lambda *a, **kw: fake_emit)
    except ImportError:
        # Fallback: patch logging
        monkeypatch.setattr("logging.Logger._log", lambda *a, **kw: logs.append(str(a)))
    yield logs

@pytest.mark.anyio
async def test_health_endpoint(async_client):
    """Test that /health returns 200 and expected payload."""
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("ok", "healthy")

@pytest.mark.anyio
async def test_openapi_schema(async_client):
    """Test that the OpenAPI schema is valid and contains required info."""
    resp = await async_client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "openapi" in schema
    assert schema["openapi"].startswith("3.")
    assert "info" in schema
    assert "paths" in schema
    # Spot check a model description
    assert any("description" in f for m in schema.get("components", {}).get("schemas", {}).values() for f in m.get("properties", {}).values())

@pytest.mark.anyio
async def test_structured_logging_parseable(capture_structured_logs, async_client):
    """Test that structured logs are JSON-parseable and contain expected fields."""
    # Trigger an agent pipeline event (e.g., place an order)
    payload = {
        "customer_id": "CUST-2001",
        "store_id": "store-101",
        "items": [
            {"sku": "SKU-1001", "qty": 1}
        ]
    }
    await async_client.post("/orders", json=payload)
    # At least one log should be parseable JSON with expected keys
    found = False
    for entry in capture_structured_logs:
        try:
            log = json.loads(entry)
            if "event" in log and ("agent" in log or "tool" in log):
                found = True
                break
        except Exception:
            continue
    assert found, "No structured agent/tool log entry found or not parseable JSON"

@pytest.mark.anyio
async def test_rfc7807_error_response(async_client):
    """Test that error responses conform to RFC 7807 (problem+json)."""
    # Send a request with invalid input to trigger validation error
    payload = {
        "customer_id": "INVALID",
        "store_id": "store-101",
        "items": [
            {"sku": "SKU-1001", "qty": 1}
        ]
    }
    resp = await async_client.post("/orders", json=payload)
    assert resp.status_code in (400, 422)
    ct = resp.headers.get("content-type", "")
    assert "application/problem+json" in ct or "application/json" in ct
    data = resp.json()
    # RFC 7807 fields
    assert "type" in data
    assert "title" in data
    assert "detail" in data
    assert "status" in data

@pytest.mark.anyio
async def test_api_versioning_headers(async_client):
    """Test that API versioning headers are present in responses."""
    resp = await async_client.get("/health")
    # Accept both X-API-Version and API-Version
    version = resp.headers.get("X-API-Version") or resp.headers.get("API-Version")
    assert version is not None
    # Should look like '1.0' or '2024-04-01' etc.
    assert re.match(r"\d+\.\d+|\d{4}-\d{2}-\d{2}", version)

@pytest.mark.anyio
async def test_webhook_callback_fires(async_client):
    """Test that webhook callback is triggered on stock reservation event."""
    # Register a webhook for 'stock_reserved' event
    webhook_url = "http://testserver/_mock_webhook"
    # Patch httpx.post to simulate webhook delivery
    with patch("httpx.post") as mock_post:
        mock_post.return_value.status_code = 200
        payload = {
            "event": "stock_reserved",
            "url": webhook_url
        }
        resp = await async_client.post("/webhooks/register", json=payload)
        assert resp.status_code == 200
        # Now, reserve stock to trigger webhook
        reserve_payload = {
            "store_id": "store-101",
            "sku": "SKU-1001",
            "qty": 1
        }
        await async_client.post("/inventory/reserve", json=reserve_payload)
        # Webhook should be called
        assert mock_post.called
        args, kwargs = mock_post.call_args
        assert webhook_url in args[0]
        # Payload should contain event and stock info
        sent = kwargs.get("json") or {}
        assert sent.get("event") == "stock_reserved"
        assert sent.get("sku") == "SKU-1001"

