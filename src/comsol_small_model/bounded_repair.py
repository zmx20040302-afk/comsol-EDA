from __future__ import annotations

from typing import Any

from .repair_policy import APPROVAL_REQUIRED_CHANGES
from .static_model_audit import contract_sha256


MAX_PATCH_LINES = 3


def apply_bounded_repair(
    contract: dict[str, Any],
    code: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Apply one exact, local code replacement without changing the contract.

    The caller must provide the diagnosed field and an exact old/new span.  The
    function rejects ambiguous, multi-location, broad, or contract-changing
    edits.  It is deliberately smaller than a general code regeneration path.
    """
    field = str(patch.get("field", ""))
    old = str(patch.get("old", ""))
    new = str(patch.get("new", ""))
    before_hash = contract_sha256(contract)
    reasons: list[str] = []

    if field in APPROVAL_REQUIRED_CHANGES:
        reasons.append("approval_required_field")
    if not old or old == new:
        reasons.append("invalid_replacement")
    if max(len(old.splitlines()), len(new.splitlines())) > MAX_PATCH_LINES:
        reasons.append("patch_span_exceeds_limit")
    occurrence_count = code.count(old) if old else 0
    if occurrence_count != 1:
        reasons.append("target_must_match_exactly_once")

    if reasons:
        return {
            "applied": False,
            "reason_codes": reasons,
            "code": code,
            "changed_line_budget": MAX_PATCH_LINES,
            "contract_sha256_before": before_hash,
            "contract_sha256_after": contract_sha256(contract),
        }

    repaired = code.replace(old, new, 1)
    return {
        "applied": True,
        "reason_codes": [],
        "code": repaired,
        "changed_line_budget": MAX_PATCH_LINES,
        "contract_sha256_before": before_hash,
        "contract_sha256_after": contract_sha256(contract),
    }
