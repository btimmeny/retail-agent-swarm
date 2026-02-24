# SPECIFICATION.md

## Project Overview and Purpose

This project implements a multi-agent orchestration platform for a retail pharmacy chain, supporting order fulfillment, inventory management, pharmacy compliance, logistics tracking, and customer service via a REST API. The system simulates real-world pharmacy operations, including HIPAA-compliant access to sensitive health data, safe conversational AI for customer interactions, and robust guardrails for data privacy, safety, and regulatory compliance.

The platform is designed to:
- Automate and coordinate order processing across inventory, pharmacy, logistics, and clinic systems.
- Provide a safe, helpful, and compliant conversational interface for customers.
- Ensure all agent actions are auditable, secure, and adhere to healthcare and retail industry standards.

---

## Functional Requirements

| ID   | Requirement                                                                                       |
|------|---------------------------------------------------------------------------------------------------|
| FR1  | Accept customer orders via REST API and process them through the multi-agent pipeline.            |
| FR2  | Check and reserve store inventory for ordered items.                                              |
| FR3  | Query distribution centers for stock and allocate replenishments as needed.                       |
| FR4  | Manage supplier relationships and create restock orders when DC stock is low.                     |
| FR5  | Track inbound logistics shipments and provide ETAs for out-of-stock items.                        |
| FR6  | Retrieve and summarize customer pharmacy data (prescriptions, refills, alerts) with HIPAA guardrails. |
| FR7  | Retrieve and summarize customer clinic data (appointments, wellness recommendations) with audit logging. |
| FR8  | Provide a customer-facing chat interface with strict safety, privacy, and escalation guardrails.  |
| FR9  | Enforce authentication, authorization, and PHI redaction for all sensitive data access.           |
| FR10 | Log all agent actions and data access for audit and compliance.                                   |
| FR11 | Provide APIs for order status, chat history, and agent pipeline logs.                             |
| FR12 | Support smoke/integration tests for end-to-end pipeline validation.                               |

---

## Data Models and Schemas

### Order Models (`models.py`)

```python
class OrderItem(BaseModel):
    sku: str
    qty: int

class OrderRequest(BaseModel):
    customer_id: str
    store_id: str
    items: list[OrderItem]

class ChatMessage(BaseModel):
    customer_id: str
    message: str

class ChatStartRequest(BaseModel):
    customer_id: str
    order_id: str
```

#### Example: OrderRequest
```json
{
  "customer_id": "CUST-2001",
  "store_id": "store-101",
  "items": [
    {"sku": "SKU-1001", "qty": 1},
    {"sku": "SKU-1002", "qty": 2}
  ]
}
```

### Inventory/Distribution/Provider Data

- **Store Inventory:** `{store_id: {sku: {on_hand, reserved, aisle, ...}}}`
- **Distribution Center:** `{dc_id: {sku: {on_hand, allocated, reorder_point, ...}}}`
- **Suppliers:** `{supplier_id: {name, skus, lead_time_days, min_order_qty, reliability_score, ...}}`
- **Pending Purchase Orders:** `[{"po_id", "supplier_id", "sku", "qty", ...}]`

### Pharmacy/Clinic/Customer Data

- **Prescriptions:** `{customer_id: [rx_dict, ...]}`
- **Pharmacist Alerts:** `{customer_id: [alert_dict, ...]}`
- **Appointments:** `{customer_id: [appt_dict, ...]}`
- **Immunization Records:** `{customer_id: [record_dict, ...]}`
- **Wellness Recommendations:** `{customer_id: [rec_dict, ...]}`

---

## API Contracts

### Health Check

- **GET /health**
  - **Response:** `{"status": "ok"}`

### Orders

- **POST /orders**
  - **Request:** `OrderRequest`
  - **Response:** 
    ```json
    {
      "order_id": "ORD-...",
      "can_fulfill": true,
      "customer_message": "...",
      "pharmacy_flags": [...],
      "clinic_reminders": [...],
      "execution_timing": {...}
    }
    ```
  - **Status:** `202 Accepted`

- **GET /orders/{order_id}**
  - **Response:** 
    ```json
    {
      "order_id": "...",
      "status": "...",
      "pipeline_log": [...],
      "final_decision": {...}
    }
    ```

### Chat

- **POST /chat/start**
  - **Request:** `ChatStartRequest`
  - **Response:** 
    ```json
    {
      "greeting": "Welcome, ...",
      "context_summary": "..."
    }
    ```

- **POST /chat/message**
  - **Request:** `ChatMessage`
  - **Response:** 
    ```json
    {
      "response": "..."
    }
    ```

- **GET /chat/{customer_id}/history**
  - **Response:** 
    ```json
    {
      "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
      ]
    }
    ```

---

## Agent Behaviors and Responsibilities

