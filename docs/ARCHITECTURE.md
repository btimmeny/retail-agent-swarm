# Retail Agent Swarm — Architecture

**Version:** 1.0.0
**Last Updated:** 2026-02-23

---

## 1. System Overview

The Retail Agent Swarm is a Python application composed of three layers:

```
┌─────────────────────────────────────────────────────────┐
│                    API LAYER (FastAPI)                    │
│  Async endpoints, request validation, response shaping   │
├─────────────────────────────────────────────────────────┤
│                   AGENT LAYER (Swarm)                    │
│  9 specialized agents + orchestrator + thread pool       │
├─────────────────────────────────────────────────────────┤
│                   DATA LAYER (Simulated)                 │
│  In-memory stores for inventory, logistics, pharmacy...  │
└─────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
   OpenAI API                    Client (REST)
   (LLM calls)                  (Mobile/Web/CLI)
```

---

## 2. Component Map

```
retail-agent-swarm/
├── app.py                  # FastAPI application entry point
├── models.py               # Pydantic request/response models
├── agents/
│   ├── base.py             # Agent base class + OpenAI client
│   ├── orchestrator.py     # Pipeline coordinator + thread pool
│   ├── customer_agent.py   # Customer-facing chat with guardrails
│   ├── inventory_agent.py  # Store-level stock checks
│   ├── logistics_agent.py  # Inbound shipment tracking
│   ├── distribution_agent.py  # DC-level stock management
│   ├── provider_agent.py   # Supplier/PO management
│   ├── history_agent.py    # Customer profile & purchase history
│   ├── pharmacy_agent.py   # Prescriptions, interactions, alerts
│   └── clinic_agent.py     # Appointments, immunizations, wellness
├── data/
│   ├── store_inventory.py  # Store stock database
│   ├── logistics.py        # Shipment tracking database
│   ├── distribution_center.py  # DC inventory database
│   ├── provider.py         # Supplier & PO database
│   ├── customer_history.py # Customer profiles & order history
│   ├── pharmacy.py         # Prescription & interaction database
│   └── clinic.py           # Appointment & wellness database
├── docs/                   # Specification, architecture, design docs
├── smoke_test.py           # End-to-end API test script
└── requirements.txt
```

---

## 3. Agent Architecture

### 3.1 Agent Base Class

Every domain agent inherits a common pattern defined in `agents/base.py`:

```
┌─────────────────────────────────────────────┐
│                  Agent                        │
├─────────────────────────────────────────────┤
│  name: str                                   │
│  system_prompt: str                          │
│  tools: list[dict]        # OpenAI tool defs │
│  tool_handlers: dict      # fn_name → callable│
│  model: str               # e.g. "gpt-4.1"  │
├─────────────────────────────────────────────┤
│  run(message, context?) → dict               │
│    ├─ Builds message array (system + context)│
│    ├─ Calls OpenAI chat.completions.create() │
│    ├─ If tool_calls: execute locally, loop   │
│    └─ Returns {response, tool_calls, raw}    │
└─────────────────────────────────────────────┘
```

**Key design:** Each agent's tools map directly to functions in the `data/` layer. The LLM decides which tools to call and how to interpret the results. The agent base handles the tool-calling loop (up to 5 rounds) automatically.

### 3.2 Agent Communication

Agents do **not** communicate directly with each other. The Orchestrator mediates all inter-agent data flow:

```
                    Orchestrator
                   ┌─────┴─────┐
            ┌──────┤  context   ├──────┐
            │      └───────────┘      │
            ▼                          ▼
      Agent A                    Agent B
    (produces data)          (receives context)
```

**Context passing examples:**
- Inventory Agent produces out-of-stock SKU list → Logistics Agent receives it
- DC Agent produces availability report → Provider Agent receives it as context
- All agents produce reports → Synthesis LLM receives all of them

### 3.3 Customer Conversation Agent

