from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CHINA_TZ = timezone(timedelta(hours=8))
REQUIRED_SCENARIO_FIELDS = {
    "id",
    "role",
    "name_zh",
    "eda_stage",
    "design_question",
    "engineering_decision",
    "design_variables",
    "operating_variables",
    "objectives",
    "constraints",
    "required_outputs",
    "physics_plan",
    "automatic_stop_conditions",
    "evidence",
}
REQUIRED_DECISION_FIELDS = {"decision", "value", "decision_owner"}
REQUIRED_PHYSICS_FIELDS = {"interfaces", "couplings", "study", "validation_rules"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    result: dict[str, Any] = {
        "path": relative_path,
        "exists": path.is_file(),
        "size_bytes": path.stat().st_size if path.is_file() else 0,
    }
    if path.is_file():
        result["sha256"] = _sha256(path)
    return result


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _parse_datetime(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _validate_fresh_experiment(
    root: Path,
    scenario_id: str,
    report_relative_path: object,
    frozen_at: object,
) -> dict[str, Any]:
    relative_path = str(report_relative_path or "").strip()
    checks: dict[str, bool] = {
        "report_path_declared": bool(relative_path),
        "report_exists": False,
        "scenario_matches": False,
        "report_passed": False,
        "generated_after_contract_freeze": False,
        "required_artifacts_exist": False,
        "artifact_hashes_match": False,
    }
    result: dict[str, Any] = {
        "path": relative_path,
        "checks": checks,
        "valid": False,
    }
    if not relative_path:
        return result
    report_path = root / relative_path
    checks["report_exists"] = report_path.is_file()
    if not report_path.is_file():
        return result
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        return result
    checks["scenario_matches"] = report.get("scenario_id") == scenario_id
    checks["report_passed"] = report.get("passed") is True
    generated = _parse_datetime(report.get("generated_at"))
    frozen = _parse_datetime(frozen_at)
    if generated and frozen:
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        if frozen.tzinfo is None:
            frozen = frozen.replace(tzinfo=timezone.utc)
        checks["generated_after_contract_freeze"] = generated > frozen
    artifacts = report.get("artifacts", {})
    required_names = ("input_csv", "result_csv", "mph", "matlab_log")
    inspected: dict[str, Any] = {}
    all_exist = True
    all_hashes = True
    for name in required_names:
        declared = artifacts.get(name, {}) if isinstance(artifacts, dict) else {}
        artifact_path = root / str(declared.get("path", ""))
        exists = artifact_path.is_file()
        expected_hash = str(declared.get("sha256", ""))
        actual_hash = _sha256(artifact_path) if exists else ""
        hash_matches = bool(expected_hash) and expected_hash == actual_hash
        inspected[name] = {
            "path": str(declared.get("path", "")),
            "exists": exists,
            "sha256_matches": hash_matches,
        }
        all_exist = all_exist and exists
        all_hashes = all_hashes and hash_matches
    checks["required_artifacts_exist"] = all_exist
    checks["artifact_hashes_match"] = all_hashes
    result.update(
        {
            "generated_at": report.get("generated_at"),
            "experiment_type": report.get("experiment_type"),
            "artifacts": inspected,
            "valid": all(checks.values()),
        }
    )
    return result


def _variable_valid(variable: object) -> bool:
    if not isinstance(variable, dict):
        return False
    if not all(str(variable.get(field, "")).strip() for field in ("name", "unit", "meaning")):
        return False
    lower = variable.get("lower")
    upper = variable.get("upper")
    return (
        isinstance(lower, (int, float))
        and not isinstance(lower, bool)
        and isinstance(upper, (int, float))
        and not isinstance(upper, bool)
        and lower <= upper
    )


def validate_scenario_contract(scenario: dict[str, Any]) -> dict[str, Any]:
    missing_fields = sorted(REQUIRED_SCENARIO_FIELDS - set(scenario))
    decision = scenario.get("engineering_decision", {})
    physics = scenario.get("physics_plan", {})
    checks = {
        "required_fields_present": not missing_fields,
        "design_question_present": bool(str(scenario.get("design_question", "")).strip()),
        "engineering_decision_complete": isinstance(decision, dict)
        and REQUIRED_DECISION_FIELDS.issubset(decision)
        and all(str(decision.get(field, "")).strip() for field in REQUIRED_DECISION_FIELDS),
        "design_variables_valid": bool(scenario.get("design_variables"))
        and all(_variable_valid(row) for row in scenario.get("design_variables", [])),
        "operating_variables_valid": all(
            _variable_valid(row) for row in scenario.get("operating_variables", [])
        ),
        "objectives_present": bool(scenario.get("objectives")),
        "constraints_present": bool(scenario.get("constraints")),
        "outputs_present": bool(scenario.get("required_outputs")),
        "physics_plan_complete": isinstance(physics, dict)
        and REQUIRED_PHYSICS_FIELDS.issubset(physics)
        and bool(physics.get("interfaces"))
        and bool(str(physics.get("study", "")).strip())
        and bool(physics.get("validation_rules")),
        "stop_conditions_present": bool(scenario.get("automatic_stop_conditions")),
    }
    return {
        "valid": all(checks.values()),
        "missing_fields": missing_fields,
        "checks": checks,
    }


def _busbar_snapshot(root: Path) -> dict[str, Any]:
    path = root / "generated/p5/final_evaluation/p5_final_evaluation_evaluated.csv"
    if not path.is_file():
        return {"available": False, "path": path.relative_to(root).as_posix()}
    rows = [row for row in _read_csv(path) if row.get("sample_role") == "p5_independent_domain_test"]
    feasible = sum(_truthy(row.get("actual_constraints_passed")) for row in rows)
    released = sum(_truthy(row.get("released_safe")) for row in rows)
    false_safe = sum(_truthy(row.get("false_safe")) for row in rows)
    return {
        "available": True,
        "scope": "retired P5 independent domain set; diagnostic only after P1 freeze",
        "evaluated_points": len(rows),
        "comsol_feasible_points": feasible,
        "safely_released_points": released,
        "false_safe_points": false_safe,
    }


def _mems_snapshot(root: Path) -> dict[str, Any]:
    paths = [
        root / "generated/training_runs/thermal_actuator_simplified_training.csv",
        root / "generated/training_runs/thermal_actuator_simplified_holdout.csv",
    ]
    if not all(path.is_file() for path in paths):
        return {"available": False}
    rows = [row for path in paths for row in _read_csv(path)]
    feasible_rows = []
    for row in rows:
        try:
            feasible = (
                float(row["Tmax_K"]) <= 550.0
                and float(row["umax_m"]) >= 0.9e-6
                and float(row["joule_power_W"]) <= 0.016
            )
        except (KeyError, TypeError, ValueError):
            feasible = False
        if feasible:
            feasible_rows.append(row)
    best = max(feasible_rows, key=lambda row: float(row["umax_m"])) if feasible_rows else None
    return {
        "available": True,
        "scope": "historical COMSOL training plus independent holdout; diagnostic only after P1 freeze",
        "evaluated_points": len(rows),
        "feasible_points_under_p1_thresholds": len(feasible_rows),
        "best_feasible_observed": {
            key: float(best[key])
            for key in ("DV_V", "htc_s_W_m2K", "htc_us_W_m2K", "Tmax_K", "umax_m", "joule_power_W")
        }
        if best
        else None,
    }


def build_p1_report(root: Path) -> dict[str, Any]:
    config_path = root / "configs/dac2027_p1_eda_scenarios.json"
    p7_path = root / "generated/p7/p7_eda_multicase_report.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    contract_frozen_at = config.get("frozen_at")
    p7_report = json.loads(p7_path.read_text(encoding="utf-8")) if p7_path.is_file() else {"cases": []}
    p7_cases = {str(row.get("id")): row for row in p7_report.get("cases", [])}

    scenario_results: list[dict[str, Any]] = []
    for scenario in config.get("scenarios", []):
        validation = validate_scenario_contract(scenario)
        evidence = scenario.get("evidence", {})
        artifacts = [_artifact(root, str(path)) for path in evidence.get("artifacts", [])]
        linked_case = p7_cases.get(str(evidence.get("linked_p7_case", "")), {})
        artifacts_present = bool(artifacts) and all(row["exists"] for row in artifacts)
        numerical_evidence_passed = bool(linked_case.get("passed"))
        declared_fresh = evidence.get("tier") == "fresh_current_project_comsol_closed_loop"
        fresh_experiment = _validate_fresh_experiment(
            root,
            str(scenario.get("id", "")),
            evidence.get("fresh_experiment_report"),
            contract_frozen_at,
        )
        fresh_post_freeze = fresh_experiment["valid"]
        scenario_results.append(
            {
                "id": scenario.get("id"),
                "name_zh": scenario.get("name_zh"),
                "role": scenario.get("role"),
                "eda_stage": scenario.get("eda_stage"),
                "contract": validation,
                "evidence_tier": evidence.get("tier"),
                "linked_p7_case": evidence.get("linked_p7_case"),
                "linked_p7_case_passed": numerical_evidence_passed,
                "artifacts_present": artifacts_present,
                "artifacts": artifacts,
                "fresh_current_project_evidence": declared_fresh,
                "fresh_post_p1_freeze_run": fresh_post_freeze,
                "fresh_experiment": fresh_experiment,
                "definition_ready": validation["valid"] and artifacts_present and numerical_evidence_passed,
                "submission_experiment_ready": validation["valid"]
                and artifacts_present
                and numerical_evidence_passed
                and fresh_post_freeze,
                "decision_snapshot": _busbar_snapshot(root)
                if scenario.get("id") == "busbar_power_delivery_design"
                else _mems_snapshot(root),
            }
        )

    primary = [row for row in scenario_results if row["role"] == "primary"]
    fresh_post_freeze_count = sum(row["fresh_post_p1_freeze_run"] for row in primary)
    acceptance = config["acceptance"]
    gates = {
        "minimum_primary_scenarios": len(primary) >= int(acceptance["minimum_primary_scenarios"]),
        "minimum_eda_stages": len({str(row["eda_stage"]) for row in primary})
        >= int(acceptance["minimum_eda_stages"]),
        "all_primary_contracts_complete": bool(primary) and all(row["contract"]["valid"] for row in primary),
        "all_primary_artifacts_traceable": bool(primary) and all(row["artifacts_present"] for row in primary),
        "all_linked_numerical_evidence_passed": bool(primary)
        and all(row["linked_p7_case_passed"] for row in primary),
        "historical_evidence_not_misclassified_as_fresh": all(
            row["evidence_tier"] != "historical_independent_comsol_holdout"
            or not row["fresh_current_project_evidence"]
            for row in primary
        ),
    }
    definition_completed = all(gates.values())
    submission_gate = (
        definition_completed
        and fresh_post_freeze_count
        >= int(acceptance["minimum_fresh_post_freeze_scenarios_for_submission"])
    )
    return {
        "schema": "dac2027-p1-eda-scenario-report",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(CHINA_TZ).isoformat(),
        "phase": "DAC2027-P1",
        "title": "EDA 场景与设计任务定义",
        "status": "definition_completed_experiment_pending" if definition_completed and not submission_gate else (
            "completed" if submission_gate else "incomplete"
        ),
        "p1_definition_completed": definition_completed,
        "submission_two_case_experiment_completed": submission_gate,
        "primary_scenario_count": len(primary),
        "definition_ready_count": sum(row["definition_ready"] for row in primary),
        "fresh_post_freeze_count": fresh_post_freeze_count,
        "eda_stage_count": len({str(row["eda_stage"]) for row in primary}),
        "gates": gates,
        "scenarios": scenario_results,
        "config": _artifact(root, config_path.relative_to(root).as_posix()),
        "next_actions": (
            [
                "冻结并保存两个 P1 实验包，不再使用本轮结果调整阈值或选择规则",
                "进入 P2：在同一任务、工具与预算下执行方法对照和消融实验",
                "论文中仅声明冻结的名义工况候选与四点 MEMS 网格，不外推为产品认证或全工作域鲁棒性",
            ]
            if submission_gate
            else [
                "在冻结合同不变的前提下重新运行尚未完成的主案例并记录 P1 运行标识",
                "保存 MPH、CSV、MATLAB 日志、物理验收和工程决策结果",
                "两个新实验完成后再将 submission_two_case_experiment_completed 标记为 true",
            ]
        ),
        "claim_boundary": (
            "Two fresh post-freeze COMSOL experiments completed under predeclared points, thresholds, and selection rules. "
            "They support the two named EDA decisions at the tested nominal points, but do not establish product qualification "
            "or robustness over the full manufacturing and operating space."
            if submission_gate
            else "P1 definition completion means that two EDA scenarios have executable and auditable design contracts. "
            "It does not mean that two fresh post-freeze COMSOL experiments have completed."
        ),
    }


def write_p1_report(root: Path, output_path: Path | None = None) -> Path:
    target = output_path or root / "generated/dac2027/p1/readiness_status.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_p1_report(root), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target

