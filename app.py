"""
FastAPI application — REST API for the Retail Agent Swarm.

Endpoints:
  POST /orders          — Place an order (triggers the full agent pipeline)
  GET  /orders/{id}     — Get a processed order result
  POST /chat/start      — Start a customer conversation about an order
  POST /chat/message    — Send a follow-up message in an existing conversation
  GET  /chat/{cust}/history — Get conversation history
  GET  /health          — Health check
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from models import OrderRequest, ChatMessage, ChatStartRequest
from agents.orchestrator import Orchestrator
from agents.customer_agent import CustomerAgent

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

# ── In-memory stores (would be a database in production) ──────────────
order_results: dict[str, dict] = {}
orchestrator: Orchestrator | None = None
customer_agent: CustomerAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator, customer_agent
    orchestrator = Orchestrator()
    customer_agent = CustomerAgent()
    yield


app = FastAPI(
    title="Retail Agent Swarm",
    description="Multi-agent retail order processing with pharmacy and clinic integration",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Health ────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "retail-agent-swarm"}


# ── Orders ────────────────────────────────────────────────────────────

@app.post("/orders", status_code=202)
async def place_order(req: OrderRequest):
    """
    Place an order. This triggers the full agent swarm pipeline:

    Phase 1 (parallel):  Customer History + Store Inventory
    Phase 2 (sequential): Logistics (if items out of stock)
    Phase 3 (parallel):  Distribution Center + Provider + Pharmacy + Clinic
    Phase 4 (sequential): Synthesis of all agent reports
    """
    items = [item.model_dump() for item in req.items]
    # Run the blocking orchestrator in a thread so we don't block the event loop
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: orchestrator.process_order(
            customer_id=req.customer_id,
            store_id=req.store_id,
            items=items,
        ),
    )
    order_id = result["order_id"]
    order_results[order_id] = result

    return {
        "order_id": order_id,
        "status": "processed",
        "can_fulfill": result["final_decision"].get("can_fulfill"),
        "customer_message": result["final_decision"].get("customer_message"),
        "pharmacy_flags": result["final_decision"].get("pharmacy_flags", []),
        "clinic_reminders": result["final_decision"].get("clinic_reminders", []),
        "execution_timing": result.get("execution_timing"),
    }


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    """Get full order details including the complete pipeline log."""
    result = order_results.get(order_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return result


@app.get("/orders")
def list_orders():
    """List all processed orders (summary view)."""
    return [
        {
            "order_id": oid,
            "customer_id": r["customer_id"],
            "store_id": r["store_id"],
            "can_fulfill": r["final_decision"].get("can_fulfill"),
            "timestamp": r["timestamp"],
        }
        for oid, r in order_results.items()
    ]


# ── Chat ──────────────────────────────────────────────────────────────

@app.post("/chat/start")
async def start_chat(req: ChatStartRequest):
    """Start a customer conversation about a specific order."""
    order = order_results.get(req.order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {req.order_id} not found")

    loop = asyncio.get_running_loop()
    greeting = await loop.run_in_executor(
        None,
        lambda: customer_agent.start_conversation(
            customer_id=req.customer_id,
            order_context=order["final_decision"],
        ),
    )
    return {
        "customer_id": req.customer_id,
        "order_id": req.order_id,
        "greeting": greeting,
    }


@app.post("/chat/message")
async def send_chat_message(req: ChatMessage):
    """Send a follow-up message in an existing customer conversation."""
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: customer_agent.send_message(
            customer_id=req.customer_id,
            message=req.message,
        ),
    )
    if response.startswith("Error:"):
        raise HTTPException(status_code=400, detail=response)
    return {
        "customer_id": req.customer_id,
        "response": response,
    }


@app.get("/chat/{customer_id}/history")
def get_chat_history(customer_id: str):
    """Get the conversation history for a customer."""
    history = customer_agent.get_conversation_history(customer_id)
    return {"customer_id": customer_id, "messages": history}