The Customer Agent is architecturally distinct — it maintains **stateful conversation sessions** per customer (in-memory dict), does not use function-calling tools, and applies a post-processing guardrail check on every response.

```
┌──────────────────────────────────────────────┐
│           CustomerAgent                        │
├──────────────────────────────────────────────┤
│  conversations: dict[customer_id → messages]   │
├──────────────────────────────────────────────┤
│  start_conversation(customer_id, order_ctx)    │
│    └─ Injects system prompt + guardrails       │
│    └─ Injects order context as system message  │
│    └─ Generates initial greeting               │
│                                                │
│  send_message(customer_id, message)            │
│    └─ Appends to conversation history          │
│    └─ Calls LLM with full history              │
│    └─ Post-processes for guardrail violations   │
│    └─ Returns response                         │
└──────────────────────────────────────────────┘
```

---

## 4. Parallel Execution Architecture

### 4.1 Dependency Graph

```
    ┌──────────┐     ┌──────────┐
    │ History  │     │Inventory │     Phase 1: PARALLEL
    └────┬─────┘     └────┬─────┘     (no dependencies)
         │                │
         └───────┬────────┘
                 ▼
         ┌──────────────┐
         │  Logistics   │              Phase 2: SEQUENTIAL
         │ (conditional)│              (needs inventory out-of-stock list)
         └──────┬───────┘
                ▼
    ┌────┐  ┌────────┐  ┌────────┐  ┌──────┐
    │ DC │→ │Provider│  │Pharmacy│  │Clinic│   Phase 3: PARALLEL
    └──┬─┘  └───┬────┘  └───┬────┘  └──┬───┘  (DC first → Provider;
       │        │            │          │       Pharmacy & Clinic independent)
       └────────┴────────────┴──────────┘
                        │
                        ▼
               ┌──────────────┐
               │  Synthesis   │        Phase 4: SEQUENTIAL
               └──────────────┘        (needs all results)
```

### 4.2 Thread Pool Design

```python
ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-worker")
```

| Decision | Rationale |
|----------|-----------|
| **Threads, not processes** | OpenAI API calls are I/O-bound (network wait). Python's GIL doesn't block I/O. Threads are lighter weight and share memory. |
| **4 workers** | Phase 3 has up to 4 concurrent agents. More workers would be idle. |
| **Named threads** | `agent-worker-0` through `agent-worker-3` for debugging/observability. |
| **Not asyncio** | OpenAI's sync client is used by the Agent base class. Thread pool wraps sync calls cleanly without rewriting the agent layer. |

### 4.3 Execution Flow (Detailed)

```
Main Thread                    Worker Pool (4 threads)
    │
    ├─ submit(History)  ──────→  [worker-0] History.run()
    ├─ submit(Inventory) ─────→  [worker-1] Inventory.run()
    │
    ├─ collect(History)  ◄────── [worker-0] done ✓
    ├─ collect(Inventory) ◄───── [worker-1] done ✓
    │
    ├─ extract_out_of_stock()
    │
    ├─ run_sync(Logistics) ────  [main thread] Logistics.run()
    │                             done ✓
    │
    ├─ submit(DC)  ───────────→  [worker-0] DC.run()
    ├─ submit(Pharmacy) ──────→  [worker-1] Pharmacy.run()
    ├─ submit(Clinic) ────────→  [worker-2] Clinic.run()
    │
    ├─ collect(DC)  ◄──────────  [worker-0] done ✓
    │
    ├─ submit(Provider) ──────→  [worker-3] Provider.run(dc_context)
    │
    ├─ collect(Pharmacy) ◄─────  [worker-1] done ✓
    ├─ collect(Clinic) ◄───────  [worker-2] done ✓
    ├─ collect(Provider) ◄─────  [worker-3] done ✓
    │
    ├─ synthesize()  ──────────  [main thread] LLM call
    │                             done ✓
    │
    └─ return result
```

### 4.4 Timing Instrumentation

