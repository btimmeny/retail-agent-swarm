"""
Smoke test — exercises the full pipeline end-to-end via the REST API.

Usage:
    1. Start the server:  uvicorn app:app --port 8000
    2. Run this script:   python smoke_test.py
"""

import json
import requests

BASE = "http://localhost:8000"


def banner(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    # ── Health check ──────────────────────────────────────────
    banner("Health Check")
    r = requests.get(f"{BASE}/health", timeout=5)
    print(f"GET /health → {r.status_code}: {r.json()}")
    assert r.status_code == 200

    # ── Place an order (Maria Johnson — has prescriptions, allergies, clinic appts) ──
    banner("Place Order — Maria Johnson (CUST-2001)")
    order_payload = {
        "customer_id": "CUST-2001",
        "store_id": "store-101",
        "items": [
            {"sku": "SKU-1001", "qty": 1},   # Ibuprofen — interacts with Lisinopril!
            {"sku": "SKU-1002", "qty": 2},   # Vitamin D3 — out of stock at store
            {"sku": "SKU-1005", "qty": 1},   # Allergy Relief — in stock
        ],
    }
    r = requests.post(f"{BASE}/orders", json=order_payload, timeout=120)
    print(f"POST /orders → {r.status_code}")
    order_resp = r.json()
    print(f"\nOrder ID: {order_resp['order_id']}")
    print(f"Can fulfill: {order_resp.get('can_fulfill')}")
    print(f"\nCustomer message:\n  {order_resp.get('customer_message', '')}")
    if order_resp.get("pharmacy_flags"):
        print(f"\nPharmacy flags: {order_resp['pharmacy_flags']}")
    if order_resp.get("clinic_reminders"):
        print(f"Clinic reminders: {order_resp['clinic_reminders']}")

    # Show parallel execution timing
    timing = order_resp.get("execution_timing", {})
    if timing:
        print(f"\n--- Execution Timing ---")
        print(f"Total pipeline: {timing.get('total_duration_sec', '?')}s")
        for phase in timing.get("phases", []):
            agents = ", ".join(phase.get("agents", []))
            skipped = " (SKIPPED)" if phase.get("skipped") else ""
            print(f"  Phase {phase['phase']} [{phase['mode']}] {phase['duration_sec']}s{skipped}")
            if agents:
                print(f"    Agents: {agents}")

    assert r.status_code == 202
    order_id = order_resp["order_id"]

    # ── Get full order details ────────────────────────────────
    banner("Get Full Order Details")
    r = requests.get(f"{BASE}/orders/{order_id}", timeout=10)
    print(f"GET /orders/{order_id} → {r.status_code}")
    full_order = r.json()
    # Print pipeline log with per-agent timing and thread info
    print(f"\nPipeline steps: {len(full_order.get('pipeline_log', []))}")
    for step in full_order.get("pipeline_log", []):
        duration = step.get('duration_sec', '?')
        thread = step.get('thread', '?')
        tools = step.get('tools_used', [])
        print(f"  → {step['agent']:30s} {duration:>5}s  thread={thread:<20s} tools={tools}")

    print("\nFinal Decision:")
    print(json.dumps(full_order.get("final_decision", {}), indent=2, default=str))

    # ── Start a customer chat ─────────────────────────────────
    banner("Start Customer Chat")
    r = requests.post(
        f"{BASE}/chat/start",
        json={"customer_id": "CUST-2001", "order_id": order_id},
        timeout=60,
    )
    print(f"POST /chat/start → {r.status_code}")
    chat_resp = r.json()
    print(f"\nGreeting:\n{chat_resp.get('greeting', '')}")

    # ── Send a follow-up message ──────────────────────────────
    banner("Customer Follow-up Question")
    r = requests.post(
        f"{BASE}/chat/message",
        json={
            "customer_id": "CUST-2001",
            "message": "When will the Vitamin D3 be back in stock? Also, is there anything "
                       "I should know about taking ibuprofen with my current medications?",
        },
        timeout=60,
    )
    print(f"POST /chat/message → {r.status_code}")
    print(f"\nResponse:\n{r.json().get('response', '')}")

    # ── Get chat history ──────────────────────────────────────
    banner("Chat History")
    r = requests.get(f"{BASE}/chat/CUST-2001/history", timeout=10)
    history = r.json()
    print(f"Messages in conversation: {len(history.get('messages', []))}")

    banner("Smoke Test Complete ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
