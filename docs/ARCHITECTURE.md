# ARCHITECTURE.md

## System Overview

This repository implements an **AI-powered agent orchestration platform** for a retail pharmacy chain. It simulates a multi-agent system where each domain agent (Inventory, Logistics, Pharmacy, Clinic, Distribution, Provider, Customer History) is responsible for a specific business capability. Agents are coordinated in a pipeline to fulfill customer orders, answer questions, and provide personalized recommendations, leveraging both LLMs (OpenAI) and structured data sources.

The system exposes a REST API (via FastAPI, not shown here) for order placement, chat, and status queries. Orders and customer inquiries are processed by orchestrating multiple agents, each of which may call domain-specific tools (functions) backed by in-memory data modules.

---

## Layered Architecture Diagram

```text
+-------------------------------------------------------------+
|                         API Layer                           |
|     (FastAPI REST Endpoints: /orders, /chat, /health)       |
+--------------------------+----------------------------------+
                           |
                           v
+--------------------------+----------------------------------+
|                   Orchestration Layer                       |
|          (orchestrator.py: Agent Pipeline, Parallelism)     |
+--------------------------+----------------------------------+
                           |
                           v
+--------------------------+----------------------------------+
|                  Agent Swarm Layer                          |
|  (agents/*.py: Inventory, Logistics, Pharmacy, Clinic, etc) |
|  [Each agent wraps an OpenAI LLM + domain tools]            |
+--------------------------+----------------------------------+
                           |
                           v
+--------------------------+----------------------------------+
|                    Data Access Layer                        |
| (data/*.py: store_inventory, logistics, provider, etc.)     |
| [In-memory, simulated DBs; can be swapped for real DBs]     |
+--------------------------+----------------------------------+
                           |
                           v
+--------------------------+----------------------------------+
|                External Dependencies                        |
|   - OpenAI API (LLM)                                        |
|   - (Optionally: Real DBs, 3rd-party APIs)                  |
+-------------------------------------------------------------+
```

---

## Component Descriptions

| Component                | Responsibility                                                                                         |
|--------------------------|-------------------------------------------------------------------------------------------------------|
| **API Layer**            | Exposes REST endpoints for orders, chat, and health checks. Validates requests and returns responses. |
| **Orchestration Layer**  | Coordinates the agent pipeline for each order/chat. Manages parallel execution, context passing, and aggregation of results. |
| **Agent Swarm Layer**    | Implements domain-specific agents (Inventory, Logistics, Pharmacy, etc.), each wrapping an LLM and toolset. |
| **Data Access Layer**    | Provides in-memory data access for inventory, logistics, pharmacy, clinic, distribution, provider, and customer history. |
| **External Dependencies**| Integrates with OpenAI API for LLM calls. Optionally, can be extended to real databases or external APIs. |
| **Run Logger**           | Persists detailed pipeline execution logs for auditing and debugging.                                  |

---

## Parallel Execution Strategy & Thread Pool Design

### Overview

- **Agent Pipeline**: The orchestrator executes agents in a multi-phase pipeline. Some phases run agents in parallel (e.g., Inventory, Logistics, Pharmacy, Clinic), others are sequential (e.g., final synthesis).
- **Thread Pool**: Python's `concurrent.futures.ThreadPoolExecutor` (not shown, but implied by orchestration and timing logs) is used to parallelize agent invocations.
- **Thread Assignment**: Each agent execution is assigned a thread, and per-agent timing/thread info is logged for observability.

### Example Execution Flow

```text
Phase 1 (Parallel):      InventoryAgent, LogisticsAgent, PharmacyAgent, ClinicAgent
Phase 2 (Parallel):      DistributionAgent, ProviderAgent
Phase 3 (Sequential):    Synthesis/Final Decision Agent
```

- Each agent's `.run()` method is called in a thread, allowing for concurrent LLM and data tool calls.
- Results are aggregated, and context is passed to downstream agents as needed.

### Thread Pool Sizing

- Default: Number of agents per phase (typically 4-6).
- Scalable: Can be tuned based on deployment environment and LLM API rate limits.

---

## Data Layer Design

### Structure

- **In-memory "databases"**: Each `data/*.py` module simulates a domain database (store inventory, logistics, pharmacy, etc.) using Python dicts/lists.
- **Domain Functions**: Each data module exposes functions for CRUD-like operations (e.g., `check_stock`, `get_inbound_for_sku`, `get_prescriptions`).
- **Swappable**: Data modules are designed for easy replacement with real DB queries or API calls.

### Example: Store Inventory

```python
STORE_INVENTORY = {
    "store-101": {
        "SKU-1001": { "on_hand": 24, ... },
        ...
    }
}

def check_stock(store_id: str, sku: str) -> dict:
    ...
```

### Data Flow

- Agents call data functions via their tool handlers.
- Data is read/written in memory for simulation; in production, this would be transactional DB access.

---

## External Dependencies & Integration Points

| Dependency         | Integration Point                                      | Purpose                                  |
|--------------------|-------------------------------------------------------|------------------------------------------|
| **OpenAI API**     | `agents/base.py` (`OpenAI` client)                    | LLM-powered agent reasoning and tool use |
| **Requests**       | `smoke_test.py` (test client)                         | API testing                              |
| **FastAPI**        | (Implied in `app.py`, not shown)                      | REST API framework                       |
| **Pydantic**       | `models.py`                                           | Request/response validation              |
| **(Optional)**     | Replace `data/*.py` with real DBs or external APIs    | Real-world data integration              |