| Agent                  | Responsibilities                                                                                                   |
|------------------------|--------------------------------------------------------------------------------------------------------------------|
| CustomerAgent          | Conversational interface for customers. Applies guardrails for safety, privacy, and escalation.                    |
| InventoryAgent         | Checks/reserves store inventory. Reports stock, aisle, reorder needs.                                              |
| DistributionAgent      | Checks DC stock, allocates replenishments, flags reorder needs at DC level.                                        |
| ProviderAgent          | Manages supplier relationships, checks pending POs, creates restock orders.                                        |
| LogisticsAgent         | Tracks inbound shipments, provides ETAs, shipment details, and status.                                             |
| PharmacyAgent          | Retrieves prescriptions, refills, alerts, and checks drug interactions. Enforces HIPAA guardrails and redaction.   |
| ClinicAgent            | Retrieves appointments, immunizations, wellness recommendations. Logs all access for audit.                        |
| HistoryAgent           | Looks up customer profile, order history, frequently purchased items. Enforces HIPAA guardrails and redaction.     |
| Orchestrator           | Coordinates agent pipeline for order fulfillment and chat context assembly.                                         |

---

## Guardrails and Safety Rules

### General Guardrails

- **No Medical Advice:** Never diagnose, recommend dosages, or suggest treatments. Always escalate to a pharmacist for such queries.
- **PHI Protection:** All access to protected health information (PHI) requires authentication, role-based authorization, and PHI redaction in responses/logs.
- **Data Privacy:** Never share raw customer data (address, phone, email, full history) in chat. Summarize only.
- **Stock/Price Accuracy:** Only quote confirmed inventory and prices. Never guess.
- **Escalation:** Escalate complex, sensitive, or frustrated customer situations to a human associate.
- **Audit Logging:** All access to sensitive data (pharmacy, clinic, customer history) is logged for compliance.

### Agent-Specific Guardrails

- **PharmacyAgent:** Enforces HIPAA, PHI redaction, and minimum necessary disclosure. No prescription info to unauthenticated users.
- **CustomerAgent:** Applies strict conversational guardrails (see `GUARDRAILS` in code) for safety, privacy, and regulatory compliance.
- **HistoryAgent/ClinicAgent:** Redact PHI for unauthorized requests. Log all access.
- **All Agents:** Never speculate about data not checked. Respond with factual, structured data.

---

## Acceptance Criteria

| ID   | Criteria                                                                                                       |
|------|---------------------------------------------------------------------------------------------------------------|
| AC1  | Orders submitted via API are processed through all relevant agents, with each agent performing its role.       |
| AC2  | InventoryAgent accurately reports and reserves stock, failing gracefully if out of stock.                      |
| AC3  | DistributionAgent allocates from DCs and flags reorder needs if thresholds are crossed.                       |
| AC4  | ProviderAgent creates restock orders with correct supplier, lead time, and min order qty.                     |
| AC5  | LogisticsAgent provides accurate ETAs and shipment details for inbound stock.                                  |
| AC6  | PharmacyAgent enforces authentication, role checks, and PHI redaction; flags drug interactions correctly.      |
| AC7  | ClinicAgent logs all access and provides accurate appointment/wellness info.                                   |
| AC8  | CustomerAgent never violates guardrails (no medical advice, no PHI leaks, proper escalation, etc.).           |
| AC9  | All sensitive data access is logged and auditable.                                                             |
| AC10 | All API endpoints return correct status codes, schemas, and error messages as specified.                       |
| AC11 | End-to-end smoke tests pass, demonstrating the full order and chat pipeline.                                   |

---

## Appendix: Example Agent Pipeline (Order Processing)

1. **Order Received:** Orchestrator receives `OrderRequest`.
2. **InventoryAgent:** Checks/reserves store stock for each item.
3. **DistributionAgent:** If out of stock, checks DCs and allocates replenishment.
4. **ProviderAgent:** If DC stock is low, creates restock PO with supplier.
5. **LogisticsAgent:** Checks inbound shipments for ETAs on out-of-stock items.
6. **PharmacyAgent:** Checks prescriptions, refills, drug interactions, and alerts (with HIPAA guardrails).
7. **ClinicAgent:** Retrieves upcoming appointments and wellness recommendations (with audit logging).
8. **HistoryAgent:** Summarizes customer profile and purchasing patterns (with PHI redaction as needed).
9. **CustomerAgent:** Assembles a safe, personalized message for the customer, applying all conversational guardrails.
10. **Response:** API returns order status, customer message, and pipeline log.

---

## References

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DESIGN.md](DESIGN.md)
- [README.md](README.md)
- [smoke_test.py](smoke_test.py) for end-to-end test scenarios

---

**End of SPECIFICATION.md**