"""Rank learned COMSOL cases for automatic CSV sweep preparation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from comsol_small_model.case_memory import load_memory


SUPPORTED_PHYSICS = {
    "Heat Transfer": ("thermal", ["Tmax_K", "Tavg_K"]),
    "Electric Currents": ("electrothermal", ["Tmax_K", "joule_power_W"]),
    "Solid Mechanics": ("structural", ["u_max_m", "mises_max_Pa"]),
    "Laminar Flow": ("fluid", ["pressure_drop_Pa", "outlet_flow_m3_s"]),
}

UNSUPPORTED_FOR_AUTOMATIC_SWEEP = (
    "magnetic",
    "electrostatics",
    "particle",
    "acoustic",
    "wave",
    "semiconductor",
    "plasma",
    "piezo",
    "electrochem",
    "diluted species",
    "dilutedspecies",
    "general form pde",
    "global ode",
    "optimization",
    "rotating machinery",
)

OUTPUT_PATTERNS = (
    r"mph(?:global|max|min|int\d?)\s*\(\s*model\s*,\s*['\"]([^'\"]+)",
    r"result\.numerical\s*\(\s*['\"][^'\"]+['\"]\s*\)\.set\s*\(\s*['\"]expr['\"]\s*,\s*['\"]([^'\"]+)",
)
NUMERICAL_EXPR_PATTERN = re.compile(
    r"result\s*\.numerical\s*\([^)]*\)\s*(?:\.\s*)?set\s*\(\s*['\"]expr['\"]\s*,\s*(?:new\s+String\s*\[\s*\]\s*)?\{(?P<items>.*?)\}\s*\)",
    flags=re.IGNORECASE | re.DOTALL,
)
QUOTED_VALUE_PATTERN = re.compile(r"['\"]([^'\"]+)['\"]")


def _script_output_expressions(case_dir: Path, sources: object) -> list[str]:
    expressions: list[str] = []
    seen: set[str] = set()
    if not isinstance(sources, list):
        return expressions
    for source in sources:
        if not isinstance(source, dict):
            continue
        name = str(source.get("name", ""))
        if Path(name).suffix.lower() not in {".m", ".java"}:
            continue
        path = Path(str(source.get("path", ""))) if source.get("path") else case_dir / name
        if not path.is_file():
            matches = list(case_dir.rglob(name)) if name else []
            path = matches[0] if len(matches) == 1 else path
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        source_text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in OUTPUT_PATTERNS:
            for expression in re.findall(pattern, source_text, flags=re.IGNORECASE):
                normalized = str(expression).strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    expressions.append(normalized)
        for match in NUMERICAL_EXPR_PATTERN.finditer(source_text):
            for expression in QUOTED_VALUE_PATTERN.findall(match.group("items")):
                normalized = expression.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    expressions.append(normalized)
    return expressions


def _declared_result_names(case: dict[str, object]) -> list[str]:
    content = case.get("case_content", {})
    raw_results = content.get("results", []) if isinstance(content, dict) else []
    names: list[str] = []
    for value in raw_results if isinstance(raw_results, list) else []:
        candidate = str(value).strip()
        lowered = candidate.lower()
        if candidate and "/" not in candidate and not any(
            token in lowered for token in ("plotgroup", "dataset", "table", "export")
        ):
            names.append(candidate)
    return names


def _contains(text: str, *tokens: str) -> bool:
    return any(token.lower() in text.lower() for token in tokens)


def _canonical_physics(physics: list[str]) -> set[str]:
    tags: set[str] = set()
    for value in physics:
        lowered = value.lower()
        matched = False
        for name, aliases in {
            "Heat Transfer": ("heat transfer", "heattransfer"),
            "Electric Currents": ("electric currents", "conductivemedia"),
            "Solid Mechanics": ("solid mechanics", "solidmechanics"),
            "Laminar Flow": ("laminar flow", "laminarflow"),
        }.items():
            if any(alias in lowered for alias in aliases):
                tags.add(name)
                matched = True
        if any(token in lowered for token in UNSUPPORTED_FOR_AUTOMATIC_SWEEP) or not matched:
            tags.add(f"__unsupported__:{value}")
    return tags


def _candidate(case: dict[str, object]) -> dict[str, object] | None:
    summary = case.get("file_summary", {}) if isinstance(case.get("file_summary"), dict) else {}
    quality = case.get("quality", {}) if isinstance(case.get("quality"), dict) else {}
    content = case.get("case_content", {}) if isinstance(case.get("case_content"), dict) else {}
    physics = [str(value) for value in content.get("physics", [])]
    canonical_physics = _canonical_physics(physics)
    if any(value.startswith("__unsupported__:") for value in canonical_physics):
        return None
    if canonical_physics == {"Electric Currents", "Heat Transfer"}:
        matched, domain, outputs = ["Electric Currents", "Heat Transfer"], "electrothermal", ["Tmax_K", "joule_power_W"]
    elif len(canonical_physics) == 1 and "Heat Transfer" in canonical_physics:
        matched, domain, outputs = ["Heat Transfer"], "thermal", ["Tmax_K", "Tavg_K"]
    elif len(canonical_physics) == 1 and "Solid Mechanics" in canonical_physics:
        matched, domain, outputs = ["Solid Mechanics"], "structural", ["u_max_m", "mises_max_Pa"]
    elif len(canonical_physics) == 1 and "Laminar Flow" in canonical_physics:
        matched, domain, outputs = ["Laminar Flow"], "fluid", ["pressure_drop_Pa", "outlet_flow_m3_s"]
    else:
        return None
    if int(summary.get("csv_files", 0) or 0):
        return None
    if not (int(summary.get("matlab_files", 0) or 0) or int(summary.get("java_files", 0) or 0)):
        return None
    checks = quality.get("checks", {}) if isinstance(quality.get("checks"), dict) else {}
    if not (checks.get("physics") and checks.get("parameters") and checks.get("study")):
        return None

    case_dir = Path(str(case.get("case_dir", "")))
    output_evidence = [
        *_declared_result_names(case),
        *_script_output_expressions(case_dir, case.get("source_files", [])),
    ]
    if not output_evidence:
        return None

    domain, outputs = SUPPORTED_PHYSICS[matched[0]]
    parameters = case.get("parameters", []) if isinstance(case.get("parameters"), list) else []
    parameter_names = [str(item.get("name", "")) for item in parameters if isinstance(item, dict) and item.get("name")]
    if domain == "electrothermal":
        preferred = [name for name in parameter_names if _contains(name, "V", "I", "current", "Jan", "htc", "Ta")]
    elif domain == "thermal":
        preferred = [name for name in parameter_names if _contains(name, "T", "k", "h", "Q", "heat")]
    elif domain == "structural":
        preferred = [name for name in parameter_names if _contains(name, "E", "nu", "load", "F", "p", "thick")]
    else:
        preferred = [name for name in parameter_names if _contains(name, "u", "v", "p", "mu", "Re")]
    selected_inputs = (preferred or parameter_names)[:3]
    if len(selected_inputs) < 2:
        return None

    score = int(quality.get("score", 0))
    score += min(12, len(selected_inputs) * 3)
    score += 8 if int(summary.get("mph_files", 0) or 0) else 0
    risk = "baseline_review_required"
    return {
        "title": case.get("title"),
        "case_dir": case.get("case_dir"),
        "score": score,
        "risk": risk,
        "physics": matched,
        "domain": domain,
        "suggested_inputs": selected_inputs,
        "suggested_outputs": outputs,
        "output_evidence": output_evidence,
        "sample_design": "3 levels per input plus separate midpoint holdout; verify baseline solve before queueing.",
        "reason": "已检测到受支持的单场或明确电-热耦合，以及脚本/结果节点中的显式标量输出证据；仍需先通过一次 COMSOL 基准求解。",
    }


def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-path", type=Path, default=Path("generated/case_memory/case_memory.json"))
    parser.add_argument("--output", type=Path, default=Path("generated/training_candidates/case_csv_candidates.json"))
    parser.add_argument("--top-k", type=int, default=20)
    args = parser.parse_args()
    memory = load_memory(args.memory_path)
    candidates = [candidate for case in memory.get("cases", []) if (candidate := _candidate(case))]
    candidates.sort(key=lambda item: int(item["score"]), reverse=True)
    payload = {
        "kind": "comsol_case_csv_candidate_plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_case_count": len(memory.get("cases", [])),
        "candidate_count": len(candidates),
        "candidates": candidates[: args.top_k],
        "workflow": [
            "Validate source model with one baseline COMSOL solve.",
            "Generate a bounded parameter sweep from the suggested inputs.",
            "Export inputs and declared outputs to CSV.",
            "Run data checks and reserve independent holdout points.",
            "Train and register a surrogate only after holdout validation passes.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "candidate_count": len(candidates), "selected": payload["candidates"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


