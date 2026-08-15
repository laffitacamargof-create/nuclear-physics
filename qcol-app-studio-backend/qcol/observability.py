"""Minimum structured observability contract for QCOL stations."""
from __future__ import annotations

def public_observability_contract() -> dict:
    return {
        "schema_version": "qcol-observability-contract/1.0",
        "required_event_fields": ["run_id", "station", "status", "timestamp_utc"],
        "conditional_fields": ["failure_code", "artifact_fingerprint", "comparison_id", "provider_job_id"],
        "structured_logs_required": True,
        "scientific_payload_redaction_required": True,
        "full_opentelemetry_required_before_freeze": False,
    }

__all__ = ["public_observability_contract"]