Every agent call is timed using `time.monotonic()`. The response includes:

```json
{
    "execution_timing": {
        "total_duration_sec": 12.45,
        "phases": [
            {"phase": 1, "agents": ["CustomerHistoryAgent", "StoreInventoryAgent"], "mode": "parallel", "duration_sec": 3.21},
            {"phase": 2, "agents": ["LogisticsAgent"], "mode": "sequential (conditional)", "duration_sec": 2.10},
            {"phase": 3, "agents": ["DistributionCenterAgent", "ProviderAgent", "PharmacyAgent", "ClinicAgent"], "mode": "parallel", "duration_sec": 4.55},
            {"phase": 4, "agents": ["SynthesisLLM"], "mode": "sequential", "duration_sec": 2.59}
        ]
    }
}
```

Each pipeline log entry also records the thread name, enabling verification that parallel agents ran on separate threads.

---

## 5. API Layer Architecture

### 5.1 FastAPI + Async

```
Client Request
    │
    ▼
FastAPI (async event loop)
    │
    ├─ async def place_order()
    │      │
    │      └─ run_in_executor(None, orchestrator.process_order)
    │              │
    │              └─ Orchestrator runs on default thread pool
    │                  └─ Spawns agent workers on its own ThreadPoolExecutor
    │
    └─ Response returned to client
```

**Why `run_in_executor`?** The orchestrator and agents use the synchronous OpenAI client. Rather than blocking FastAPI's event loop, we offload the entire pipeline to a thread. FastAPI remains responsive to other requests (health checks, order lookups) while a pipeline runs.

### 5.2 State Management

| Store | Type | Scope | Contents |
|-------|------|-------|----------|
| `order_results` | `dict[str, dict]` | App lifetime | Processed order results by order_id |
| `orchestrator` | `Orchestrator` | Singleton | Agent instances + thread pool |
| `customer_agent` | `CustomerAgent` | Singleton | Conversation sessions |
| `data/*` | Module globals | App lifetime | Simulated databases (mutable) |

**Note:** All state is in-memory. A production implementation would use Redis or PostgreSQL.

---

## 6. External Dependencies

| Dependency | Purpose | Layer |
|-----------|---------|-------|
| **OpenAI API** | LLM inference for all agents | Agent |
| **FastAPI** | HTTP framework | API |
| **uvicorn** | ASGI server | API |
| **Pydantic** | Request/response validation | API |
| **python-dotenv** | Environment variable loading | Config |

### 6.1 OpenAI Usage Pattern

Each agent call = 1+ OpenAI `chat.completions.create()` calls:
- 1 call if the LLM responds directly
- 2+ calls if the LLM uses tools (tool call → execute → feed result → LLM responds)
- Max 5 rounds per agent invocation

The synthesis step uses `response_format={"type": "json_object"}` for structured output.

---

## 7. Security Considerations

| Concern | Mitigation |
|---------|------------|
| API key exposure | `.env` file, excluded from git via `.gitignore` |
| Prompt injection via customer chat | System prompt with strict guardrails, post-processing keyword check |
| Data leakage in chat | Guardrail G-05 prevents sharing raw records; system context marked as internal |
| Unauthorized prescription access | Guardrail G-02 requires customer authentication before sharing Rx info |
| Medical liability | Guardrails G-01/G-03 prevent medical advice; always redirect to pharmacist |

---

## 8. Scalability Path

This architecture is designed for demonstration. A production path would involve:

| Current | Production |
|---------|------------|
| In-memory data stores | PostgreSQL + Redis cache |
| In-memory order results | Event-sourced with message bus (Kafka/Redis Streams) |
| Single-process thread pool | Distributed agent workers (Celery/Ray) |
| Sync OpenAI client | Async OpenAI client with native asyncio |
| In-memory conversation state | Redis-backed session store |
| Single uvicorn process | Multi-worker deployment behind load balancer |
