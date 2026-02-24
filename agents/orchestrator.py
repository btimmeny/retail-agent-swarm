"""
Orchestrator Agent — coordinates the full order pipeline across all domain agents.

Parallel execution strategy (4 phases instead of 7 sequential calls):

  Phase 1 ─ PARALLEL: Customer History + Store Inventory
       │                  (independent — one needs customer_id, other needs store+SKUs)
       ▼
  Phase 2 ─ SEQUENTIAL: Logistics
       │                  (depends on Phase 1 — needs out-of-stock SKUs from inventory)
       ▼
  Phase 3 ─ PARALLEL: Distribution Center + Provider + Pharmacy + Clinic
       │                  (all independent — DC/Provider use SKU list,
       │                   Pharmacy/Clinic use customer_id)
       ▼
  Phase 4 ─ SEQUENTIAL: Synthesis
                          (depends on all previous results)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from datetime import datetime
from typing import Any

from agents.base import Agent, get_client
from agents import (
    inventory_agent,
    logistics_agent,
    distribution_agent,
    provider_agent,
    history_agent,
    pharmacy_agent,
    clinic_agent,
)

log = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates the agent swarm to process an order end-to-end with parallel execution."""

    MAX_WORKERS = 4  # Max threads for parallel agent calls

    def __init__(self):
        self.inventory = inventory_agent.create()
        self.logistics = logistics_agent.create()
        self.distribution = distribution_agent.create()
        self.provider = provider_agent.create()
        self.history = history_agent.create()
        self.pharmacy = pharmacy_agent.create()
        self.clinic = clinic_agent.create()
        self._executor = ThreadPoolExecutor(
            max_workers=self.MAX_WORKERS,
            thread_name_prefix="agent-worker",
        )

    def process_order(
        self,
        customer_id: str,
        store_id: str,
        items: list[dict],
    ) -> dict:
        """
        Process a full order through the agent pipeline with parallel execution.

        Args:
            customer_id: Customer placing the order
            store_id: Store the order is placed at
            items: List of {"sku": str, "qty": int}

        Returns:
            Complete pipeline result with all agent responses, timing, and final decision.
        """
        pipeline_log: list[dict] = []
        phase_timings: list[dict] = []
        pipeline_start = time.monotonic()

        sku_list = [item["sku"] for item in items]
        sku_str = ", ".join(sku_list)
        items_desc = json.dumps(items)

        # ━━ Phase 1 ━━ PARALLEL: Customer History + Store Inventory ━━━
        phase_start = time.monotonic()
        log.info("Phase 1: launching Customer History + Store Inventory in parallel")

        history_future = self._submit_agent(
            self.history,
            f"Look up customer {customer_id}. Get their profile, recent orders, "
            f"and frequently purchased items. They are ordering: {items_desc}",
        )
        inventory_future = self._submit_agent(
            self.inventory,
            f"Check stock at {store_id} for these SKUs: {sku_str}. "
            f"The customer wants these quantities: {items_desc}",
        )

        history_result = self._collect(history_future, pipeline_log)
        inventory_result = self._collect(inventory_future, pipeline_log)

        phase_timings.append({
            "phase": 1,
            "agents": ["CustomerHistoryAgent", "StoreInventoryAgent"],
            "mode": "parallel",
            "duration_sec": round(time.monotonic() - phase_start, 2),
        })

        # Determine which items are out of stock or low
        out_of_stock_skus = self._extract_out_of_stock(inventory_result, items)

        # ━━ Phase 2 ━━ SEQUENTIAL: Logistics (conditional) ━━━━━━━━━━━
        phase_start = time.monotonic()
        logistics_result = None
        if out_of_stock_skus:
            log.info("Phase 2: out-of-stock SKUs detected %s — running Logistics", out_of_stock_skus)
            logistics_result = self._run_agent_sync(
                self.logistics,
                f"Check inbound shipments to {store_id} for these SKUs that are "
                f"out of stock or low: {', '.join(out_of_stock_skus)}. "
                f"When is the next delivery expected?",
                pipeline_log,
            )
        else:
            log.info("Phase 2: all items in stock — skipping Logistics")

        phase_timings.append({
            "phase": 2,
            "agents": ["LogisticsAgent"] if out_of_stock_skus else [],
            "mode": "sequential (conditional)",
            "skipped": not bool(out_of_stock_skus),
            "duration_sec": round(time.monotonic() - phase_start, 2),
        })

        # ━━ Phase 3 ━━ PARALLEL: DC + Provider + Pharmacy + Clinic ━━━
        phase_start = time.monotonic()
        log.info("Phase 3: launching DC + Provider + Pharmacy + Clinic in parallel")

        dc_future = self._submit_agent(
            self.distribution,
            f"Check all distribution centers serving {store_id} for SKUs: {sku_str}. "
            f"Report availability and whether any DCs need to reorder. "
            f"Out-of-stock at store level: {', '.join(out_of_stock_skus) if out_of_stock_skus else 'none'}",
        )
        pharmacy_future = self._submit_agent(
            self.pharmacy,
            f"Check pharmacy context for customer {customer_id}. "
            f"They are ordering these SKUs: {sku_str}. "
            f"Check for active prescriptions, upcoming refills, drug interactions "
            f"with the ordered items, and any pharmacist alerts.",
        )
        clinic_future = self._submit_agent(
            self.clinic,
            f"Check clinic context for customer {customer_id}. "
            f"Do they have upcoming appointments? Any wellness recommendations "
            f"that relate to the items they're ordering ({sku_str})?",
        )

        # DC must finish before Provider (Provider uses DC assessment as context)
        dc_result = self._collect(dc_future, pipeline_log)

        # Now launch Provider with DC context — it runs in parallel with Pharmacy/Clinic
        provider_future = self._submit_agent(
            self.provider,
            f"Check supplier status for SKUs: {sku_str}. "
            f"Are there pending purchase orders? What are lead times? "
            f"If DC stock is low, consider recommending a restock order.",
            context={"dc_assessment": dc_result.get("response", "")},
        )

        # Collect remaining Phase 3 agents (Pharmacy, Clinic, Provider finish in any order)
        pharmacy_result = self._collect(pharmacy_future, pipeline_log)
        clinic_result = self._collect(clinic_future, pipeline_log)
        provider_result = self._collect(provider_future, pipeline_log)

        phase_timings.append({
            "phase": 3,
            "agents": ["DistributionCenterAgent", "ProviderAgent", "PharmacyAgent", "ClinicAgent"],
            "mode": "parallel (DC first, then Provider || Pharmacy || Clinic)",
            "duration_sec": round(time.monotonic() - phase_start, 2),
        })

        # ━━ Phase 4 ━━ SEQUENTIAL: Synthesis ━━━━━━━━━━━━━━━━━━━━━━━━━
        phase_start = time.monotonic()
        log.info("Phase 4: synthesizing final decision")

        final_decision = self._synthesize(
            customer_id=customer_id,
            store_id=store_id,
            items=items,
            history=history_result,
            inventory=inventory_result,
            logistics=logistics_result,
            distribution=dc_result,
            provider=provider_result,
            pharmacy=pharmacy_result,
            clinic=clinic_result,
        )

        phase_timings.append({
            "phase": 4,
            "agents": ["SynthesisLLM"],
            "mode": "sequential",
            "duration_sec": round(time.monotonic() - phase_start, 2),
        })

        total_duration = round(time.monotonic() - pipeline_start, 2)
        log.info("Pipeline complete in %.2fs", total_duration)

        return {
            "order_id": f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "customer_id": customer_id,
            "store_id": store_id,
            "items_requested": items,
            "pipeline_log": pipeline_log,
            "execution_timing": {
                "total_duration_sec": total_duration,
                "phases": phase_timings,
            },
            "final_decision": final_decision,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── Agent execution helpers ───────────────────────────────────────

    def _submit_agent(
        self,
        agent: Agent,
        message: str,
        context: dict | None = None,
    ) -> Future:
        """Submit an agent to run on the thread pool. Returns a Future."""
        return self._executor.submit(self._run_agent_work, agent, message, context)

    def _run_agent_work(
        self,
        agent: Agent,
        message: str,
        context: dict | None = None,
    ) -> dict:
        """The actual work function executed in a worker thread."""
        start = time.monotonic()
        result = agent.run(message, context=context)
        result["_duration_sec"] = round(time.monotonic() - start, 2)
        result["_thread"] = threading.current_thread().name
        log.info(
            "%s completed in %.2fs on %s",
            result["agent"], result["_duration_sec"], result["_thread"],
        )
        return result

    def _collect(self, future: Future, pipeline_log: list[dict]) -> dict:
        """Block until a Future resolves, then append to the pipeline log."""
        result = future.result()  # blocks until done
        pipeline_log.append({
            "agent": result["agent"],
            "response": result["response"],
            "tools_used": [tc["tool"] for tc in result["tool_calls_made"]],
            "tool_details": result["tool_calls_made"],
            "duration_sec": result.get("_duration_sec"),
            "thread": result.get("_thread"),
        })
        return result

    def _run_agent_sync(
        self,
        agent: Agent,
        message: str,
        pipeline_log: list[dict],
        context: dict | None = None,
    ) -> dict:
        """Run a single agent synchronously (for sequential phases)."""
        start = time.monotonic()
        result = agent.run(message, context=context)
        duration = round(time.monotonic() - start, 2)
        pipeline_log.append({
            "agent": result["agent"],
            "response": result["response"],
            "tools_used": [tc["tool"] for tc in result["tool_calls_made"]],
            "tool_details": result["tool_calls_made"],
            "duration_sec": duration,
            "thread": "main",
        })
        return result

    def _extract_out_of_stock(self, inventory_result: dict, items: list[dict]) -> list[str]:
        """Determine which SKUs are out of stock or have insufficient quantity."""
        out_of_stock = []
        raw = inventory_result.get("raw_data", {})

        # Check from tool call results
        for tool_name, result in raw.items():
            if tool_name == "check_multiple" and isinstance(result, list):
                for item_result in result:
                    if isinstance(item_result, dict):
                        if not item_result.get("in_stock", True) or item_result.get("needs_reorder", False):
                            sku = item_result.get("sku")
                            if sku:
                                out_of_stock.append(sku)
            elif tool_name == "check_stock" and isinstance(result, dict):
                if not result.get("in_stock", True) or result.get("needs_reorder", False):
                    sku = result.get("sku")
                    if sku:
                        out_of_stock.append(sku)

        # If we couldn't parse tool results, check the text response for clues
        if not out_of_stock:
            response_text = inventory_result.get("response", "").lower()
            for item in items:
                sku = item["sku"]
                if "out of stock" in response_text and sku.lower() in response_text:
                    out_of_stock.append(sku)
                elif "not in stock" in response_text and sku.lower() in response_text:
                    out_of_stock.append(sku)

        return list(set(out_of_stock))

    def _synthesize(self, **kwargs) -> dict:
        """Use the orchestrator LLM to synthesize all agent outputs into a final decision."""
        agent_summaries = []
        for key in ["history", "inventory", "logistics", "distribution", "provider", "pharmacy", "clinic"]:
            result = kwargs.get(key)
            if result and isinstance(result, dict):
                agent_summaries.append(f"**{key.upper()} AGENT**: {result.get('response', 'No response')}")

        synthesis_prompt = f"""You are the Order Orchestrator for a retail pharmacy chain.
You have received reports from all domain agents about an order.

Customer: {kwargs['customer_id']}
Store: {kwargs['store_id']}
Items Requested: {json.dumps(kwargs['items'])}

Agent Reports:
{chr(10).join(agent_summaries)}

Based on all agent reports, produce a final order decision in this JSON structure:
{{
    "can_fulfill": true/false,
    "fulfillment_plan": [
        {{"sku": "...", "status": "in_stock|backordered|arriving_soon", "action": "...", "eta": "..."}}
    ],
    "pharmacy_flags": ["list of any pharmacy warnings or required consultations"],
    "clinic_reminders": ["list of any clinic appointment reminders or wellness suggestions"],
    "personalization_notes": ["list of personalized suggestions based on customer history"],
    "customer_message": "A friendly, concise message to the customer summarizing their order status"
}}

RULES:
- If all items are in stock, confirm the order
- If some items are backordered, provide ETAs and offer alternatives
- Always include pharmacy warnings if drug interactions were detected
- Include clinic reminders if the customer has upcoming appointments
- Personalize based on customer history and loyalty tier
- The customer_message should be warm, professional, and actionable
"""

        client = get_client()
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": synthesis_prompt}],
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response.choices[0].message.content)
        except (json.JSONDecodeError, TypeError):
            return {
                "can_fulfill": False,
                "error": "Failed to synthesize agent reports",
                "raw_response": response.choices[0].message.content,
            }
