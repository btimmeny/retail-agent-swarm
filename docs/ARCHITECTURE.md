# ARCHITECTURE.md

## System Overview

This repository implements a **retail pharmacy chain orchestration platform**. It coordinates customer orders, inventory, logistics, pharmacy, clinic, and provider operations using a multi-agent architecture. The system exposes a REST API for order placement, chat, and status queries, and internally orchestrates specialized "agents" (domain experts) to handle different aspects of the business logic.

Agents communicate via function calls and share context through an orchestrator. The system is designed for **parallel execution** of independent agent tasks, with robust security, audit, and compliance guardrails (HIPAA, PHI redaction, RBAC).

---

## Layered Architecture Diagram

```ascii
+-------------------+         +---------------------+
|  External Clients | <-----> |    REST API Layer   |
+-------------------+         +---------------------+
                                      |
                                      v
+--------------------------------------------------------------+
|                    Orchestrator Layer                        |
|  (Coordinates agent pipelines, parallelizes independent work)|
+--------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------+
|                       Agent Layer                            |
|  +---------------+  +----------------+  +----------------+  |
|  | Inventory     |  | Pharmacy       |  | Distribution   |  |
|  | Agent         |  | Agent          |  | Agent          |  |
|  +---------------+  +----------------+  +----------------+  |
|  | Provider      |  | Logistics      |  | Clinic         |  |
|  | Agent         |  | Agent          |  | Agent          |  |
|  +---------------+  +----------------+  +----------------+  |
|  | Customer      |  | History Agent  |  | Customer Chat  |  |
|  | Agent         |  |                |  | Agent          |  |
|  +---------------+  +----------------+  +----------------+  |
+--------------------------------------------------------------+
                                      |
                                      v
+-------------------+    +-------------------+    +-------------------+
|  Data Layer       |    |  External Systems |    |  Audit/Security   |
|  (in-memory,      |    |  (Email, LLM API) |    |  (Logging, RBAC)  |
|   simulated)      |    +-------------------+    +-------------------+
+-------------------+
```

---

## Component Descriptions & Responsibilities

| Component            | Responsibility                                                                                  |
|----------------------|-----------------------------------------------------------------------------------------------|
| **REST API Layer**   | Exposes endpoints for orders, chat, health, etc. Validates input, returns structured responses.|
| **Orchestrator**     | Receives API requests, decomposes them into agent tasks, manages context, parallelizes work.   |
| **Agent Layer**      | Specialized domain agents (Inventory, Pharmacy, Logistics, etc.) encapsulate business logic.   |
| **Data Layer**       | In-memory simulation of inventory, pharmacy, logistics, clinic, and provider data.             |
| **External Systems** | Integrates with LLM APIs (for chat), email, and other services as needed.                      |
| **Audit/Security**   | Enforces authentication, RBAC, PHI redaction, and logs sensitive access for compliance.        |

### Key Agents

- **Inventory Agent**: Checks/reserves store stock, flags reorder needs.
- **Distribution Agent**: Manages DC stock, allocates bulk replenishment.
- **Provider Agent**: Handles supplier relationships, purchase orders.
- **Pharmacy Agent**: Manages prescriptions, refills, drug interactions, RBAC, PHI redaction.
- **Logistics Agent**: Tracks inbound shipments, ETAs.
- **Clinic Agent**: Manages appointments, immunizations, wellness.
- **Customer History Agent**: Looks up profiles, order history, with HIPAA guardrails.
- **Customer Agent**: Conversational interface with strict safety/guardrails.

---

## Parallel Execution Strategy & Thread Pool Design

### Overview

- **Orchestrator** decomposes requests into agent tasks.
- **Independent agent tasks** (e.g., inventory, pharmacy, logistics) are executed in **parallel** using a thread pool.
- **Dependencies** are respected: e.g., pharmacy checks may depend on inventory results for drug interaction checks.
- **Execution timing** and thread info are logged for observability.

### Thread Pool Design

- Uses a **ThreadPoolExecutor** (Python standard library) for parallel agent execution.
- **Max workers**: Configurable (default: 4–8, depending on deployment).
- **Task submission**: Each agent receives its context and function call; results are aggregated.
- **Timeouts**: Each agent call has a timeout to prevent blocking the pipeline.
- **Error isolation**: Agent failures are caught and logged; orchestrator can continue with partial results if appropriate.

#### Example (simplified):

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(agent.run, context): agent for agent in agents}
    results = {}
    for future in as_completed(futures):
        agent = futures[future]
        try:
            results[agent.name] = future.result(timeout=10)
        except Exception as e:
            results[agent.name] = {"error": str(e)}
