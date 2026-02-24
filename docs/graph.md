# System Relationship Graphs

This document provides a comprehensive set of Mermaid diagrams visualizing the relationships, data flow, agent orchestration, parallelism, and API request handling for the retail pharmacy agent system.

---

## 1. Component Dependency Graph

This graph shows which modules import or depend on which others, focusing on the main agent and data modules.

```mermaid
graph TD
  %% Agents
  A1[agents/base.py]
  A2[agents/clinic_agent.py]
  A3[agents/customer_agent.py]
  A4[agents/distribution_agent.py]
  A5[agents/history_agent.py]
  A6[agents/inventory_agent.py]
  A7[agents/logistics_agent.py]
  A8[agents/pharmacy_agent.py]
  A9[agents/provider_agent.py]
  AO[agents/orchestrator.py]

  %% Data
  D1[data/clinic.py]
  D2[data/customer_history.py]
  D3[data/distribution_center.py]
  D4[data/logistics.py]
  D5[data/pharmacy.py]
  D6[data/provider.py]
  D7[data/store_inventory.py]

  %% Models and Utility
  M1[models.py]
  RL[run_logger.py]
  AP[app.py]

  %% Imports
  A2 --> A1
  A2 --> D1
  A3 --> A1
  A4 --> A1
  A4 --> D3
  A5 --> A1
  A5 --> D2
  A6 --> A1
  A6 --> D7
  A7 --> A1
  A7 --> D4
  A8 --> A1
  A8 --> D5
  A9 --> A1
  A9 --> D6

  AO --> A2
  AO --> A4
  AO --> A5
  AO --> A6
  AO --> A7
  AO --> A8
  AO --> A9

  AP --> AO
  AP --> M1
  AP --> RL

  RL --> AO

  %% Data modules may cross-reference each other (not shown for brevity)
```

**Explanation:**  
- Each agent imports the `base.py` agent class and its relevant data module.
- The orchestrator imports all agents.
- The API (`app.py`) imports the orchestrator, models, and logger.
- Data modules are standalone per domain.

---

## 2. Data Flow Diagram

This diagram shows how data (e.g., order requests, customer info, inventory, etc.) moves through the system from API entry to fulfillment.

```mermaid
flowchart TD
  User([User / API Client])
  API[app.py (FastAPI)]
  Orchestrator[agents/orchestrator.py]
  Agents{{Domain Agents}}
  AgentClinic[Clinic Agent]
  AgentHistory[History Agent]
  AgentInventory[Inventory Agent]
  AgentLogistics[Logistics Agent]
  AgentDistribution[Distribution Agent]
  AgentProvider[Provider Agent]
  AgentPharmacy[Pharmacy Agent]
  DataClinic[data/clinic.py]
  DataHistory[data/customer_history.py]
  DataInventory[data/store_inventory.py]
  DataLogistics[data/logistics.py]
  DataDistribution[data/distribution_center.py]
  DataProvider[data/provider.py]
  DataPharmacy[data/pharmacy.py]
  Logger[run_logger.py]
  Models[models.py]

  User -->|HTTP POST /orders| API
  API -->|OrderRequest| Orchestrator
  Orchestrator -->|Delegates| Agents
  Agents --> AgentClinic
  Agents --> AgentHistory
  Agents --> AgentInventory
  Agents --> AgentLogistics
  Agents --> AgentDistribution
  Agents --> AgentProvider
  Agents --> AgentPharmacy

  AgentClinic --> DataClinic
  AgentHistory --> DataHistory
  AgentInventory --> DataInventory
  AgentLogistics --> DataLogistics
  AgentDistribution --> DataDistribution
  AgentProvider --> DataProvider
  AgentPharmacy --> DataPharmacy

  Orchestrator -->|Pipeline result| Logger
  Logger -->|Log file| (runs/)

  API --> Models
  Models -.-> API
```

**Explanation:**  
- The user sends an order to the API.
- The API parses and validates the request, then passes it to the orchestrator.
- The orchestrator coordinates the domain agents in a pipeline.
- Each agent queries its respective data module.
- Results are aggregated, logged, and returned to the user.

---

## 3. Agent Interaction Sequence Diagram

This sequence diagram illustrates how the orchestrator coordinates the agents for an order, including context passing and tool calls.

