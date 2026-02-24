"""
Run Logger — saves detailed pipeline execution logs to the runs/ directory.

Each run is saved as a timestamped JSON file with full pipeline details,
and a runs/INDEX.md is auto-generated as a summary table.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

RUNS_DIR = Path(__file__).parent / "runs"


def save_run(order_result: dict) -> str:
    """
    Save a full pipeline result to runs/ as a JSON file.

    Args:
        order_result: The complete pipeline result dict from the orchestrator.

    Returns:
        The path to the saved log file.
    """
    RUNS_DIR.mkdir(exist_ok=True)

    order_id = order_result.get("order_id", "unknown")
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{order_id}.json"
    filepath = RUNS_DIR / filename

    # Build the log entry with extra metadata
    log_entry = {
        "run_metadata": {
            "saved_at": datetime.utcnow().isoformat() + "Z",
            "log_file": filename,
            "order_id": order_id,
            "customer_id": order_result.get("customer_id"),
            "store_id": order_result.get("store_id"),
            "items_count": len(order_result.get("items_requested", [])),
            "agents_executed": len(order_result.get("pipeline_log", [])),
            "total_duration_sec": order_result.get("execution_timing", {}).get("total_duration_sec"),
            "can_fulfill": order_result.get("final_decision", {}).get("can_fulfill"),
        },
        "order_result": order_result,
    }

    with open(filepath, "w") as f:
        json.dump(log_entry, f, indent=2, default=str)

    # Rebuild the index
    _rebuild_index()

    return str(filepath)


def _rebuild_index():
    """Rebuild runs/INDEX.md from all saved run files."""
    if not RUNS_DIR.exists():
        return

    run_files = sorted(RUNS_DIR.glob("*.json"), reverse=True)
    if not run_files:
        return

    lines = [
        "# Pipeline Run Logs\n",
        "",
        f"**Total runs:** {len(run_files)}",
        f"**Last updated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "| # | Timestamp | Order ID | Customer | Items | Agents | Duration | Fulfill | Log |",
        "|---|-----------|----------|----------|-------|--------|----------|---------|-----|",
    ]

    for i, run_file in enumerate(run_files, 1):
        try:
            with open(run_file) as f:
                data = json.load(f)
            meta = data.get("run_metadata", {})
            ts = meta.get("saved_at", "?")[:19].replace("T", " ")
            order_id = meta.get("order_id", "?")
            customer = meta.get("customer_id", "?")
            items = meta.get("items_count", "?")
            agents = meta.get("agents_executed", "?")
            duration = meta.get("total_duration_sec", "?")
            if isinstance(duration, (int, float)):
                duration = f"{duration}s"
            can_fulfill = meta.get("can_fulfill")
            fulfill_str = "✅" if can_fulfill else ("❌" if can_fulfill is False else "?")
            lines.append(
                f"| {i} | {ts} | `{order_id}` | `{customer}` | {items} | {agents} | {duration} | {fulfill_str} | [{run_file.name}]({run_file.name}) |"
            )
        except (json.JSONDecodeError, KeyError):
            lines.append(f"| {i} | ? | ? | ? | ? | ? | ? | ? | [{run_file.name}]({run_file.name}) |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Log File Contents")
    lines.append("")
    lines.append("Each JSON log file contains:")
    lines.append("")
    lines.append("- **`run_metadata`** — summary fields (order ID, customer, timing, fulfillment status)")
    lines.append("- **`order_result`** — complete pipeline output including:")
    lines.append("  - `pipeline_log` — per-agent responses, tool calls, durations, and thread assignments")
    lines.append("  - `execution_timing` — phase-by-phase timing breakdown")
    lines.append("  - `final_decision` — synthesized fulfillment plan, pharmacy flags, clinic reminders")
    lines.append("  - `items_requested` — original order items")
    lines.append("")

    index_path = RUNS_DIR / "INDEX.md"
    with open(index_path, "w") as f:
        f.write("\n".join(lines))
