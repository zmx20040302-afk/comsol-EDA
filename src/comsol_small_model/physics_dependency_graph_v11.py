from __future__ import annotations

from copy import deepcopy
from typing import Any

from .physics_dependency_graph import compile_physics_dependency_plan
from .requirement_completeness_v11 import analyze_requirement_completeness, sanitize_missing_clauses


GRAPH_VERSION = "1.1.0"


def compile_physics_dependency_plan_v11(
    requirement: str,
    domains: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Add negation-aware completeness gating without modifying frozen v1.0."""
    original = " ".join(str(requirement or "").split())
    if not original:
        raise ValueError("requirement is empty")
    sanitized, removed = sanitize_missing_clauses(original)
    selection_text = sanitized or original
    plan = deepcopy(compile_physics_dependency_plan(selection_text, domains))
    goal_ids = {row["id"] for row in plan["goals"]}
    completeness = analyze_requirement_completeness(
        original,
        interface_ids=plan["interface_ids"],
        goal_ids=goal_ids,
        coupling_ids=plan["coupling_ids"],
    )

    reason_codes = list(plan["decision"]["reason_codes"])
    for code in completeness["reason_codes"]:
        if code not in reason_codes:
            reason_codes.append(code)
    questions = list(plan["clarification_questions"])
    for question in completeness["clarification_questions"]:
        if question not in questions:
            questions.append(question)

    plan.update({
        "schemaVersion": GRAPH_VERSION,
        "requirement": original,
        "selection_requirement": selection_text,
        "completeness": completeness,
        "clarification_questions": questions,
        "decision": {
            "blocked": bool(plan["decision"]["blocked"] or not completeness["complete"]),
            "reason_codes": reason_codes,
        },
        "scope_note": (
            "Version 1.1 layers explicit missing-field and negation evidence over the frozen v1.0 dependency compiler. "
            "It does not claim unrestricted language understanding or validate unsupported COMSOL couplings."
        ),
    })
    if removed:
        plan["selection_note"] = "Explicit missing-information clauses were excluded from positive physics evidence."
    return plan
