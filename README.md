# Retail Agent Swarm

A multi-agent system that simulates a full retail pharmacy order pipeline — from customer order placement through inventory, logistics, distribution, supplier management, pharmacy review, and clinic integration.

## Documentation

| Document | Description |
|----------|-------------|
| [Specification](docs/SPEC.md) | Requirements, data models, API contracts, acceptance criteria |
| [Architecture](docs/ARCHITECTURE.md) | System components, parallel execution, thread pool design |
| [Design](docs/DESIGN.md) | Design decisions, agent patterns, guardrail rationale, data flow |
| **Wiki Site** | Run `mkdocs serve` to browse docs locally at http://localhost:8001 |

## Architecture

```
Customer (REST API)
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                               │
│          ThreadPoolExecutor (4 workers)                       │
│                                                               │
│  Phase 1 ═══ PARALLEL ════════════════════════════════════    │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │ Customer History │    │ Store Inventory  │   2 agents       │
│  │     Agent        │    │     Agent        │   in parallel    │
│  └────────┬────────┘    └────────┬────────┘                   │
│           └──────────┬───────────┘                             │
│                      ▼                                        │
│  Phase 2 ═══ SEQUENTIAL (conditional) ════════════════════    │
│  ┌─────────────────┐                                          │
│  │   Logistics     │  ← only if items are out of stock        │
│  │     Agent       │                                          │
│  └────────┬────────┘                                          │
│           ▼                                                   │
│  Phase 3 ═══ PARALLEL ════════════════════════════════════    │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │    DC     │ │ Provider │ │ Pharmacy │ │  Clinic  │ 4 agents│
│  │   Agent   │→│  Agent   │ │  Agent   │ │  Agent   │ parallel│
│  └───────────┘ └──────────┘ └──────────┘ └──────────┘        │
│           └──────────┬───────────────────────┘                │
│                      ▼                                        │
│  Phase 4 ═══ SEQUENTIAL ══════════════════════════════════    │
│  ┌─────────────────────────────────┐                          │
│  │   Synthesis (LLM call)          │  → final order decision  │
│  └────────────────┬────────────────┘                          │
│                   ▼                                           │
│  ┌─────────────────────────────────┐                          │
│  │  Customer Conversation Agent    │  → guardrailed chat      │
│  └─────────────────────────────────┘                          │
└──────────────────────────────────────────────────────────────┘
```

## Agents

| Agent | Domain | Responsibilities |
|-------|--------|------------------|
| **Customer History** | CRM | Profile lookup, purchase history, loyalty tier, frequently bought items |
| **Store Inventory** | Store Ops | Check local stock, aisle locations, reserve quantities |
| **Logistics** | Supply Chain | Track inbound shipments, ETAs, carriers |
| **Distribution Center** | Warehousing | DC-level stock, allocation for store replenishment |
| **Provider/Supplier** | Procurement | Supplier relationships, lead times, purchase orders, restocking |
| **Pharmacy** | Pharmacy Dept | Prescriptions, refills, drug interactions, pharmacist alerts |
| **Clinic** | In-store Clinic | Appointments, immunizations, wellness recommendations |
| **Customer Conversation** | Customer Service | Guardrailed chat with safety, privacy, and escalation rules |
| **Orchestrator** | Coordination | Runs agents in **parallel phases**, synthesizes final order decision |

## Parallel Execution

The orchestrator uses `concurrent.futures.ThreadPoolExecutor` to run independent agents simultaneously. OpenAI API calls are I/O-bound, making threads ideal.

| Phase | Agents | Mode | Why |
|-------|--------|------|-----|
| **1** | Customer History + Store Inventory | **Parallel** | Independent — one needs `customer_id`, the other needs `store_id` + SKUs |
| **2** | Logistics | Sequential | Depends on Phase 1 — needs the out-of-stock SKU list from Inventory. Skipped entirely if everything is in stock |
| **3** | DC + Provider + Pharmacy + Clinic | **Parallel** | Independent data sources. DC resolves first so Provider gets DC context, but Pharmacy and Clinic run simultaneously |
| **4** | Synthesis | Sequential | Needs all previous results to produce the final order decision |

**Result:** 7 sequential LLM calls → **4 phases** (with up to 4 concurrent calls per phase). Each agent call and phase is timed — the `execution_timing` field in the API response shows exact durations and which thread each agent ran on.

## Guardrails (Customer Agent)

1. **No medical advice** — always refers to pharmacist
2. **Drug interaction escalation** — mandatory pharmacist consultation
3. **Allergy safety** — flags known allergies when relevant
4. **Data privacy** — never shares raw customer records
5. **Price accuracy** — only quotes confirmed prices
6. **Stock honesty** — clear about availability with ETAs
7. **Scope boundaries** — redirects out-of-scope questions
8. **Escalation** — offers human handoff when appropriate

## Setup

```bash
cd retail-agent-swarm

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set your OpenAI API key
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Run

```bash
# Start the API server
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# In another terminal, run the smoke test
python smoke_test.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/orders` | Place an order (triggers full agent pipeline) |
| `GET` | `/orders` | List all processed orders |
| `GET` | `/orders/{id}` | Get full order details with pipeline log |
| `POST` | `/chat/start` | Start a customer conversation about an order |
| `POST` | `/chat/message` | Send a follow-up chat message |
| `GET` | `/chat/{customer_id}/history` | Get conversation history |

## Example Order Request

```json
{
    "customer_id": "CUST-2001",
    "store_id": "store-101",
    "items": [
        {"sku": "SKU-1001", "qty": 1},
        {"sku": "SKU-1002", "qty": 2},
        {"sku": "SKU-1005", "qty": 1}
    ]
}
```

## Simulated Data

The system includes rich mock data for testing:

- **3 customers** with varying loyalty tiers, allergies, and histories
- **7 products** across OTC medicine, vitamins, personal care, health devices, and nutrition
- **3 inbound shipments** with different carriers and ETAs
- **2 distribution centers** (East and West) with different stock levels
- **4 suppliers** with varying lead times and reliability
- **Active prescriptions** with refill schedules and drug interaction checks
- **Clinic appointments**, immunization records, and wellness recommendations

## Test Scenarios

The smoke test exercises a particularly interesting scenario:

- **CUST-2001 (Maria Johnson)** — Gold loyalty member with penicillin allergy
  - Orders **Ibuprofen** (SKU-1001) → triggers drug interaction warning with her Lisinopril prescription
  - Orders **Vitamin D3** (SKU-1002) → out of stock at store, but shipment arriving in 2 days
  - Orders **Allergy Relief** (SKU-1005) → in stock
  - Has upcoming flu shot and BP check appointments
  - Clinic recommended Vitamin D supplementation
