# Retail Agent Swarm — Design Document

**Version:** 1.0.0
**Last Updated:** 2026-02-23

---

## 1. Design Philosophy

### 1.1 Principles

- **Agent autonomy with orchestrated coordination** — Each agent independently decides which tools to call and how to interpret results. The orchestrator controls sequencing and data flow, not agent behavior.
- **Parallelism by dependency analysis** — Agents that don't depend on each other's output run concurrently. The dependency graph is explicit and auditable.
- **Safety by default** — Guardrails are baked into system prompts, not bolted on. The customer agent has both pre-processing (system prompt rules) and post-processing (keyword scanner) safety layers.
- **Observability first** — Every agent call is timed, thread-tagged, and logged. The pipeline is transparent by design.
- **Simulated realism** — Mock data mirrors real-world complexity: drug interactions, allergy conflicts, supply chain dependencies, and cross-department coordination.

### 1.2 Key Trade-offs

| Decision | Alternative | Why This Way |
|----------|------------|-------------|
| Thread pool over asyncio | Native async with `openai.AsyncOpenAI` | Simpler agent base class; OpenAI sync client is well-tested; threads handle I/O concurrency fine |
| Function calling over ReAct prompting | Free-form tool use via prompt engineering | Function calling is more reliable, type-safe, and auditable |
| Stateless agents, stateful orchestrator | Each agent maintains its own state | Easier to test, swap, and parallelize agents when they're pure functions |
| In-memory data over database | SQLite, Redis, PostgreSQL | Eliminates infrastructure dependencies for demo; data layer is easily swappable |
| Single orchestrator pattern | Event-driven pub/sub between agents | Simpler to reason about, debug, and observe; pub/sub is the scalability path |

---

## 2. Agent Design Patterns

### 2.1 Tool-Augmented LLM Pattern

Each agent follows the same pattern:

```
Input (natural language task + optional context)
    │
    ▼
┌─────────────────────────────┐
│  System Prompt               │  ← domain expertise + behavioral rules
│  + Context (from other agents│
│  + User Message              │
└──────────┬──────────────────┘
           ▼
     OpenAI LLM Call
           │
           ├─── No tool calls? → Return text response
           │
           └─── Tool calls detected:
                    │
                    ▼
              Execute tools locally (data layer functions)
                    │
                    ▼
              Feed results back to LLM
                    │
                    ▼
              LLM synthesizes final response
```

**Why this pattern?** The LLM acts as the "brain" that decides what information to gather and how to interpret it. The tools are deterministic data lookups. This gives us:
- **Flexibility** — the agent adapts to different queries without code changes
- **Auditability** — every tool call and result is logged
- **Reliability** — data functions are tested, deterministic, and fast

### 2.2 Agent Specialization Strategy

Each agent has exactly one domain and a bounded set of tools:

| Agent | # Tools | Domain Boundary |
|-------|---------|----------------|
| Store Inventory | 3 | Store-level stock only. Cannot see DC or logistics data. |
| Logistics | 3 | Inbound shipments only. Cannot modify inventory. |
| Distribution Center | 3 | DC stock only. Cannot see store-level data. |
| Provider | 3 | Supplier relationships only. Cannot see customer data. |
| Customer History | 3 | Customer profiles only. Cannot see pharmacy or clinic data. |
| Pharmacy | 4 | Prescriptions and interactions only. Cannot modify orders. |
| Clinic | 4 | Appointments and wellness only. Cannot access pharmacy data. |

**Why strict boundaries?** Prevents agents from exceeding their authority. The Pharmacy Agent cannot modify an order — it can only flag concerns. The Inventory Agent cannot see a customer's prescriptions. The orchestrator is the only component with a cross-domain view.

### 2.3 Context Injection Pattern

When an agent needs information from a prior agent's output, the orchestrator injects it as a system message:

```python
# In the agent's message array:
{"role": "system", "content": f"Context from other agents:\n{json.dumps(context)}"}
```

This keeps agents decoupled — they receive context as data, not as a dependency on another agent's implementation.

**Current context flows:**
- DC Agent output → Provider Agent (so Provider knows DC stock levels)
- All agent outputs → Synthesis LLM (for final decision)
- Final decision → Customer Agent (for conversation context)