```

---

## Data Layer Design

- **In-memory dictionaries** simulate all data sources:
    - `store_inventory.py`: Store-level stock, reservations.
    - `distribution_center.py`: DC-level stock, allocations.
    - `provider.py`: Supplier info, purchase orders.
    - `pharmacy.py`: Prescriptions, alerts, drug interactions.
    - `clinic.py`: Appointments, immunizations, wellness.
    - `logistics.py`: Inbound shipments, ETAs.
    - `customer_history.py`: Profiles, order history.

- **Validation**: Each data access function validates input (e.g., SKU format, customer ID).
- **Audit Logging**: Sensitive data access (PHI, appointments, prescriptions) is logged for compliance.

#### Example Data Access

```python
def get_prescriptions(customer_id: str) -> list[dict]:
    _validate_customer_id(customer_id)
    return [rx for rx in PRESCRIPTIONS.get(customer_id, []) if rx["status"] == "active"]
```

---

## External Dependencies & Integration Points

| Dependency         | Purpose/Integration Point                                      |
|--------------------|---------------------------------------------------------------|
| **OpenAI LLM API** | Used by CustomerAgent for chat completions.                   |
| **Email**          | (Planned) For supplier/provider notifications.                |
| **PyDantic**       | API request/response validation.                              |
| **FastAPI**        | (Assumed) REST API framework.                                 |
| **ThreadPoolExecutor** | Parallel agent execution.                                 |
| **pytest**         | Testing (smoke, integration, security).                       |
| **Docker**         | Containerized deployment.                                     |

---

## Security Considerations

| Area                | Controls Implemented                                                                                                   |
|---------------------|-----------------------------------------------------------------------------------------------------------------------|
| **Authentication**  | All sensitive agent actions require user context; enforced via decorators or explicit checks.                         |
| **RBAC**            | Role-based access enforced for PHI (e.g., only pharmacists/providers/admins can access prescription data).            |
| **PHI Redaction**   | All agent responses that may include PHI are passed through redaction utilities before returning/logging.             |
| **Audit Logging**   | All access to sensitive data (clinic, pharmacy, history) is logged with timestamp, user, and action for compliance.   |
| **Input Validation**| All data access functions validate input formats to prevent injection or malformed requests.                           |
| **Guardrails**      | Customer-facing agent has strict guardrails (no medical advice, no PHI, no raw data sharing, escalation protocols).   |
| **HIPAA Compliance**| Explicitly designed for HIPAA compliance in all PHI-handling agents and data flows.                                   |
| **API Security**    | (Assumed) API endpoints require authentication tokens (not shown in code snippets).                                   |

---

## Scalability Path

- **Stateless Orchestrator**: Can be horizontally scaled; each API request is independent.
- **Thread Pool**: Configurable; can be tuned or migrated to async/event-driven for higher concurrency.
- **Agent Modularity**: New agents can be added without affecting others; agent logic is isolated.
- **Data Layer**: Replace in-memory stores with persistent databases (PostgreSQL, Redis, etc.) for production.
- **LLM Integration**: Can be swapped for on-prem or alternative providers as needed.
- **API Gateway**: Add rate limiting, authentication, and monitoring at the ingress point.
- **Observability**: Per-agent timing and thread info logged for bottleneck analysis.

---

## Error Handling Strategy

| Error Source         | Handling Approach                                                                                 |
|---------------------|--------------------------------------------------------------------------------------------------|
| **Agent Failures**  | Exceptions caught per agent; errors logged and returned in agent result.                          |
| **Timeouts**        | Each agent call has a timeout; orchestrator can proceed with partial results if non-critical.     |
| **Input Validation**| Invalid input returns structured error messages; never propagates stack traces to clients.        |
| **External Calls**  | LLM and email failures are caught and logged; user receives fallback message.                     |
| **Security Errors** | Unauthorized access returns 401/403 with minimal info; all attempts are logged for audit.         |
| **Pipeline Logging**| All steps (success/failure) are logged with timing, thread, and error info for traceability.      |

#### Example Error Handling

```python
try:
    result = agent.run(context)
except UnauthorizedError:
    log.warning("Unauthorized access attempt")
    return {"error": "Unauthorized"}
except Exception as e:
    log.error(f"Agent {agent.name} failed: {e}")
    return {"error": str(e)}
```

---

## Appendix: Key Tables

### Agent Responsibilities

| Agent Name            | Responsibility Summary                                    |
|-----------------------|----------------------------------------------------------|
| InventoryAgent        | Store stock, reservations, aisle info, reorder flags     |
| DistributionAgent     | DC stock, allocations, reorder to supplier               |
| ProviderAgent         | Supplier lookup, purchase orders, lead times             |
| PharmacyAgent         | Prescriptions, refills, drug interactions, alerts, RBAC  |
| LogisticsAgent        | Inbound shipments, ETAs, carrier info                    |
| ClinicAgent           | Appointments, immunizations, wellness, audit logging     |
| CustomerHistoryAgent  | Profile, order history, frequent items, PHI redaction    |
| CustomerAgent         | Chat, customer interaction, guardrails, escalation       |

---

## Summary

This system provides a robust, modular, and secure orchestration platform for retail pharmacy operations, with a strong focus on compliance, parallelism, and extensibility. Each agent encapsulates a domain, and the orchestrator coordinates their work efficiently, enabling rapid, safe, and scalable order processing and customer engagement.