```mermaid
sequenceDiagram
  participant User as User/API
  participant API as app.py
  participant Orchestrator as Orchestrator
  participant History as HistoryAgent
  participant Clinic as ClinicAgent
  participant Pharmacy as PharmacyAgent
  participant Inventory as InventoryAgent
  participant Logistics as LogisticsAgent
  participant Distribution as DistributionAgent
  participant Provider as ProviderAgent

  User->>API: POST /orders (OrderRequest)
  API->>Orchestrator: process_order(request)
  Orchestrator->>History: run(user_message, context)
  History-->>Orchestrator: customer profile, order history
  Orchestrator->>Clinic: run(user_message, context)
  Clinic-->>Orchestrator: appointments, immunizations, recommendations
  Orchestrator->>Pharmacy: run(user_message, context)
  Pharmacy-->>Orchestrator: prescriptions, alerts, interactions
  par Inventory/Logistics/Distribution
    Orchestrator->>Inventory: run(user_message, context)
    Inventory-->>Orchestrator: stock status, reservations

    Orchestrator->>Logistics: run(user_message, context)
    Logistics-->>Orchestrator: inbound shipments, ETAs

    Orchestrator->>Distribution: run(user_message, context)
    Distribution-->>Orchestrator: DC stock, allocations
  end
  Orchestrator->>Provider: run(user_message, context)
  Provider-->>Orchestrator: supplier info, restock orders

  Orchestrator->>API: pipeline result (can_fulfill, flags, messages)
  API->>User: Response (OrderResult)
```

**Explanation:**  
- The orchestrator runs agents in a specific order, passing context between them.
- Inventory, logistics, and distribution may run in parallel.
- Provider agent runs after DC/Logistics.
- Results are synthesized and returned.

---

## 4. Parallel Execution Flow Diagram

This diagram shows which agents can execute in parallel and how the pipeline is structured for concurrency.

```mermaid
flowchart LR
  Start([Start Order Pipeline])
  History[History Agent]
  Clinic[Clinic Agent]
  Pharmacy[Pharmacy Agent]
  ParallelFork{{Parallel}}
  Inventory[Inventory Agent]
  Logistics[Logistics Agent]
  Distribution[Distribution Agent]
  ParallelJoin{{Join}}
  Provider[Provider Agent]
  End([Synthesize & Respond])

  Start --> History
  History --> Clinic
  Clinic --> Pharmacy
  Pharmacy --> ParallelFork
  ParallelFork --> Inventory
  ParallelFork --> Logistics
  ParallelFork --> Distribution
  Inventory --> ParallelJoin
  Logistics --> ParallelJoin
  Distribution --> ParallelJoin
  ParallelJoin --> Provider
  Provider --> End
```

**Explanation:**  
- After initial context agents (history, clinic, pharmacy), the pipeline fans out to inventory, logistics, and distribution in parallel.
- Results are joined and passed to the provider agent.
- The pipeline then synthesizes the final response.

---

## 5. API Request Flow Diagram

This diagram details the REST API endpoints and their flow through the system.

```mermaid
flowchart TD
  subgraph API Layer
    A1[POST /orders]
    A2[GET /orders/{order_id}]
    A3[POST /chat/start]
    A4[POST /chat/message]
    A5[GET /chat/{customer_id}/history]
    A6[GET /health]
  end

  A1 -->|OrderRequest| Orchestrator
  Orchestrator -->|OrderResult| A1
  A2 -->|Fetch pipeline log| Orchestrator
  Orchestrator -->|OrderResult| A2
  A3 -->|ChatStartRequest| Orchestrator
  Orchestrator -->|Greeting| A3
  A4 -->|ChatMessage| Orchestrator
  Orchestrator -->|ChatResponse| A4
  A5 -->|Get chat log| Orchestrator
  Orchestrator -->|ChatHistory| A5
  A6 -->|Health check| (OK)

  Orchestrator -->|Log| Logger
  Logger -->|Log files| (runs/)
```

**Explanation:**  
- `/orders` endpoints handle order placement and retrieval.
- `/chat` endpoints manage customer chat sessions.
- All business logic routes through the orchestrator, which logs runs.
- `/health` is a simple status endpoint.

---

# Summary

- **Component dependency**: Agents depend on their data modules and the base agent class; orchestrator coordinates all.
- **Data flow**: API → Orchestrator → Agents → Data modules → Logger → API response.
- **Agent sequence**: Context agents first, then parallel stock agents, then provider, then synthesis.
- **Parallelism**: Inventory, logistics, and distribution agents run concurrently.
- **API**: RESTful endpoints for orders and chat, all routed through orchestrator logic.

These diagrams provide a holistic view of the system's structure and runtime behavior.