---

## Security Considerations

| Area                | Consideration                                                                                      |
|---------------------|---------------------------------------------------------------------------------------------------|
| **PII Handling**    | Agents are instructed (in system prompts) not to expose raw customer data; only summaries allowed.|
| **LLM Guardrails**  | Prompts enforce medical/legal guardrails (no diagnosis, no dosage advice, refer to professionals).|
| **API Auth**        | (Not shown) In production, endpoints should require authentication and authorization.              |
| **Data Privacy**    | In-memory data is for simulation; real deployments must secure customer, prescription, and health data per HIPAA/PCI/etc.|
| **External Calls**  | OpenAI API keys are loaded from environment; should be stored securely and rotated as needed.      |
| **Logging**         | Run logs avoid storing sensitive data; only metadata and agent responses are logged.               |

---

## Scalability Path

| Aspect            | Current State                 | Scalability Path                                                          |
|-------------------|------------------------------|---------------------------------------------------------------------------|
| **Agents**        | In-memory, per-process        | Stateless agent logic; can be horizontally scaled across processes/nodes.  |
| **Data Layer**    | In-memory Python dicts/lists  | Swap for transactional DBs (Postgres, Redis, etc.) or external APIs.      |
| **LLM Calls**     | Synchronous OpenAI API calls  | Use async APIs, batch requests, or dedicated LLM inference clusters.       |
| **Thread Pool**   | Per-request, per-process      | Tune thread pool size, use process pools, or distributed task queues.      |
| **API Layer**     | Single FastAPI instance       | Deploy behind a load balancer, scale out with multiple workers.            |
| **Logging**       | Local filesystem logs         | Centralize logs (S3, ELK, etc.) for multi-node deployments.                |

---

## Error Handling Strategy

| Layer               | Strategy                                                                                   |
|---------------------|--------------------------------------------------------------------------------------------|
| **API Layer**       | Validates requests with Pydantic; returns 4xx/5xx on error.                                |
| **Orchestration**   | Catches agent and thread errors; logs failures per agent; continues pipeline if possible.   |
| **Agent Layer**     | Each agent's tool handler returns structured error dicts (e.g., `{"error": ...}`); LLM is prompted to handle tool errors gracefully. |
| **Data Layer**      | Functions return error dicts if data is missing or invalid (e.g., not found, insufficient stock). |
| **External Calls**  | LLM API errors are caught; retries or fallback responses as needed.                        |
| **Logging**         | All errors are logged in run logs for auditing and debugging.                              |

### Example Error Propagation

- If `reserve_stock` fails due to insufficient stock, agent returns `{"reserved": False, "error": ...}`.
- Orchestrator aggregates agent errors and includes them in the final decision and customer message.
- If an agent fails completely (e.g., LLM API error), the orchestrator logs the error and continues with available data.

---

## Appendix: Key Data Flows

### Order Fulfillment

1. **Order Placed** (`POST /orders`)
2. **Orchestrator** launches agent pipeline:
    - InventoryAgent: Checks/reserves store stock
    - LogisticsAgent: Checks inbound shipments
    - PharmacyAgent: Checks prescriptions, interactions
    - ClinicAgent: Checks appointments, recommendations
    - DistributionAgent: Checks DC stock
    - ProviderAgent: Checks supplier pipeline
    - Synthesis: Aggregates results, decides fulfillment
3. **Run Logger** saves pipeline log and summary.
4. **API** returns fulfillment plan and customer message.

### Chat

1. **Chat Started** (`POST /chat/start`)
2. **Orchestrator** provides context from prior order.
3. **Agents** answer follow-up questions, using tools as needed.
4. **Chat history** is maintained per customer.

---

## Summary Table

| Layer         | Technology         | Example Files/Modules         | Notes                                   |
|---------------|-------------------|------------------------------|-----------------------------------------|
| API           | FastAPI           | `app.py`                     | REST endpoints                          |
| Orchestration | Python threading  | `orchestrator.py`            | Agent pipeline, thread pool             |
| Agents        | OpenAI LLM + tools| `agents/*.py`, `base.py`     | Domain-specific reasoning               |
| Data          | In-memory Python  | `data/*.py`                  | Simulated DBs, swappable                |
| Models        | Pydantic          | `models.py`                  | API schemas                             |
| Logging       | JSON, Markdown    | `run_logger.py`, `runs/`     | Pipeline run logs, index                |

---

## ASCII Sequence Example

```text
User → API → Orchestrator
           ↓
    ┌─────────────┬─────────────┬─────────────┬─────────────┐
    │ Inventory   │ Logistics   │ Pharmacy    │ Clinic      │  (Parallel Phase)
    └─────┬───────┴─────┬───────┴─────┬───────┴─────┬───────┘
          ↓             ↓             ↓             ↓
    ┌─────────────┬─────────────┐
    │ Distribution│ Provider    │  (Parallel Phase)
    └─────┬───────┴─────┬───────┘
          ↓             ↓
        Synthesis/Final Decision
                ↓
             Response
```

---

## End of ARCHITECTURE.md