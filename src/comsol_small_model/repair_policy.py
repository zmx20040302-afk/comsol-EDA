from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .execution_diagnostics import diagnose_execution_failure


AUTO_REPAIR_CATEGORIES = {"variable", "api_property", "result_validation", "artifact", "mesh", "solver"}
APPROVAL_REQUIRED_CHANGES = {
    "geometry_dimensions", "material_properties", "load_values", "boundary_values",
    "physics_interface", "remove_coupling", "relax_acceptance_threshold",
}


def build_repair_decision(
    error: str,
    *,
    attempt: int,
    max_attempts: int = 3,
    proposed_changes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    diagnosis = diagnose_execution_failure(error)
    changes = list(proposed_changes or [])
    approval_changes = [row for row in changes if str(row.get("field", "")) in APPROVAL_REQUIRED_CHANGES]
    allowed_changes = [row for row in changes if row not in approval_changes]
    exhausted = int(attempt) >= int(max_attempts)
    category = str(diagnosis.get("category", "unknown"))
    auto_allowed = category in AUTO_REPAIR_CATEGORIES and not approval_changes and not exhausted
    return {
        "schema": "comsol-controlled-repair-decision",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "attempt": int(attempt),
        "max_attempts": int(max_attempts),
        "primary_error_category": category,
        "diagnosis": diagnosis,
        "auto_repair_allowed": auto_allowed,
        "requires_user_approval": bool(approval_changes),
        "retry_allowed": not exhausted,
        "allowed_changes": allowed_changes[:1],
        "approval_required_changes": approval_changes,
        "policy": {
            "one_primary_category_per_attempt": True,
            "rerun_affected_validations": True,
            "retain_contract_and_code_diff": True,
            "api_cannot_bypass_local_gates": True,
        },
        "next_action": (
            "request_user_approval" if approval_changes else
            "stop_retry_limit" if exhausted else
            "apply_one_change_and_rerun" if auto_allowed else
            "manual_model_review"
        ),
    }
