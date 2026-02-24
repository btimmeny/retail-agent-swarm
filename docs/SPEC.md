# Retail Agent Swarm — Specification

**Version:** 1.0.0
**Last Updated:** 2026-02-23
**Status:** Active Development

---

## 1. Overview

The Retail Agent Swarm is a multi-agent system that processes customer orders for a retail pharmacy chain. When a customer places an order via REST API, the system orchestrates a pipeline of specialized AI agents that collectively evaluate inventory, supply chain, pharmacy safety, and clinic context before confirming the order and engaging the customer in a guardrailed conversation.

### 1.1 Goals

- Simulate a realistic end-to-end retail pharmacy order flow
- Demonstrate multi-agent coordination with parallel execution
- Enforce safety guardrails for pharmacy/healthcare interactions
- Provide a conversational customer interface with appropriate boundaries

### 1.2 Non-Goals

- Production-grade persistence (uses in-memory stores)
- Real payment processing or shipping integration
- HIPAA-compliant data handling (simulated data only)
- Real-time inventory sync with physical store systems

---

## 2. Functional Requirements

### 2.1 Order Placement

| ID | Requirement | Priority |
|----|------------|----------|
| FR-001 | Customer can place an order via `POST /orders` with customer ID, store ID, and item list | Must |
| FR-002 | Each order triggers the full agent pipeline before returning a response | Must |
| FR-003 | Order response includes fulfillment status, pharmacy flags, and clinic reminders | Must |
| FR-004 | Order response includes execution timing for observability | Should |
| FR-005 | Orders are retrievable by ID via `GET /orders/{id}` | Must |
| FR-006 | All processed orders are listable via `GET /orders` | Should |

### 2.2 Agent Pipeline

| ID | Requirement | Priority |
|----|------------|----------|
| FR-010 | Customer History Agent retrieves profile, loyalty tier, allergies, and purchase patterns | Must |
| FR-011 | Store Inventory Agent checks on-hand stock, aisle locations, and reorder thresholds | Must |
| FR-012 | Logistics Agent checks inbound shipments and ETAs for out-of-stock items | Must |
| FR-013 | Distribution Center Agent checks DC-level bulk stock across all serving DCs | Must |
| FR-014 | Provider Agent checks supplier status, pending POs, and lead times | Must |
| FR-015 | Pharmacy Agent checks prescriptions, refills, drug interactions, and pharmacist alerts | Must |
| FR-016 | Clinic Agent checks appointments, immunization history, and wellness recommendations | Must |
| FR-017 | Orchestrator synthesizes all agent reports into a final order decision | Must |
| FR-018 | Agents in independent phases run in parallel via thread pool | Must |
| FR-019 | Logistics Agent is skipped when all items are in stock | Should |

### 2.3 Customer Conversation

| ID | Requirement | Priority |
|----|------------|----------|
| FR-020 | Customer can start a chat session tied to a specific order via `POST /chat/start` | Must |
| FR-021 | Customer can send follow-up messages via `POST /chat/message` | Must |
| FR-022 | Conversation history is retrievable via `GET /chat/{customer_id}/history` | Should |
| FR-023 | Customer agent has access to the full order decision context | Must |
| FR-024 | All 10 guardrails are enforced in every response (see Section 5) | Must |

### 2.4 Health & Observability

| ID | Requirement | Priority |
|----|------------|----------|
| FR-030 | Health endpoint at `GET /health` | Must |
| FR-031 | Per-agent execution timing in pipeline log | Should |
| FR-032 | Thread assignment tracking for parallel execution verification | Should |

---

## 3. Data Models

### 3.1 Order Request

```json
{
    "customer_id": "string — e.g. CUST-2001",
    "store_id": "string — e.g. store-101",
    "items": [
        {
            "sku": "string — e.g. SKU-1001",
            "qty": "integer — quantity requested"
        }
    ]
}
```