---

## 3. Orchestration Design

### 3.1 Phase-Based Pipeline

The pipeline is organized into phases based on data dependencies:

```
Phase 1: Information Gathering (parallel)
    History + Inventory run simultaneously.
    No dependencies — History needs customer_id, Inventory needs store+SKUs.

Phase 2: Gap Analysis (conditional sequential)
    Logistics runs ONLY if Inventory found out-of-stock items.
    Sequential because it depends on Phase 1's out-of-stock list.
    If everything is in stock, this phase is skipped entirely.

Phase 3: Deep Assessment (parallel with micro-dependency)
    DC, Pharmacy, and Clinic launch immediately in parallel.
    DC must complete before Provider launches (Provider needs DC context).
    Provider then runs in parallel with the still-running Pharmacy/Clinic.

Phase 4: Decision Synthesis (sequential)
    Single LLM call that receives all agent outputs.
    Produces structured JSON with the final order decision.
```

### 3.2 Why Not Fully Parallel?

Some agents genuinely depend on prior outputs:

- **Logistics** needs the out-of-stock SKU list from Inventory — without it, Logistics doesn't know what to look for
- **Provider** needs the DC assessment — without it, Provider can't assess whether the supply chain needs intervention
- **Synthesis** needs everything — it's the convergence point

We maximize parallelism within these constraints. The result is **4 phases with 8 LLM calls** where a naive sequential approach would be **8 phases with 8 LLM calls**.

### 3.3 Future: Collect Pattern

The current `_collect()` method blocks on a specific future. A more advanced pattern would use `as_completed()` to process results as they arrive:

```python
# Current: ordered collection
dc_result = self._collect(dc_future, pipeline_log)      # blocks until DC done
pharmacy_result = self._collect(pharmacy_future, pipeline_log)  # then Pharmacy
clinic_result = self._collect(clinic_future, pipeline_log)      # then Clinic

# Future: first-available collection
for future in as_completed([dc_future, pharmacy_future, clinic_future]):
    result = future.result()
    # Process immediately, potentially launching dependent agents sooner
```

This would allow Provider to launch the instant DC finishes, even if Pharmacy/Clinic are still running.

---

## 4. Guardrail Design

### 4.1 Defense in Depth

The customer agent has three layers of safety:

```
Layer 1: System Prompt (pre-generation)
    └─ 10 explicit guardrail rules in the system prompt
    └─ LLM is instructed to follow them at all times
    └─ Includes specific redirect phrases for each scenario

Layer 2: Context Isolation (data protection)
    └─ Order context injected as system message marked "INTERNAL"
    └─ LLM instructed not to share raw data with customer
    └─ Only summarized insights should reach the customer

Layer 3: Post-Processing (post-generation)
    └─ Keyword scanner checks for medical advice patterns
    └─ If detected, appends disclaimer to response
    └─ Acts as a safety net for prompt adherence failures
```

### 4.2 Guardrail Categories

| Category | Guardrails | Risk Mitigated |
|----------|-----------|----------------|
| **Medical Safety** | G-01, G-03, G-04 | Liability from medical advice, interaction harm, allergy reactions |
| **Data Privacy** | G-02, G-05 | PII exposure, HIPAA-like violations |
| **Accuracy** | G-06, G-07 | Customer trust from wrong prices or false stock promises |
| **Scope** | G-08 | Liability from out-of-domain advice |
| **Experience** | G-09, G-10 | Customer satisfaction, proper escalation |

### 4.3 Drug Interaction Flow

This is the highest-stakes guardrail in the system:

```
Customer orders OTC item (e.g., Ibuprofen)
    │
    ▼
Pharmacy Agent checks: check_drug_interaction(customer_id, sku)
    │
    ├─ No interaction → proceed normally
    │
    └─ Interaction detected:
         │
         ▼
    Agent flags in response:
      - Conflicting medication name
      - Warning text
      - Severity level
         │
         ▼
    Synthesis includes in pharmacy_flags[]
         │
         ▼
    Customer Agent receives flag in context
         │
         ▼
    Guardrail G-03 REQUIRES the agent to:
      1. Mention the interaction to the customer
      2. Recommend pharmacist consultation
      3. Never downplay the severity
```

