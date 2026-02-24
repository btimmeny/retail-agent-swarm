"""
Run Logger  saves detailed pipeline execution logs to the runs/ directory.

Each run is saved as a timestamped JSON file with full pipeline details,
and a runs/INDEX.md is auto-generated as a summary table.

Data Retention & Deletion Policy:
- HIPAA: Retain logs for minimum 6 years (2190 days)
- PCI-DSS: Retain payment/order logs for minimum 2 years (730 days)
- This logger defaults to 6 years (2190 days) retention for all logs.
- Files older than retention period are securely deleted by cleanup_old_logs().
- cleanup_old_logs() is called at the start of save_run().
- For stricter requirements, schedule cleanup_old_logs() periodically.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
import copy
import sys

RUNS_DIR = Path(__file__).parent / "runs"

# PHI fields to redact or mask in logs
PHI_FIELDS_TO_REDACT = [
    # Top-level fields
    "customer_name", "customer_address", "customer_phone", "customer_email",
    # Nested fields in items_requested
    "prescription_details", "clinic_notes", "diagnosis", "medication_name", "dosage", "instructions",
    # Within pipeline_log agent responses
    "agent_response", "agent_notes", "pharmacy_details", "clinic_details",
    # Any other known PHI fields
]

REDACTION_STRING = "[REDACTED]"

# Retention policy (in days)
# HIPAA: 6 years (2190 days), PCI-DSS: 2 years (730 days)
# Default to 6 years for all logs
LOG_RETENTION_DAYS = 2190  # 6 years

# --- Structured JSON Logger ---
class StructuredLogger:
    """
    Structured JSON logger for pipeline events, agent invocations, and errors.
    Logs are written as JSON objects to stdout or a dedicated log file.
    """
    def __init__(self, log_to_file: bool = False, log_file_path: Optional[Path] = None):
        self.log_to_file = log_to_file
        self.log_file_path = log_file_path
        self._file_handle = None
        if self.log_to_file and self.log_file_path:
            self._file_handle = open(self.log_file_path, "a")

    def _emit(self, record: dict):
        json_record = json.dumps(record, default=str)
        # Always write to stdout
        print(json_record, file=sys.stdout, flush=True)
        # Optionally write to file
        if self.log_to_file and self._file_handle:
            print(json_record, file=self._file_handle, flush=True)

    def info(self, event: str, **kwargs):
        record = {
            "level": "INFO",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": event,
            **kwargs,
        }
        self._emit(record)

    def error(self, event: str, **kwargs):
        record = {
            "level": "ERROR",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": event,
            **kwargs,
        }
        self._emit(record)

    def close(self):
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

# Singleton logger instance for this module
# By default, logs to stdout only. To log to file, set log_to_file=True and provide a path.
log = StructuredLogger()


def sanitize_for_logging(order_result: dict) -> dict:
    """
    Remove or mask PHI fields from order_result before logging.
    Returns a sanitized deep copy.
    """
    def redact_dict(d: Dict[str, Any], parent_key="") -> Dict[str, Any]:
        sanitized = {}
        for k, v in d.items():
            # Redact if field is in PHI_FIELDS_TO_REDACT
            if k in PHI_FIELDS_TO_REDACT:
                sanitized[k] = REDACTION_STRING
            elif isinstance(v, dict):
                sanitized[k] = redact_dict(v, parent_key=k)
            elif isinstance(v, list):
                sanitized[k] = [redact_dict(i, parent_key=k) if isinstance(i, dict) else i for i in v]
            else:
                sanitized[k] = v
        return sanitized

    sanitized_result = copy.deepcopy(order_result)

    # Redact top-level PHI fields
    for field in PHI_FIELDS_TO_REDACT:
        if field in sanitized_result:
            sanitized_result[field] = REDACTION_STRING

    # Redact PHI in items_requested
    if "items_requested" in sanitized_result:
        sanitized_result["items_requested"] = [
            redact_dict(item) if isinstance(item, dict) else item
            for item in sanitized_result["items_requested"]
        ]

    # Redact PHI in pipeline_log agent responses
    if "pipeline_log" in sanitized_result:
        sanitized_result["pipeline_log"] = [
            redact_dict(agent_log) if isinstance(agent_log, dict) else agent_log
            for agent_log in sanitized_result["pipeline_log"]
        ]

    # Redact PHI in final_decision
    if "final_decision" in sanitized_result and isinstance(sanitized_result["final_decision"], dict):
        sanitized_result["final_decision"] = redact_dict(sanitized_result["final_decision"])

    return sanitized_result


def _extract_audit_log_ids(order_result: dict) -> Optional[list]:
    """
    Attempt to extract audit log IDs or references from the order_result.
    This assumes that audit log IDs are present in order_result["audit_log_ids"]
    or within pipeline_log entries as 'audit_log_id'.
    Returns a list of unique audit log IDs or None if not found.
    """
    audit_log_ids = set()
    # Check top-level
    if "audit_log_ids" in order_result and isinstance(order_result["audit_log_ids"], list):
        audit_log_ids.update(str(x) for x in order_result["audit_log_ids"] if x)
    # Check pipeline_log entries
    pipeline_log = order_result.get("pipeline_log", [])
    if isinstance(pipeline_log, list):
        for entry in pipeline_log:
            if isinstance(entry, dict):
                audit_id = entry.get("audit_log_id")
                if audit_id:
                    audit_log_ids.add(str(audit_id))
    # Optionally check other locations as needed
    if audit_log_ids:
        return sorted(audit_log_ids)
    return None


def cleanup_old_logs(retention_days: int = LOG_RETENTION_DAYS):
    """
    Delete run log files older than the retention period from runs/ directory.
    Args:
        retention_days: Number of days to retain logs (default: 2190 = 6 years)
    Procedure:
        - For each .json file in runs/, check last modified time.
        - If older than retention_days, securely delete the file.
        - (Optionally, implement archiving instead of deletion.)
    """
    if not RUNS_DIR.exists():
        return
    now = datetime.utcnow()
    cutoff = now - timedelta(days=retention_days)
    for file in RUNS_DIR.glob("*.json"):
        try:
            mtime = datetime.utcfromtimestamp(file.stat().st_mtime)
            if mtime < cutoff:
                # Secure deletion: overwrite then remove
                try:
                    with open(file, "r+b") as f:
                        length = file.stat().st_size
                        f.write(b"\x00" * length)
                        f.flush()
                        os.fsync(f.fileno())
                except Exception as e:
                    log.error('secure_delete_failed', path=str(file), error=str(e))
                file.unlink()
                log.info('old_log_deleted', path=str(file), deleted_at=datetime.utcnow().isoformat() + "Z")
        except Exception as e:
            log.error('cleanup_old_logs_error', path=str(file), error=str(e))
            continue  # Ignore errors for individual files


def save_run(order_result: dict) -> str:
    """
    Save a full pipeline result to runs/ as a JSON file.

    Args:
        order_result: The complete pipeline result dict from the orchestrator.

    Returns:
        The path to the saved log file.
    """
    RUNS_DIR.mkdir(exist_ok=True)

    # Enforce data retention policy before saving new run
    cleanup_old_logs()

    order_id = order_result.get("order_id", "unknown")
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{order_id}.json"
    filepath = RUNS_DIR / filename

    # Extract audit log references for traceability
    audit_log_ids = _extract_audit_log_ids(order_result)

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
            # AUDIT LOG REFERENCE for HIPAA/FDA 21 CFR Part 11 compliance
            "audit_log_ids": audit_log_ids,
        },
        # Store only sanitized order_result for logging
        "order_result": sanitize_for_logging(order_result),
    }

    try:
        with open(filepath, "w") as f:
            json.dump(log_entry, f, indent=2, default=str)
        log.info('run_saved', path=str(filepath), metadata=log_entry['run_metadata'])
    except Exception as e:
        log.error('run_save_failed', path=str(filepath), error=str(e))
        raise

    # Rebuild the index
    try:
        _rebuild_index()
        log.info('index_rebuilt', index_path=str(RUNS_DIR / "INDEX.md"))
    except Exception as e:
        log.error('index_rebuild_failed', error=str(e))

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
        "**Total runs:** {0}".format(len(run_files)),
        "**Last updated:** {0} UTC".format(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')),
        "",
        "| # | Timestamp | Order ID | Customer | Items | Agents | Duration | Fulfillment Status | Audit Log IDs | Log |",
        "|---|-----------|----------|----------|-------|--------|----------|-------------------|---------------|-----|",
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
            # Accessibility: Use clear text for status, not icons or color
            if can_fulfill is True:
                fulfill_str = "Fulfilled"
            elif can_fulfill is False:
                fulfill_str = "Not Fulfilled"
            elif can_fulfill is None:
                fulfill_str = "Unknown"
            else:
                fulfill_str = str(can_fulfill)
            audit_log_ids = meta.get("audit_log_ids")
            if audit_log_ids is None:
                audit_log_ids_str = "-"
            elif isinstance(audit_log_ids, list):
                audit_log_ids_str = ", ".join(str(x) for x in audit_log_ids)
            else:
                audit_log_ids_str = str(audit_log_ids)
            lines.append(
                f"| {i} | {ts} | `{order_id}` | `{customer}` | {items} | {agents} | {duration} | {fulfill_str} | {audit_log_ids_str} | [{run_file.name}]({run_file.name}) |"
            )
        except (json.JSONDecodeError, KeyError) as e:
            lines.append(f"| {i} | ? | ? | ? | ? | ? | ? | ? | - | [{run_file.name}]({run_file.name}) |")
            log.error('index_entry_failed', file=str(run_file), error=str(e))

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Log File Contents")
    lines.append("")
    lines.append("Each JSON log file contains:")
    lines.append("")
    lines.append("- **`run_metadata`**: summary fields (order ID, customer, timing, fulfillment status, audit log references)")
    lines.append("- **`order_result`**: sanitized pipeline output (PHI redacted) including:")
    lines.append("  - `pipeline_log`: per-agent responses, tool calls, durations, and thread assignments (PHI redacted)")
    lines.append("  - `execution_timing`: phase-by-phase timing breakdown")
    lines.append("  - `final_decision`: synthesized fulfillment plan, pharmacy flags, clinic reminders (PHI redacted)")
    lines.append("  - `items_requested`: original order items (PHI redacted)")
    lines.append("")

    index_path = RUNS_DIR / "INDEX.md"
    with open(index_path, "w") as f:
        f.write("\n".join(lines))