### 3.2 Order Response (Summary)

```json
{
    "order_id": "string — generated, e.g. ORD-20260223193045",
    "status": "processed",
    "can_fulfill": "boolean",
    "customer_message": "string — personalized message to the customer",
    "pharmacy_flags": ["string — list of pharmacy warnings"],
    "clinic_reminders": ["string — list of clinic reminders"],
    "execution_timing": {
        "total_duration_sec": "float",
        "phases": [
            {
                "phase": "integer",
                "agents": ["string"],
                "mode": "string — parallel | sequential",
                "duration_sec": "float"
            }
        ]
    }
}
```

### 3.3 Full Order Details (via GET)

Extends the summary with:

- `items_requested` — original item list
- `pipeline_log` — array of agent execution records, each containing:
  - `agent` — agent name
  - `response` — agent's text response
  - `tools_used` — list of tool function names called
  - `tool_details` — full tool call records with args and results
  - `duration_sec` — execution time
  - `thread` — thread name
- `final_decision` — synthesized JSON with fulfillment plan, pharmacy flags, clinic reminders, personalization notes

### 3.4 Final Decision Schema

```json
{
    "can_fulfill": "boolean",
    "fulfillment_plan": [
        {
            "sku": "string",
            "status": "in_stock | backordered | arriving_soon",
            "action": "string — what happens next",
            "eta": "string — estimated availability"
        }
    ],
    "pharmacy_flags": ["string"],
    "clinic_reminders": ["string"],
    "personalization_notes": ["string"],
    "customer_message": "string"
}
```

### 3.5 Chat Models

**Start Request:**
```json
{
    "customer_id": "string",
    "order_id": "string"
}
```

**Message Request:**
```json
{
    "customer_id": "string",
    "message": "string"
}
```

**Message Response:**
```json
{
    "customer_id": "string",
    "response": "string"
}
```

---

## 4. API Contract

| Method | Path | Request Body | Response | Status |
|--------|------|-------------|----------|--------|
| `GET` | `/health` | — | `{"status": "ok"}` | 200 |
| `POST` | `/orders` | `OrderRequest` | Order Summary | 202 |
| `GET` | `/orders` | — | List of order summaries | 200 |
| `GET` | `/orders/{order_id}` | — | Full order details | 200 / 404 |
| `POST` | `/chat/start` | `ChatStartRequest` | `{"greeting": "..."}` | 200 / 404 |
| `POST` | `/chat/message` | `ChatMessage` | `{"response": "..."}` | 200 / 400 |
| `GET` | `/chat/{customer_id}/history` | — | `{"messages": [...]}` | 200 |

---

## 5. Guardrails Specification

The Customer Conversation Agent enforces these guardrails at all times:

| # | Guardrail | Enforcement |
|---|-----------|-------------|
| G-01 | **No medical advice** | Never diagnose, recommend dosages, or suggest treatments. Redirect to pharmacist. |
| G-02 | **Prescription privacy** | Prescription info only shared after customer authentication (customer_id verified). |
| G-03 | **Drug interaction escalation** | If interaction flag present, MUST mention it and recommend pharmacist consult. Never downplay. |
| G-04 | **Allergy safety** | Flag known allergies when ordering potentially concerning products. |
| G-05 | **Data privacy** | Never share raw customer records (address, phone, email). Summarize only. |
| G-06 | **Price accuracy** | Only quote prices from verified inventory data. Never estimate. |
| G-07 | **Stock honesty** | If out of stock, say so clearly with ETA. Never promise unconfirmed availability. |
| G-08 | **Scope boundaries** | Redirect out-of-scope questions (legal, insurance, complex medical) to appropriate resources. |
| G-09 | **Professional tone** | Warm, concise, professional. Use customer's name. Acknowledge loyalty status. |
| G-10 | **Human escalation** | Offer handoff to human associate when customer is frustrated or situation is complex. |

