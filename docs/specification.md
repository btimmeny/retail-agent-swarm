# SPECIFICATION.md

---

## Project Overview and Purpose

This project implements a **multi-agent orchestration system** for a retail pharmacy chain, supporting order fulfillment, customer support, and domain-specific reasoning across inventory, logistics, pharmacy, clinic, and supplier operations. The system leverages a swarm of specialized AI agents, each with domain-specific tools and guardrails, to process customer orders, answer questions, and coordinate fulfillment across the supply chain.

The primary goals are:
- **Automated, safe, and explainable order fulfillment** for retail pharmacy customers.
- **Domain-aware conversational support** for customers (e.g., order status, health reminders, inventory).
- **End-to-end traceability** and auditability of pipeline decisions via structured logs.

---

## Functional Requirements

| ID     | Requirement Description                                                                                       |
|--------|--------------------------------------------------------------------------------------------------------------|
| FR-001 | Accept customer orders via REST API, including multiple SKUs and quantities.                                 |
| FR-002 | Check local store inventory for requested items and reserve stock if available.                              |
| FR-003 | If items are out of stock, check inbound shipments and provide ETA details.                                  |
| FR-004 | If store and inbound are insufficient, check distribution center (DC) stock and allocate replenishment.      |
| FR-005 | If DC stock is low, check supplier pipeline and create restock orders as needed.                             |
| FR-006 | For each order, check customer pharmacy profile for active prescriptions, refills, and interaction warnings. |
| FR-007 | Surface pharmacist alerts and require pharmacist review if drug interactions are detected.                   |
| FR-008 | Integrate in-store clinic data: appointments, immunizations, and wellness recommendations.                   |
| FR-009 | Provide customers with order status, fulfillment plan, and relevant health reminders.                        |
| FR-010 | Support customer chat sessions for order follow-up and Q&A.                                                  |
| FR-011 | Log all pipeline runs with agent-level details for audit and traceability.                                   |
| FR-012 | Enforce domain-specific safety guardrails (e.g., no medical advice, privacy).                               |
| FR-013 | Provide REST API endpoints for order placement, order status, chat, and health checks.                      |

---

## Data Models and Schemas

### Order Models

```python
class OrderItem(BaseModel):
    sku: str
    qty: int

class OrderRequest(BaseModel):
    customer_id: str
    store_id: str
    items: list[OrderItem]
```

### Chat Models

```python
class ChatMessage(BaseModel):
    customer_id: str
    message: str

class ChatStartRequest(BaseModel):
    customer_id: str
    order_id: str
```

### Inventory Model (Store-level)

```json
{
  "sku": "SKU-1001",
  "store_id": "store-101",
  "name": "Ibuprofen 200mg 100ct",
  "in_stock": true,
  "on_hand": 24,
  "aisle": "Pharmacy-A3",
  "price": 8.99,
  "needs_reorder": false
}
```

### Distribution Center Inventory

```json
{
  "dc_id": "DC-EAST-01",
  "sku": "SKU-1001",
  "name": "Ibuprofen 200mg 100ct",
  "on_hand": 2400,
  "allocated": 200,
  "available": 2200,
  "needs_reorder": false
}
```

### Inbound Shipment

```json
{
  "shipment_id": "SHIP-5001",
  "destination_store": "store-101",
  "origin": "DC-EAST-01",
  "carrier": "FedEx Freight",
  "status": "in_transit",
  "eta": "2024-06-18T12:00:00Z",
  "items": [
    {"sku": "SKU-1002", "qty": 60, "name": "Vitamin D3 2000IU 90ct"}
  ]
}
```

### Supplier/Purchase Order

```json
{
  "po_id": "PO-8001",
  "supplier_id": "SUP-002",
  "sku": "SKU-1002",
  "qty": 500,
  "status": "confirmed",
  "ordered_at": "2024-06-10T14:00:00Z",
  "expected_delivery": "2024-06-20T14:00:00Z",
  "destination_dc": "DC-EAST-01"
}
```

### Pharmacy Profile

```json
{
  "rx_id": "RX-3001",
  "medication": "Lisinopril 10mg",
  "status": "active",
  "refills_remaining": 3,
  "next_refill_due": "2024-06-20T00:00:00Z"
}
```

### Clinic Data

```json
{
  "appt_id": "APPT-4001",
  "type": "Annual Flu Shot",
  "scheduled_at": "2024-06-18T10:00:00Z",
  "status": "confirmed",
  "location": "store-101 Clinic Room A"
}
```

---

## API Contracts

### Health Check

- **GET /health**
  - **Response**: `{ "status": "ok" }`

### Place Order

- **POST /orders**
  - **Request Body**: `OrderRequest`
  - **Response**: 
    ```json
    {
      "order_id": "ORD-202406170001",
      "can_fulfill": true,
      "customer_message": "...",
      "pharmacy_flags": [...],
      "clinic_reminders": [...],
      "execution_timing": {...},
      "pipeline_log": [...],
      "items_requested": [...]
    }
    ```
  - **Status**: `202 Accepted`

