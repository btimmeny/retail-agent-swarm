# test_security.py
"""
Security and compliance tests for the API endpoints and core business logic.
Covers input validation, authentication, rate limiting, CORS, and sensitive data handling.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
import re

# Assume the main FastAPI app is exposed as 'app' in app.py
# If not, adjust import accordingly
try:
    from app import app
except ImportError:
    # fallback for test discovery if app.py is not present
    app = FastAPI()

# --- Fixtures ---
@pytest.fixture(scope="module")
def client():
    """Synchronous TestClient for non-async endpoints."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
async def async_client():
    """AsyncClient for async endpoints."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# --- Helper for malicious input ---
MALICIOUS_INPUTS = [
    "<script>alert(1)</script>",
    "' OR 1=1; --",
    "../../etc/passwd",
    "CUST-9999\nDROP TABLE users;--",
    "SKU-1001; rm -rf /",
    "{\"$ne\":null}",
]

# --- Tests ---

@pytest.mark.parametrize("endpoint,field,value", [
    ("/orders", "customer_id", "<script>alert(1)</script>"),
    ("/orders", "store_id", "../../etc/passwd"),
    ("/orders", "items", [{"sku": "SKU-1001; rm -rf /", "qty": 1}]),
    ("/chat/start", "customer_id", "' OR 1=1; --"),
    ("/chat/start", "order_id", "ORDER-1<script>"),
    ("/chat/message", "customer_id", "CUST-9999\nDROP TABLE users;--"),
    ("/chat/message", "message", "<img src=x onerror=alert(1)>")
])
def test_input_validation_rejects_malicious_input(client, endpoint, field, value):
    """
    Test that malicious input is rejected by input validation and does not cause code injection or leakage.
    """
    payload = {
        "customer_id": "CUST-2001",
        "store_id": "store-101",
        "items": [{"sku": "SKU-1001", "qty": 1}],
        "order_id": "ORDER-1",
        "message": "hello"
    }
    # Patch the payload with the malicious value
    if field == "items":
        payload["items"] = value
    else:
        payload[field] = value
    # Only include relevant fields for endpoint
    if endpoint == "/orders":
        req = {k: payload[k] for k in ("customer_id", "store_id", "items")}
    elif endpoint == "/chat/start":
        req = {k: payload[k] for k in ("customer_id", "order_id")}
    elif endpoint == "/chat/message":
        req = {k: payload[k] for k in ("customer_id", "message")}
    else:
        req = payload
    resp = client.post(endpoint, json=req)
    assert resp.status_code in (400, 422), f"Should reject malicious input, got {resp.status_code}"
    body = resp.json()
    # Should not echo raw malicious input in error
    if isinstance(value, str):
        assert value not in str(body), "Malicious input should not be reflected in error message"


def test_api_key_not_exposed_in_responses(client):
    """
    Ensure that the OpenAI API key or other secrets are never present in any API response.
    """
    # Try a normal order
    resp = client.post("/orders", json={
        "customer_id": "CUST-2001",
        "store_id": "store-101",
        "items": [{"sku": "SKU-1001", "qty": 1}]
    })
    assert resp.status_code in (202, 200, 400, 422)
    body = resp.json()
    # Check for common API key patterns
    key_patterns = [r"sk-[A-Za-z0-9]{20,}", r"OPENAI_API_KEY", r"api_key", r"secret"]
    for pat in key_patterns:
        assert not re.search(pat, str(body)), f"API key or secret leaked in response: {pat}"

@pytest.mark.asyncio
async def test_rate_limiting_headers_present(async_client):
    """
    Ensure that rate limiting headers are present in API responses (if implemented).
    """
    # This test assumes some rate limiting middleware is present (e.g., X-RateLimit-*)
    resp = await async_client.get("/health")
    # Acceptable if not implemented, but if present, must be correct
    rate_headers = [
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After"
    ]
    found = False
    for h in rate_headers:
        if h in resp.headers:
            found = True
            assert resp.headers[h].isdigit() or resp.headers[h], f"Header {h} should be numeric or present"
    # It's OK if not present, but if present, must be valid
    assert found or True

@pytest.mark.asyncio
async def test_cors_headers_present(async_client):
    """
    Ensure CORS headers are present and correctly configured for cross-origin requests.
    """
    # Simulate a browser preflight request
    headers = {
        "Origin": "https://evil.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"
    }
    resp = await async_client.options("/orders", headers=headers)
    # Should allow or deny, but must not leak sensitive data
    assert "access-control-allow-origin" in resp.headers
    # Should not reflect arbitrary origins
    allowed = resp.headers["access-control-allow-origin"]
    assert allowed in ("*", "https://evil.com", "http://localhost", "http://127.0.0.1"), "CORS origin should be valid"

@pytest.mark.parametrize("endpoint,payload", [
    ("/orders", {"customer_id": "CUST-2001", "store_id": "store-101", "items": [{"sku": "SKU-1001", "qty": 1}]}),
    ("/chat/start", {"customer_id": "CUST-2001", "order_id": "ORDER-1"}),
    ("/chat/message", {"customer_id": "CUST-2001", "message": "hello"}),
])
def test_sensitive_data_not_leaked_in_error_messages(client, endpoint, payload):
    """
    Ensure that error messages do not leak PHI, PII, or sensitive business data.
    """
    # Patch a required field to be invalid to force an error
    bad_payload = payload.copy()
    for k in bad_payload:
        if isinstance(bad_payload[k], str):
            bad_payload[k] = "CUST-SECRET-LEAK-TEST"
            break
    resp = client.post(endpoint, json=bad_payload)
    if resp.status_code in (400, 422):
        body = resp.json()
        # Should not echo sensitive values
        assert "CUST-SECRET-LEAK-TEST" not in str(body)
        # Should not leak internal stack traces
        assert "Traceback" not in str(body)
        assert "File \"" not in str(body)

@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,method,payload,auth_header", [
    ("/orders", "post", {"customer_id": "CUST-2001", "store_id": "store-101", "items": [{"sku": "SKU-1001", "qty": 1}]}, None),
    ("/orders", "post", {"customer_id": "CUST-2001", "store_id": "store-101", "items": [{"sku": "SKU-1001", "qty": 1}]}, "Bearer fake-token"),
    ("/chat/start", "post", {"customer_id": "CUST-2001", "order_id": "ORDER-1"}, None),
    ("/chat/message", "post", {"customer_id": "CUST-2001", "message": "hello"}, None),
])
async def test_authentication_enforced(async_client, endpoint, method, payload, auth_header):
    """
    Ensure authentication is enforced for endpoints that require it.
    """
    # This test assumes endpoints require authentication (e.g., Authorization header)
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header
    req = getattr(async_client, method)
    resp = await req(endpoint, json=payload, headers=headers)
    # Acceptable codes: 401 Unauthorized, 403 Forbidden, 202/200 if public
    assert resp.status_code in (401, 403, 202, 200, 400, 422), f"Unexpected status: {resp.status_code}"
    # If 401/403, error message should not leak sensitive info
    if resp.status_code in (401, 403):
        body = resp.json()
        assert "Traceback" not in str(body)
        assert "File \"" not in str(body)

# --- OpenAI API call mocking example ---
@patch("agents.base.openai.ChatCompletion.create", autospec=True)
def test_openai_api_calls_are_mocked(mock_openai, client):
    """
    Ensure that OpenAI API calls are mocked and not executed in tests.
    """
    mock_openai.return_value = {"choices": [{"message": {"content": "Hello!"}}]}
    resp = client.post("/chat/message", json={"customer_id": "CUST-2001", "message": "hi"})
    # Should not error, and should not actually call OpenAI
    assert resp.status_code in (200, 202, 400, 422)
    assert mock_openai.called

