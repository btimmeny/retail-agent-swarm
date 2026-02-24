# Pipeline Run Logs


**Total runs:** 1
**Last updated:** 2026-02-24 02:55:11 UTC

| # | Timestamp | Order ID | Customer | Items | Agents | Duration | Fulfill | Log |
|---|-----------|----------|----------|-------|--------|----------|---------|-----|
| 1 | 2026-02-24 02:55:11 | `ORD-20260224025511` | `CUST-2001` | 3 | 7 | 33.54s | ❌ | [20260224_025511_ORD-20260224025511.json](20260224_025511_ORD-20260224025511.json) |

---

## Log File Contents

Each JSON log file contains:

- **`run_metadata`** — summary fields (order ID, customer, timing, fulfillment status)
- **`order_result`** — complete pipeline output including:
  - `pipeline_log` — per-agent responses, tool calls, durations, and thread assignments
  - `execution_timing` — phase-by-phase timing breakdown
  - `final_decision` — synthesized fulfillment plan, pharmacy flags, clinic reminders
  - `items_requested` — original order items