### Get Order Status

- **GET /orders/{order_id}**
  - **Response**: Full pipeline log and final decision for the order.

### Start Customer Chat

- **POST /chat/start**
  - **Request Body**: `ChatStartRequest`
  - **Response**:
    ```json
    {
      "greeting": "Welcome back, Maria! Your order ORD-202406170001 is being prepared...",
      "order_id": "ORD-202406170001"
    }
    ```

### Send Chat Message

- **POST /chat/message**
  - **Request Body**: `ChatMessage`
  - **Response**:
    ```json
    {
      "response": "Vitamin D3 is expected to arrive in 2 days. Ibuprofen may interact with your Lisinopril prescription..."
    }
    ```

### Get Chat History

- **GET /chat/{customer_id}/history**
  - **Response**:
    ```json
    {
      "messages": [
        {"role": "customer", "message": "..."},
        {"role": "agent", "message": "..."}
      ]
    }
    ```

---

## Agent Behaviors and Responsibilities

| Agent Name                | Responsibilities                                                                                                   |
|---------------------------|-------------------------------------------------------------------------------------------------------------------|
| **StoreInventoryAgent**   | Check/reserve store stock, report aisle, flag reorder needs.                                                      |
| **LogisticsAgent**        | Track inbound shipments, report ETAs, carrier/status, and quantities.                                             |
| **DistributionCenterAgent** | Check DC stock, allocate replenishment, flag DC reorder needs.                                                  |
| **ProviderAgent**         | Manage supplier relationships, check pending purchase orders, create restock orders.                              |
| **PharmacyAgent**         | Check prescriptions, refills, drug interactions, pharmacist alerts; flag for pharmacist review if needed.         |
| **ClinicAgent**           | Surface clinic appointments, immunization history, wellness recommendations; enforce medical guardrails.           |
| **CustomerHistoryAgent**  | Retrieve customer profile, order history, frequently purchased items, and allergy flags for personalization.       |

---

## Guardrails and Safety Rules

| Domain        | Guardrail / Rule                                                                                      |
|---------------|------------------------------------------------------------------------------------------------------|
| Clinic        | Never diagnose or provide medical advice; recommendations are informational only.                     |
| Clinic        | Appointment details only to authenticated customers.                                                  |
| Clinic        | For health concerns, direct to clinic provider.                                                       |
| Pharmacy      | Never provide medical advice or dosage recommendations.                                               |
| Pharmacy      | Always recommend consulting pharmacist for interactions.                                              |
| Pharmacy      | Flag high-severity alerts; require pharmacist review for interactions.                               |
| Customer Data | Never share raw customer data externally; only summarize insights.                                    |
| All           | Only operate within assigned domain; do not speculate outside data/tools.                             |
| All           | Log all actions and tool calls for auditability.                                                      |

---

## Acceptance Criteria

| ID     | Acceptance Criteria                                                                                  |
|--------|-----------------------------------------------------------------------------------------------------|
| AC-001 | Orders with all items in stock at store are fulfilled and reserved, with confirmation message.       |
| AC-002 | Orders with out-of-stock items provide ETA from inbound shipments or DC replenishment.               |
| AC-003 | If DC and inbound are insufficient, system creates supplier restock order and notifies customer.     |
| AC-004 | Drug interactions are detected and flagged; customer is advised to consult pharmacist.              |
| AC-005 | Clinic reminders and wellness recommendations are surfaced in order summary and chat.                |
| AC-006 | All agent actions, tool calls, and pipeline decisions are logged per run.                            |
| AC-007 | REST API endpoints respond with correct status codes and data schemas.                               |
| AC-008 | Customer chat supports order follow-up and Q&A, with agent responses grounded in pipeline data.      |
| AC-009 | Guardrails are enforced: no medical advice, privacy, and domain boundaries are respected.            |
| AC-010 | Smoke test passes: end-to-end order, chat, and status flows are exercised successfully.              |

---

## Appendix: Example Pipeline Flow

1. **Customer places order** → `/orders`  
2. **StoreInventoryAgent** checks/reserves stock  
3. If out of stock, **LogisticsAgent** checks inbound shipments  
4. If still insufficient, **DistributionCenterAgent** checks/allocates DC stock  
5. If DC low, **ProviderAgent** checks supplier pipeline/creates restock  
6. **PharmacyAgent** checks prescriptions, refills, interactions, and flags alerts  
7. **ClinicAgent** surfaces appointments, immunizations, wellness recommendations  
8. **CustomerHistoryAgent** provides personalization context  
9. **Orchestrator** synthesizes fulfillment plan and customer message  
10. **RunLogger** saves full pipeline log for traceability  
11. **Customer can follow up via chat** (`/chat/start`, `/chat/message`)  

---

**End of SPECIFICATION.md**