---

## 5. Data Layer Design

### 5.1 Module-Per-Domain Pattern

Each data module is self-contained with:
- **Constants** — the simulated database (dict/list at module level)
- **Query functions** — pure functions that read from the constants
- **Mutation functions** — functions that modify state (e.g., `reserve_stock`, `create_restock_order`)

```python
# Pattern for every data module:
DATABASE: dict = { ... }           # The "database"

def query_something(id: str) -> dict:     # Read operation
    return DATABASE.get(id)

def mutate_something(id: str, ...) -> dict:  # Write operation
    DATABASE[id]["field"] = new_value
    return {"success": True, ...}
```

### 5.2 Data Relationships

```
Customer (CUST-*)
    ├── Order History (ORD-*)
    ├── Prescriptions (RX-*)
    ├── Pharmacy Alerts
    ├── Clinic Appointments (APPT-*)
    ├── Immunization Records
    └── Wellness Recommendations → SKUs

Store (store-*)
    ├── Store Inventory → SKUs
    └── DC Map → Distribution Centers (DC-*)

Distribution Center (DC-*)
    └── DC Inventory → SKUs

Supplier (SUP-*)
    ├── SKU Catalog
    └── Purchase Orders (PO-*)

Shipment (SHIP-*)
    ├── Origin → DC
    ├── Destination → Store
    └── Items → SKUs
```

### 5.3 Intentional Data Scenarios

The simulated data is crafted to trigger specific agent behaviors:

| Scenario | Data Setup | Expected Behavior |
|----------|-----------|-------------------|
| Out-of-stock item | SKU-1002 has 0 on_hand at store-101 | Triggers Logistics agent, shows inbound shipment ETA |
| Drug interaction | CUST-2001 on Lisinopril + ordering Ibuprofen | Pharmacy agent flags moderate interaction |
| Low stock / reorder needed | SKU-1004 has 3 units (threshold: 5) | Inventory flags needs_reorder, DC/Provider assess supply |
| Cross-department recommendation | Clinic recommends Vitamin D (SKU-1002) for CUST-2001 | Clinic agent surfaces this when customer orders related items |
| Upcoming refill | CUST-2001 Lisinopril refill due in 2 days | Pharmacy agent proactively mentions this |
| Allergy concern | CUST-2001 allergic to penicillin | History agent flags allergy, Pharmacy agent includes in alerts |

---

## 6. Error Handling Design

### 6.1 Agent-Level

- **Tool not found** — returns `{"error": "Unknown tool: <name>"}` and continues
- **Tool execution error** — caught by the agent base, returned as error result to LLM
- **Max rounds exceeded** — returns partial results after 5 tool-calling rounds
- **OpenAI API error** — propagates to orchestrator (no retry currently)

### 6.2 Orchestrator-Level

- **Agent failure** — `future.result()` raises the exception; currently unhandled (would crash the pipeline)
- **Synthesis parse failure** — returns a degraded response with `can_fulfill: false` and the raw LLM output

### 6.3 API-Level

- **Order not found** — 404 with descriptive message
- **Chat without session** — 400 with "No active conversation" message
- **Validation error** — Pydantic returns 422 automatically

### 6.4 Future: Resilience

| Enhancement | Description |
|------------|-------------|
| Agent retry with backoff | Retry failed OpenAI calls with exponential backoff |
| Circuit breaker | If an agent fails repeatedly, skip it and note in pipeline log |
| Graceful degradation | If Pharmacy agent fails, still process order but flag for manual review |
| Timeout per agent | Kill agents that take too long (currently unbounded) |

---

## 7. Testing Strategy

### 7.1 Current

- **Smoke test** (`smoke_test.py`) — end-to-end API test exercising the full pipeline, chat session, and timing output

### 7.2 Planned

| Level | What | How |
|-------|------|-----|
| **Unit** | Data layer functions | pytest, no API key needed |
| **Unit** | Agent tool handlers | pytest, mock OpenAI responses |
| **Integration** | Agent pipeline | pytest + recorded OpenAI responses |
| **Guardrail** | Customer agent safety | Adversarial prompt test suite |
| **Performance** | Parallel vs sequential timing | Benchmark comparison |