**Post-processing check:** After every response, a keyword scanner checks for medical advice patterns and appends a disclaimer if detected.

---

## 6. Simulated Data Inventory

### 6.1 Customers

| ID | Name | Loyalty | Allergies | Key Traits |
|----|------|---------|-----------|------------|
| CUST-2001 | Maria Johnson | Gold | Penicillin, Sulfa | Active prescriptions (Lisinopril, Metformin), clinic appointments |
| CUST-2002 | James Chen | Platinum | None | On Atorvastatin, cholesterol screening scheduled |
| CUST-2003 | Sarah Williams | Silver | Latex | New customer, recent first aid kit order |

### 6.2 Products

| SKU | Name | Category | Store Stock | Price |
|-----|------|----------|-------------|-------|
| SKU-1001 | Ibuprofen 200mg 100ct | OTC Medicine | 24 | $8.99 |
| SKU-1002 | Vitamin D3 2000IU 90ct | Vitamins | **0** | $12.49 |
| SKU-1003 | Hand Sanitizer 8oz | Personal Care | 56 | $3.99 |
| SKU-1004 | Blood Pressure Monitor | Health Devices | 3 | $49.99 |
| SKU-1005 | Allergy Relief 24hr 30ct | OTC Medicine | 42 | $14.99 |
| SKU-1006 | First Aid Kit Deluxe | First Aid | 1 | $24.99 |
| SKU-1007 | Protein Bars Variety 12pk | Nutrition | 18 | $19.99 |

### 6.3 Drug Interactions

| OTC Item | Conflicts With | Severity | Warning |
|----------|---------------|----------|---------|
| SKU-1001 (Ibuprofen) | Lisinopril (CUST-2001) | Moderate | NSAIDs may reduce ACE inhibitor effectiveness |

### 6.4 Suppliers

| ID | Name | SKUs | Lead Time | Reliability |
|----|------|------|-----------|-------------|
| SUP-001 | PharmaCorp Inc. | SKU-1001, SKU-1005 | 7 days | 96% |
| SUP-002 | VitaHealth Supply | SKU-1002, SKU-1007 | 10 days | 91% |
| SUP-003 | MedDevice Global | SKU-1004, SKU-1006 | 14 days | 88% |
| SUP-004 | CleanCare Products | SKU-1003 | 5 days | 99% |

---

## 7. Acceptance Criteria

### 7.1 Smoke Test Scenario

**Customer:** CUST-2001 (Maria Johnson)
**Store:** store-101
**Items:** SKU-1001 (Ibuprofen, qty 1), SKU-1002 (Vitamin D3, qty 2), SKU-1005 (Allergy Relief, qty 1)

**Expected pipeline behavior:**

1. History Agent finds Maria's Gold tier, penicillin allergy, previous purchases
2. Inventory Agent finds SKU-1001 in stock (24), SKU-1002 **out of stock** (0), SKU-1005 in stock (42)
3. Logistics Agent finds inbound shipment SHIP-5001 with SKU-1002 (60 units, ETA ~2 days)
4. DC Agent finds SKU-1002 available at DC-EAST-01 (1740 available) and DC-WEST-01 (900 available)
5. Provider Agent finds pending PO-8001 for SKU-1002 from VitaHealth Supply
6. Pharmacy Agent detects **drug interaction**: Ibuprofen + Lisinopril (moderate severity). Flags upcoming Lisinopril refill in 2 days.
7. Clinic Agent finds upcoming flu shot (5 days) and BP check (12 days). Surfaces Vitamin D recommendation from prior visit.
8. Synthesis produces order decision with pharmacy warning and clinic reminders

**Expected customer message traits:**
- Confirms in-stock items
- Provides ETA for Vitamin D3
- Warns about ibuprofen/Lisinopril interaction
- Recommends pharmacist consultation
- Reminds about upcoming appointments
- Acknowledges Gold loyalty status
