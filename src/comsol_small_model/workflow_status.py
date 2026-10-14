from __future__ import annotations

from typing import Final


WORKFLOW_STATUSES: Final[tuple[str, ...]] = (
    "draft",
    "missing_information",
    "ready_for_review",
    "approved_for_generation",
    "generated",
    "build_failed",
    "built",
    "mesh_failed",
    "solve_failed",
    "solved",
    "validation_failed",
    "completed",
)

EVIDENCE_LEVELS: Final[tuple[str, ...]] = (
    "missing",
    "proposed",
    "source_supported",
    "user_confirmed",
    "template_verified",
    "comsol_verified",
)

RISK_LEVELS: Final[tuple[str, ...]] = ("A", "B", "C")

WORKFLOW_STATUS_SET: Final[frozenset[str]] = frozenset(WORKFLOW_STATUSES)
EVIDENCE_LEVEL_SET: Final[frozenset[str]] = frozenset(EVIDENCE_LEVELS)
RISK_LEVEL_SET: Final[frozenset[str]] = frozenset(RISK_LEVELS)


LEGACY_WORKFLOW_STATUS_MAP: Final[dict[str, str]] = {
    "waiting_for_approval": "ready_for_review",
    "needs_revision": "ready_for_review",
    "complete": "generated",
}


def normalize_workflow_status(value: object, default: str = "draft") -> str:
    text = str(value or "").strip()
    text = LEGACY_WORKFLOW_STATUS_MAP.get(text, text)
    return text if text in WORKFLOW_STATUS_SET else default


def validate_evidence_level(value: object) -> str:
    text = str(value or "").strip()
    if text not in EVIDENCE_LEVEL_SET:
        raise ValueError(f"unsupported evidence level: {text or '<empty>'}")
    return text


def evidence_rank(value: object) -> int:
    text = str(value or "missing")
    try:
        return EVIDENCE_LEVELS.index(text)
    except ValueError:
        return 0

