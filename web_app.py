from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import socket
import subprocess
import sys
import traceback
import webbrowser
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.constraints import validate_constraints
from comsol_small_model.article_knowledge import summarize_article_docx
from comsol_small_model.augmentation_retrain import prepare_augmentation_retrain
from comsol_small_model.case_knowledge import summarize_case_directory
from comsol_small_model.case_sources import case_source_status, resolve_case_source_path
from comsol_small_model.case_memory import (
    generate_model_plan,
    refresh_knowledge_system,
    remember_case,
    remember_learning_summary,
    remember_physics_correction,
    sync_template_validations,
)
from comsol_small_model.closure_audit import build_closure_audit
from comsol_small_model.code_generator import generate_comsol_code_from_memory
from comsol_small_model.code_workspace import modify_code_file, read_code_file
from comsol_small_model.comsol_server import ensure_comsol_server
from comsol_small_model.comsol_preview import PreviewExportError, export_mph_preview, resolve_generated_mph
from comsol_small_model.comsol_3d_preview import StlExportError, export_mph_stl
from comsol_small_model.execution_jobs import (
    DEFAULT_JOB_DIR,
    JobStore,
    create_job,
    create_approved_package_job,
    create_constraint_template_job,
    create_thermal_augmentation_job,
    create_thermal_augmentation_retrain_job,
    create_matched_template_job,
    create_thermal_sweep_training_job,
    create_joule_heat_benchmark_job,
    load_execution_node_config,
    process_next_job,
    rebuild_artifact_index,
    summarize_artifacts,
)
from comsol_small_model.experimental_validation import validate_temperature_experiment
from comsol_small_model.file_reader import (
    build_learning_summary,
    summarize_collection,
    summarize_file,
    summarize_files,
    summarize_uploaded_binary,
    summarize_uploaded_text,
    summarize_uploaded_texts,
)
from comsol_small_model.instruction_agent import ANSWER_POLICY, respond_to_instruction
from comsol_small_model.livelink_builder import build_livelink_script_from_constraints
from comsol_small_model.matlab_reader import inspect_matlab_file
from comsol_small_model.holdout_independence import build_holdout_independence_report
from comsol_small_model.mesh_convergence import assess_mesh_convergence
from comsol_small_model.parameter_coverage import assess_parameter_coverage
from comsol_small_model.reference_checks import evaluate_reference_case
from comsol_small_model.reference_artifacts import list_reference_reports, write_reference_report
from comsol_small_model.reference_comparison import (
    compare_comsol_observation_to_reference,
    compare_comsol_results_csv_to_reference,
)
from comsol_small_model.staged_modeling import (
    build_workflow_download_archive,
    list_staged_workflows,
    load_workflow,
    retry_failed_stage,
)
from comsol_small_model.staged_modeling_v11 import (
    approve_current_step_v11 as approve_current_step,
    create_staged_workflow_v11 as create_staged_workflow,
    final_modeling_package_v11 as final_modeling_package,
)
from comsol_small_model.surrogate_runtime import (
    extract_joule_rectangle_prediction_inputs,
    extract_thermal_actuator_prediction_inputs,
    extract_thermal_plate_prediction_inputs,
    detect_joule_rectangle_scope_changes,
    is_joule_rectangle_prediction_request,
    is_thermal_actuator_prediction_request,
    is_thermal_actuator_augmentation_request,
    latest_validated_thermal_model,
    predict_registered_surrogate,
    predict_validated_surrogate,
    write_registered_augmentation_plan,
    write_thermal_augmentation_plan,
)
from comsol_small_model.remote_assistant import (
    RemoteAssistantError,
    complete_task,
    load_public_config,
    redact_secrets,
    save_config,
)
from comsol_small_model.surrogate_runtime_audit import (
    audit_registered_surrogates,
    write_runtime_audit,
)
from comsol_small_model.template_parameters import derive_constraints, extract_text_overrides
from comsol_small_model.thermal_sweep import write_thermal_sweep_matlab
from comsol_small_model.training_roadmap import build_training_roadmap
from comsol_small_model.validated_templates import select_validated_template
from comsol_small_model.work_feedback import append_work_log, build_work_feedback
from comsol_small_model.workchain_package import (
    archive_reference_workchain_package,
    create_reference_workchain_package,
    list_reference_workchain_packages,
    validate_reference_workchain_package,
    validate_reference_workchain_archive,
)


GENERATED_DIR = ROOT / "generated"
MODELS_DIR = ROOT / "models"
WORK_LOG_PATH = GENERATED_DIR / "work_logs.jsonl"
JOBS_DIR = GENERATED_DIR / "execution_jobs"
WORKER_STATUS_PATH = JOBS_DIR / "worker_status.json"
ASSISTANT_CONFIG_PATH = ROOT / "configs" / "assistant_mode.json"
ASSISTANT_KEYS_PATH = GENERATED_DIR / "local_secrets" / "api_assistant_keys.json"
BUSBAR_BENCHMARK_DIR = GENERATED_DIR / "benchmarks" / "busbar_joule_heat"
SURROGATE_REGISTRY_PATH = GENERATED_DIR / "models" / "surrogate_registry.json"
LEGACY_SURROGATE_REGISTRY_PATH = GENERATED_DIR / "surrogate_registry.json"
SURROGATE_RUNTIME_AUDIT_PATH = SURROGATE_REGISTRY_PATH.with_name("surrogate_runtime_audit.json")
EXPERIMENT_VALIDATION_REPORT_PATH = GENERATED_DIR / "experimental_validation" / "temperature_validation_report.json"
EXPERIMENT_VALIDATION_CONFIG_PATH = ROOT / "configs" / "experimental_temperature_validation.json"
EXPERIMENT_VALIDATION_MODEL_PATH = GENERATED_DIR / "execution_jobs" / "expanded_validation_20261008" / "thermal_plate_surrogate_expanded_validated.joblib"
P3_DIR = GENERATED_DIR / "p3"
P4_DIR = GENERATED_DIR / "p4"
P5_DIR = GENERATED_DIR / "p5"
P6_DIR = GENERATED_DIR / "p6"
P7_DIR = GENERATED_DIR / "p7"
DAC2027_P1_DIR = GENERATED_DIR / "dac2027" / "p1"
DAC2027_P0_DIR = GENERATED_DIR / "dac2027" / "p0"
DAC2027_P2_DIR = GENERATED_DIR / "dac2027" / "p2"
DAC2027_P3_DIR = GENERATED_DIR / "dac2027" / "p3"
DAC2027_P4_DIR = GENERATED_DIR / "dac2027" / "p4"
DAC2027_P0_CAMPAIGN_DIR = ROOT / "benchmarks" / "dac2027_p0" / "dac2027-p0-blind-20261013"
JOULE_RECTANGLE_MODEL_ID = "joule_rectangle_validated_surrogate"
GECKO_FOOT_MODEL_ID = "gecko_foot_surrogate"
THERMAL_ACTUATOR_MODEL_ID = "thermal_actuator_voltage_dense_poly_warningfree_tmax_surrogate"
THERMAL_ACTUATOR_SIMPLIFIED_MODEL_ID = "thermal_actuator_simplified_multioutput_surrogate"
CIRCUIT_FEM_RESISTOR_MODEL_ID = "circuit_fem_resistor_multioutput_surrogate"
MAST_DIAGONAL_MOUNTING_MODEL_ID = "mast_diagonal_mounting_stiffness_surrogate"
HEAT_CONVECTION_2D_MODEL_ID = "heat_convection_2d_surrogate"
ELECTRIC_FIELD_CONCENTRIC_CYLINDERS_MODEL_ID = "electric_field_concentric_cylinders_surrogate"
CAPACITOR_DC_PERMITTIVITY_MODEL_ID = "capacitor_dc_permittivity_surrogate"
SIMPLE_RESISTOR_CONDUCTIVITY_MODEL_ID = "simple_resistor_conductivity_surrogate"
HEAT_RADIATION_1D_MODEL_ID = "heat_radiation_1d_emissivity_surrogate"
TAPERED_CANTILEVER_FORCE_MODEL_ID = "tapered_cantilever_force_surrogate"
LID_DRIVEN_CAVITY_REYNOLDS_MODEL_ID = "lid_driven_cavity_reynolds_surrogate"
ROOM_ACOUSTIC_TARGET_MODE_MODEL_ID = "room_acoustic_target_mode_surrogate"
EFFECTIVE_DIFFUSIVITY_1D_MODEL_ID = "effective_diffusivity_1d_surrogate"
FRESNEL_EQUATIONS_RF_MODEL_ID = "fresnel_equations_rf_surrogate"
MAGNETIC_FIELD_INFINITE_CONDUCTOR_MODEL_ID = "magnetic_field_infinite_conductor_surrogate"
HELMHOLTZ_COIL_MODEL_ID = "helmholtz_coil_surrogate"
PARALLEL_WIRES_FORCE_MODEL_ID = "parallel_wires_force_surrogate"
THERMOELECTRIC_GENERATOR_MODEL_ID = "thermoelectric_generator_surrogate"
PN_JUNCTION_CARRIER_MODEL_ID = "pn_junction_carrier_surrogate"
PN_JUNCTION_CURRENT_DENSITY_MODEL_ID = "pn_junction_current_density_surrogate"
POWER_INDUCTOR_FREQUENCY_MODEL_ID = "power_inductor_frequency_dense_surrogate"


def _p3_status_payload() -> dict[str, object]:
    report_paths = {
        "current_drive": P3_DIR / "current_drive_baseline" / "current_drive_baseline_report.json",
        "geometry_smoke": P3_DIR / "geometry_smoke" / "geometry_smoke_report.json",
        "initial_design": P3_DIR / "initial_design" / "initial_design_report.json",
        "optimization": P3_DIR / "optimization" / "surrogate_optimization_report.json",
        "pareto_verification": P3_DIR / "pareto_verification" / "pareto_verification_report.json",
        "final_evaluation": P3_DIR / "final_evaluation" / "final_evaluation_report.json",
    }
    reports: dict[str, object] = {}
    for name, path in report_paths.items():
        if path.exists():
            try:
                reports[name] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                reports[name] = {"available": False, "error": str(exc)}
        else:
            reports[name] = {"available": False, "path": str(path.relative_to(ROOT))}
    final_report = reports.get("final_evaluation", {})
    pareto_report = reports.get("pareto_verification", {})
    current_report = reports.get("current_drive", {})
    return {
        "ok": True,
        "phase": "P3",
        "title": "固定电流母排 EDA 设计优化闭环",
        "comsol_execution_passed": bool(isinstance(final_report, dict) and final_report.get("execution_passed")),
        "surrogate_release_passed": bool(isinstance(final_report, dict) and final_report.get("surrogate_release_passed")),
        "verified_pareto_count": int(pareto_report.get("verified_pareto_count", 0)) if isinstance(pareto_report, dict) else 0,
        "baseline_current_A": current_report.get("measured", {}).get("terminal_current_A") if isinstance(current_report, dict) else None,
        "reports": reports,
        "policy": "只有真实 COMSOL 验证通过的 Pareto 方案可作为设计证据；未通过独立发布门槛的代理模型不会在网页中开放数值预测。",
    }


def _p4_status_payload() -> dict[str, object]:
    report_paths = {
        "candidate_models": P4_DIR / "model_selection" / "candidate_model_report.json",
        "adaptive_training": P4_DIR / "adaptive_training_report.json",
        "sealed_design": P4_DIR / "sealed_final_design" / "sealed_design_manifest.json",
        "final_evaluation": P4_DIR / "final_evaluation" / "p4_final_evaluation_report.json",
    }
    reports: dict[str, object] = {}
    for name, path in report_paths.items():
        if path.exists():
            try:
                reports[name] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                reports[name] = {"available": False, "error": str(exc)}
        else:
            reports[name] = {"available": False, "path": str(path.relative_to(ROOT))}
    training = reports.get("adaptive_training", {})
    final_report = reports.get("final_evaluation", {})
    checks = final_report.get("release_checks", {}) if isinstance(final_report, dict) else {}
    accuracy_passed = bool(
        isinstance(checks, dict)
        and checks.get("tmax_rmse_at_most_15_K")
        and checks.get("power_relative_rmse_at_most_15_percent")
        and checks.get("mass_relative_rmse_at_most_10_percent")
        and checks.get("all_intervals_picp_at_least_0_90")
    )
    return {
        "ok": True,
        "phase": "P4",
        "title": "自适应代理模型修复与独立终评",
        "adaptive_comsol_cases": int(
            training.get("adaptive_rounds", 0) * training.get("cases_per_round", 0)
        ) if isinstance(training, dict) else 0,
        "training_rows": int(training.get("final_training_rows", 0)) if isinstance(training, dict) else 0,
        "comsol_execution_passed": bool(isinstance(final_report, dict) and final_report.get("execution_passed")),
        "accuracy_passed": accuracy_passed,
        "safe_release_coverage": float(final_report.get("safe_release_coverage", 0.0)) if isinstance(final_report, dict) else 0.0,
        "surrogate_release_passed": bool(isinstance(final_report, dict) and final_report.get("surrogate_release_passed")),
        "reports": reports,
        "policy": "P4 精度通过与发布通过分别显示。安全放行覆盖率未达到预先声明的 10% 时，代理模型仍不开放直接预测。",
    }


def _p5_status_payload() -> dict[str, object]:
    report_paths = {
        "calibration_selection": P5_DIR / "calibration_selection_report.json",
        "sealed_design": P5_DIR / "sealed_final_design" / "sealed_design_manifest.json",
        "final_evaluation": P5_DIR / "final_evaluation" / "p5_final_evaluation_report.json",
    }
    reports: dict[str, object] = {}
    for name, path in report_paths.items():
        if path.exists():
            try:
                reports[name] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                reports[name] = {"available": False, "error": str(exc)}
        else:
            reports[name] = {"available": False, "path": str(path.relative_to(ROOT))}
    calibration = reports.get("calibration_selection", {})
    final_report = reports.get("final_evaluation", {})
    counts = final_report.get("counts", {}) if isinstance(final_report, dict) else {}
    return {
        "ok": True,
        "phase": "P5",
        "title": "单侧局部保形校准与发布闭环",
        "calibration_method": calibration.get("selected_method") if isinstance(calibration, dict) else None,
        "comsol_execution_passed": bool(isinstance(final_report, dict) and final_report.get("execution_passed")),
        "released_safe_count": int(counts.get("released_safe_upper_95", 0)) if isinstance(counts, dict) else 0,
        "false_safe_count": int(counts.get("false_safe_upper_95", 0)) if isinstance(counts, dict) else 0,
        "safe_release_coverage": float(final_report.get("safe_release_coverage", 0.0)) if isinstance(final_report, dict) else 0.0,
        "surrogate_release_passed": bool(isinstance(final_report, dict) and final_report.get("surrogate_release_passed")),
        "reports": reports,
        "policy": "P5 只在声明的七变量域内使用局部缩放单侧 95% 上界进行约束判定；任何域外输入仍必须交给 COMSOL。",
    }


def _p6_status_payload(path: str | Path | None = None) -> dict[str, object]:
    report_path = Path(path) if path is not None else P6_DIR / "p6_status.json"
    if not report_path.is_file():
        return {
            "ok": True,
            "phase": "P6",
            "title": "外部证据与双执行路径",
            "status": "not_started",
            "local_readiness_passed": False,
            "publication_external_gate_passed": False,
            "gates": {},
            "remaining_actions": ["build_p6_status"],
        }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "phase": "P6", "error": str(exc)}
    report["ok"] = True
    return report


def _p7_status_payload(path: str | Path | None = None) -> dict[str, object]:
    report_path = Path(path) if path is not None else P7_DIR / "p7_eda_multicase_report.json"
    if not report_path.is_file():
        return {
            "ok": True,
            "phase": "P7",
            "title": "多 EDA 案例与可扩展性验证",
            "status": "not_started",
            "p7_completed": False,
            "main_case_count": 0,
            "passed_main_case_count": 0,
            "extension_case_count": 0,
            "passed_extension_case_count": 0,
            "physics_family_count": 0,
            "gates": {},
            "cases": [],
        }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "phase": "P7", "error": str(exc)}
    report["ok"] = True
    return report


def _dac2027_p1_status_payload(path: str | Path | None = None) -> dict[str, object]:
    report_path = Path(path) if path is not None else DAC2027_P1_DIR / "readiness_status.json"
    if not report_path.is_file():
        return {
            "ok": True,
            "phase": "DAC2027-P1",
            "title": "EDA 场景与设计任务定义",
            "status": "not_started",
            "p1_definition_completed": False,
            "submission_two_case_experiment_completed": False,
            "primary_scenario_count": 0,
            "definition_ready_count": 0,
            "fresh_post_freeze_count": 0,
            "eda_stage_count": 0,
            "gates": {},
            "scenarios": [],
        }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "phase": "DAC2027-P1", "error": str(exc)}
    report["ok"] = True
    return report


def _dac2027_p0_status_payload() -> dict[str, object]:
    readiness_path = DAC2027_P0_DIR / "readiness_status.json"
    acquisition_path = DAC2027_P0_DIR / "acquisition_status.json"
    author_dir = DAC2027_P0_CAMPAIGN_DIR / "returns" / "authors"
    adjudicator_dir = DAC2027_P0_CAMPAIGN_DIR / "returns" / "adjudicators"
    readiness: dict[str, object] = {}
    acquisition: dict[str, object] = {}
    errors: list[str] = []
    for path, target in ((readiness_path, readiness), (acquisition_path, acquisition)):
        if not path.is_file():
            errors.append(f"missing: {path.relative_to(ROOT)}")
            continue
        try:
            target.update(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: {exc}")
    evidence = readiness.get("publication_evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    method_counts = evidence.get("measured_responses_by_method", {})
    if not isinstance(method_counts, dict):
        method_counts = {}
    author_count = len(list(author_dir.glob("*.json"))) if author_dir.is_dir() else 0
    adjudicator_count = len(list(adjudicator_dir.glob("*.json"))) if adjudicator_dir.is_dir() else 0
    measured_tasks = int(evidence.get("external_blind_task_count", 0) or 0)
    measured_responses = int(evidence.get("measured_response_count", 0) or 0)
    gate_passed = bool(evidence.get("p0_publication_gate_passed"))
    intake_url = str(acquisition.get("intake_url") or "http://127.0.0.1:8891/")
    if gate_passed:
        next_action = "P0 论文证据门已通过，可冻结结果并同步论文表格。"
    elif author_count < 24:
        next_action = "由项目组外作者填写剩余需求；作者只写工程需求，不接触标准答案。"
    elif adjudicator_count < 24:
        next_action = "由不同人员独立裁决接口、耦合、研究类型与阻断决策。"
    elif measured_tasks < 24:
        next_action = "24 对记录齐全后由采集服务校验并密封盲测任务。"
    else:
        next_action = "在同一批密封任务上完成四种方法的 96 条实测并运行配对统计。"
    return {
        "ok": not errors,
        "phase": "DAC2027-P0",
        "title": "第三方盲测与四方法配对比较",
        "campaign_id": acquisition.get("campaign_id", "dac2027-p0-blind-20261013"),
        "intake_url": intake_url,
        "author_submissions": author_count,
        "adjudicator_submissions": adjudicator_count,
        "measured_blind_tasks": measured_tasks,
        "measured_responses": measured_responses,
        "measured_responses_by_method": method_counts,
        "publication_gate_passed": gate_passed,
        "infrastructure": readiness.get("infrastructure", {}),
        "next_action": next_action,
        "evidence_boundary": readiness.get("evidence_boundary", ""),
        "validation_error": readiness.get("validation_error", ""),
        "errors": errors,
    }


def _dac2027_p2_status_payload(path: str | Path | None = None) -> dict[str, object]:
    report_path = Path(path) if path is not None else DAC2027_P2_DIR / "readiness_status.json"
    if not report_path.is_file():
        return {
            "ok": True,
            "phase": "DAC2027-P2",
            "title": "同任务四方法对照与消融",
            "status": "not_started",
            "task_count": 0,
            "method_count": 4,
            "measured_response_count": 0,
            "measured_responses_by_method": {},
            "controlled_comparison_completed": False,
            "ablation_completed": False,
            "p2_development_gate_passed": False,
            "publication_external_gate_passed": False,
        }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "phase": "DAC2027-P2", "error": str(exc)}
    report["ok"] = True
    return report


def _dac2027_p3_status_payload(path: str | Path | None = None) -> dict[str, object]:
    report_path = Path(path) if path is not None else DAC2027_P3_DIR / "readiness_status.json"
    if not report_path.is_file():
        return {
            "ok": True,
            "phase": "DAC2027-P3",
            "title": "前瞻独立多案例评测与统计",
            "status": "not_started",
            "protocol_frozen": False,
            "p3_infrastructure_gate_passed": False,
            "p3_main_result_gate_passed": False,
            "required_task_count": 24,
            "required_family_count": 8,
            "required_observation_count": 192,
            "accepted_task_count": 0,
            "accepted_family_count": 0,
            "measured_observation_count": 0,
        }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "phase": "DAC2027-P3", "error": str(exc)}
    report["ok"] = True
    return report


def _dac2027_p4_status_payload(path: str | Path | None = None) -> dict[str, object]:
    report_path = Path(path) if path is not None else DAC2027_P4_DIR / "readiness_status.json"
    if not report_path.is_file():
        return {
            "ok": True,
            "phase": "DAC2027-P4",
            "title": "双盲稿件、相关工作与匿名复现包",
            "status": "not_started",
            "p4_infrastructure_gate_passed": False,
            "p4_final_submission_gate_passed": False,
            "format_and_page_gate_passed": False,
            "double_blind_gate_passed": False,
            "related_work_matrix_completed": False,
            "ai_content_statement_completed": False,
            "reproducibility_package_passed": False,
            "p3_external_main_result_gate_passed": False,
            "accepted_external_task_count": 0,
            "required_external_task_count": 24,
            "measured_external_observation_count": 0,
            "required_external_observation_count": 192,
            "next_action": "生成并检查 DAC P4 双盲稿件与匿名复现包。",
        }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "phase": "DAC2027-P4", "error": str(exc)}
    report["ok"] = True
    return report


def _prepare_dac2027_p3_payload() -> dict[str, object]:
    """Validate and seal accepted P0 tasks without inventing missing evidence."""
    protocol_path = ROOT / "configs" / "dac2027_p3_protocol.json"
    try:
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        task_path = ROOT / str(protocol["task_source"]["path"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return {
            "ok": False,
            "sealed": False,
            "message": f"P3 协议读取失败：{exc}",
            "status": _dac2027_p3_status_payload(),
        }

    if not task_path.is_file():
        return {
            "ok": True,
            "ready": False,
            "sealed": False,
            "message": "尚未形成 24 条经过作者提交和独立裁决的 P0 外部任务，未执行 P3 密封。",
            "task_path": task_path.relative_to(ROOT).as_posix(),
            "status": _dac2027_p3_status_payload(),
        }

    command = [sys.executable, str(ROOT / "scripts" / "prepare_dac2027_p3.py"), "--seal"]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "sealed": False,
            "message": f"P3 校验与密封命令执行失败：{exc}",
            "status": _dac2027_p3_status_payload(),
        }

    status = _dac2027_p3_status_payload()
    sealed = bool(status.get("sealed_external_tasks"))
    validation_error = str(status.get("validation_error") or "").strip()
    if sealed:
        message = "P0 外部任务已通过数量、状态分布、案例族隔离和文件哈希检查，并完成 P3 密封。"
    elif validation_error:
        message = f"P0 外部任务未通过 P3 校验：{validation_error}"
    else:
        message = "P3 校验已执行，但任务尚未达到可密封条件。"
    return {
        "ok": completed.returncode == 0,
        "ready": sealed,
        "sealed": sealed,
        "message": message,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "status": status,
    }


class AppHandler(BaseHTTPRequestHandler):
    server_version = "ComsolSmallModelWeb/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(CONVERSATIONAL_INDEX)
        elif parsed.path == "/api/health":
            self._send_json(_health_payload())
        elif parsed.path == "/api/case-sources":
            self._send_json({"ok": True, "case_sources": case_source_status(project_root=ROOT)})
        elif parsed.path == "/api/comsol/observer":
            self._send_json(_comsol_observer_payload())
        elif parsed.path == "/api/assistant/config":
            self._send_json({"ok": True, "config": load_public_config(ASSISTANT_CONFIG_PATH, ASSISTANT_KEYS_PATH)})
        elif parsed.path == "/api/staged-workflows":
            limit = int(parse_qs(parsed.query).get("limit", [30])[0])
            self._send_json({"ok": True, "workflows": list_staged_workflows(GENERATED_DIR / "staged_workflows", limit)})
        elif parsed.path == "/api/staged-workflow":
            workflow_path = _resolve_user_path(parse_qs(parsed.query).get("path", [""])[0])
            self._send_json({"ok": True, "workflow": load_workflow(workflow_path)})
        elif parsed.path == "/api/staged-workflow/download":
            workflow_path = _resolve_user_path(parse_qs(parsed.query).get("path", [""])[0])
            archive = build_workflow_download_archive(workflow_path)
            self._send_download(archive, "application/zip")
        elif parsed.path == "/api/comsol/preview":
            preview_path = parse_qs(parsed.query).get("path", [""])[0]
            self._send_comsol_preview(preview_path)
        elif parsed.path == "/api/default-constraints":
            self._send_json(json.loads((ROOT / "configs" / "thermal_constraints.json").read_text(encoding="utf-8")))
        elif parsed.path == "/api/jobs":
            limit = int(parse_qs(parsed.query).get("limit", [30])[0])
            self._send_json({"ok": True, "jobs": JobStore(JOBS_DIR).list(limit), "node": load_execution_node_config(ROOT / "configs" / "execution_node.json")})
        elif parsed.path == "/api/artifacts":
            limit = int(parse_qs(parsed.query).get("limit", [200])[0])
            self._send_json({"ok": True, "artifact_index": rebuild_artifact_index(JOBS_DIR, limit=limit)})
        elif parsed.path == "/api/artifacts/recent":
            limit = int(parse_qs(parsed.query).get("limit", [8])[0])
            self._send_json({"ok": True, "summary": summarize_artifacts(JOBS_DIR, limit=limit)})
        elif parsed.path == "/api/knowledge/template-validations":
            memory = json.loads((GENERATED_DIR / "case_memory" / "case_memory.json").read_text(encoding="utf-8"))
            self._send_json({"ok": True, "template_validations": memory.get("template_validations", [])})
        elif parsed.path == "/api/training/roadmap":
            self._send_json({"ok": True, "roadmap": build_training_roadmap(GENERATED_DIR / "case_memory" / "case_memory.json")})
        elif parsed.path == "/api/training/closure-audit":
            self._send_json({"ok": True, "audit": build_closure_audit(GENERATED_DIR, ROOT / "training_program.json")})
        elif parsed.path == "/api/surrogates/registry":
            registries = _registered_surrogate_registry_paths()
            models: dict[str, object] = {}
            for registry_path in registries:
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
                for item in registry.get("models", []):
                    if isinstance(item, dict):
                        models.setdefault(str(item.get("id", "")), item)
            self._send_json({
                "ok": True,
                "registry": {"schema": "comsol-surrogate-registry", "schemaVersion": "1.0.0", "models": list(models.values())},
                "paths": [str(path) for path in registries],
            })
        elif parsed.path == "/api/experimental-validation/status":
            self._send_json({"ok": True, "experimental_validation": _experimental_validation_status()})
        elif parsed.path == "/api/p3/status":
            self._send_json(_p3_status_payload())
        elif parsed.path == "/api/p4/status":
            self._send_json(_p4_status_payload())
        elif parsed.path == "/api/p5/status":
            self._send_json(_p5_status_payload())
        elif parsed.path == "/api/p6/status":
            self._send_json(_p6_status_payload())
        elif parsed.path == "/api/p7/status":
            self._send_json(_p7_status_payload())
        elif parsed.path == "/api/dac2027/p1/status":
            self._send_json(_dac2027_p1_status_payload())
        elif parsed.path == "/api/dac2027/p0/status":
            self._send_json(_dac2027_p0_status_payload())
        elif parsed.path == "/api/dac2027/p2/status":
            self._send_json(_dac2027_p2_status_payload())
        elif parsed.path == "/api/dac2027/p3/status":
            self._send_json(_dac2027_p3_status_payload())
        elif parsed.path == "/api/dac2027/p4/status":
            self._send_json(_dac2027_p4_status_payload())
        elif parsed.path == "/api/reference-reports":
            limit = int(parse_qs(parsed.query).get("limit", [30])[0])
            self._send_json({"ok": True, "reports": list_reference_reports(GENERATED_DIR / "reference_reports", limit=limit)})
        elif parsed.path == "/api/workchain-packages":
            limit = int(parse_qs(parsed.query).get("limit", [30])[0])
            self._send_json({"ok": True, "packages": list_reference_workchain_packages(GENERATED_DIR / "workchain_packages", limit=limit)})
        elif parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.removeprefix("/api/jobs/").strip()
            self._send_json({"ok": True, "job": JobStore(JOBS_DIR).get(job_id)})
        elif parsed.path == "/api/benchmarks/busbar-joule-heat":
            self._send_json({"ok": True, "capabilities": _load_busbar_benchmark_capabilities()})
        else:
            self.send_error(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        self._active_endpoint = parsed.path
        self._active_request_payload = {}
        try:
            payload = self._read_json()
            self._active_request_payload = payload
            if parsed.path == "/api/assistant/config":
                self._assistant_config(payload)
            elif parsed.path == "/api/dac2027/p3/prepare":
                self._send_json(_prepare_dac2027_p3_payload())
            elif parsed.path == "/api/assistant/test":
                self._assistant_test(payload)
            elif parsed.path == "/api/assistant/complete":
                self._assistant_complete(payload)
            elif parsed.path == "/api/comsol/connect":
                self._connect_comsol_server()
            elif parsed.path == "/api/comsol/export-preview":
                self._export_comsol_preview(payload)
            elif parsed.path == "/api/comsol/export-3d":
                self._export_comsol_3d(payload)
            elif parsed.path == "/api/inspect-matlab":
                self._inspect_matlab(payload)
            elif parsed.path == "/api/validate-constraints":
                self._validate_constraints(payload)
            elif parsed.path == "/api/reference-check":
                self._evaluate_reference_check(payload)
            elif parsed.path == "/api/reference-compare":
                self._compare_reference_observation(payload)
            elif parsed.path == "/api/reference-compare-csv":
                self._compare_reference_results_csv(payload)
            elif parsed.path == "/api/workchain/assemble":
                self._assemble_workchain_package(payload)
            elif parsed.path == "/api/workchain/validate":
                self._validate_workchain_package(payload)
            elif parsed.path == "/api/workchain/archive":
                self._archive_workchain_package(payload)
            elif parsed.path == "/api/workchain/archive/validate":
                self._validate_workchain_archive(payload)
            elif parsed.path == "/api/generate-matlab":
                self._generate_matlab(payload)
            elif parsed.path == "/api/generate-comsol-code":
                self._generate_comsol_code(payload)
            elif parsed.path == "/api/read-code":
                self._read_code(payload)
            elif parsed.path == "/api/modify-code":
                self._modify_code(payload)
            elif parsed.path == "/api/train":
                self._train(payload)
            elif parsed.path == "/api/train-with-comsol-holdout":
                self._train_with_comsol_holdout(payload)
            elif parsed.path == "/api/inspect-training-csv":
                self._inspect_training_csv(payload)
            elif parsed.path == "/api/training/prepare-thermal-sweep":
                self._prepare_thermal_sweep(payload)
            elif parsed.path == "/api/training/mesh-convergence":
                self._assess_mesh_convergence(payload)
            elif parsed.path == "/api/training/parameter-coverage":
                self._assess_parameter_coverage(payload)
            elif parsed.path == "/api/training/holdout-independence":
                self._assess_holdout_independence(payload)
            elif parsed.path == "/api/training/prepare-augmentation-retrain":
                self._prepare_augmentation_retrain(payload)
            elif parsed.path == "/api/benchmarks/busbar-joule-heat/predict":
                self._predict_busbar_joule_heat(payload)
            elif parsed.path == "/api/surrogates/thermal-plate/predict":
                self._predict_thermal_plate(payload)
            elif parsed.path == "/api/experimental-validation/run":
                csv_path = _resolve_project_file(
                    str(payload.get("csv_path") or "examples/experimental_temperature_measurements_template.csv")
                )
                model_path = _resolve_project_file(
                    str(payload.get("model_path") or EXPERIMENT_VALIDATION_MODEL_PATH)
                )
                report = validate_temperature_experiment(
                    csv_path,
                    model_path,
                    config_path=EXPERIMENT_VALIDATION_CONFIG_PATH,
                    output_path=EXPERIMENT_VALIDATION_REPORT_PATH,
                )
                self._send_json({"ok": True, "experimental_validation": report})
            elif parsed.path == "/api/surrogates/registered/predict":
                self._predict_registered_surrogate(payload)
            elif parsed.path == "/api/surrogates/registered/augmentation-plan":
                self._create_registered_augmentation_plan(payload)
            elif parsed.path == "/api/surrogates/thermal-plate/augmentation-plan":
                self._create_thermal_augmentation_plan(payload)
            elif parsed.path == "/api/surrogates/thermal-plate/augmentation-queue":
                self._queue_thermal_augmentation(payload)
            elif parsed.path == "/api/surrogates/thermal-plate/augmentation-retrain":
                self._queue_thermal_augmentation_retrain(payload)
            elif parsed.path == "/api/read-file":
                self._read_file(payload)
            elif parsed.path == "/api/read-files":
                self._read_files(payload)
            elif parsed.path == "/api/read-uploaded-file":
                self._read_uploaded_file(payload)
            elif parsed.path == "/api/read-uploaded-files":
                self._read_uploaded_files(payload)
            elif parsed.path == "/api/instruction":
                self._instruction(payload)
            elif parsed.path == "/api/learning-summary":
                self._learning_summary(payload)
            elif parsed.path == "/api/learn-case":
                self._learn_case(payload)
            elif parsed.path == "/api/learn-article":
                self._learn_article(payload)
            elif parsed.path == "/api/plan-model":
                self._plan_model(payload)
            elif parsed.path == "/api/knowledge-system":
                self._knowledge_system(payload)
            elif parsed.path == "/api/knowledge/sync-template-validations":
                self._send_json({"ok": True, "sync": sync_template_validations(JOBS_DIR / "artifact_index.json")})
            elif parsed.path == "/api/staged-workflow":
                self._staged_workflow(payload)
            elif parsed.path == "/api/approve-staged-step":
                self._approve_staged_step(payload)
            elif parsed.path == "/api/finalize-staged-workflow":
                self._finalize_staged_workflow(payload)
            elif parsed.path == "/api/staged-workflow/queue-execution":
                self._queue_staged_package_execution(payload)
            elif parsed.path == "/api/staged-workflow/retry-failed":
                workflow_path = _resolve_user_path(str(payload.get("workflow_path", "")))
                self._send_json({"ok": True, "workflow": retry_failed_stage(workflow_path)})
            elif parsed.path == "/api/jobs":
                self._create_execution_job(payload)
            elif parsed.path == "/api/jobs/joule-heat-benchmark":
                self._create_joule_heat_benchmark(payload)
            elif parsed.path == "/api/jobs/constraint-template":
                self._create_constraint_template_job(payload)
            elif parsed.path == "/api/jobs/match-template":
                self._create_matched_template_job(payload)
            elif parsed.path == "/api/jobs/thermal-sweep-training":
                self._create_thermal_sweep_training_job(payload)
            elif parsed.path == "/api/templates/derive":
                self._derive_template(payload)
            elif parsed.path == "/api/templates/derive-and-queue":
                self._derive_and_queue_template(payload)
            elif parsed.path == "/api/templates/extract-overrides":
                self._extract_template_overrides(payload)
            elif parsed.path == "/api/templates/extract-derive-and-queue":
                self._extract_derive_and_queue(payload)
            elif parsed.path == "/api/templates/match-extract-derive-and-queue":
                self._match_extract_derive_and_queue(payload)
            elif parsed.path == "/api/jobs/process-next":
                self._process_next_job(payload)
            elif parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/retry"):
                job_id = parsed.path.removeprefix("/api/jobs/").removesuffix("/retry").strip("/")
                self._send_json({"ok": True, "job": JobStore(JOBS_DIR).requeue(job_id)})
            elif parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/approve-review"):
                job_id = parsed.path.removeprefix("/api/jobs/").removesuffix("/approve-review").strip("/")
                self._send_json({"ok": True, "job": JobStore(JOBS_DIR).approve_execution_review(job_id)})
            else:
                self.send_error(404, "Not found")
        except RemoteAssistantError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=502)
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                {
                    "ok": False,
                    "error": str(exc),
                    "trace": traceback.format_exc(limit=2),
                },
                status=400,
            )

    def log_message(self, fmt: str, *args: object) -> None:
        print(fmt % args)

    def _assistant_config(self, payload: dict[str, object]) -> None:
        config = save_config(payload, ASSISTANT_CONFIG_PATH, ASSISTANT_KEYS_PATH)
        self._send_json({"ok": True, "message": "AI 接入设置已保存。", "config": config})

    def _assistant_test(self, payload: dict[str, object]) -> None:
        provider = str(payload.get("provider", "")).strip() or None
        result = complete_task(
            "请只回复“API 连接成功”，并附上你实际使用的模型名称。",
            {"purpose": "连接测试"},
            ASSISTANT_CONFIG_PATH,
            ASSISTANT_KEYS_PATH,
            provider_override=provider,
        )
        self._send_json({**result, "message": "远程 AI 连接测试成功。"})

    def _assistant_complete(self, payload: dict[str, object]) -> None:
        context = payload.get("context", {})
        result = complete_task(
            str(payload.get("task", "")),
            context,
            ASSISTANT_CONFIG_PATH,
            ASSISTANT_KEYS_PATH,
            provider_override=str(payload.get("provider", "")).strip() or None,
        )
        self._send_json(result)

    def _inspect_matlab(self, payload: dict[str, object]) -> None:
        path = _resolve_user_path(str(payload.get("path", "")))
        summary = inspect_matlab_file(path)
        self._send_json({"ok": True, "summary": json.loads(summary.to_json())})

    def _validate_constraints(self, payload: dict[str, object]) -> None:
        cfg = _constraints_from_payload(payload)
        validate_constraints(cfg)
        self._send_json({"ok": True, "message": "constraints are valid"})

    def _generate_matlab(self, payload: dict[str, object]) -> None:
        cfg = _constraints_from_payload(payload)
        validate_constraints(cfg)
        script = build_livelink_script_from_constraints(cfg)
        GENERATED_DIR.mkdir(exist_ok=True)
        output_name = _safe_file_name(str(payload.get("output_name") or f"generated_build_{cfg['model_name']}.m"))
        if not output_name.endswith(".m"):
            output_name += ".m"
        output_path = GENERATED_DIR / output_name
        output_path.write_text(script, encoding="utf-8")
        self._send_json({"ok": True, "path": str(output_path), "script": script})

    def _generate_comsol_code(self, payload: dict[str, object]) -> None:
        requirement = str(payload.get("requirement", "")).strip()
        if not requirement:
            raise ValueError("requirement is empty")
        result = generate_comsol_code_from_memory(
            requirement=requirement,
            memory_path=str(payload.get("memory_path", "generated/case_memory/case_memory.json")),
            output_dir=str(payload.get("output_dir", GENERATED_DIR / "code")),
            output_prefix=_safe_file_name(str(payload.get("output_prefix") or "generated_comsol_model")),
            top_k=int(payload.get("top_k", 5)),
            existing_content=str(payload.get("existing_content", "")),
        )
        self._send_json({"ok": True, **result.as_dict()})

    def _read_code(self, payload: dict[str, object]) -> None:
        path = _resolve_user_path(str(payload.get("path", "")))
        result = read_code_file(path)
        self._send_json({"ok": True, "code": result.as_dict()})

    def _modify_code(self, payload: dict[str, object]) -> None:
        path = _resolve_user_path(str(payload.get("path", "")))
        output_raw = str(payload.get("output_path", "")).strip()
        output_path = None
        if output_raw:
            output_path = Path(output_raw)
            if not output_path.is_absolute():
                output_path = (ROOT / output_path).resolve()
        result = modify_code_file(
            path,
            str(payload.get("instruction", "")),
            find_text=str(payload.get("find_text", "")),
            replace_text=str(payload.get("replace_text", "")),
            append_text=str(payload.get("append_text", "")),
            output_path=output_path,
            overwrite=bool(payload.get("overwrite", False)),
        )
        self._send_json({"ok": True, "edit": result.as_dict()})

    def _train(self, payload: dict[str, object]) -> None:
        try:
            from comsol_small_model.surrogate import auto_train_surrogate, train_surrogate
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                f"Missing dependency {exc.name}. Run: pip install -r requirements.txt"
            ) from exc

        csv_path = _resolve_user_path(str(payload.get("csv_path", "")))
        input_columns = _split_columns(str(payload.get("input_columns", "")))
        output_columns = _split_columns(str(payload.get("output_columns", "")))
        MODELS_DIR.mkdir(exist_ok=True)
        model_name = _safe_file_name(str(payload.get("model_name") or "model.joblib"))
        if not model_name.endswith(".joblib"):
            model_name += ".joblib"
        model_path = MODELS_DIR / model_name
        auto = bool(payload.get("auto", False)) or not input_columns or not output_columns
        if auto:
            report, inspection = auto_train_surrogate(
                csv_path,
                model_path,
                input_columns=input_columns or None,
                output_columns=output_columns or None,
            )
            self._send_json(
                {
                    "ok": True,
                    "model_path": str(model_path),
                    "report": asdict(report),
                    "inspection": inspection,
                    "auto_selected": True,
                }
            )
            return
        report = train_surrogate(csv_path, model_path, input_columns, output_columns)
        self._send_json({"ok": True, "model_path": str(model_path), "report": asdict(report), "auto_selected": False})

    def _evaluate_reference_check(self, payload: dict[str, object]) -> None:
        case_type = str(payload.get("case_type", "")).strip()
        parameters = payload.get("parameters_si", {})
        if not case_type or not isinstance(parameters, dict):
            raise ValueError("case_type and parameters_si JSON object are required")
        report = evaluate_reference_case(case_type, parameters)
        self._send_json({"ok": True, "report": report, "artifact": write_reference_report(report, GENERATED_DIR / "reference_reports")})

    def _compare_reference_observation(self, payload: dict[str, object]) -> None:
        parameters = payload.get("parameters_si", {})
        if not isinstance(parameters, dict):
            raise ValueError("parameters_si must be a JSON object")
        report = compare_comsol_observation_to_reference(
            str(payload.get("case_type", "")).strip(),
            parameters,
            reference_key=str(payload.get("reference_key", "")).strip(),
            observed_value=float(payload.get("observed_value")),
            observed_unit=str(payload.get("observed_unit", "")),
            relative_error_threshold_percent=float(payload.get("relative_error_threshold_percent", 5.0)),
        )
        self._send_json({"ok": True, "report": report, "artifact": write_reference_report(report, GENERATED_DIR / "reference_reports")})

    def _compare_reference_results_csv(self, payload: dict[str, object]) -> None:
        parameters = payload.get("parameters_si", {})
        if not isinstance(parameters, dict):
            raise ValueError("parameters_si must be a JSON object")
        report = compare_comsol_results_csv_to_reference(
            _resolve_user_path(str(payload.get("results_csv", ""))),
            observed_result_name=str(payload.get("observed_result_name", "")).strip(),
            case_type=str(payload.get("case_type", "")).strip(),
            parameters_si=parameters,
            reference_key=str(payload.get("reference_key", "")).strip(),
            relative_error_threshold_percent=float(payload.get("relative_error_threshold_percent", 5.0)),
            observed_unit=str(payload.get("observed_unit", "")),
        )
        self._send_json({"ok": True, "report": report, "artifact": write_reference_report(report, GENERATED_DIR / "reference_reports")})

    def _assemble_workchain_package(self, payload: dict[str, object]) -> None:
        raw_paths = payload.get("reference_report_paths", [])
        if not isinstance(raw_paths, list):
            raise ValueError("reference_report_paths must be a JSON array")
        package = create_reference_workchain_package(
            [_resolve_user_path(str(path)) for path in raw_paths],
            GENERATED_DIR / "workchain_packages",
            title=str(payload.get("title", "physics_reference_validation")),
        )
        self._send_json({"ok": True, "package": package})

    def _validate_workchain_package(self, payload: dict[str, object]) -> None:
        package_path = _resolve_user_path(str(payload.get("package_path", "")))
        self._send_json({"ok": True, "report": validate_reference_workchain_package(package_path)})

    def _archive_workchain_package(self, payload: dict[str, object]) -> None:
        package_path = _resolve_user_path(str(payload.get("package_path", "")))
        archive = archive_reference_workchain_package(package_path, GENERATED_DIR / "workchain_archives")
        self._send_json({"ok": True, "archive": archive})

    def _validate_workchain_archive(self, payload: dict[str, object]) -> None:
        archive_path = _resolve_user_path(str(payload.get("archive_path", "")))
        self._send_json({"ok": True, "report": validate_reference_workchain_archive(archive_path)})

    def _assess_mesh_convergence(self, payload: dict[str, object]) -> None:
        records = payload.get("records", [])
        if not isinstance(records, list):
            raise ValueError("records must be a JSON array")
        report = assess_mesh_convergence(
            records,
            output_name=str(payload.get("output_name", "quantity_of_interest")).strip() or "quantity_of_interest",
            relative_change_threshold_percent=float(payload.get("relative_change_threshold_percent", 1.0)),
        )
        self._send_json({"ok": True, "report": report})

    def _assess_parameter_coverage(self, payload: dict[str, object]) -> None:
        import pandas as pd

        csv_path = _resolve_user_path(str(payload.get("csv_path", "")))
        ranges = payload.get("parameter_ranges", {})
        if not isinstance(ranges, dict):
            raise ValueError("parameter_ranges must be a JSON object")
        report = assess_parameter_coverage(pd.read_csv(csv_path), ranges, bins=int(payload.get("bins", 5)))
        self._send_json({"ok": True, "report": report})

    def _assess_holdout_independence(self, payload: dict[str, object]) -> None:
        report = build_holdout_independence_report(
            _resolve_user_path(str(payload.get("training_csv", ""))),
            _resolve_user_path(str(payload.get("holdout_csv", ""))),
            _split_columns(str(payload.get("input_columns", ""))),
            training_manifest=_optional_user_path(payload.get("training_manifest")),
            holdout_manifest=_optional_user_path(payload.get("holdout_manifest")),
        )
        self._send_json({"ok": True, "report": report})

    def _prepare_augmentation_retrain(self, payload: dict[str, object]) -> None:
        output_path = _resolve_user_path(str(payload.get("output_csv", "generated/merged_augmentation_training.csv")))
        report = prepare_augmentation_retrain(
            _resolve_user_path(str(payload.get("training_csv", ""))),
            _resolve_user_path(str(payload.get("augmentation_csv", ""))),
            _resolve_user_path(str(payload.get("previous_holdout_csv", ""))),
            _resolve_user_path(str(payload.get("fresh_holdout_csv", ""))),
            _split_columns(str(payload.get("input_columns", ""))),
            output_path,
        )
        self._send_json({"ok": True, "report": report})

    def _inspect_training_csv(self, payload: dict[str, object]) -> None:
        try:
            from comsol_small_model.surrogate import inspect_training_csv
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                f"Missing dependency {exc.name}. Run: pip install -r requirements.txt"
            ) from exc

        csv_path = _resolve_user_path(str(payload.get("csv_path", "")))
        input_columns = _split_columns(str(payload.get("input_columns", "")))
        output_columns = _split_columns(str(payload.get("output_columns", "")))
        inspection = inspect_training_csv(
            csv_path,
            input_columns=input_columns or None,
            output_columns=output_columns or None,
        )
        self._send_json({"ok": True, "inspection": inspection})

    def _train_with_comsol_holdout(self, payload: dict[str, object]) -> None:
        try:
            from comsol_small_model.surrogate import train_surrogate_with_comsol_holdout
            from comsol_small_model.surrogate_model_card import register_general_surrogate, write_general_surrogate_model_card
            from comsol_small_model.surrogate_validation import validate_surrogate_holdout_relative
        except ModuleNotFoundError as exc:
            raise RuntimeError(f"Missing dependency {exc.name}. Run: pip install -r requirements.txt") from exc

        csv_path = _resolve_user_path(str(payload.get("csv_path", "")))
        holdout_path = _resolve_user_path(str(payload.get("holdout_csv_path", "")))
        inputs = _split_columns(str(payload.get("input_columns", "")))
        outputs = _split_columns(str(payload.get("output_columns", "")))
        if not inputs or not outputs:
            raise ValueError("input_columns and output_columns are required for independent holdout training")
        threshold = float(payload.get("max_relative_error_percent", 5.0))
        model_name = _safe_file_name(str(payload.get("model_name") or "validated_surrogate.joblib"))
        if not model_name.endswith(".joblib"):
            model_name += ".joblib"
        MODELS_DIR.mkdir(exist_ok=True)
        model_path = MODELS_DIR / model_name
        selected = train_surrogate_with_comsol_holdout(csv_path, holdout_path, model_path, inputs, outputs)
        validation_dir = GENERATED_DIR / "surrogate_validations"
        validation = validate_surrogate_holdout_relative(model_path, holdout_path, max_relative_error_percent=threshold, output_path=validation_dir / f"{model_path.stem}_holdout_validation.json")
        card = write_general_surrogate_model_card(
            model_name=Path(model_name).stem,
            model_path=model_path,
            training_csv=csv_path,
            holdout_csv=holdout_path,
            input_columns=inputs,
            output_columns=outputs,
            physical_scope=str(payload.get("physical_scope", "")).strip(),
            validation=validation,
            output_dir=GENERATED_DIR / "model_cards",
        )
        registry = register_general_surrogate(
            model_name=Path(model_name).stem,
            model_path=model_path,
            card=card,
            validation=validation,
            registry_path=SURROGATE_REGISTRY_PATH,
        )
        runtime_audit = audit_registered_surrogates(
            SURROGATE_REGISTRY_PATH,
            simulate_relocation=True,
        )
        write_runtime_audit(runtime_audit, SURROGATE_RUNTIME_AUDIT_PATH)
        self._send_json({"ok": True, "model_path": str(model_path), "selection": selected, "validation": validation, "model_card": card, "registry": registry, "runtime_audit": runtime_audit})

    def _prepare_thermal_sweep(self, payload: dict[str, object]) -> None:
        spec_path = ROOT / "configs" / "thermal_plate_sweep_training.json"
        output_dir = GENERATED_DIR / "training_sweeps"
        result = write_thermal_sweep_matlab(
            spec_path,
            output_dir / "run_thermal_plate_sweep.m",
            output_dir / "thermal_plate_sweep.csv",
        )
        self._send_json({"ok": True, **result, "next_action": "Run the generated MATLAB script with the local COMSOL LiveLink node, then inspect and train the CSV."})

    def _predict_busbar_joule_heat(self, payload: dict[str, object]) -> None:
        from comsol_small_model.surrogate import predict

        voltage_mv = float(payload.get("Vtot_mV"))
        htc_w_m2k = float(payload.get("htc_W_m2K"))
        capabilities = _load_busbar_benchmark_capabilities()
        estimator = capabilities["fast_estimator"]
        ranges = estimator["validated_ranges"]
        in_range = (
            ranges["Vtot_mV"][0] <= voltage_mv <= ranges["Vtot_mV"][1]
            and ranges["htc_W_m2K"][0] <= htc_w_m2k <= ranges["htc_W_m2K"][1]
        )
        if not in_range:
            self._send_json(
                {
                    "ok": False,
                    "error": "输入超出已验证代理模型范围，请改用 COMSOL 真实求解。",
                    "validated_ranges": ranges,
                },
                status=400,
            )
            return
        prediction = predict(BUSBAR_BENCHMARK_DIR / estimator["model"], [voltage_mv, htc_w_m2k])
        self._send_json(
            {
                "ok": True,
                "benchmark": "busbar_joule_heat",
                "inputs": {"Vtot_mV": voltage_mv, "htc_W_m2K": htc_w_m2k},
                "prediction": prediction,
                "validated_ranges": ranges,
                "holdout_relative_error_percent": estimator["holdout_relative_error_percent"],
                "guidance": "此结果仅适用于当前母线板几何、材料与边界条件；发生变化时请执行 COMSOL 求解。",
            }
        )

    def _predict_thermal_plate(self, payload: dict[str, object]) -> None:
        raw_path = str(payload.get("model_path", "")).strip()
        model_path = _resolve_user_path(raw_path) if raw_path else latest_validated_thermal_model(JOBS_DIR)
        inputs = {
            "L_m": payload.get("L_m"),
            "W_m": payload.get("W_m"),
            "k_W_mK": payload.get("k_W_mK"),
            "T_hot_K": payload.get("T_hot_K"),
            "T_cold_K": payload.get("T_cold_K"),
        }
        self._send_json(predict_validated_surrogate(model_path, inputs))

    def _predict_registered_surrogate(self, payload: dict[str, object]) -> None:
        model_id = str(payload.get("model_id", "")).strip()
        raw_inputs = payload.get("inputs", {})
        if not model_id:
            raise ValueError("model_id is required")
        if not isinstance(raw_inputs, dict):
            raise ValueError("inputs must be a JSON object")
        result = predict_registered_surrogate(_registered_surrogate_registry_path(model_id), model_id, raw_inputs)
        self._send_json(result, status=200 if result.get("ok") else 400)

    def _create_registered_augmentation_plan(self, payload: dict[str, object]) -> None:
        model_id = str(payload.get("model_id", "")).strip()
        raw_inputs = payload.get("inputs", {})
        if not model_id or not isinstance(raw_inputs, dict):
            raise ValueError("model_id and JSON object inputs are required")
        plan = write_registered_augmentation_plan(
            _registered_surrogate_registry_path(model_id),
            model_id,
            raw_inputs,
            GENERATED_DIR / "augmentation_plans",
        )
        self._send_json({"ok": True, "plan": plan})

    def _create_thermal_augmentation_plan(self, payload: dict[str, object]) -> None:
        raw_path = str(payload.get("model_path", "")).strip()
        model_path = _resolve_user_path(raw_path) if raw_path else latest_validated_thermal_model(JOBS_DIR)
        inputs = {
            "L_m": payload.get("L_m"),
            "W_m": payload.get("W_m"),
            "k_W_mK": payload.get("k_W_mK"),
            "T_hot_K": payload.get("T_hot_K"),
            "T_cold_K": payload.get("T_cold_K"),
        }
        plan = write_thermal_augmentation_plan(model_path, inputs, GENERATED_DIR / "augmentation_plans")
        self._send_json({"ok": True, "plan": plan})

    def _queue_thermal_augmentation(self, payload: dict[str, object]) -> None:
        plan_path = _resolve_user_path(str(payload.get("plan_path", "")))
        job = create_thermal_augmentation_job(plan_path, job_dir=JOBS_DIR)
        self._send_json({"ok": True, "job": job})

    def _queue_thermal_augmentation_retrain(self, payload: dict[str, object]) -> None:
        job_id = str(payload.get("augmentation_job_id", "")).strip()
        if not job_id:
            raise ValueError("augmentation_job_id is required")
        job = create_thermal_augmentation_retrain_job(job_id, job_dir=JOBS_DIR)
        self._send_json({"ok": True, "job": job})

    def _read_file(self, payload: dict[str, object]) -> None:
        path = _resolve_user_path(str(payload.get("path", "")))
        summary = summarize_file(path)
        self._send_json({"ok": True, "summary": summary.as_dict()})

    def _read_files(self, payload: dict[str, object]) -> None:
        raw_paths = payload.get("paths", [])
        if isinstance(raw_paths, str):
            raw_paths = _split_lines(raw_paths)
        if not isinstance(raw_paths, list) or not raw_paths:
            raise ValueError("paths must be a non-empty list")
        paths = [_resolve_user_path(str(path)) for path in raw_paths]
        summary = summarize_files(paths)
        self._send_json({"ok": True, "summary": summary})

    def _read_uploaded_file(self, payload: dict[str, object]) -> None:
        name = str(payload.get("name", "uploaded.txt"))
        encoded = str(payload.get("content_base64", ""))
        if encoded:
            summary = summarize_uploaded_binary(name, base64.b64decode(encoded, validate=True))
        else:
            summary = summarize_uploaded_text(name, str(payload.get("content", "")))
        self._send_json({"ok": True, "summary": summary.as_dict()})

    def _read_uploaded_files(self, payload: dict[str, object]) -> None:
        files = payload.get("files", [])
        if not isinstance(files, list) or not files:
            raise ValueError("files must be a non-empty list")
        normalized = []
        for file in files:
            if not isinstance(file, dict):
                raise ValueError("each uploaded file must be an object")
            name = str(file.get("name", "uploaded.txt"))
            encoded = str(file.get("content_base64", ""))
            if encoded:
                normalized.append(
                    summarize_uploaded_binary(name, base64.b64decode(encoded, validate=True)).as_dict()
                )
            else:
                normalized.append(summarize_uploaded_text(name, str(file.get("content", ""))).as_dict())
        summary = summarize_collection(normalized)
        self._send_json({"ok": True, "summary": summary})

    def _instruction(self, payload: dict[str, object]) -> None:
        instruction = str(payload.get("instruction", ""))
        file_summary = payload.get("file_summary")
        if file_summary is not None and not isinstance(file_summary, dict):
            raise ValueError("file_summary must be an object")
        model_plan = None
        if instruction.strip():
            try:
                model_plan = generate_model_plan(
                    instruction,
                    str(payload.get("memory_path", "generated/case_memory/case_memory.json")),
                    int(payload.get("top_k", 3)),
                )
            except Exception as exc:  # noqa: BLE001
                model_plan = {"error": str(exc), "matched_cases": [], "case_count": 0}
        joule_inputs = extract_joule_rectangle_prediction_inputs(instruction)
        actuator_inputs = extract_thermal_actuator_prediction_inputs(instruction)
        circuit_resistor_inputs = _extract_circuit_fem_resistor_inputs(instruction)
        mast_inputs = _extract_mast_diagonal_mounting_inputs(instruction)
        heat_convection_inputs = _extract_heat_convection_2d_inputs(instruction)
        electric_field_inputs = _extract_electric_field_concentric_cylinders_inputs(instruction)
        capacitor_inputs = _extract_capacitor_dc_permittivity_inputs(instruction)
        simple_resistor_inputs = _extract_simple_resistor_conductivity_inputs(instruction)
        heat_radiation_inputs = _extract_heat_radiation_1d_inputs(instruction)
        tapered_cantilever_inputs = _extract_tapered_cantilever_force_inputs(instruction)
        lid_driven_cavity_inputs = _extract_lid_driven_cavity_reynolds_inputs(instruction)
        room_acoustic_inputs = _extract_room_acoustic_target_mode_inputs(instruction)
        effective_diffusivity_inputs = _extract_effective_diffusivity_1d_inputs(instruction)
        fresnel_inputs = _extract_fresnel_equations_rf_inputs(instruction)
        magnetic_field_inputs = _extract_magnetic_field_infinite_conductor_inputs(instruction)
        helmholtz_inputs = _extract_helmholtz_coil_inputs(instruction)
        parallel_wires_inputs = _extract_parallel_wires_force_inputs(instruction)
        thermoelectric_inputs = _extract_thermoelectric_generator_inputs(instruction)
        pn_junction_inputs = _extract_pn_junction_carrier_inputs(instruction)
        pn_junction_current_density_inputs = _extract_pn_junction_current_density_inputs(instruction)
        power_inductor_inputs = _extract_power_inductor_frequency_inputs(instruction)
        thermal_inputs = extract_thermal_plate_prediction_inputs(instruction)
        gecko_inputs = _extract_gecko_foot_inputs(instruction)
        joule_scope_changes = detect_joule_rectangle_scope_changes(instruction)
        if _is_execution_review_approval_request(instruction):
            response = _approve_execution_review_from_chat(instruction)
        elif _is_execution_status_query(instruction):
            response = _execution_status_dialogue(_health_payload())
        elif _is_validated_surrogate_catalog_request(instruction):
            response = _validated_surrogate_catalog_dialogue()
        elif _is_chat_code_read_request(instruction):
            response = _code_read_dialogue(_chat_code_read_result(instruction))
        elif _is_gecko_foot_request(instruction) and gecko_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(GECKO_FOOT_MODEL_ID),
                GECKO_FOOT_MODEL_ID,
                gecko_inputs,
            )
            response = _gecko_foot_prediction_dialogue(prediction)
        elif _is_gecko_foot_request(instruction):
            response = _gecko_foot_missing_inputs_dialogue()
        elif _is_mast_diagonal_mounting_request(instruction) and mast_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(MAST_DIAGONAL_MOUNTING_MODEL_ID),
                MAST_DIAGONAL_MOUNTING_MODEL_ID,
                mast_inputs,
            )
            response = _mast_diagonal_mounting_prediction_dialogue(prediction)
        elif _is_mast_diagonal_mounting_request(instruction):
            response = _mast_diagonal_mounting_missing_inputs_dialogue()
        elif _is_heat_convection_2d_request(instruction) and heat_convection_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(HEAT_CONVECTION_2D_MODEL_ID),
                HEAT_CONVECTION_2D_MODEL_ID,
                heat_convection_inputs,
            )
            response = _heat_convection_2d_prediction_dialogue(prediction)
        elif _is_heat_convection_2d_request(instruction):
            response = _heat_convection_2d_missing_inputs_dialogue()
        elif _is_electric_field_concentric_cylinders_request(instruction) and electric_field_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(ELECTRIC_FIELD_CONCENTRIC_CYLINDERS_MODEL_ID),
                ELECTRIC_FIELD_CONCENTRIC_CYLINDERS_MODEL_ID,
                electric_field_inputs,
            )
            response = _electric_field_concentric_cylinders_prediction_dialogue(prediction)
        elif _is_electric_field_concentric_cylinders_request(instruction):
            response = _electric_field_concentric_cylinders_missing_inputs_dialogue()
        elif _is_capacitor_dc_permittivity_request(instruction) and capacitor_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(CAPACITOR_DC_PERMITTIVITY_MODEL_ID),
                CAPACITOR_DC_PERMITTIVITY_MODEL_ID,
                capacitor_inputs,
            )
            response = _capacitor_dc_permittivity_prediction_dialogue(prediction)
        elif _is_capacitor_dc_permittivity_request(instruction):
            response = _capacitor_dc_permittivity_missing_inputs_dialogue()
        elif _is_simple_resistor_conductivity_request(instruction) and simple_resistor_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(SIMPLE_RESISTOR_CONDUCTIVITY_MODEL_ID),
                SIMPLE_RESISTOR_CONDUCTIVITY_MODEL_ID,
                simple_resistor_inputs,
            )
            response = _simple_resistor_conductivity_prediction_dialogue(prediction)
        elif _is_simple_resistor_conductivity_request(instruction):
            response = _simple_resistor_conductivity_missing_inputs_dialogue()
        elif _is_heat_radiation_1d_request(instruction) and heat_radiation_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(HEAT_RADIATION_1D_MODEL_ID),
                HEAT_RADIATION_1D_MODEL_ID,
                heat_radiation_inputs,
            )
            response = _heat_radiation_1d_prediction_dialogue(prediction)
        elif _is_heat_radiation_1d_request(instruction):
            response = _heat_radiation_1d_missing_inputs_dialogue()
        elif _is_tapered_cantilever_force_request(instruction) and tapered_cantilever_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(TAPERED_CANTILEVER_FORCE_MODEL_ID),
                TAPERED_CANTILEVER_FORCE_MODEL_ID,
                tapered_cantilever_inputs,
            )
            response = _tapered_cantilever_force_prediction_dialogue(prediction)
        elif _is_tapered_cantilever_force_request(instruction):
            response = _tapered_cantilever_force_missing_inputs_dialogue()
        elif _is_lid_driven_cavity_reynolds_request(instruction) and lid_driven_cavity_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(LID_DRIVEN_CAVITY_REYNOLDS_MODEL_ID),
                LID_DRIVEN_CAVITY_REYNOLDS_MODEL_ID,
                lid_driven_cavity_inputs,
            )
            response = _lid_driven_cavity_reynolds_prediction_dialogue(prediction)
        elif _is_lid_driven_cavity_reynolds_request(instruction):
            response = _lid_driven_cavity_reynolds_missing_inputs_dialogue()
        elif _is_room_acoustic_target_mode_request(instruction) and room_acoustic_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(ROOM_ACOUSTIC_TARGET_MODE_MODEL_ID),
                ROOM_ACOUSTIC_TARGET_MODE_MODEL_ID,
                room_acoustic_inputs,
            )
            response = _room_acoustic_target_mode_prediction_dialogue(prediction)
        elif _is_room_acoustic_target_mode_request(instruction):
            response = _room_acoustic_target_mode_missing_inputs_dialogue()
        elif _is_effective_diffusivity_1d_request(instruction) and effective_diffusivity_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(EFFECTIVE_DIFFUSIVITY_1D_MODEL_ID),
                EFFECTIVE_DIFFUSIVITY_1D_MODEL_ID,
                effective_diffusivity_inputs,
            )
            response = _effective_diffusivity_1d_prediction_dialogue(prediction)
        elif _is_effective_diffusivity_1d_request(instruction):
            response = _effective_diffusivity_1d_missing_inputs_dialogue()
        elif _is_fresnel_equations_rf_request(instruction) and fresnel_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(FRESNEL_EQUATIONS_RF_MODEL_ID),
                FRESNEL_EQUATIONS_RF_MODEL_ID,
                fresnel_inputs,
            )
            response = _fresnel_equations_rf_prediction_dialogue(prediction)
        elif _is_fresnel_equations_rf_request(instruction):
            response = _fresnel_equations_rf_missing_inputs_dialogue()
        elif _is_magnetic_field_infinite_conductor_request(instruction) and magnetic_field_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(MAGNETIC_FIELD_INFINITE_CONDUCTOR_MODEL_ID),
                MAGNETIC_FIELD_INFINITE_CONDUCTOR_MODEL_ID,
                magnetic_field_inputs,
            )
            response = _magnetic_field_infinite_conductor_prediction_dialogue(prediction)
        elif _is_magnetic_field_infinite_conductor_request(instruction):
            response = _magnetic_field_infinite_conductor_missing_inputs_dialogue()
        elif _is_helmholtz_coil_request(instruction) and helmholtz_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(HELMHOLTZ_COIL_MODEL_ID),
                HELMHOLTZ_COIL_MODEL_ID,
                helmholtz_inputs,
            )
            response = _helmholtz_coil_prediction_dialogue(prediction)
        elif _is_helmholtz_coil_request(instruction):
            response = _helmholtz_coil_missing_inputs_dialogue()
        elif _is_parallel_wires_force_request(instruction) and parallel_wires_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(PARALLEL_WIRES_FORCE_MODEL_ID),
                PARALLEL_WIRES_FORCE_MODEL_ID,
                parallel_wires_inputs,
            )
            response = _parallel_wires_force_prediction_dialogue(prediction)
        elif _is_parallel_wires_force_request(instruction):
            response = _parallel_wires_force_missing_inputs_dialogue()
        elif _is_thermoelectric_generator_request(instruction) and thermoelectric_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(THERMOELECTRIC_GENERATOR_MODEL_ID),
                THERMOELECTRIC_GENERATOR_MODEL_ID,
                thermoelectric_inputs,
            )
            response = _thermoelectric_generator_prediction_dialogue(prediction)
        elif _is_thermoelectric_generator_request(instruction):
            response = _thermoelectric_generator_missing_inputs_dialogue()
        elif _is_pn_junction_current_density_request(instruction) and pn_junction_current_density_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(PN_JUNCTION_CURRENT_DENSITY_MODEL_ID),
                PN_JUNCTION_CURRENT_DENSITY_MODEL_ID,
                pn_junction_current_density_inputs,
            )
            response = _pn_junction_current_density_prediction_dialogue(prediction)
        elif _is_pn_junction_current_density_request(instruction):
            response = _pn_junction_current_density_missing_inputs_dialogue()
        elif _is_pn_junction_carrier_request(instruction) and pn_junction_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(PN_JUNCTION_CARRIER_MODEL_ID),
                PN_JUNCTION_CARRIER_MODEL_ID,
                pn_junction_inputs,
            )
            response = _pn_junction_carrier_prediction_dialogue(prediction)
        elif _is_pn_junction_carrier_request(instruction):
            response = _pn_junction_carrier_missing_inputs_dialogue()
        elif _is_circuit_fem_resistor_request(instruction) and circuit_resistor_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(CIRCUIT_FEM_RESISTOR_MODEL_ID),
                CIRCUIT_FEM_RESISTOR_MODEL_ID,
                circuit_resistor_inputs,
            )
            response = _circuit_fem_resistor_prediction_dialogue(prediction)
        elif _is_circuit_fem_resistor_request(instruction):
            response = _circuit_fem_resistor_missing_inputs_dialogue()
        elif _is_simplified_thermal_actuator_request(instruction) and actuator_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(THERMAL_ACTUATOR_SIMPLIFIED_MODEL_ID),
                THERMAL_ACTUATOR_SIMPLIFIED_MODEL_ID,
                actuator_inputs,
            )
            response = _thermal_actuator_simplified_prediction_dialogue(prediction)
        elif _is_simplified_thermal_actuator_request(instruction):
            response = _thermal_actuator_simplified_missing_inputs_dialogue()
        elif is_thermal_actuator_augmentation_request(instruction) and actuator_inputs:
            plan = write_registered_augmentation_plan(
                _registered_surrogate_registry_path(THERMAL_ACTUATOR_MODEL_ID),
                THERMAL_ACTUATOR_MODEL_ID,
                actuator_inputs,
                GENERATED_DIR / 'augmentation_plans',
            )
            response = _thermal_actuator_augmentation_dialogue(plan)
        elif actuator_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(THERMAL_ACTUATOR_MODEL_ID),
                THERMAL_ACTUATOR_MODEL_ID,
                actuator_inputs,
            )
            response = _thermal_actuator_prediction_dialogue(prediction)
        elif is_thermal_actuator_prediction_request(instruction):
            response = _thermal_actuator_missing_inputs_dialogue()
        elif is_joule_rectangle_prediction_request(instruction) and joule_scope_changes:
            response = _joule_rectangle_scope_change_dialogue(joule_scope_changes)
        elif joule_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(JOULE_RECTANGLE_MODEL_ID),
                JOULE_RECTANGLE_MODEL_ID,
                joule_inputs,
            )
            response = _joule_rectangle_prediction_dialogue(prediction)
        elif is_joule_rectangle_prediction_request(instruction):
            response = _joule_rectangle_missing_voltage_dialogue()
        elif _is_power_inductor_frequency_request(instruction) and power_inductor_inputs:
            prediction = predict_registered_surrogate(
                _registered_surrogate_registry_path(POWER_INDUCTOR_FREQUENCY_MODEL_ID),
                POWER_INDUCTOR_FREQUENCY_MODEL_ID,
                power_inductor_inputs,
            )
            response = _power_inductor_frequency_prediction_dialogue(prediction)
        elif _is_power_inductor_frequency_request(instruction):
            response = _power_inductor_frequency_missing_inputs_dialogue()
        elif thermal_inputs:
            prediction = predict_validated_surrogate(latest_validated_thermal_model(JOBS_DIR), thermal_inputs)
            response = _thermal_prediction_dialogue(prediction)
        else:
            response = respond_to_instruction(instruction, file_summary, model_plan)
        prediction_details = locals().get("prediction")
        if isinstance(prediction_details, dict) and isinstance(response, dict):
            response = _attach_prediction_quality(response, prediction_details)
        correction_memory = None
        correction = response.get("physics_correction") if isinstance(response, dict) else None
        if isinstance(correction, dict) and correction.get("corrected_physics"):
            memory_path = str(payload.get("memory_path", "generated/case_memory/case_memory.json"))
            correction_memory = remember_physics_correction(
                requirement=str(correction.get("requirement", instruction)),
                corrected_physics=str(correction.get("corrected_physics", "")),
                rationale=str(correction.get("rationale", "")),
                memory_path=memory_path,
            )
            response["correction_memory"] = {
                "path": correction_memory["memory_path"],
                "correction_count": correction_memory["correction_count"],
                "corrected_physics": correction_memory["correction"]["corrected_physics"],
            }
        self._send_json({"ok": True, "response": response})

    def _learning_summary(self, payload: dict[str, object]) -> None:
        file_summary = payload.get("file_summary")
        if not isinstance(file_summary, dict):
            raise ValueError("file_summary must be an object")
        learning = build_learning_summary(file_summary)
        response: dict[str, object] = {"ok": True, "summary": learning}
        if bool(payload.get("remember", True)):
            remembered = remember_learning_summary(
                file_summary,
                memory_path=str(payload.get("memory_path", "generated/case_memory/case_memory.json")),
                title=str(payload.get("title", "")).strip(),
            )
            response["memory"] = {
                "path": remembered["memory_path"],
                "case_count": remembered["case_count"],
                "entry_title": remembered["entry"]["title"],
                "quality": remembered["entry"].get("quality", {}),
            }
        self._send_json(response)

    def _learn_case(self, payload: dict[str, object]) -> None:
        case_dir = _resolve_user_path(str(payload.get("case_dir", "")))
        title = str(payload.get("title", "")).strip() or None
        output_dir = str(payload.get("output_dir", "generated/case_knowledge"))
        memory_path = str(payload.get("memory_path", "generated/case_memory/case_memory.json"))
        prompt_summary = str(payload.get("prompt_summary", "")).strip()
        result = summarize_case_directory(case_dir, title=title, output_dir=output_dir, prompt_summary=prompt_summary)
        memory = remember_case(result["card"], memory_path)
        summary = result["card"].get("post_learning_summary", {})
        self._send_json(
            {
                "ok": True,
                "card": result["card"],
                "summary": summary,
                "outputs": result["outputs"],
                "memory": {
                    "path": memory["memory_path"],
                    "case_count": memory["case_count"],
                },
            }
        )

    def _learn_article(self, payload: dict[str, object]) -> None:
        article_path = _resolve_user_path(str(payload.get("article_path", "")))
        output_dir = str(payload.get("output_dir", "generated/article_knowledge"))
        memory_path = str(payload.get("memory_path", "generated/case_memory/case_memory.json"))
        result = summarize_article_docx(article_path, output_dir=output_dir, memory_path=memory_path)
        self._send_json(
            {
                "ok": True,
                "card": result["card"],
                "outputs": result["outputs"],
                "memory": {
                    "path": result["memory"]["memory_path"],
                    "case_count": result["memory"]["case_count"],
                    "quality": result["memory"]["entry"].get("quality", {}),
                },
            }
        )

    def _plan_model(self, payload: dict[str, object]) -> None:
        requirement = str(payload.get("requirement", "")).strip()
        if not requirement:
            raise ValueError("requirement is empty")
        memory_path = str(payload.get("memory_path", "generated/case_memory/case_memory.json"))
        top_k = int(payload.get("top_k", 5))
        self._send_json({"ok": True, "plan": generate_model_plan(requirement, memory_path, top_k)})

    def _knowledge_system(self, payload: dict[str, object]) -> None:
        memory_path = str(payload.get("memory_path", "generated/case_memory/case_memory.json"))
        self._send_json({"ok": True, **refresh_knowledge_system(memory_path)})

    def _staged_workflow(self, payload: dict[str, object]) -> None:
        requirement = str(payload.get("requirement", "")).strip()
        if not requirement:
            raise ValueError("requirement is empty")
        workflow = create_staged_workflow(
            requirement,
            memory_path=str(payload.get("memory_path", "generated/case_memory/case_memory.json")),
            output_dir=str(payload.get("output_dir", GENERATED_DIR / "staged_workflows")),
            top_k=int(payload.get("top_k", 5)),
        )
        self._send_json({"ok": True, "workflow": workflow})

    def _approve_staged_step(self, payload: dict[str, object]) -> None:
        workflow_path = _resolve_user_path(str(payload.get("workflow_path", "")))
        workflow = approve_current_step(
            workflow_path,
            approved=bool(payload.get("approved", True)),
            comment=str(payload.get("comment", "")),
            output_dir=workflow_path.parent,
        )
        self._send_json({"ok": True, "workflow": workflow})

    def _finalize_staged_workflow(self, payload: dict[str, object]) -> None:
        workflow_path = _resolve_user_path(str(payload.get("workflow_path", "")))
        result = final_modeling_package(workflow_path, output_dir=workflow_path.parent)
        self._send_json({"ok": True, **result})

    def _queue_staged_package_execution(self, payload: dict[str, object]) -> None:
        package_path = _resolve_user_path(str(payload.get("package_path", "")))
        job = create_approved_package_job(package_path, job_dir=JOBS_DIR)
        self._send_json({"ok": True, "job": job, "package_path": str(package_path)})

    def _create_execution_job(self, payload: dict[str, object]) -> None:
        job = create_job(
            str(payload.get("requirement", "")),
            job_type=str(payload.get("job_type", "comsol_modeling")),
            job_dir=JOBS_DIR,
            memory_path=str(payload.get("memory_path", "generated/case_memory/case_memory.json")),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
        )
        self._send_json({"ok": True, "job": job})

    def _create_joule_heat_benchmark(self, payload: dict[str, object]) -> None:
        job = create_joule_heat_benchmark_job(
            job_dir=JOBS_DIR,
            memory_path=str(payload.get("memory_path", "generated/case_memory/case_memory.json")),
        )
        self._send_json({"ok": True, "job": job})

    def _create_constraint_template_job(self, payload: dict[str, object]) -> None:
        template_path = _resolve_user_path(str(payload.get("template_path", "")))
        job = create_constraint_template_job(template_path, job_dir=JOBS_DIR)
        self._send_json({"ok": True, "job": job, "template_path": str(template_path)})

    def _create_matched_template_job(self, payload: dict[str, object]) -> None:
        job = create_matched_template_job(str(payload.get("requirement", "")), job_dir=JOBS_DIR)
        self._send_json({"ok": True, "job": job, "template_match": job.get("template_match", {})})

    def _create_thermal_sweep_training_job(self, payload: dict[str, object]) -> None:
        job = create_thermal_sweep_training_job(job_dir=JOBS_DIR)
        self._send_json({"ok": True, "job": job})

    def _derive_template(self, payload: dict[str, object]) -> None:
        source = _resolve_user_path(str(payload.get("template_path", "")))
        overrides = payload.get("overrides", {})
        if not isinstance(overrides, dict):
            raise ValueError("overrides must be an object")
        result = derive_constraints(source, overrides, GENERATED_DIR / "derived_constraints")
        self._send_json({"ok": True, **result})

    def _derive_and_queue_template(self, payload: dict[str, object]) -> None:
        source = _resolve_user_path(str(payload.get("template_path", "")))
        overrides = payload.get("overrides", {})
        if not isinstance(overrides, dict):
            raise ValueError("overrides must be an object")
        result = derive_constraints(source, overrides, GENERATED_DIR / "derived_constraints")
        job = create_constraint_template_job(result["path"], job_dir=JOBS_DIR)
        self._send_json({"ok": True, **result, "job": job})

    def _extract_template_overrides(self, payload: dict[str, object]) -> None:
        source = _resolve_user_path(str(payload.get("template_path", "")))
        result = extract_text_overrides(str(payload.get("requirement", "")), source)
        self._send_json({"ok": True, **result})

    def _extract_derive_and_queue(self, payload: dict[str, object]) -> None:
        source = _resolve_user_path(str(payload.get("template_path", "")))
        extracted = extract_text_overrides(str(payload.get("requirement", "")), source)
        if not extracted["overrides"]:
            raise ValueError("No supported parameter with an explicit value and unit was found.")
        result = derive_constraints(source, extracted["overrides"], GENERATED_DIR / "derived_constraints")
        job = create_constraint_template_job(result["path"], job_dir=JOBS_DIR)
        self._send_json({"ok": True, "extracted": extracted, **result, "job": job})

    def _match_extract_derive_and_queue(self, payload: dict[str, object]) -> None:
        requirement = str(payload.get("requirement", "")).strip()
        match = select_validated_template(requirement, ROOT)
        if not match.get("matched"):
            raise ValueError(str(match.get("reason", "No validated template matched the requirement.")))
        source = Path(str(match["template_path"]))
        extracted = extract_text_overrides(requirement, source)
        if not extracted["overrides"]:
            raise ValueError("A validated template matched, but no explicit supported parameter value was found in the instruction.")
        result = derive_constraints(source, extracted["overrides"], GENERATED_DIR / "derived_constraints")
        job = create_constraint_template_job(result["path"], job_dir=JOBS_DIR)
        self._send_json({"ok": True, "template_match": match, "extracted": extracted, **result, "job": job})

    def _process_next_job(self, payload: dict[str, object]) -> None:
        job = process_next_job(
            job_dir=JOBS_DIR,
            node_config_path=ROOT / "configs" / "execution_node.json",
        )
        self._send_json({"ok": True, "job": job, "node": load_execution_node_config(ROOT / "configs" / "execution_node.json")})

    def _connect_comsol_server(self) -> None:
        config = load_execution_node_config(ROOT / "configs" / "execution_node.json")
        connect_config = dict(config)
        connect_config["start_comsol_server"] = True
        log_path = GENERATED_DIR / "training_runs" / "comsol_mphserver_connect.log"
        result = ensure_comsol_server(connect_config, log_path=log_path, detached=True)
        ready = bool(result.get("ready"))
        self._send_json(
            {
                "ok": ready,
                "connection": result,
                "message": result.get("message", ""),
            },
            status=200 if ready else 503,
        )

    def _export_comsol_preview(self, payload: dict[str, object]) -> None:
        config = load_execution_node_config(ROOT / "configs" / "execution_node.json")
        try:
            model_path = resolve_generated_mph(GENERATED_DIR, str(payload.get("path", "")))
        except PreviewExportError as exc:
            self._send_json({"ok": False, "message": str(exc)}, status=400)
            return

        connect_config = dict(config)
        connect_config["start_comsol_server"] = True
        server = ensure_comsol_server(
            connect_config,
            log_path=GENERATED_DIR / "training_runs" / "comsol_mphserver_preview.log",
            detached=True,
        )
        if not server.get("ready"):
            self._send_json(
                {"ok": False, "message": str(server.get("message", "COMSOL 端口连接失败。")), "connection": server},
                status=503,
            )
            return
        try:
            result = export_mph_preview(model_path, config=config, matlab_script_dir=ROOT / "matlab")
        except PreviewExportError as exc:
            self._send_json({"ok": False, "message": str(exc), "connection": server}, status=502)
            return

        preview_path = Path(str(result["preview_path"])).resolve()
        relative_preview = preview_path.relative_to(GENERATED_DIR.resolve()).as_posix()
        result["preview_path"] = relative_preview
        result["preview_url"] = f"/api/comsol/preview?path={quote(relative_preview, safe='')}"
        self._send_json(
            {
                "ok": True,
                "message": "COMSOL 已导出当前模型预览。",
                "connection": server,
                "preview": result,
            }
        )

    def _export_comsol_3d(self, payload: dict[str, object]) -> None:
        config = load_execution_node_config(ROOT / "configs" / "execution_node.json")
        try:
            model_path = resolve_generated_mph(GENERATED_DIR, str(payload.get("path", "")))
            result = export_mph_stl(model_path, config=config, working_root=GENERATED_DIR)
        except (PreviewExportError, StlExportError) as exc:
            self._send_json({"ok": False, "message": str(exc)}, status=502)
            return
        stl_path = Path(str(result["stl_path"])).resolve()
        relative_stl = stl_path.relative_to(GENERATED_DIR.resolve()).as_posix()
        result["stl_path"] = relative_stl
        result["stl_url"] = f"/api/comsol/preview?path={quote(relative_stl, safe='')}"
        self._send_json({"ok": True, "message": "COMSOL 三维几何已导出。", "preview": result})

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _send_json(self, payload: object, status: int = 200) -> None:
        if isinstance(payload, dict) and getattr(self, "_active_endpoint", "").startswith("/api/"):
            payload = self._with_work_feedback(payload)
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _with_work_feedback(self, payload: dict[str, object]) -> dict[str, object]:
        if "work_feedback" in payload:
            return payload
        endpoint = getattr(self, "_active_endpoint", "")
        request_payload = redact_secrets(getattr(self, "_active_request_payload", {}))
        feedback = build_work_feedback(endpoint, request_payload, payload)
        enriched = dict(payload)
        enriched["work_feedback"] = feedback
        append_work_log(WORK_LOG_PATH, feedback)
        return enriched

    def _send_html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_comsol_preview(self, relative_path: str) -> None:
        generated_root = GENERATED_DIR.resolve()
        candidate = (generated_root / relative_path).resolve()
        if not candidate.is_relative_to(generated_root) or candidate.suffix.lower() not in {".png", ".jpg", ".jpeg", ".stl"}:
            self.send_error(403, "Preview path is not allowed")
            return
        if not candidate.is_file():
            self.send_error(404, "Preview not found")
            return
        content_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".stl": "model/stl",
        }[candidate.suffix.lower()]
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_download(self, path: Path, content_type: str) -> None:
        candidate = path.resolve()
        if not candidate.is_relative_to(GENERATED_DIR.resolve()) or not candidate.is_file():
            self.send_error(403, "Download path is not allowed")
            return
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{candidate.name}"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def _constraints_from_payload(payload: dict[str, object]) -> dict[str, object]:
    text = str(payload.get("constraints_json", "")).strip()
    if not text:
        raise ValueError("constraints_json is empty")
    return json.loads(text)


def _health_payload() -> dict[str, object]:
    config = load_execution_node_config(ROOT / "configs" / "execution_node.json")
    memory_path = GENERATED_DIR / "case_memory" / "case_memory.json"
    server_host = str(config.get("comsol_server_host", "localhost"))
    server_port = int(config.get("comsol_server_port", 2036))
    return {
        "ok": True,
        "service": "comsol-training-small-model",
        "web_root": str(ROOT),
        "knowledge_memory_available": memory_path.is_file(),
        "execution_node": {
            "enabled": bool(config.get("enabled", False)),
            "external_execution_allowed": bool(config.get("allow_external_execution", False)),
            "comsol_server_host": server_host,
            "comsol_server_port": server_port,
            "server_reachable": _server_reachable(server_host, server_port),
            "auto_start_server": bool(config.get("start_comsol_server", True)),
            "multi_connection": bool(config.get("comsol_server_multi_connection", True)),
        },
        "execution_worker": _worker_status(),
        "surrogate_runtime": _surrogate_runtime_audit_status(),
        "experimental_validation": _experimental_validation_status(),
    }


def _experimental_validation_status(path: str | Path | None = None) -> dict[str, object]:
    report_path = Path(path) if path is not None else EXPERIMENT_VALIDATION_REPORT_PATH
    if not report_path.is_file():
        return {
            "available": False,
            "status": "not_started",
            "passed": False,
            "report_path": str(report_path),
        }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "status": "invalid_report",
            "passed": False,
            "report_path": str(report_path),
            "error": str(exc),
        }
    return {
        "available": True,
        "status": str(report.get("status", "unknown")),
        "passed": bool(report.get("passed", False)),
        "sample_count": int(report.get("sample_count", 0)),
        "created_at": report.get("created_at"),
        "interpretation": report.get("interpretation", ""),
        "report_path": str(report_path),
    }


def _resolve_project_file(value: str) -> Path:
    path = Path(value)
    candidate = path if path.is_absolute() else ROOT / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("实验验证文件必须位于当前项目目录内。") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"实验验证文件不存在：{resolved}")
    return resolved


def _comsol_observer_payload(limit: int = 30) -> dict[str, object]:
    config = load_execution_node_config(ROOT / "configs" / "execution_node.json")
    server_host = str(config.get("comsol_server_host", "localhost"))
    server_port = int(config.get("comsol_server_port", 2036))
    search_roots = (
        GENERATED_DIR / "execution_jobs",
        GENERATED_DIR / "benchmarks",
        GENERATED_DIR / "staged_workflows" / "final_code",
    )
    model_paths: list[Path] = []
    for search_root in search_roots:
        if search_root.is_dir():
            model_paths.extend(path for path in search_root.rglob("*.mph") if path.is_file())
    model_paths.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    artifacts: list[dict[str, object]] = []
    for model_path in model_paths[: max(1, limit)]:
        preview_candidates = (
            model_path.with_name(f"{model_path.stem}_preview.png"),
            model_path.with_name(f"{model_path.stem}_geometry.png"),
            model_path.with_suffix(".png"),
        )
        preview_path = next((path for path in preview_candidates if path.is_file()), None)
        stl_path = model_path.with_name(f"{model_path.stem}_preview.stl")
        relative_model = model_path.resolve().relative_to(GENERATED_DIR.resolve()).as_posix()
        artifact: dict[str, object] = {
            "name": model_path.name,
            "path": relative_model,
            "size_bytes": model_path.stat().st_size,
            "updated_at": datetime.fromtimestamp(model_path.stat().st_mtime, timezone.utc).astimezone().isoformat(),
            "preview_available": preview_path is not None,
            "three_d_available": stl_path.is_file() and stl_path.stat().st_size >= 84,
        }
        if preview_path is not None:
            relative_preview = preview_path.resolve().relative_to(GENERATED_DIR.resolve()).as_posix()
            artifact["preview_path"] = relative_preview
            artifact["preview_url"] = f"/api/comsol/preview?path={quote(relative_preview, safe='')}"
        if stl_path.is_file() and stl_path.stat().st_size >= 84:
            relative_stl = stl_path.resolve().relative_to(GENERATED_DIR.resolve()).as_posix()
            artifact["stl_path"] = relative_stl
            artifact["stl_url"] = f"/api/comsol/preview?path={quote(relative_stl, safe='')}"
            artifact["stl_size_bytes"] = stl_path.stat().st_size
        artifacts.append(artifact)
    return {
        "ok": True,
        "connection": {
            "host": server_host,
            "port": server_port,
            "reachable": _server_reachable(server_host, server_port),
            "external_execution_allowed": bool(config.get("allow_external_execution", False)),
            "preview_export_allowed": bool(config.get("allow_preview_export", False)),
        },
        "artifacts": artifacts,
        "refresh_seconds": 5,
    }


def _surrogate_runtime_audit_status(
    path: str | Path | None = None,
    registry_path: str | Path | None = None,
    legacy_registry_path: str | Path | None = None,
) -> dict[str, object]:
    report_path = Path(path) if path is not None else SURROGATE_RUNTIME_AUDIT_PATH
    current_registry_path = (
        Path(registry_path)
        if registry_path is not None
        else SURROGATE_REGISTRY_PATH
    )
    legacy_path = (
        Path(legacy_registry_path)
        if legacy_registry_path is not None
        else LEGACY_SURROGATE_REGISTRY_PATH
    )
    if not report_path.is_file():
        return {
            "available": False,
            "healthy": False,
            "report_path": str(report_path),
            "state": "not_audited",
        }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        expected_fingerprint = str(report.get("registry_sha256", ""))
        current_fingerprint = (
            hashlib.sha256(current_registry_path.read_bytes()).hexdigest()
            if current_registry_path.is_file()
            else ""
        )
        audit_matches_registry = bool(expected_fingerprint) and expected_fingerprint == current_fingerprint
        registry_conflicts = _legacy_registry_conflicts(current_registry_path, legacy_path)
        report_passed = bool(report.get("overall_passed"))
        healthy = report_passed and audit_matches_registry and not registry_conflicts
        if healthy:
            state = "passed"
        elif registry_conflicts:
            state = "registry_split"
        elif report_passed:
            state = "stale"
        else:
            state = "failed"
        return {
            "available": True,
            "healthy": healthy,
            "state": state,
            "report_path": str(report_path),
            "registry_path": str(current_registry_path),
            "audit_matches_registry": audit_matches_registry,
            "registry_sha256": current_fingerprint,
            "audited_registry_sha256": expected_fingerprint,
            "legacy_registry_path": str(legacy_path),
            "legacy_registry_conflicts": registry_conflicts,
            "generated_at": report.get("generated_at", ""),
            "registered_models": int(report.get("registered_models", 0)),
            "validated_models": int(report.get("validated_models", 0)),
            "superseded_models": int(report.get("superseded_models", 0)),
            "active_unvalidated_models": int(report.get("active_unvalidated_models", 0)),
            "passed": int(report.get("passed", 0)),
            "failed": int(report.get("failed", 0)),
            "missing_artifacts": int(report.get("missing_artifacts", 0)),
            "feature_name_warning_count": int(report.get("feature_name_warning_count", 0)),
            "dependency_warning_count": int(report.get("warning_count", 0)),
            "compatibility_notices": report.get("compatibility_notices", []),
            "relocation_tested": bool(report.get("relocation_tested")),
            "relocation_failures": int(report.get("relocation_failures", 0)),
        }
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {
            "available": False,
            "healthy": False,
            "report_path": str(report_path),
            "state": "unreadable",
        }


def _legacy_registry_conflicts(canonical_path: Path, legacy_path: Path) -> list[str]:
    if not legacy_path.is_file():
        return []
    try:
        canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["__unreadable_registry__"]
    canonical_by_id = {
        str(item.get("id", "")): item
        for item in canonical.get("models", [])
        if isinstance(item, dict)
    }
    conflicts = []
    for item in legacy.get("models", []):
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", ""))
        canonical_item = canonical_by_id.get(model_id)
        if canonical_item is None or canonical_item != item:
            conflicts.append(model_id or "__missing_model_id__")
    return sorted(set(conflicts))


def _worker_status() -> dict[str, object]:
    queue = _execution_queue_counts()
    if not WORKER_STATUS_PATH.is_file():
        return {"online": False, "state": "not_started", "queue": queue}
    try:
        data = json.loads(WORKER_STATUS_PATH.read_text(encoding="utf-8"))
        updated_at = datetime.fromisoformat(str(data.get("updated_at", "")).replace("Z", "+00:00"))
        age_seconds = max(0.0, (datetime.now(timezone.utc) - updated_at).total_seconds())
        return {
            "online": data.get("state") == "running" and age_seconds <= 15.0,
            "state": data.get("state", "unknown"),
            "pid": data.get("pid"),
            "age_seconds": round(age_seconds, 1),
            "last_job_id": data.get("last_job_id", ""),
            "last_job_status": data.get("last_job_status", ""),
            "queue": queue,
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"online": False, "state": "unreadable", "queue": queue}


def _execution_queue_counts() -> dict[str, object]:
    try:
        jobs = JobStore(JOBS_DIR).list(200)
        awaiting = [job for job in jobs if job.get("status") == "awaiting_model_review"]
        return {
            "queued": sum(1 for job in jobs if job.get("status") == "queued"),
            "running": sum(1 for job in jobs if job.get("status") in {"preparing", "running"}),
            "awaiting_review": len(awaiting),
            "awaiting_review_jobs": [
                {"id": str(job.get("id", "")), "requirement": str(job.get("payload", {}).get("requirement", ""))[:160]}
                for job in awaiting[:3]
            ],
        }
    except (OSError, ValueError):
        return {"queued": 0, "running": 0, "awaiting_review": 0, "awaiting_review_jobs": []}


def _server_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _resolve_user_path(value: str) -> Path:
    return resolve_case_source_path(value, project_root=ROOT)


def _optional_user_path(value: object) -> Path | None:
    text = str(value or "").strip()
    return _resolve_user_path(text) if text else None


def _load_busbar_benchmark_capabilities() -> dict[str, object]:
    path = BUSBAR_BENCHMARK_DIR / "benchmark_capabilities.json"
    if not path.is_file():
        raise FileNotFoundError(f"焦耳热标杆能力清单不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_file_name(value: str) -> str:
    keep = []
    for char in value.strip():
        if char.isalnum() or char in "._-":
            keep.append(char)
    name = "".join(keep)
    return name or "generated.m"


def _split_columns(value: str) -> list[str]:
    return [part for part in value.replace(",", " ").split() if part]


def _split_lines(value: str) -> list[str]:
    return [part.strip() for part in value.replace(";", "\n").splitlines() if part.strip()]


def _attach_prediction_quality(
    response: dict[str, object],
    prediction: dict[str, object],
) -> dict[str, object]:
    """Expose runtime domain checks and uncertainty in every surrogate dialogue."""
    confidence = prediction.get("confidence", {})
    domain = prediction.get("input_domain", {})
    uncertainty = prediction.get("uncertainty", {})
    if not isinstance(confidence, dict) or not confidence:
        return response

    quality_items = [
        f"可信度：{confidence.get('label', '未知')}（{confidence.get('score', 0)}/100）",
        *[str(item) for item in confidence.get("reasons", []) if str(item).strip()],
    ]
    if isinstance(domain, dict):
        status = "训练范围内" if domain.get("status") == "inside" else "超出训练范围"
        quality_items.append(f"训练域检测：{status}")
        distance = domain.get("nearest_training_distance_normalized")
        if isinstance(distance, (int, float)):
            quality_items.append(f"距最近训练样本的归一化距离：{float(distance):.3f}")

    interval_items: list[str] = []
    intervals = uncertainty.get("intervals", {}) if isinstance(uncertainty, dict) else {}
    if isinstance(intervals, dict):
        for name, interval in intervals.items():
            if not isinstance(interval, dict):
                continue
            if interval.get("available"):
                level = float(interval.get("confidence_level", 0.95)) * 100.0
                interval_items.append(
                    f"{name}：{level:.0f}% 预测区间 "
                    f"[{float(interval['lower']):.6g}, {float(interval['upper']):.6g}]"
                )
            else:
                interval_items.append(f"{name}：预测区间暂不可用")

    updated = dict(response)
    sections = list(updated.get("explanation_sections", []))
    sections.append({"title": "预测可信度", "items": quality_items})
    if interval_items:
        sections.append({"title": "不确定性区间", "items": interval_items})
    updated["explanation_sections"] = sections
    updated["prediction_quality"] = {
        "confidence": confidence,
        "input_domain": domain,
        "uncertainty": uncertainty,
    }
    if confidence.get("requires_comsol"):
        intent = list(updated.get("intent", []))
        for item in ("low_confidence", "comsol_resolve_required"):
            if item not in intent:
                intent.append(item)
        updated["intent"] = intent
        reminder = str(confidence.get("reminder", ""))
        if reminder:
            updated["assistant_message"] = f"{updated.get('assistant_message', '')}\n\n可信度提醒：{reminder}"
    return updated


def _thermal_actuator_augmentation_dialogue(plan: dict[str, object]) -> dict[str, object]:
    samples = plan.get("recommended_comsol_samples", []) if isinstance(plan.get("recommended_comsol_samples"), list) else []
    return {
        "intent": ["surrogate_augmentation_plan", "comsol_resolve_required"],
        "assistant_message": (
            f"已为超出验证范围的微执行器工况生成 COMSOL 补样计划，共 {len(samples)} 个建议工况。\n\n"
            "判断依据：原代理模型不能对超范围输入外推；计划以目标工况为中心，在超出范围的参数附近增加真实 COMSOL 样本。\n\n"
            "下一步：使用同一几何、材料、电-热耦合和边界条件运行这些工况，合并 CSV 后必须使用新的独立留出集重新验证。"
        ),
        "explanation_sections": [
            {"title": "建议 COMSOL 补样", "items": [str(item) for item in samples]},
            {"title": "计划文件", "items": [str(plan.get("path", ""))]},
        ],
        "suggested_tool": "COMSOL 参数扫描补样",
        "response_policy": {"general_rule": "超范围时创建补样计划，不输出外推温度。", "theory_rule": "新数据必须来自同一物理模型的真实求解。", "physics_rule": "保持微执行器电-热耦合与对流边界不变，才能扩展原代理模型。"},
    }


def _is_power_inductor_frequency_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("功率电感器", "功率电感", "power inductor", "power_inductor"))


def _extract_power_inductor_frequency_inputs(instruction: str) -> dict[str, float]:
    match = re.search(
        r"(?:频率|frequency|freq|\bf\b)\s*(?:为|是|=|:|：)?\s*"
        r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*(kHz|MHz|Hz)?",
        str(instruction or ""),
        flags=re.IGNORECASE,
    )
    if not match:
        return {}
    value = float(match.group(1))
    unit = (match.group(2) or "Hz").lower()
    multiplier = {"hz": 1.0, "khz": 1e3, "mhz": 1e6}[unit]
    return {"frequency_Hz": value * multiplier}


def _power_inductor_frequency_missing_inputs_dialogue() -> dict[str, object]:
    return {
        "intent": ["validated_surrogate_prediction", "missing_prediction_inputs"],
        "assistant_message": "要预测功率电感器频率响应，请提供频率，例如 10 kHz。",
        "explanation_sections": [
            {"title": "已验证范围", "items": ["频率：500-20000 Hz", "输出：电感与等效电导"]}
        ],
    }


def _power_inductor_frequency_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {
            "intent": ["validated_surrogate_prediction", "comsol_resolve_required"],
            "assistant_message": (
                "该频率超出功率电感器代理模型的已验证范围 500-20000 Hz，不能外推；"
                "请使用相同 COMSOL 模型补充真实频率扫描后再训练。"
            ),
        }
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    candidates = validation.get("candidate_reports", {}) if isinstance(validation.get("candidate_reports"), dict) else {}
    selected_name = str(validation.get("selected_model", "log_frequency_log_output"))
    selected_metrics = candidates.get(selected_name, {}) if isinstance(candidates.get(selected_name), dict) else {}
    return {
        "intent": ["validated_surrogate_prediction", "power_inductor_frequency"],
        "assistant_message": (
            f"结论：在该频率下，预测电感为 {float(outputs.get('inductance_H', 0.0)):.9g} H，"
            f"等效电导为 {float(outputs.get('conductance_S', 0.0)):.9g} S。\n\n"
            "判断依据：固定功率电感器几何、材料、端口、网格和研究设置，"
            "使用真实 COMSOL 频率扫描训练的对数频率-对数输出代理。\n\n"
            "适用范围：500-20000 Hz；改变几何、材料、端口或研究设置，或超出频率范围时必须重新运行 COMSOL。"
        ),
        "explanation_sections": [
            {"title": "独立 COMSOL 验证", "items": [
                f"训练样本：{validation.get('training_rows', '未知')}，留出样本：{validation.get('holdout_rows', '未知')}",
                f"选定模型：{selected_name}",
                f"最大相对误差：{selected_metrics.get('max_relative_error_percent', '未知')}%",
                f"验证通过：{'是' if validation.get('passed') else '否'}",
            ]}
        ],
    }

def _is_validated_surrogate_catalog_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("已验证代理模型", "可用代理模型", "当前代理模型", "已训练模型"))


def _validated_surrogate_catalog_dialogue() -> dict[str, object]:
    registry_path = SURROGATE_REGISTRY_PATH
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        models = registry.get("models", []) if isinstance(registry, dict) else []
    except (OSError, json.JSONDecodeError):
        models = []
    validated = [item for item in models if isinstance(item, dict) and item.get("validation_passed")]
    items = []
    for item in validated:
        ranges = item.get("validated_input_ranges", {})
        items.append(f"{item.get('id', 'unknown')} / {item.get('name', '未命名模型')}：输入范围 {ranges}")
    return {
        "intent": ["validated_surrogate_catalog"],
        "assistant_message": f"当前共有 {len(validated)} 个已通过独立 COMSOL 验证的本地代理模型。它们只能在各自声明的输入范围内用于快速比较，超出范围、改变几何、材料或边界时必须回到 COMSOL。",
        "explanation_sections": [{"title": "可用模型与范围", "items": items or ["暂无已验证代理模型"]}],
    }

def _is_heat_convection_2d_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("稳态传导", "二维传导", "heat_convection_2d", "对流换热系数", "传导-对流"))


def _extract_heat_convection_2d_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:对流换热系数|换热系数|\bh\b)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"convection_coefficient_W_m2_K": float(match.group(1))} if match else {}


def _heat_convection_2d_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测二维稳态传导-对流温度，请提供对流换热系数 h，单位为 W/(m2*K)。", "explanation_sections": [{"title": "已验证范围", "items": ["h: 500-1000 W/(m2*K)"]}]}


def _heat_convection_2d_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "该对流换热系数超出 h=500-1000 W/(m2*K) 的已验证范围，不能外推；请补充真实 COMSOL 扫描。"}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    return {"intent": ["validated_surrogate_prediction", "heat_convection_2d"], "assistant_message": f"结论：测点 (0.6 m, 0.2 m) 温度为 {float(outputs.get('temperature_at_0p6_0p2_K', 0.0)):.3f} K；最高温度为 {float(outputs.get('maximum_temperature_K', 0.0)):.3f} K。\n\n判断依据：固定二维稳态传导、导热系数、定温边界和环境温度，只改变对流换热系数；h 增大时边界散热增强，测点温度降低。\n\n适用范围：h=500-1000 W/(m2*K)，改变几何、材料或边界时需重新运行 COMSOL。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}

def _is_electric_field_concentric_cylinders_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("同心圆柱", "圆柱电场", "concentric_cylinders", "静电场"))


def _extract_electric_field_concentric_cylinders_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:内圆柱电势|电压|电势|v0|\bv\b)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"voltage_V": float(match.group(1))} if match else {}


def _electric_field_concentric_cylinders_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测同心圆柱之间的静电场，请提供内圆柱电势 V0，单位为 V。", "explanation_sections": [{"title": "已验证范围", "items": ["V0: 50-150 V", "内半径 0.1 m、外半径 1 m，外圆柱接地，输出 r=0.5 m 处的电势和径向电场"]}]}


def _electric_field_concentric_cylinders_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "输入电势超出 V0=50-150 V 的已验证范围，不能外推。请运行真实 COMSOL 静电扫描补样。", "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    return {"intent": ["validated_surrogate_prediction", "electric_field_concentric_cylinders"], "assistant_message": f"结论：r=0.5 m 处电势为 {float(outputs.get('potential_mid_V', 0.0)):.3f} V；径向电场为 {float(outputs.get('electric_field_mid_V_m', 0.0)):.3f} V/m。\n\n判断依据：模型固定同心圆柱几何，外圆柱接地，只改变内圆柱电势；在该线性静电问题中，电势和电场随 V0 同比例变化。\n\n适用范围：V0=50-150 V。改变半径、介质、边界或加入电荷耦合后，必须重新用 COMSOL 求解。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}

def _is_capacitor_dc_permittivity_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("计算电容", "电容预测", "介电常数", "capacitor_dc", "电容器"))


def _extract_capacitor_dc_permittivity_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:相对介电常数|介电常数|epsilon_r|epsr|εr)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"relative_permittivity": float(match.group(1))} if match else {}


def _capacitor_dc_permittivity_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测该三维电容器的 Maxwell 电容，请提供石英域的相对介电常数 εr。", "explanation_sections": [{"title": "已验证范围", "items": ["εr: 2-8", "固定三维几何、端子、接地与网格"]}]}


def _capacitor_dc_permittivity_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "相对介电常数超出 εr=2-8 的已验证范围，不能外推。请运行真实 COMSOL 静电扫描补样。", "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    return {"intent": ["validated_surrogate_prediction", "capacitor_dc_permittivity"], "assistant_message": f"结论：预测 Maxwell 电容为 {float(outputs.get('capacitance_F', 0.0)):.6e} F。\n\n判断依据：保持电容器几何、端子和接地不变时，介质极化决定电位移通量；相对介电常数提高，电容随之增大。\n\n适用范围：εr=2-8。改变几何、介质分布、端子或边界后，必须重新运行 COMSOL。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}

def _is_simple_resistor_conductivity_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("计算导线电阻", "导线电阻", "导体电阻", "simple_resistor"))


def _extract_simple_resistor_conductivity_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:电导率|conductivity|sigma|σ)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"conductivity_S_m": float(match.group(1))} if match else {}


def _simple_resistor_conductivity_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测该三维导线的电阻，请提供材料电导率 sigma，单位为 S/m。", "explanation_sections": [{"title": "已验证范围", "items": ["sigma: 3e7-7e7 S/m", "固定几何、1 A 端子、接地和网格"]}]}


def _simple_resistor_conductivity_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "电导率超出 sigma=3e7-7e7 S/m 的已验证范围，不能外推。请运行真实 COMSOL 电流场扫描补样。", "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    return {"intent": ["validated_surrogate_prediction", "simple_resistor_conductivity"], "assistant_message": f"结论：预测导线电阻为 {float(outputs.get('resistance_ohm', 0.0)):.6e} ohm。\n\n判断依据：在固定几何、端子电流和边界下，欧姆定律给出电阻与电导率成反比；电导率提高会降低电阻。\n\n适用范围：sigma=3e7-7e7 S/m。改变几何、端子电流、温度或接触条件后，必须重新运行 COMSOL。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}

def _is_heat_radiation_1d_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("稳态辐射传热", "辐射传热", "发射率", "heat_radiation_1d"))


def _extract_heat_radiation_1d_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:发射率|emissivity|epsilon|ε)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"emissivity": float(match.group(1))} if match else {}


def _heat_radiation_1d_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测一维稳态辐射传热的辐射端温度，请提供表面发射率 ε。", "explanation_sections": [{"title": "已验证范围", "items": ["ε: 0.2-0.98", "左端 1000 K、环境 300 K、几何和网格固定"]}]}


def _heat_radiation_1d_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "发射率超出 ε=0.2-0.98 的已验证范围，不能外推。请运行真实 COMSOL 辐射传热扫描补样。", "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    return {"intent": ["validated_surrogate_prediction", "heat_radiation_1d"], "assistant_message": f"结论：预测辐射端温度为 {float(outputs.get('radiating_end_temperature_K', 0.0)):.3f} K。\n\n判断依据：表面对环境辐射热流与发射率及绝对温度四次方有关；在固定左端温度与环境温度下，发射率增大将增强散热并降低辐射端温度。\n\n适用范围：ε=0.2-0.98。改变几何、端温、环境温度或加入对流后，必须重新运行 COMSOL。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}

















def _is_pn_junction_current_density_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return bool(
        re.search(r"p\s*[-‐‑–—]?\s*n\s*结", text)
        and any(token in text for token in ("电流密度", "current density", "semi.jx", "i-v", "iv曲线"))
    )


def _extract_pn_junction_current_density_inputs(instruction: str) -> dict[str, float]:
    return _extract_pn_junction_carrier_inputs(instruction)


def _pn_junction_current_density_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent":["validated_surrogate_prediction","missing_prediction_inputs"],"assistant_message":"要预测一维 P-N 结的截面电流密度，请提供正向偏压，单位为 V。\n\n示例：P-N 结电流密度，偏压=0.3 V。","explanation_sections":[{"title":"已验证范围","items":["偏压：0.05-0.5 V","输出为 x=2.5 um 的 x 向总电流密度 semi.JX，单位 A/m^2","固定 Tl=300 K、Na=Nd=1e15 1/cm^3、几何、接触与网格"]}]}


def _pn_junction_current_density_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent":["validated_surrogate_prediction","comsol_resolve_required"],"assistant_message":"偏压超出 0.05-0.5 V 的独立 COMSOL 验证范围，不能外推。请运行真实半导体漂移-扩散求解补样。","explanation_sections":[{"title":"已验证范围","items":[str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    current_density = float(outputs.get("current_density_at_x_2_5um_A_m2", 0.0))
    return {"intent":["validated_surrogate_prediction","pn_junction_current_density"],"assistant_message":f"结论：预测 x=2.5 um 截面的 x 向总电流密度 semi.JX 为 {current_density:.6e} A/m^2。\n\n判断依据：正向偏压降低结区势垒，电子与空穴注入增强，电流密度随偏压跨数量级增长；模型对电流密度绝对值取 log10 拟合，并恢复 COMSOL 的负 x 方向符号。\n\n适用范围：正向偏压 0.05-0.5 V。该输出是单位截面积的截面电流密度，不是未定义截面积下的总端子电流；改变掺杂、温度、几何、接触或载流子模型时必须重新运行 COMSOL。"}

def _is_pn_junction_carrier_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return bool(
        re.search(r"p\s*[-‐‑–—]?\s*n\s*结", text)
        or any(token in text for token in ("pn_junction", "结区载流子"))
    )


def _extract_pn_junction_carrier_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:偏压|电压|bias|va)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"bias_V": float(match.group(1))} if match else {}


def _pn_junction_carrier_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent":["validated_surrogate_prediction","missing_prediction_inputs"],"assistant_message":"要预测一维 P-N 结结区的电子和空穴浓度，请提供正向偏压，单位为 V。\n\n示例：P-N 结，偏压=0.3 V。","explanation_sections":[{"title":"已验证范围","items":["偏压：0-0.5 V","Tl=300 K、Na=Nd=1e15 1/cm^3、几何、材料、网格和金属接触固定"]}]}


def _pn_junction_carrier_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent":["validated_surrogate_prediction","comsol_resolve_required"],"assistant_message":"偏压超出 0-0.5 V 的独立 COMSOL 验证范围，不能外推。请运行真实半导体漂移-扩散求解补样。","explanation_sections":[{"title":"已验证范围","items":[str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    n = float(outputs.get("electron_density_at_junction_cm3", 0.0)); p = float(outputs.get("hole_density_at_junction_cm3", 0.0))
    return {"intent":["validated_surrogate_prediction","pn_junction_carriers"],"assistant_message":f"结论：预测结区电子浓度为 {n:.6e} 1/cm^3，空穴浓度为 {p:.6e} 1/cm^3。\n\n判断依据：正向偏压降低 P-N 结势垒并增强少数载流子注入，因此结区载流子浓度随偏压呈近似指数增长；模型在 log10 浓度空间拟合，并以独立 COMSOL 偏压点验证。\n\n适用范围：正向偏压 0-0.5 V。当前模型只验证了结区载流子浓度，未验证端子 I-V 电流；改变掺杂、温度、材料寿命、几何或接触条件时必须重新运行 COMSOL。"}
def _is_thermoelectric_generator_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("热电发电机", "thermoelectric_generator", "热电开路电压"))


def _extract_thermoelectric_generator_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:热端温度|t0|hot\s*temperature)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"hot_temperature_degC": float(match.group(1))} if match else {}


def _thermoelectric_generator_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测热电发电机的开路电压，请提供热端温度，单位为 degC。\n\n示例：热电发电机，热端温度=150 degC。", "explanation_sections": [{"title": "已验证范围", "items": ["热端温度：100-200 degC", "冷端固定 0 degC，几何、端子、材料和温度相关物性固定"]}]}


def _thermoelectric_generator_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "热端温度超出 100-200 degC 的独立 COMSOL 验证范围，不能外推。请运行真实热-电耦合求解补样。", "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    voltage = float(outputs.get("open_circuit_voltage_V", 0.0))
    return {"intent": ["validated_surrogate_prediction", "thermoelectric_generator"], "assistant_message": f"结论：预测浮动端开路电压为 {voltage:.6e} V。\n\n判断依据：热端与固定冷端形成温差，温差通过 Seebeck 效应产生电势；本案例材料的 Seebeck 系数、电导率和导热率均随温度变化，因此采用 COMSOL 数据验证的二次代理模型。负号表示相对于当前接地端的电势方向。\n\n适用范围：热端 100-200 degC、冷端 0 degC，且几何、材料、端子和温度相关物性不变。改变冷端温度、负载、材料、几何或接触热阻时必须重新运行 COMSOL。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}
def _is_parallel_wires_force_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return ("平行载流导线" in text or "parallel_wires" in text) and any(token in text for token in ("电磁力", "受力", "force"))


def _extract_parallel_wires_force_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:电流|current|i0)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"current_A": float(match.group(1))} if match else {}


def _parallel_wires_force_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测平行载流导线的电磁力，请提供两根同向导线的共同电流，单位为 A。\n\n示例：平行载流导线电磁力，电流=1.5 A。", "explanation_sections": [{"title": "已验证范围", "items": ["共同电流：0.25-3 A", "导线半径、间距、方向、外域和力计算区域固定"]}]}


def _parallel_wires_force_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "电流超出 0.25-3 A 的独立 COMSOL 验证范围，不能外推。请运行真实静磁场力计算补样。", "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    force_x = float(outputs.get("force_x_wire2_N", 0.0))
    return {"intent": ["validated_surrogate_prediction", "parallel_wires_force"], "assistant_message": f"结论：预测第二根导线的 x 向电磁力为 {force_x:.6e} N。\n\n判断依据：每根导线产生的磁场与其电流成正比，另一根导线的洛伦兹力还与自身电流相乘；在两根导线均采用同一同向电流时，力随电流平方变化。正 x 号表示当前坐标定义下的受力方向。\n\n适用范围：共同电流 0.25-3 A，导线半径、间距、方向、材料和计算域固定。若两根电流不相等、方向相反，或改变间距、介质磁导率与几何，则必须重新运行 COMSOL。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}
def _is_helmholtz_coil_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("亥姆霍兹", "helmholtz", "双线圈中心磁场"))


def _extract_helmholtz_coil_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:线圈电流|电流|current|i0)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"coil_current_mA": float(match.group(1))} if match else {}


def _helmholtz_coil_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测亥姆霍兹线圈中心磁场，请提供两个同向等电流线圈的电流，单位为 mA。\n\n示例：亥姆霍兹线圈，电流=0.25 mA。", "explanation_sections": [{"title": "已验证范围", "items": ["线圈电流：0.05-0.6 mA", "双线圈几何、材料、中心测点、无限元域和边界固定"]}]}


def _helmholtz_coil_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "线圈电流超出 0.05-0.6 mA 的独立 COMSOL 验证范围，不能外推。请运行真实三维磁场求解补样。", "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    center_by = float(outputs.get("center_By_T", 0.0))
    return {"intent": ["validated_surrogate_prediction", "helmholtz_coil"], "assistant_message": f"结论：预测两线圈中心的 By 为 {center_by:.6e} T。\n\n判断依据：亥姆霍兹结构由两个同向等电流圆线圈叠加磁场，中心附近具有较高均匀性；在固定几何与线性材料下，中心 By 与线圈电流成正比。负号表示场沿当前坐标系的 -y 方向。\n\n适用范围：每个线圈电流 0.05-0.6 mA，两个线圈同向等电流。改变匝数、间距、线圈形状、材料、测点或电流方向时必须重新运行 COMSOL。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}
def _is_magnetic_field_infinite_conductor_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("无限导体", "长直导线磁场", "infinite_conductor", "导体磁场"))


def _extract_magnetic_field_infinite_conductor_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:电流|current|i0)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"current_A": float(match.group(1))} if match else {}


def _magnetic_field_infinite_conductor_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测无限导体的磁感应强度，请提供导体电流，单位为 A。\n\n示例：无限导体磁场，电流=2 A。", "explanation_sections": [{"title": "已验证范围", "items": ["电流：0.25-5 A", "导体半径 1 cm、外域半径 10 cm、测点距中心 5 cm，几何和边界固定"]}]}


def _magnetic_field_infinite_conductor_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "电流超出 0.25-5 A 的独立 COMSOL 验证范围，不能外推。请运行真实静磁场求解补样。", "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    magnetic_flux_density = float(outputs.get("magnetic_flux_density_at_5cm_T", 0.0))
    return {"intent": ["validated_surrogate_prediction", "magnetic_field_infinite_conductor"], "assistant_message": f"结论：预测距导体中心 5 cm 处磁感应强度为 {magnetic_flux_density:.6e} T。\n\n判断依据：固定圆导体半径和观察位置时，静磁场由电流密度激励；在线性磁性假设下，磁感应强度与电流成正比。结果来自真实 COMSOL 静态扫描的区间内预测。\n\n适用范围：电流 0.25-5 A，导体半径 1 cm、外域半径 10 cm、测点 5 cm 固定。改变几何、测点、材料磁导率或加入铁磁非线性时必须重新运行 COMSOL。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}
def _is_fresnel_equations_rf_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("菲涅尔", "fresnel", "te反射", "tm反射", "s偏振", "p偏振"))


def _extract_fresnel_equations_rf_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:入射角|incident\s*angle|alpha|α)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"incident_angle_deg": float(match.group(1))} if match else {}


def _fresnel_equations_rf_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测菲涅尔方程模型的 TE/TM 功率反射率，请提供入射角，单位为 deg。\n\n示例：菲涅尔反射，入射角=45 deg。", "explanation_sections": [{"title": "已验证范围", "items": ["入射角：0-75 deg", "空气 n=1、无损介质 n=1.5、频率 f0 与平面界面固定"]}]}


def _fresnel_equations_rf_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "入射角超出 0-75 deg 的独立 COMSOL 验证范围，不能外推。请运行真实电磁波频域求解补样。", "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_absolute_validation", {}) if isinstance(validation.get("per_output_absolute_validation"), dict) else {}
    quality = [f"{name} 最大绝对误差：{item.get('max_absolute_error', '未知')}" for name, item in metrics.items() if isinstance(item, dict)]
    te = float(outputs.get("TE_reflectance", 0.0))
    tm = float(outputs.get("TM_reflectance", 0.0))
    return {"intent": ["validated_surrogate_prediction", "fresnel_equations_rf"], "assistant_message": f"结论：预测 TE 功率反射率为 {te:.6f}，TM 功率反射率为 {tm:.6f}。\n\n判断依据：在空气 n=1 到无损介质 n=1.5 的固定平面界面上，TE 与 TM 的边界连续条件不同；TM 在约 56 度的布儒斯特角附近反射接近零。该结果来自真实 COMSOL 频域扫描的区间内插值。\n\n适用范围：入射角 0-75 deg，频率、折射率、界面和偏振定义固定。改变折射率、材料损耗、频率、几何或边界条件时必须重新运行 COMSOL。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}
def _is_effective_diffusivity_1d_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("有效扩散系数", "多孔扩散", "effective_diffusivity", "等效扩散"))


def _extract_effective_diffusivity_1d_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:d1|有效扩散系数|扩散系数)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"D1_m2_s": float(match.group(1))} if match else {}


def _effective_diffusivity_1d_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent":["validated_surrogate_prediction","missing_prediction_inputs"],"assistant_message":"要预测一维等效多孔扩散模型的内部浓度，请提供有效扩散系数 D1，单位 m^2/s。\n\n示例：多孔扩散，D1=2.15e-6 m^2/s。","explanation_sections":[{"title":"已验证范围","items":["D1：1e-6-4e-6 m^2/s","固定孔隙率 epsilon=0.383、传质系数、几何、网格和 100 ms 观测时刻"]}]}


def _effective_diffusivity_1d_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent":["validated_surrogate_prediction","comsol_resolve_required"],"assistant_message":"D1 超出 1e-6-4e-6 m^2/s 的独立 COMSOL 验证范围，不能外推。请运行真实瞬态传质求解补样。","explanation_sections":[{"title":"已验证范围","items":[str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    concentration = float(outputs.get("concentration_x0p2mm_t100ms_mol_m3", 0.0))
    return {"intent":["validated_surrogate_prediction","effective_diffusivity_1d"],"assistant_message":f"结论：预测 x=0.2 mm、t=100 ms 处浓度为 {concentration:.6e} mol/m^3。\n\n判断依据：在固定孔隙率和边界传质条件下，D1 增大意味着更快的等效扩散，固定位置在该时刻的浓度随之提高；该结果来自真实 COMSOL 瞬态扫描的区间内插值。\n\n适用范围：D1=1e-6-4e-6 m^2/s。改变孔隙率、传质系数、初始浓度、几何或观测时刻时必须重新运行 COMSOL。","explanation_sections":[{"title":"独立 COMSOL 验证","items":quality or ["验证通过"]}]}
def _is_room_acoustic_target_mode_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("房间特征模态", "房间声学模态", "eigenmodes_of_room", "目标模态频率"))


def _extract_room_acoustic_target_mode_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:声速|sound\s*speed|c)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"sound_speed_m_s": float(match.group(1))} if match else {}


def _room_acoustic_target_mode_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测房间声学的目标模态频率，请提供空气声速，单位 m/s。\n\n示例：房间特征模态，声速=343 m/s。", "explanation_sections": [{"title": "已验证范围", "items": ["声速：300-380 m/s", "固定房间几何、空气密度、网格和压力声学特征频率研究", "输出为基准声速 343 m/s 时靠近 90 Hz 的同一目标模态，不是首阶模态"]}]}


def _room_acoustic_target_mode_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "声速超出 300-380 m/s 的独立 COMSOL 验证范围，不能外推。请运行真实压力声学特征频率求解。", "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    frequency = float(outputs.get("tracked_eigenfrequency_Hz", 0.0))
    return {"intent": ["validated_surrogate_prediction", "room_acoustic_target_mode"], "assistant_message": f"结论：预测房间声学目标模态频率为 {frequency:.6f} Hz。\n\n判断依据：在固定几何、边界、网格和空气密度下，压力声学特征频率与声速成正比；模型通过靠近缩放目标频率的规则追踪同一模态。\n\n适用范围：声速 300-380 m/s。该结果不是首阶模态；改变房间几何、壁面条件、空气密度或追踪的模态时必须重新运行 COMSOL。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}
def _is_lid_driven_cavity_reynolds_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("顶盖驱动方腔流", "lid_driven_cavity", "方腔流"))


def _extract_lid_driven_cavity_reynolds_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:reynolds(?:\s*number)?|雷诺数|\bre\b)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"Re": float(match.group(1))} if match else {}


def _lid_driven_cavity_reynolds_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测顶盖驱动方腔流的采样点速度，请提供 Reynolds 数 Re。\n\n示例：顶盖驱动方腔流，Re=500。", "explanation_sections": [{"title": "已验证范围", "items": ["Re：50-800", "二维单位方腔、单位顶盖速度、密度 1、黏度 1/Re、固定网格和压力点约束"]}]}


def _lid_driven_cavity_reynolds_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "Re 超出 50-800 的独立 COMSOL 验证范围，不能外推。请执行真实 COMSOL 方腔流扫描补样。", "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    speed = float(outputs.get("speed_mid_upper_m_s", 0.0))
    return {"intent": ["validated_surrogate_prediction", "lid_driven_cavity_reynolds"], "assistant_message": f"结论：预测方腔内采样点 (x=0.5, y=0.75) 的速度模为 {speed:.6f} m/s。\n\n判断依据：顶盖滑移驱动形成腔内回流，Re 增大等效于黏度降低，速度场会改变；该模型使用真实 COMSOL 扫描数据进行区间内局部插值。\n\n适用范围：Re=50-800。改变顶盖速度、方腔尺寸、网格、流体密度、边界或研究类型时，必须重新进行 COMSOL 求解。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}
def _is_tapered_cantilever_force_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("锥形悬臂梁", "tapered_cantilever", "悬臂梁位移"))


def _extract_tapered_cantilever_force_inputs(instruction: str) -> dict[str, float]:
    match = re.search(r"(?:边界力|线载荷|force|载荷)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", str(instruction or ""), flags=re.IGNORECASE)
    return {"boundary_force_N_m": float(match.group(1))} if match else {}


def _tapered_cantilever_force_missing_inputs_dialogue() -> dict[str, object]:
    return {"intent": ["validated_surrogate_prediction", "missing_prediction_inputs"], "assistant_message": "要预测锥形悬臂梁的受力工况端部位移，请提供边界线载荷，单位 N/m。\n\n示例：锥形悬臂梁，边界力=10000000 N/m。", "explanation_sections": [{"title": "已验证范围", "items": ["边界力：5e6-1.5e7 N/m", "固定二维锥形几何、钢材 E=210 GPa、nu=0.3、约束、重力和网格"]}]}


def _tapered_cantilever_force_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        return {"intent": ["validated_surrogate_prediction", "comsol_resolve_required"], "assistant_message": "边界力超出 5e6-1.5e7 N/m 的独立 COMSOL 验证范围，不能外推。请在真实 COMSOL 中完成载荷扫描后补充 CSV 训练数据。", "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}]}
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{item.get('max_relative_error_percent', '未知')}%" for name, item in metrics.items() if isinstance(item, dict)]
    displacement = float(outputs.get("force_case_tip_displacement_m", 0.0))
    return {"intent": ["validated_surrogate_prediction", "tapered_cantilever_force"], "assistant_message": f"结论：预测受力工况下悬臂梁端部位移为 {displacement:.6e} m。\n\n判断依据：该二维锥形梁采用小变形线弹性固体力学，固定材料、几何、约束和重力后，端部位移与边界线载荷成正比。\n\n适用范围：边界力 5e6-1.5e7 N/m。改变材料、厚度、几何、支撑条件或进入大变形后，必须重新进行 COMSOL 求解。", "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}]}
def _is_gecko_foot_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    has_case = any(token in text for token in ("壁虎足", "gecko foot", "gecko_foot"))
    asks_for_response = any(token in text for token in ("预测", "响应", "应力", "位移", "应变", "surrogate", "predict"))
    return has_case and asks_for_response


def _extract_gecko_foot_inputs(instruction: str) -> dict[str, float]:
    text = str(instruction or "")

    def find(patterns: tuple[str, ...], unit_pattern: str, scale: float = 1.0) -> float | None:
        for pattern in patterns:
            match = re.search(
                rf"(?:{pattern})\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)\s*(?:{unit_pattern})?",
                text,
                flags=re.IGNORECASE,
            )
            if match:
                return float(match.group(1)) * scale
        return None

    values = {
        "Fc_uN": find((r"Fc(?:_uN)?", r"法向力", r"接触力"), r"uN|μN|微牛(?:顿)?", 1.0),
        "Ff_uN": find((r"Ff(?:_uN)?", r"切向力", r"摩擦力"), r"uN|μN|微牛(?:顿)?", 1.0),
        "theta_deg": find((r"theta(?:_deg)?", r"接触角", r"角度"), r"deg|°|度", 1.0),
    }
    return {name: value for name, value in values.items() if value is not None}


def _gecko_foot_missing_inputs_dialogue() -> dict[str, object]:
    return {
        "intent": ["validated_surrogate_prediction", "missing_prediction_inputs"],
        "assistant_message": (
            "要预测壁虎足结构响应，请同时提供 Fc、Ff 和 theta。"
            "Fc、Ff 单位为 uN，theta 单位为度。"
            "例如：壁虎足预测，Fc=0.3 uN，Ff=0.25 uN，theta=60 度。"
        ),
        "explanation_sections": [
            {
                "title": "已验证范围",
                "items": [
                    "Fc：0.2-0.6 uN",
                    "Ff：0.1-0.3 uN",
                    "theta：30-90 度",
                    "输出：最大 von Mises 应力、最大位移、最大主应变",
                ],
            }
        ],
        "suggested_tool": "壁虎足代理模型快速预测",
        "response_policy": {"general_rule": "输入不完整时不输出数值。"},
    }


def _gecko_foot_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        rejected = prediction.get("out_of_range", {})
        return {
            "intent": ["validated_surrogate_prediction", "comsol_resolve_required"],
            "assistant_message": (
                "结论：请求工况超出壁虎足代理模型的已验证范围，不能进行外推预测。"
                "请使用相同几何、材料、边界条件和研究设置的 COMSOL 模型补充真实样本。"
            ),
            "explanation_sections": [
                {"title": "超范围参数", "items": [str(rejected)]},
                {"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]},
            ],
            "suggested_tool": "COMSOL 参数扫描与补充验证",
            "response_policy": {"general_rule": "超出范围时不输出代理数值。"},
        }
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [
        f"{name} 最大相对误差：{float(item.get('max_relative_error_percent')):.3f}%"
        for name, item in metrics.items()
        if isinstance(item, dict) and item.get("max_relative_error_percent") is not None
    ]
    return {
        "intent": ["validated_surrogate_prediction", "gecko_foot_response"],
        "assistant_message": (
            "结论：壁虎足已验证范围内的代理预测为："
            f"最大 von Mises 应力 {float(outputs.get('max_v_Mises_Pa', 0.0)):.6e} Pa，"
            f"最大位移 {float(outputs.get('max_disp_m', 0.0)):.6e} m，"
            f"最大主应变 {float(outputs.get('max_ep1', 0.0)):.6e}。"
            "这些结果适合当前固定模型内的快速比较；改变几何、材料、边界条件或超出范围时必须回到 COMSOL。"
        ),
        "explanation_sections": [
            {"title": "独立 COMSOL 验证", "items": [f"通过：{validation.get('passed', False)}", f"训练样本：{validation.get('training_rows', 0)}，留出样本：{validation.get('holdout_rows', 0)}", *quality]},
            {"title": "适用范围", "items": [str(prediction.get("validated_ranges", {}))]},
        ],
        "suggested_tool": "壁虎足代理模型快速预测",
        "response_policy": {"general_rule": "仅在模型卡声明范围内插值预测。"},
    }


def _is_mast_diagonal_mounting_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("通信塔桅", "塔桅刚度", "刚度比", "mast_diagonal_mounting"))


def _extract_mast_diagonal_mounting_inputs(instruction: str) -> dict[str, float]:
    text = str(instruction or "")
    plate = re.search(r"(?:t_p|板厚)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    mount = re.search(r"(?:t_m|安装厚度|安装件厚度)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if not plate or not mount:
        return {}
    return {"t_p_mm": float(plate.group(1)), "t_m_mm": float(mount.group(1))}


def _mast_diagonal_mounting_missing_inputs_dialogue() -> dict[str, object]:
    return {
        "intent": ["validated_surrogate_prediction", "missing_prediction_inputs"],
        "assistant_message": "要预测通信塔桅安装结构的刚度比，请同时提供板厚 t_p 与安装厚度 t_m，单位为 mm。",
        "explanation_sections": [{"title": "已验证范围", "items": ["t_p: 10-12 mm", "t_m: 10-15 mm", "固定结构钢、安装拓扑、约束和载荷定义"]}],
        "suggested_tool": "结构刚度比代理模型快速预测",
        "response_policy": {"general_rule": "输入不完整时不输出数值。", "theory_rule": "刚度比由几何刚度和固定材料参数共同决定。", "physics_rule": "保持稳态固体力学模型、约束和载荷定义不变。"},
    }


def _mast_diagonal_mounting_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        rejected = prediction.get("out_of_range", {})
        return {
            "intent": ["validated_surrogate_prediction", "comsol_resolve_required"],
            "assistant_message": f"结论：{', '.join(rejected) if isinstance(rejected, dict) else '几何参数'} 超出通信塔桅刚度比模型的已验证范围，不能进行外推预测。请执行真实 COMSOL 几何扫描补样。",
            "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}],
            "suggested_tool": "COMSOL 几何参数扫描",
            "response_policy": {"general_rule": "超范围时不输出数值。", "theory_rule": "代理模型只能在独立验证的几何范围内插值。", "physics_rule": "几何变化需重建网格并重新求解结构响应。"},
        }
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{values.get('max_relative_error_percent', '未知')}%" for name, values in metrics.items() if isinstance(values, dict)]
    return {
        "intent": ["validated_surrogate_prediction", "mast_diagonal_mounting_stiffness"],
        "assistant_message": (
            f"结论：在通信塔桅安装结构的已验证范围内，预测无量纲刚度比 S_R 为 {float(outputs.get('stiffness_ratio_1', 0.0)):.6f}。\n\n"
            "判断依据：输入几何位于真实 COMSOL 几何扫描范围内；每个样本均重建几何和网格后进行稳态固体力学求解。\n\n"
            "使用建议：适合比较 t_p=10-12 mm、t_m=10-15 mm 内的相对刚度；改变材料、载荷定义、约束或安装拓扑时必须回到 COMSOL。"
        ),
        "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}],
        "suggested_tool": "结构刚度比代理模型快速预测",
        "response_policy": {"general_rule": "仅回答当前固定塔桅结构的刚度比预测。", "theory_rule": "输出为刚度与理想刚度之比。", "physics_rule": "板厚和安装厚度改变结构变形能力，进而改变刚度比。"},
    }

def _is_circuit_fem_resistor_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(token in text for token in ("电阻 fem", "场路耦合", "circuit_fem_resistor", "电阻器代理"))


def _extract_circuit_fem_resistor_inputs(instruction: str) -> dict[str, float]:
    text = str(instruction or "")
    match = re.search(r"(?:sigma|电导率)\s*(?:为|是|=|:|：)?\s*([-+]?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    return {"sigma_S_m": float(match.group(1))} if match else {}


def _circuit_fem_resistor_missing_inputs_dialogue() -> dict[str, object]:
    return {
        "intent": ["validated_surrogate_prediction", "missing_prediction_inputs"],
        "assistant_message": "要预测电阻 FEM 场路耦合模型，请提供电导率 sigma，单位为 S/m。",
        "explanation_sections": [{"title": "已验证范围", "items": ["sigma: 800-1200 S/m", "固定圆柱几何、端子和电路拓扑"]}],
        "suggested_tool": "场路耦合代理模型快速预测",
        "response_policy": {"general_rule": "输入不完整时不输出数值。", "theory_rule": "电阻由材料电导率和固定几何共同确定。", "physics_rule": "保持 Electric Currents 与 Electrical Circuit 耦合不变。"},
    }


def _circuit_fem_resistor_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        rejected = prediction.get("out_of_range", {})
        return {
            "intent": ["validated_surrogate_prediction", "comsol_resolve_required"],
            "assistant_message": f"结论：{', '.join(rejected) if isinstance(rejected, dict) else '电导率'} 超出电阻 FEM 场路耦合模型的已验证范围，不能进行外推预测。请执行真实 COMSOL 扫描补样。",
            "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}],
            "suggested_tool": "COMSOL 参数扫描补样",
            "response_policy": {"general_rule": "超范围时不输出数值。", "theory_rule": "代理模型只能在独立验证的范围内插值。", "physics_rule": "改变电导率范围需重新确认场路耦合关系。"},
        }
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    quality = [f"{name} 最大相对误差：{values.get('max_relative_error_percent', '未知')}%" for name, values in metrics.items() if isinstance(values, dict)]
    return {
        "intent": ["validated_surrogate_prediction", "circuit_fem_resistor_multioutput"],
        "assistant_message": (
            f"结论：在电阻 FEM 场路耦合模型的已验证范围内，场路耦合电阻为 {float(outputs.get('resistance_circuit_ohm', 0.0)):.6f} ohm；"
            f"解析电阻为 {float(outputs.get('resistance_analytic_ohm', 0.0)):.6f} ohm。\n\n"
            "判断依据：仅改变电导率，圆柱几何、端子、电路拓扑和稳态研究保持不变；代理模型由真实 COMSOL 扫描和独立留出点验证。\n\n"
            "使用建议：适合在 800-1200 S/m 内快速比较；改变几何、R1/R2、端子或电路连接时必须重新运行 COMSOL。"
        ),
        "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}],
        "suggested_tool": "场路耦合代理模型快速预测",
        "response_policy": {"general_rule": "仅回答固定场路耦合模型的电阻预测。", "theory_rule": "比较有限元场路耦合电阻与解析电阻。", "physics_rule": "导电率增大时固定几何下的等效电阻下降。"},
    }

def _is_simplified_thermal_actuator_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return "热微执行器的简化模型" in text or "热微执行器简化模型" in text or "thermal_actuator_simplified" in text


def _thermal_actuator_simplified_missing_inputs_dialogue() -> dict[str, object]:
    return {
        "intent": ["validated_surrogate_prediction", "missing_prediction_inputs"],
        "assistant_message": "要预测热微执行器简化模型，请同时提供 DV、htc_s 和 htc_us。该模型固定为电-热-结构稳态耦合，输出最高温度、最大位移和焦耳热功率。",
        "explanation_sections": [{"title": "已验证范围", "items": ["DV: 4.5-5.5 V", "htc_s: 15000-25000 W/(m2*K)", "htc_us: 400 W/(m2*K)"]}],
        "suggested_tool": "多输出代理模型快速预测",
        "response_policy": {"general_rule": "输入不完整时不输出数值。", "theory_rule": "三个输入共同决定电热源与对流散热。", "physics_rule": "该模型同时计算焦耳热、固体传热和热变形。"},
    }


def _thermal_actuator_simplified_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    if not prediction.get("ok"):
        rejected = prediction.get("out_of_range", {})
        return {
            "intent": ["validated_surrogate_prediction", "comsol_resolve_required"],
            "assistant_message": f"结论：{', '.join(rejected) if isinstance(rejected, dict) else '输入参数'} 超出热微执行器简化模型的已验证范围，不能进行外推预测。请执行真实 COMSOL 扫描补样。",
            "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}],
            "suggested_tool": "COMSOL 真实求解",
            "response_policy": {"general_rule": "超范围时不输出数值。", "theory_rule": "代理模型只能插值。", "physics_rule": "电热与热变形耦合在范围外需重新求解。"},
        }
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    metrics = validation.get("per_output_relative_validation", {}) if isinstance(validation.get("per_output_relative_validation"), dict) else {}
    items = [
        f"最高温度：{float(outputs.get('Tmax_K', 0.0)):.2f} K",
        f"最大位移：{float(outputs.get('umax_m', 0.0)):.3e} m",
        f"焦耳热功率：{float(outputs.get('joule_power_W', 0.0)):.5f} W",
    ]
    quality = [f"{name} 最大相对误差：{values.get('max_relative_error_percent', '未知')}%" for name, values in metrics.items() if isinstance(values, dict)]
    return {
        "intent": ["validated_surrogate_prediction", "thermal_actuator_simplified_multioutput"],
        "assistant_message": "结论：在热微执行器简化模型的已验证范围内，" + "；".join(items) + "。\n\n判断依据：输入处于独立 COMSOL 留出集验证过的参数范围，模型保持电流-传热-结构耦合、几何、材料和边界不变。\n\n使用建议：可用于该固定模型的快速比较；改变几何、材料、边界或 htc_us 时必须回到 COMSOL。",
        "explanation_sections": [{"title": "独立 COMSOL 验证", "items": quality or ["验证通过"]}],
        "suggested_tool": "多输出代理模型快速预测",
        "response_policy": {"general_rule": "仅回答当前简化微执行器预测。", "theory_rule": "预测基于独立 COMSOL 工况验证后的插值。", "physics_rule": "焦耳热升温会引起热变形，因此同时返回温度、位移和功率。"},
    }

def _thermal_actuator_missing_inputs_dialogue() -> dict[str, object]:
    return {
        "intent": ["validated_surrogate_prediction", "missing_prediction_inputs"],
        "assistant_message": (
            "要预测微执行器焦耳热的最高温度，请同时提供驱动电压 DV、htc_s 和 htc_us。\n\n"
            "判断依据：该模型是三输入代理模型；缺少任一对流边界参数就不能唯一确定稳态温度场。\n\n"
            "示例：微执行器焦耳热温度预测，DV=3 V，htc_s=20000，htc_us=400。"
        ),
        "explanation_sections": [{"title": "已验证输入范围", "items": ["DV: 2-5 V", "htc_s: 15000-25000 W/(m²·K)", "htc_us: 300-500 W/(m²·K)"]}],
        "suggested_tool": "代理模型快速预测",
        "response_policy": {"general_rule": "参数不完整时不输出数值预测。", "theory_rule": "温度场由电热源和两个对流边界共同决定。", "physics_rule": "该能力对应微执行器电-热耦合稳态模型。"},
    }


def _thermal_actuator_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    if not prediction.get("ok"):
        rejected = prediction.get("out_of_range", {})
        rejected_names = ", ".join(rejected) if isinstance(rejected, dict) else "输入参数"
        return {
            "intent": ["validated_surrogate_prediction", "comsol_resolve_required"],
            "assistant_message": (
                f"结论：{rejected_names} 超出微执行器案例的已验证范围，不能给出可靠的代理温度预测。\n\n"
                "判断依据：该代理模型只在既定几何、电-热耦合、材料和对流边界下完成过 COMSOL 扫描与独立验证；外推可能进入高温失控区。\n\n"
                "建议：保持同一案例模型执行真实 COMSOL 求解，并将新工况加入 CSV 后重新进行独立验证。"
            ),
            "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}],
            "suggested_tool": "COMSOL 真实求解",
            "response_policy": {"general_rule": "超范围时不输出数值预测。", "theory_rule": "代理模型只能在训练覆盖范围内插值。", "physics_rule": "高电压下焦耳热会导致明显非线性温升，应回到 COMSOL 电-热耦合求解。"},
        }
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    tmax = float(outputs.get("Tmax_K", 0.0))
    per_output = validation.get("per_output", {}) if isinstance(validation.get("per_output"), dict) else {}
    metrics = per_output.get("Tmax_K", {}) if isinstance(per_output.get("Tmax_K"), dict) else {}
    return {
        "intent": ["validated_surrogate_prediction"],
        "assistant_message": (
            f"结论：在该微执行器焦耳热案例的已验证范围内，预测最高温度为 {tmax:.2f} K。\n\n"
            "判断依据：DV、htc_s 和 htc_us 均位于真实 COMSOL 参数扫描范围内，且代理模型使用未参与训练的 COMSOL 点独立验证。\n\n"
            "使用建议：可用于当前结构与边界下的快速参数比较；更改几何、材料、物理场或超出范围时必须重新执行 COMSOL。"
        ),
        "explanation_sections": [{"title": "独立 COMSOL 验证", "items": [f"通过：{validation.get('passed', False)}", f"Tmax RMSE：{metrics.get('rmse', '未知')} K", f"Tmax MAE：{metrics.get('mae', '未知')} K"]}],
        "suggested_tool": "代理模型快速预测",
        "response_policy": {"general_rule": "仅回答当前微执行器温度预测。", "theory_rule": "预测基于已验证工作区内的数值插值。", "physics_rule": "电流产生焦耳热并与固体传热、对流边界共同决定稳态最高温度。"},
    }

def _thermal_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    if not prediction.get("ok"):
        rejected = prediction.get("out_of_range", {})
        rejected_names = ", ".join(rejected) if isinstance(rejected, dict) else "输入参数"
        return {
            "intent": ["validated_surrogate_prediction", "comsol_resolve_required"],
            "assistant_message": (
                f"结论：{rejected_names} 超出已验证代理模型的训练范围，不能用小模型给出可靠温度预测。\n\n"
                "判断依据：该代理模型只对已完成 COMSOL 扫描和独立验证的参数范围有效；外推会掩盖边界条件或几何变化带来的误差。\n\n"
                "建议：执行一次真实 COMSOL 求解，并将新工况结果加入参数扫描数据后重新训练。"
            ),
            "explanation_sections": [{"title": "已验证范围", "items": [str(prediction.get("validated_ranges", {}))]}],
            "suggested_tool": "COMSOL 真实求解",
            "response_policy": {"general_rule": "当前输入超出范围，因此不输出数值预测。", "theory_rule": "代理模型只能在训练覆盖范围内插值使用。", "physics_rule": "几何或边界变化需由 COMSOL 方程重新求解。"},
        }
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    tmax = float(outputs.get("Tmax_K", 0.0))
    tavg = float(outputs.get("Tavg_K", 0.0))
    max_error = validation.get("max_absolute_error", {}) if isinstance(validation.get("max_absolute_error"), dict) else {}
    return {
        "intent": ["validated_surrogate_prediction"],
        "assistant_message": (
            f"结论：在当前二维稳态传热模型的已验证范围内，预测最高温度为 {tmax:.3f} K，平均温度为 {tavg:.3f} K。\n\n"
            "判断依据：输入参数位于 COMSOL 参数扫描范围内，且该代理模型经过独立 COMSOL 工况验证。\n\n"
            "使用建议：可用于快速比较方案；最终定稿、几何改变或边界条件改变时，应执行 COMSOL 真实求解。"
        ),
        "explanation_sections": [{"title": "独立 COMSOL 验证", "items": [f"通过：{validation.get('passed', False)}", f"最大绝对误差：{max_error}"]}],
        "suggested_tool": "代理模型快速预测",
        "response_policy": {"general_rule": "仅回答当前传热预测任务。", "theory_rule": "预测基于已验证范围内的插值。", "physics_rule": "温度由固体传热控制方程的 COMSOL 扫描数据学习得到。"},
    }


def _is_execution_status_query(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(
        token in text
        for token in ("执行队列", "队列状态", "任务状态", "节点状态", "worker状态", "comsol连接", "执行状态", "运行状态")
    )


def _is_execution_review_approval_request(instruction: str) -> bool:
    text = str(instruction or "").lower()
    return any(
        token in text
        for token in ("批准执行复核", "批准当前待复核", "批准执行任务", "允许任务执行", "批准队列任务")
    )


def _is_chat_code_read_request(instruction: str) -> bool:
    text = str(instruction or "")
    wants_reading = any(
        token in text.lower()
        for token in ("读取代码", "读取matlab", "读取java", "分析代码", "检查代码", "read code", "analyze code")
    )
    has_supported_path = bool(
        re.search(r"[A-Za-z]:[\\/][^\r\n<>|?*\"']+?\.(?:m|java)\b", text, flags=re.IGNORECASE)
    )
    return wants_reading and has_supported_path


def _chat_code_read_result(instruction: str) -> dict[str, object]:
    match = re.search(
        r"[A-Za-z]:[\\/][^\r\n<>|?*\"']+?\.(?:m|java)\b",
        str(instruction or ""),
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError("未识别到 MATLAB 或 Java 代码路径")
    return read_code_file(_resolve_user_path(match.group(0))).as_dict()


def _code_read_dialogue(result: dict[str, object]) -> dict[str, object]:
    analysis = result.get("analysis", {}) if isinstance(result.get("analysis"), dict) else {}
    kind = "MATLAB" if result.get("kind") == "matlab" else "Java"
    capabilities = []
    labels = (
        ("has_parameters", "参数"),
        ("has_geometry", "几何"),
        ("has_physics", "物理场"),
        ("has_materials", "材料"),
        ("has_mesh", "网格"),
        ("has_study", "求解研究"),
        ("has_results", "结果后处理"),
    )
    for key, label in labels:
        if analysis.get(key):
            capabilities.append(label)
    functions = analysis.get("functions", []) if isinstance(analysis.get("functions"), list) else []
    classes = analysis.get("classes", []) if isinstance(analysis.get("classes"), list) else []
    features = analysis.get("comsol_features", {}) if isinstance(analysis.get("comsol_features"), dict) else {}
    physics = features.get("physics", []) if isinstance(features.get("physics"), list) else []
    suggestions = analysis.get("suggestions", []) if isinstance(analysis.get("suggestions"), list) else []
    structure = "、".join(capabilities) if capabilities else "未识别到完整的 COMSOL 建模结构"
    api_note = "已识别到 COMSOL API 调用。" if analysis.get("has_comsol_api") else "未识别到 COMSOL API 调用，可能是辅助脚本或需要结合其他文件判断。"
    detail_items = [
        f"文件：{result.get('path', '')}",
        f"类型：{kind}，共 {result.get('line_count', 0)} 行",
        f"COMSOL API：{'是' if analysis.get('has_comsol_api') else '否'}",
        f"识别模块：{structure}",
    ]
    if functions:
        detail_items.append("函数：" + "、".join(str(item) for item in functions[:6]))
    if classes:
        detail_items.append("类：" + "、".join(str(item) for item in classes[:4]))
    if physics:
        detail_items.append("物理场代码：" + "；".join(str(item) for item in physics[:3]))
    chinese_suggestions = [
        "建议补充模型保存或导出步骤。" if "model.save" in item else
        "建议核对边界实体编号，避免未经验证的选择。" if "boundary selections" in item else
        "建议补充结果或派生值导出，以便生成训练数据。" if "result or derived-value" in item else
        "建议增加 CSV 或表格导出，便于后续训练。"
        for item in suggestions[:3]
    ]
    return {
        "intent": ["code_reading", "comsol_code_analysis"],
        "assistant_message": (
            f"结论：已读取 {kind} 代码，{api_note}\n\n"
            f"代码建模逻辑：该文件包含 {structure}。"
            + (f"已识别物理场定义：{'; '.join(str(item) for item in physics[:2])}。" if physics else "")
            + "\n\n判断依据：根据代码中的 COMSOL 模型树调用、参数设置和求解/后处理节点进行识别。"
        ),
        "explanation_sections": [
            {"title": "代码识别结果", "items": detail_items},
            *([{"title": "建议", "items": chinese_suggestions}] if chinese_suggestions else []),
        ],
        "suggested_tool": "代码工作区",
        "response_policy": ANSWER_POLICY,
    }


def _approve_execution_review_from_chat(instruction: str) -> dict[str, object]:
    store = JobStore(JOBS_DIR)
    job_id_match = re.search(r"\bjob_[A-Za-z0-9_]+\b", instruction)
    awaiting = [job for job in store.list(200) if job.get("status") == "awaiting_model_review"]
    target_id = job_id_match.group(0) if job_id_match else ""
    if not target_id and len(awaiting) == 1:
        target_id = str(awaiting[0]["id"])
    if not target_id:
        choices = [str(job.get("id", "")) for job in awaiting[:5]]
        return {
            "intent": ["execution_review_approval", "approval_target_required"],
            "assistant_message": "结论：尚未执行批准操作。当前待复核任务不唯一或不存在，请明确提供任务 ID。\n\n"
            + ("可批准任务：" + "、".join(choices) if choices else "当前没有待复核任务。"),
            "explanation_sections": [],
            "suggested_tool": "任务中心",
            "response_policy": ANSWER_POLICY,
        }
    job = store.approve_execution_review(target_id)
    return {
        "intent": ["execution_review_approved"],
        "assistant_message": (
            f"结论：任务 {job['id']} 的模型复核已批准，已进入执行队列。\n\n"
            "判断依据：该操作已将任务状态从待复核变为 queued；在线 worker 会按队列顺序处理，并在实际执行阶段按配置启动 COMSOL mphserver。"
        ),
        "explanation_sections": [{"title": "任务状态", "items": [f"状态：{job['status']}", f"日志：{job['log_path']}"]}],
        "suggested_tool": "任务中心",
        "response_policy": ANSWER_POLICY,
    }


def _execution_status_dialogue(health: dict[str, object]) -> dict[str, object]:
    node = health.get("execution_node", {}) if isinstance(health.get("execution_node"), dict) else {}
    worker = health.get("execution_worker", {}) if isinstance(health.get("execution_worker"), dict) else {}
    queue = worker.get("queue", {}) if isinstance(worker.get("queue"), dict) else {}
    surrogate = health.get("surrogate_runtime", {}) if isinstance(health.get("surrogate_runtime"), dict) else {}
    worker_online = bool(worker.get("online"))
    server_online = bool(node.get("server_reachable"))
    queued = int(queue.get("queued", 0))
    running = int(queue.get("running", 0))
    awaiting_review = int(queue.get("awaiting_review", 0))
    awaiting_jobs = queue.get("awaiting_review_jobs", []) if isinstance(queue.get("awaiting_review_jobs"), list) else []
    next_step = "当前没有待执行任务。"
    if awaiting_review:
        next_step = f"有 {awaiting_review} 个任务等待模型复核；批准后才会进入执行队列。"
    elif queued and worker_online and server_online:
        next_step = f"有 {queued} 个已批准任务将由在线 worker 依次处理。"
    elif queued:
        next_step = "存在待执行任务，但执行节点或 COMSOL 连接未就绪。"
    elif not server_online:
        next_step = (
            "当前没有待执行任务；已批准任务进入执行阶段时会自动启动 mphserver。"
            if node.get("auto_start_server")
            else "当前没有待执行任务；执行前需要手动启动 mphserver 或开启自动启动配置。"
        )
    server_note = ""
    if not server_online and node.get("auto_start_server"):
        server_note = "\n\n执行配置：mphserver 会在已批准任务进入实际执行阶段时按需自动启动。"
    review_items = [
        f"{item.get('id', '')}：{item.get('requirement', '')}"
        for item in awaiting_jobs
        if isinstance(item, dict)
    ]
    return {
        "intent": ["execution_status"],
        "assistant_message": (
            f"结论：执行 worker {'在线' if worker_online else '未运行'}，COMSOL mphserver {'已连接' if server_online else '未连接'}。"
            f"当前队列：待执行 {queued}，执行中 {running}，待复核 {awaiting_review}。\n\n"
            f"下一步：{next_step}{server_note}"
        ),
        "explanation_sections": [
            {
                "title": "判断依据",
                "items": [
                    f"worker 状态：{worker.get('state', 'unknown')}",
                    f"COMSOL 端口：{node.get('comsol_server_port', '')}",
                    (
                        f"已验证代理运行时：{surrogate.get('passed', 0)}/{surrogate.get('validated_models', 0)}"
                        if surrogate.get("available")
                        else "已验证代理运行时：尚无审计报告"
                    ),
                ],
            },
            *([{"title": "待复核任务", "items": review_items}] if review_items else []),
        ],
        "suggested_tool": "任务中心",
        "response_policy": ANSWER_POLICY,
    }


def _joule_rectangle_prediction_dialogue(prediction: dict[str, object]) -> dict[str, object]:
    validation = prediction.get("validation", {}) if isinstance(prediction.get("validation"), dict) else {}
    scope = str(prediction.get("declared_scope", "二维铜矩形焦耳热模型的已登记范围"))
    if not prediction.get("ok"):
        rejected = prediction.get("out_of_range", {})
        range_item = rejected.get("Vtot_V", {}) if isinstance(rejected, dict) else {}
        requested_mv = float(range_item.get("value", 0.0)) * 1000.0
        minimum_mv = float(range_item.get("min", 0.0)) * 1000.0
        maximum_mv = float(range_item.get("max", 0.0)) * 1000.0
        return {
            "intent": ["validated_joule_surrogate", "comsol_resolve_required"],
            "assistant_message": (
                f"结论：请求电压 {requested_mv:g} mV 超出已验证范围 {minimum_mv:g}–{maximum_mv:g} mV，不能直接给出焦耳热温度预测。\n\n"
                "判断依据：当前小模型只学习了固定二维铜矩形、固定材料与对流条件下的 COMSOL 数据；改变电压范围以外的工况属于外推。\n\n"
                "下一步：用相同 COMSOL 模型补充该电压附近的真实求解结果，完成独立验证后再扩展代理模型。"
            ),
            "explanation_sections": [{"title": "模型适用范围", "items": [scope]}],
            "suggested_tool": "COMSOL 补充求解",
            "response_policy": ANSWER_POLICY,
        }
    outputs = prediction.get("prediction", {}) if isinstance(prediction.get("prediction"), dict) else {}
    voltage_mv = float(prediction.get("inputs", {}).get("Vtot_V", 0.0)) * 1000.0
    per_output = validation.get("per_output", {}) if isinstance(validation.get("per_output"), dict) else {}
    tmax_rmse = per_output.get("Tmax_K", {}).get("rmse") if isinstance(per_output.get("Tmax_K"), dict) else None
    error_note = f"独立 COMSOL 留出集的 Tmax RMSE 为 {float(tmax_rmse):.3f} K。" if tmax_rmse is not None else "已通过独立 COMSOL 留出集验证。"
    return {
        "intent": ["validated_joule_surrogate"],
        "assistant_message": (
            f"结论：在 {voltage_mv:g} mV 下，预测最高温度为 {float(outputs.get('Tmax_K', 0.0)):.3f} K，"
            f"平均温度为 {float(outputs.get('Tavg_K', 0.0)):.3f} K。\n\n"
            f"判断依据：该电压位于已训练并用独立 COMSOL 留出工况验证的范围内，{error_note}因此可用于当前固定模型的快速比较。\n\n"
            "限制：几何、铜材料参数、对流边界或研究类型改变时，必须重新执行 COMSOL 求解。"
        ),
        "explanation_sections": [{"title": "独立 COMSOL 验证", "items": [f"通过：{validation.get('passed', False)}", f"留出样本：{validation.get('holdout_rows', 0)}", f"Tmax RMSE：{tmax_rmse if tmax_rmse is not None else '未记录'} K", f"RMSE 阈值：{validation.get('rmse_threshold_k', '')} K"]}, {"title": "模型适用范围", "items": [scope]}],
        "suggested_tool": "已验证代理模型快速预测",
        "response_policy": ANSWER_POLICY,
    }


def _joule_rectangle_missing_voltage_dialogue() -> dict[str, object]:
    return {
        "intent": ["validated_joule_surrogate", "missing_prediction_input"],
        "assistant_message": (
            "结论：可以使用已验证的焦耳热代理模型，但当前缺少端电压，不能计算温度。\n\n"
            "判断依据：这个代理模型的唯一输入是端电压 Vtot；温升由焦耳热功率决定，必须给出数值和单位。\n\n"
            "请补充：端电压，例如“在 0.5 mV 下预测焦耳热温度”。当前模型只适用于 100 mm × 50 mm 的二维铜矩形、固定对流条件，且电压范围为 0.1–1 mV。"
        ),
        "explanation_sections": [{"title": "缺少参数", "items": ["端电压 Vtot（单位：mV 或 V）"]}],
        "suggested_tool": "补充预测参数",
        "response_policy": ANSWER_POLICY,
    }


def _joule_rectangle_scope_change_dialogue(changes: list[str]) -> dict[str, object]:
    return {
        "intent": ["validated_joule_surrogate", "scope_change_requires_comsol"],
        "assistant_message": (
            "结论：当前请求改变了已验证焦耳热代理模型的物理范围，因此不输出温度预测。\n\n"
            f"判断依据：{'; '.join(changes)}。代理模型只可对相同几何、材料和边界条件进行范围内插值。\n\n"
            "下一步：请用对应的新条件完成 COMSOL 参数扫描，导出真实结果后再进行独立验证和代理模型扩展。"
        ),
        "explanation_sections": [{"title": "检测到的范围变化", "items": changes}],
        "suggested_tool": "COMSOL 新工况求解",
        "response_policy": ANSWER_POLICY,
    }


def _registered_surrogate_registry_path(model_id: str) -> Path:
    for path in _registered_surrogate_registry_paths():
        registry = json.loads(path.read_text(encoding="utf-8"))
        if any(item.get("id") == model_id for item in registry.get("models", [])):
            return path
    raise FileNotFoundError(f"未找到已登记代理模型 {model_id} 的注册表。")


def _registered_surrogate_registry_paths() -> list[Path]:
    candidates = [SURROGATE_REGISTRY_PATH, LEGACY_SURROGATE_REGISTRY_PATH]
    return [path for path in candidates if path.is_file()]


def run(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    server = None
    selected_port = port
    for candidate in range(port, port + 20):
        try:
            server = ThreadingHTTPServer((host, candidate), AppHandler)
            selected_port = candidate
            break
        except OSError:
            continue
    if server is None:
        raise OSError(f"No free port found from {port} to {port + 19}")

    display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{display_host}:{selected_port}"
    if open_browser:
        webbrowser.open(url)
    print(f"COMSOL small model web app: {url}")
    if host == "0.0.0.0":
        print("LAN access URLs:")
        for address in _local_ipv4_addresses():
            print(f"  http://{address}:{selected_port}")
        print("Warning: LAN mode exposes file-reading and model-generation APIs to your local network.")
    server.serve_forever()


def _local_ipv4_addresses() -> list[str]:
    addresses = {"127.0.0.1"}
    try:
        hostname = socket.gethostname()
        for item in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            addresses.add(item[4][0])
    except OSError:
        pass
    return sorted(addresses)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the COMSOL small model web app")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Use 0.0.0.0 for LAN access.")
    parser.add_argument("--port", type=int, default=8765, help="Starting port. The app tries the next 19 ports if busy.")
    parser.add_argument("--open", action="store_true", help="Open the local URL in the default browser.")
    return parser.parse_args(argv)


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>COMSOL 智能建模工作台</title>
  <style>
    :root {
      --ink: #182026;
      --muted: #5e6a70;
      --line: #ccd5d9;
      --panel: #f6f8f8;
      --accent: #0f766e;
      --accent-2: #9a3412;
      --ok: #166534;
      --bad: #991b1b;
      --white: #ffffff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: var(--white);
      font: 14px/1.5 "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
    }
    header {
      min-height: 112px;
      padding: 28px 32px 24px;
      color: white;
      background:
        linear-gradient(90deg, rgba(15, 118, 110, .95), rgba(154, 52, 18, .82)),
        repeating-linear-gradient(135deg, rgba(255,255,255,.15) 0 1px, transparent 1px 14px);
    }
    h1 { margin: 0; font-size: 28px; font-weight: 680; letter-spacing: 0; }
    .sub { margin-top: 6px; color: rgba(255,255,255,.86); }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 420px) minmax(420px, 1fr);
      gap: 0;
      min-height: calc(100vh - 112px);
    }
    nav {
      border-right: 1px solid var(--line);
      background: var(--panel);
      padding: 18px;
    }
    section {
      padding: 22px 26px;
      border-bottom: 1px solid var(--line);
    }
    h2 { margin: 0 0 14px; font-size: 17px; font-weight: 650; }
    label { display: block; margin: 10px 0 5px; color: var(--muted); font-size: 12px; }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      color: var(--ink);
      background: white;
      font: inherit;
    }
    textarea {
      min-height: 260px;
      resize: vertical;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
    }
    textarea.compact { min-height: 120px; }
    button {
      min-height: 36px;
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 7px 12px;
      color: white;
      background: var(--accent);
      font-weight: 620;
      cursor: pointer;
    }
    button.secondary { background: var(--accent-2); }
    button.ghost {
      color: var(--ink);
      background: white;
      border-color: var(--line);
    }
    .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 12px; }
    .workspace {
      display: grid;
      grid-template-rows: auto 1fr;
      min-width: 0;
    }
    .output {
      padding: 18px 26px 26px;
      min-width: 0;
    }
    pre {
      min-height: 420px;
      overflow: auto;
      margin: 0;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #101820;
      color: #d6f3e9;
      font: 12px/1.45 Consolas, "Courier New", monospace;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .status { margin-top: 10px; min-height: 20px; color: var(--muted); }
    .status.ok { color: var(--ok); }
    .status.bad { color: var(--bad); }
    @media (max-width: 860px) {
      main { grid-template-columns: 1fr; }
      nav { border-right: 0; border-bottom: 1px solid var(--line); }
      header { padding: 22px 20px; }
      section, .output { padding-left: 18px; padding-right: 18px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>COMSOL 智能建模工作台</h1>
    <div class="sub">MATLAB 读取 · 约束建模 · LiveLink 生成 · 代理模型训练</div>
  </header>
  <main>
    <nav>
      <section>
        <h2>语言指令</h2>
        <label for="instruction">输入你的需求</label>
        <textarea id="instruction" class="compact">请读取文件，并判断能否用于 COMSOL 自动建模和代理模型训练。</textarea>
        <div class="row">
          <button onclick="sendInstruction()">获取反馈</button>
        </div>
      </section>
      <section>
        <h2>文件输入</h2>
        <label for="filePath">文件路径</label>
        <input id="filePath" value="../acoustic_rectangular_cavity/build_acoustic_rectangular_cavity.m">
        <label for="uploadFile">选择文件</label>
        <input id="uploadFile" type="file">
        <div class="row">
          <button onclick="readFilePath()">读取路径</button>
          <button class="ghost" onclick="readUploadedFile()">读取选择文件</button>
        </div>
      </section>
      <section>
        <h2>MATLAB 文件</h2>
        <label for="matlabPath">.m 路径</label>
        <input id="matlabPath" value="../acoustic_rectangular_cavity/build_acoustic_rectangular_cavity.m">
        <div class="row">
          <button onclick="inspectMatlab()">读取</button>
        </div>
      </section>
      <section>
        <h2>约束配置</h2>
        <textarea id="constraints"></textarea>
        <div class="row">
          <button class="ghost" onclick="loadDefaults()">载入示例</button>
          <button onclick="validateConstraints()">校验</button>
          <button class="secondary" onclick="generateMatlab()">生成 MATLAB</button>
        </div>
      </section>
      <section>
        <h2>训练</h2>
        <label for="csvPath">CSV 路径</label>
        <input id="csvPath" value="examples/sample_comsol_data.csv">
        <label for="inputs">输入列</label>
        <input id="inputs" value="k Q h L">
        <label for="outputs">输出列</label>
        <input id="outputs" value="Tmax Tavg">
        <label for="modelName">模型文件名</label>
        <input id="modelName" value="thermal_surrogate.joblib">
        <div class="row">
          <button onclick="trainModel()">训练</button>
        </div>
      </section>
    </nav>
    <div class="workspace">
      <section>
        <h2>结果</h2>
        <div id="status" class="status">ready</div>
      </section>
      <div class="output">
        <pre id="output">{}</pre>
      </div>
    </div>
  </main>
  <script>
    const output = document.getElementById("output");
    const statusBox = document.getElementById("status");
    const constraints = document.getElementById("constraints");
    const STAGED_WORKFLOW_STORAGE_KEY = "comsol_training_active_staged_workflow";
    let lastFileSummary = null;
    let activeStagedWorkflowPath = window.localStorage.getItem(STAGED_WORKFLOW_STORAGE_KEY) || "";

    async function request(path, body) {
      statusBox.className = "status";
      statusBox.textContent = "running";
      const response = await fetch(path, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body)
      });
      const data = await response.json();
      output.textContent = JSON.stringify(data, null, 2);
      statusBox.className = data.ok === false ? "status bad" : "status ok";
      statusBox.textContent = data.ok === false ? "failed" : "done";
      return data;
    }

    async function requestGet(path) {
      setStatus("running", "");
      const response = await fetch(path);
      const data = await response.json();
      renderJson(data);
      setStatus(data.ok === false ? "failed" : "done", data.ok === false ? "bad" : "ok");
      return data;
    }

    function setToolsCollapsed(collapsed) {
      const app = document.querySelector(".app");
      const toggle = document.getElementById("toolsToggle");
      if (!app || !toggle) return;
      app.classList.toggle("tools-collapsed", collapsed);
      toggle.textContent = collapsed ? "\u2039" : "\u203a";
      toggle.setAttribute("aria-expanded", String(!collapsed));
      toggle.setAttribute("aria-label", collapsed ? "\u5c55\u5f00\u53f3\u4fa7\u680f" : "\u6536\u56de\u53f3\u4fa7\u680f");
      toggle.title = collapsed ? "\u5c55\u5f00\u53f3\u4fa7\u680f" : "\u6536\u56de\u53f3\u4fa7\u680f";
    }

    function toggleToolsPanel() {
      const app = document.querySelector(".app");
      setToolsCollapsed(!app?.classList.contains("tools-collapsed"));
    }

    function initializeToolsPanel() {
      setToolsCollapsed(false);
    }

    async function loadDefaults() {
      const response = await fetch("/api/default-constraints");
      const data = await response.json();
      constraints.value = JSON.stringify(data, null, 2);
      output.textContent = constraints.value;
      statusBox.className = "status ok";
      statusBox.textContent = "loaded";
    }

    function inspectMatlab() {
      return request("/api/inspect-matlab", {path: document.getElementById("matlabPath").value});
    }

    async function readFilePath() {
      const data = await request("/api/read-file", {path: document.getElementById("filePath").value});
      if (data.ok) {
        lastFileSummary = data.summary;
      }
      return data;
    }

    async function uploadPayload(file) {
      if (!/\.(pdf|mph)$/i.test(file.name || "")) {
        return {name: file.name, content: await file.text()};
      }
      const bytes = new Uint8Array(await file.arrayBuffer());
      let binary = "";
      for (let offset = 0; offset < bytes.length; offset += 32768) {
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
      }
      return {name: file.name, content_base64: btoa(binary)};
    }

    async function readUploadedFile() {
      const file = document.getElementById("uploadFile").files[0];
      if (!file) {
        output.textContent = JSON.stringify({ok: false, error: "No file selected"}, null, 2);
        statusBox.className = "status bad";
        statusBox.textContent = "failed";
        return;
      }
      const data = await request("/api/read-uploaded-file", await uploadPayload(file));
      if (data.ok) {
        lastFileSummary = data.summary;
      }
      return data;
    }

    function sendInstruction() {
      return request("/api/instruction", {
        instruction: document.getElementById("instruction").value,
        file_summary: lastFileSummary
      });
    }

    function validateConstraints() {
      return request("/api/validate-constraints", {constraints_json: constraints.value});
    }

    function generateMatlab() {
      let name = "generated_build_thermal_rectangle_surrogate.m";
      try {
        const cfg = JSON.parse(constraints.value);
        name = "generated_build_" + cfg.model_name + ".m";
      } catch (err) {}
      return request("/api/generate-matlab", {constraints_json: constraints.value, output_name: name});
    }

    function trainModel() {
      return request("/api/train", {
        csv_path: document.getElementById("csvPath").value,
        input_columns: document.getElementById("inputs").value,
        output_columns: document.getElementById("outputs").value,
        model_name: document.getElementById("modelName").value
      });
    }

    loadDefaults();
  </script>
</body>
</html>
"""


CONVERSATIONAL_INDEX = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>COMSOL 本地智能建模与仿真平台</title>
  <style>
    :root {
      --bg: #f7f7f5;
      --surface: #ffffff;
      --surface-2: #f0f2f2;
      --ink: #1f2328;
      --muted: #646b72;
      --line: #d8dadd;
      --accent: #0f766e;
      --accent-dark: #0b5f59;
      --warn: #9a3412;
      --bad: #991b1b;
      --code-bg: #111827;
      --code-ink: #d1fae5;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; overflow: hidden; }
    body {
      margin: 0;
      color: var(--ink);
      background: var(--bg);
      font: 14px/1.5 "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
    }
    button, input, textarea { font: inherit; }
    button {
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 7px 11px;
      color: var(--ink);
      background: var(--surface);
      cursor: pointer;
    }
    button.primary {
      border-color: var(--accent);
      color: #fff;
      background: var(--accent);
      font-weight: 650;
    }
    button.primary:hover { background: var(--accent-dark); }
    button.warning {
      border-color: var(--warn);
      color: #fff;
      background: var(--warn);
    }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 8px 10px;
      color: var(--ink);
      background: var(--surface);
    }
    textarea {
      min-height: 96px;
      resize: vertical;
    }
    label {
      display: block;
      margin: 10px 0 5px;
      color: var(--muted);
      font-size: 12px;
    }
    .app {
      display: grid;
      grid-template-columns: 400px minmax(0, 1fr) 360px;
      height: 100vh;
      max-height: 100vh;
      min-height: 640px;
      overflow: hidden;
      transition: grid-template-columns .18s ease;
    }
    .app.tools-collapsed {
      grid-template-columns: 400px minmax(0, 1fr) 42px;
    }
    .rail {
      display: flex;
      flex-direction: column;
      border-right: 1px solid var(--line);
      background: #ecefed;
      min-width: 0;
      overflow-y: auto;
    }
    .brand {
      padding: 18px 16px 14px;
      border-bottom: 1px solid var(--line);
    }
    .brand-title {
      margin: 0;
      font-size: 16px;
      font-weight: 720;
      letter-spacing: 0;
    }
    .brand-subtitle {
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
    }
    .thread-list {
      padding: 10px;
      overflow: visible;
    }
    .thread {
      width: 100%;
      margin-bottom: 8px;
      text-align: left;
      background: transparent;
    }
    .thread.active {
      border-color: #b8c7c4;
      background: #fff;
      font-weight: 650;
    }
    .rail-foot {
      margin-top: auto;
      padding: 12px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
    }
    .rail-observer {
      margin: 0 10px 12px;
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: hidden;
      background: var(--surface);
      box-shadow: 0 1px 2px rgba(15, 23, 42, .05);
    }
    .rail-observer-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      background: #fafbfa;
    }
    .rail-observer-title { font-size: 13px; font-weight: 720; }
    .rail-observer-header .status { font-size: 11px; }
    .observer-header-actions { display: flex; align-items: center; gap: 6px; }
    .rail-observer-header button {
      display: grid;
      place-items: center;
      width: 30px;
      min-height: 30px;
      padding: 0;
      font-size: 16px;
    }
    .rail-observer-stage {
      position: relative;
      display: grid;
      place-items: center;
      height: clamp(210px, 32vh, 310px);
      padding: 10px;
      background: #e8ecea;
      background-image: linear-gradient(45deg, rgba(255,255,255,.42) 25%, transparent 25%), linear-gradient(-45deg, rgba(255,255,255,.42) 25%, transparent 25%), linear-gradient(45deg, transparent 75%, rgba(255,255,255,.42) 75%), linear-gradient(-45deg, transparent 75%, rgba(255,255,255,.42) 75%);
      background-size: 24px 24px;
      background-position: 0 0, 0 12px, 12px -12px, -12px 0;
    }
    .rail-observer-stage img {
      display: none;
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      border: 1px solid #c8cecb;
      border-radius: 6px;
      background: #fff;
      box-shadow: 0 6px 18px rgba(15, 23, 42, .12);
    }
    .rail-observer-stage canvas {
      display: none;
      width: 100%;
      height: 100%;
      border-radius: 6px;
      background: radial-gradient(circle at 50% 42%, #f7faf9 0, #e1e8e5 72%, #d2dcda 100%);
      cursor: grab;
      touch-action: none;
    }
    .rail-observer-stage canvas.dragging { cursor: grabbing; }
    .observer-view-tools {
      position: absolute;
      z-index: 3;
      top: 8px;
      right: 8px;
      display: none;
      gap: 4px;
      padding: 4px;
      border: 1px solid rgba(148, 163, 184, .55);
      border-radius: 7px;
      background: rgba(255, 255, 255, .9);
      box-shadow: 0 2px 8px rgba(15, 23, 42, .08);
    }
    .observer-view-tools button { min-height: 25px; padding: 3px 7px; border-radius: 5px; font-size: 11px; }
    .observer-view-tools button.active { border-color: var(--accent); color: #fff; background: var(--accent); }
    .observer-view-hint {
      position: absolute; z-index: 2; left: 10px; bottom: 8px; display: none;
      padding: 3px 7px; border-radius: 5px; color: #475569; background: rgba(255,255,255,.82); font-size: 10px;
    }
    .observer-empty {
      max-width: 330px;
      padding: 18px;
      text-align: center;
      color: var(--muted);
      border: 1px dashed #aeb8b4;
      border-radius: 8px;
      background: rgba(255,255,255,.82);
      font-size: 12px;
    }
    .observer-empty strong { display: block; margin-bottom: 6px; color: var(--ink); font-size: 14px; }
    .rail-observer-details { padding: 10px 12px 12px; border-top: 1px solid var(--line); }
    .rail-observer-details select { margin-bottom: 8px; padding: 6px 8px; font-size: 12px; }
    .rail-observer-details strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .rail-observer-details .observer-meta { display: block; overflow: hidden; color: var(--muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
    .observer-export-button {
      width: 100%; margin-top: 8px; padding: 8px 10px; border-color: #8fb7b0;
      color: #155e55; background: #edf8f6; font-size: 12px; font-weight: 700;
    }
    .observer-export-button:hover { border-color: var(--accent); background: #dff4ef; }
    .observer-export-button:disabled { cursor: wait; opacity: .65; }
    .observer-export-row { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
    .rail-observer-connection { padding-top: 8px; margin-top: 8px; border-top: 1px solid var(--line); }
    .rail-observer-header .comsol-connect-button {
      display: flex;
      align-items: center;
      width: auto;
      min-height: 32px;
      padding: 0 10px;
      gap: 7px;
      color: #155e55;
      border-color: #8fb7b0;
      background: #edf8f6;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    .comsol-connect-button:hover { border-color: var(--accent); background: #f0fdfa; }
    .comsol-connect-button:disabled { cursor: wait; opacity: .72; }
    .connection-line { display: flex; align-items: center; gap: 8px; margin: 3px 0; font-size: 12px; }
    .connection-dot { width: 9px; height: 9px; border-radius: 50%; background: #9ca3af; }
    .connection-dot.online { background: #16a34a; box-shadow: 0 0 0 3px rgba(22,163,74,.14); }
    .connection-dot.offline { background: #dc2626; box-shadow: 0 0 0 3px rgba(220,38,38,.12); }
    .observer-note { color: var(--muted); font-size: 11px; line-height: 1.45; }
    .chat {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      min-width: 0;
      min-height: 0;
      background: var(--surface);
    }
    .chat-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 20px;
      border-bottom: 1px solid var(--line);
    }
    .chat-title {
      font-size: 15px;
      font-weight: 700;
    }
    .status {
      color: var(--muted);
      font-size: 12px;
    }
    .status.ok { color: var(--accent-dark); }
    .status.bad { color: var(--bad); }
    .assistant-header-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 7px;
      margin-left: auto;
    }
    .mode-switch { display: flex; gap: 3px; padding: 3px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); }
    .mode-switch button { min-height: 28px; padding: 4px 9px; border-color: transparent; background: transparent; font-size: 12px; }
    .mode-switch button.active { color: #fff; border-color: var(--accent); background: var(--accent); }
    .header-provider { width: auto; min-width: 132px; padding: 6px 8px; font-size: 12px; }
    .assistant-mode-summary { max-width: 230px; color: var(--muted); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .messages {
      overflow: auto;
      min-height: 0;
      padding: 20px 24px 18px;
      scroll-behavior: smooth;
    }
    .message {
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr);
      gap: 12px;
      max-width: 920px;
      margin: 0 auto 22px;
    }
    .avatar {
      display: grid;
      place-items: center;
      width: 32px;
      height: 32px;
      border: 1px solid var(--line);
      border-radius: 50%;
      color: var(--muted);
      background: var(--surface-2);
      font-size: 12px;
      font-weight: 700;
    }
    .message.user .avatar {
      color: #fff;
      background: var(--accent);
      border-color: var(--accent);
    }
    .bubble {
      min-width: 0;
      padding-top: 4px;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .bubble h3 {
      margin: 0 0 6px;
      font-size: 14px;
    }
    .bubble ul {
      margin: 6px 0 0;
      padding-left: 18px;
    }
    .bubble code {
      padding: 1px 4px;
      border-radius: 4px;
      background: var(--surface-2);
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
    }
    .composer {
      padding: 14px 20px 18px;
      border-top: 1px solid var(--line);
      background: var(--surface);
    }
    .api-fallback-bar {
      display: none;
      max-width: 920px;
      margin: 0 auto 9px;
      padding: 9px 10px;
      border: 1px solid #f0b27a;
      border-radius: 8px;
      color: #7c2d12;
      background: #fff7ed;
      font-size: 12px;
      align-items: center;
      gap: 8px;
    }
    .api-fallback-bar.visible { display: flex; }
    .api-fallback-bar span { flex: 1; min-width: 0; }
    .api-fallback-bar button { flex: 0 0 auto; padding: 5px 8px; }
    .composer-inner {
      max-width: 920px;
      margin: 0 auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      overflow: hidden;
    }
    #prompt {
      min-height: 78px;
      max-height: 220px;
      border: 0;
      border-radius: 0;
      outline: 0;
      resize: vertical;
    }
    .composer-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 8px;
      border-top: 1px solid var(--line);
      background: #fafafa;
    }
    .quick-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .tools {
      position: relative;
      border-left: 1px solid var(--line);
      background: #f4f5f4;
      overflow: auto;
      min-width: 0;
      min-height: 0;
      height: 100vh;
      max-height: 100vh;
      overscroll-behavior: contain;
    }
    .tools-toggle {
      position: sticky;
      top: 8px;
      z-index: 5;
      display: grid;
      place-items: center;
      width: 28px;
      height: 34px;
      margin: 8px 7px 0;
      padding: 0;
      border-radius: 7px;
      color: var(--ink);
      background: var(--surface);
      border-color: var(--line);
      font-size: 16px;
      line-height: 1;
    }
    .app.tools-collapsed .tools {
      overflow: hidden;
    }
    .app.tools-collapsed .tool-section {
      display: none;
    }
    .tool-section {
      padding: 16px;
      border-bottom: 1px solid var(--line);
    }
    .tool-section > .tool-title {
      cursor: pointer;
      list-style: none;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-height: 28px;
      margin: -4px 0 10px;
      padding: 4px 0;
      user-select: none;
    }
    .tool-section > .tool-title::-webkit-details-marker { display: none; }
    .tool-section > .tool-title::after {
      content: "折叠";
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      line-height: 1;
    }
    .tool-section:not([open]) > .tool-title::after { content: "打开"; }
    .tool-section:not([open]) > :not(.tool-title) { display: none; }
    .tool-title {
      margin: 0 0 10px;
      font-size: 13px;
      font-weight: 720;
      text-transform: uppercase;
      color: var(--muted);
    }
    .api-config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 8px; }
    .api-config-grid .wide { grid-column: 1 / -1; }
    .api-key-state { margin-top: 6px; color: var(--muted); font-size: 11px; }
    .privacy-note { margin-top: 10px; padding: 8px 9px; border-radius: 6px; color: #31534e; background: #eef7f5; font-size: 11px; line-height: 1.5; }
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-top: 10px;
    }
    #constraints {
      min-height: 230px;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
    }
    .raw {
      min-height: 170px;
      max-height: 360px;
      overflow: auto;
      margin: 0;
      padding: 11px;
      border: 1px solid var(--line);
      border-radius: 7px;
      color: var(--code-ink);
      background: var(--code-bg);
      font: 12px/1.45 Consolas, "Courier New", monospace;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .progress-card {
      display: grid;
      gap: 10px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fbfbfa;
      white-space: normal;
    }
    .progress-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 12px;
    }
    .progress-bar {
      height: 8px;
      overflow: hidden;
      border-radius: 999px;
      background: var(--surface-2);
    }
    .progress-fill {
      width: 0%;
      height: 100%;
      border-radius: inherit;
      background: var(--accent);
      transition: width .25s ease;
    }
    .progress-steps {
      margin: 0;
      padding-left: 18px;
    }
    .progress-steps li {
      margin: 4px 0;
      color: var(--muted);
    }
    .progress-steps li.active {
      color: var(--ink);
      font-weight: 650;
    }
    .progress-steps li.done {
      color: var(--accent-dark);
    }
    .staged-dashboard { margin-top: 12px; }
    .staged-dashboard .progress-card { margin-top: 8px; }
    .workflow-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 10px; font-size: 11px; }
    .workflow-meta strong { display: block; color: var(--ink); font-size: 12px; }
    .workflow-warning { padding: 8px; border: 1px solid #f0b27a; border-radius: 6px; color: #7c2d12; background: #fff7ed; font-size: 11px; }
    .workflow-ok { padding: 8px; border: 1px solid #8fb7b0; border-radius: 6px; color: #155e55; background: #edf8f6; font-size: 11px; }
    @media (max-width: 1180px) {
      .app { grid-template-columns: 360px minmax(0, 1fr); }
      .app.tools-collapsed { grid-template-columns: 360px minmax(0, 1fr); }
      .tools {
        grid-column: 1 / -1;
        border-left: 0;
        border-top: 1px solid var(--line);
        max-height: 48vh;
        height: 48vh;
      }
    }
    @media (max-width: 760px) {
      .app {
        grid-template-columns: 1fr;
        height: auto;
        min-height: 100vh;
        max-height: none;
        overflow: visible;
      }
      .rail { display: none; }
      .chat { min-height: 100vh; }
      .tools { height: auto; max-height: none; }
      .app.tools-collapsed .tool-section { display: block; }
      .messages { padding: 16px; }
      .message { grid-template-columns: 28px minmax(0, 1fr); gap: 9px; }
      .avatar { width: 28px; height: 28px; }
      .chat-header { align-items: flex-start; flex-wrap: wrap; }
      .assistant-header-actions { width: 100%; justify-content: flex-start; }
      .assistant-mode-summary { max-width: 100%; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="rail">
      <div class="brand">
        <h1 class="brand-title">COMSOL Model Codex</h1>
        <div class="brand-subtitle">对话式建模与训练工作台</div>
      </div>
      <div class="thread-list">
        <button class="thread active" data-mode="chat" onclick="selectThreadMode('chat')">当前会话</button>
        <button class="thread" data-mode="modeling" onclick="selectThreadMode('modeling')">自动建模</button>
        <button class="thread" data-mode="reading" onclick="selectThreadMode('reading')">文件阅读</button>
        <button class="thread" data-mode="training" onclick="selectThreadMode('training')">代理模型训练</button>
        <button class="thread" data-mode="execution" onclick="selectThreadMode('execution')">任务中心</button>
      </div>
      <section class="rail-observer" aria-label="COMSOL 模型观测窗">
        <header class="rail-observer-header">
          <div>
            <div class="rail-observer-title">COMSOL 模型观测窗</div>
            <div class="status" id="observerRefreshStatus">每 5 秒自动刷新</div>
          </div>
          <div class="observer-header-actions">
            <button class="comsol-connect-button" id="comsolConnectButton" onclick="connectComsolServer()" title="点击启动或复用 COMSOL mphserver">
              <span class="connection-dot" id="observerConnectionDot"></span>
              <span id="observerConnectionState">连接 COMSOL</span>
            </button>
            <button class="observer-refresh-button" onclick="refreshComsolObserver(true)" aria-label="刷新模型" title="刷新模型">&#8635;</button>
          </div>
        </header>
        <div class="rail-observer-stage">
          <img id="observerImage" alt="COMSOL 模型预览">
          <canvas id="observer3dCanvas" aria-label="COMSOL 三维模型，可拖动旋转并滚轮缩放"></canvas>
          <div class="observer-view-tools" id="observerViewTools">
            <button id="observer3dModeButton" onclick="showObserverMode('3d')">三维</button>
            <button id="observerImageModeButton" onclick="showObserverMode('image')">结果图</button>
            <button onclick="resetObserver3dView()" title="重置三维视角">重置</button>
          </div>
          <div class="observer-view-hint" id="observer3dHint">拖动旋转 · 滚轮缩放</div>
          <div class="observer-empty" id="observerEmpty">
            <strong>正在查找模型预览</strong>
            MATLAB 生成模型后，这里会自动显示结果图或几何图。
          </div>
        </div>
        <div class="rail-observer-details">
          <select id="observerArtifactSelect" aria-label="最近生成的 MPH" onchange="selectObserverArtifact(this.value)"></select>
          <strong id="observerModelName">尚未选择模型</strong>
          <span class="observer-meta" id="observerModelMeta">等待最新 MPH 文件</span>
          <span class="observer-note" id="observerArtifactCount">正在读取模型列表</span>
          <div class="observer-export-row">
            <button class="observer-export-button" id="observer3dExportButton" onclick="exportSelectedComsol3d()">生成/更新三维</button>
            <button class="observer-export-button" id="observerExportButton" onclick="exportSelectedComsolPreview()">导出结果图</button>
          </div>
          <span class="observer-note" id="observerExportMessage"></span>
          <div class="rail-observer-connection">
            <div class="observer-note" id="observerConnectionAddress">localhost:2036 · 正在检测端口</div>
            <div class="observer-note" id="observerExecutionState"></div>
            <div class="observer-note" id="observerConnectMessage"></div>
          </div>
        </div>
      </section>
      <div class="rail-foot" id="nodeStatus">本地节点：正在检查</div>
    </aside>

    <main class="chat">
      <header class="chat-header">
        <div>
          <div class="chat-title">COMSOL 智能建模助手</div>
          <div class="status" id="status">ready</div>
        </div>
        <div class="assistant-header-actions">
          <div class="mode-switch" aria-label="助手运行模式">
            <button id="offlineModeButton" class="active" onclick="setAssistantModeQuick('offline')">离线模式</button>
            <button id="apiModeButton" onclick="setAssistantModeQuick('api')">API 模式</button>
          </div>
          <select id="headerAssistantProvider" class="header-provider" onchange="setAssistantProviderQuick(this.value)" aria-label="API 提供方">
            <option value="codex_local">本机 Codex（免密钥）</option>
            <option value="openai">Codex / OpenAI</option>
            <option value="deepseek">DeepSeek</option>
          </select>
          <span id="assistantModeSummary" class="assistant-mode-summary">本地离线处理</span>
          <button onclick="openAssistantSettings()">AI 接入设置</button>
          <button onclick="clearChat()">清空对话</button>
        </div>
      </header>
      <div class="messages" id="messages"></div>
      <footer class="composer">
        <div id="apiFallbackBar" class="api-fallback-bar">
          <span id="apiFallbackText">本地任务失败，可交给远程 AI 分析和补充。</span>
          <button id="apiFallbackButton" onclick="completeLastFailureWithApi(false)">交给 API 完善</button>
          <button onclick="dismissApiFallback()">关闭</button>
        </div>
        <div class="composer-inner">
          <textarea id="prompt" placeholder="输入需求，例如：读取这个 MATLAB 文件，并判断能否用于自动建模和代理模型训练。"></textarea>
          <div class="composer-actions">
            <div class="quick-actions">
              <button onclick="useTemplate('请读取文件，并判断能否用于 COMSOL 自动建模和代理模型训练。')">读取文件</button>
              <button onclick="useTemplate('根据当前约束生成 COMSOL LiveLink MATLAB 建模脚本。')">生成脚本</button>
              <button onclick="useTemplate('根据 CSV 数据训练代理模型，并说明输入列和输出列。')">训练建议</button>
              <button onclick="useTemplate('总结当前案例学到的建模理论、参数、约束、可复用功能和下一步训练路径。')">学习总结</button>
              <button onclick="planModelFromPrompt()">建模方案</button>
            </div>
            <button class="primary" onclick="sendPrompt()">发送</button>
          </div>
        </div>
      </footer>
    </main>

    <aside class="tools">
      <button class="tools-toggle" id="toolsToggle" onclick="toggleToolsPanel()" aria-label="收回右侧栏" title="收回右侧栏" aria-expanded="true">&rsaquo;</button>
      <details class="tool-section" id="tool-ai" data-tool-group="ai-access">
        <summary class="tool-title">AI 接入设置</summary>
        <div class="api-config-grid">
          <div>
            <label for="assistantMode">运行模式</label>
            <select id="assistantMode" onchange="setAssistantModeQuick(this.value)">
              <option value="offline">离线模式</option>
              <option value="api">API 模式</option>
            </select>
          </div>
          <div>
            <label for="assistantProvider">API 提供方</label>
            <select id="assistantProvider" onchange="renderAssistantProviderFields()">
              <option value="codex_local">本机 Codex（免密钥）</option>
              <option value="openai">Codex / OpenAI</option>
              <option value="deepseek">DeepSeek</option>
            </select>
          </div>
          <div class="wide">
            <label for="assistantBaseUrl">API 地址</label>
            <input id="assistantBaseUrl" autocomplete="off">
          </div>
          <div class="wide">
            <label for="assistantModel">模型名称</label>
            <input id="assistantModel" autocomplete="off">
          </div>
          <div>
            <label for="assistantReasoning">推理强度</label>
            <select id="assistantReasoning">
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
            </select>
          </div>
          <div>
            <label for="assistantTimeout">超时（秒）</label>
            <input id="assistantTimeout" type="number" min="10" max="600" value="120">
          </div>
          <div class="wide">
            <label for="assistantApiKey">API 密钥（留空表示不修改）</label>
            <input id="assistantApiKey" type="password" autocomplete="new-password" placeholder="输入后仅保存在本机">
            <div id="assistantKeyState" class="api-key-state">尚未配置密钥</div>
          </div>
        </div>
        <label><input id="assistantClearKey" type="checkbox"> 清除当前提供方已保存的密钥</label>
        <label><input id="assistantAutoFallback" type="checkbox"> 本地任务失败时自动交给当前 API 分析</label>
        <div class="row">
          <button class="primary" onclick="saveAssistantSettings(false)">保存设置</button>
          <button onclick="testAssistantConnection()">保存并测试连接</button>
        </div>
        <div class="privacy-note">“本机 Codex”复用当前电脑已登录的 Codex，无需 API 密钥，并以只读临时会话运行。自定义密钥仅写入本机忽略目录，不会显示在页面或工作日志中。自动转交默认关闭；开启后会发送失败摘要、接口名称和脱敏后的任务参数。</div>
      </details>
      <details class="tool-section" id="tool-files" data-tool-group="case-learning" open>
        <summary class="tool-title">案例学习与文件</summary>
        <label for="filePath">路径，每行一个</label>
        <textarea id="filePath" oninput="syncCaseFieldsFromPaths()" onchange="syncCaseFieldsFromPaths()">../acoustic_rectangular_cavity/build_acoustic_rectangular_cavity.m
examples/sample_comsol_data.csv
configs/thermal_constraints.json</textarea>
        <label for="uploadFile">选择文件，可多选</label>
        <input id="uploadFile" type="file" multiple onchange="syncCaseFieldsFromUpload()">
        <div class="row">
          <button onclick="readFilePath()">读取路径文件</button>
          <button onclick="readUploadedFile()">读取选择文件</button>
          <button onclick="buildLearningSummary()">学习总结</button>
        </div>
        <label for="caseDir">COMSOL 案例目录</label>
        <input id="caseDir" value="/home/lab/zhangmx/案例下载/案例下载/" oninput="syncCaseTitleFromCaseDir()" onchange="syncCaseTitleFromCaseDir()">
        <label for="caseTitle">案例名称</label>
        <input id="caseTitle" value="科赫雪花建模">
        <label for="caseSyncInfo">自动关联信息</label>
        <input id="caseSyncInfo" value="等待选择文件或输入路径" readonly>
        <div class="row">
          <button onclick="refreshCaseSourceStatus(true)">检测案例源</button>
          <button class="primary" onclick="learnCaseDirectory()">学习案例并输出总结</button>
          <button onclick="buildKnowledgeSystem()">形成知识体系</button>
        </div>
        <label for="articlePath">文章/论文 Word 路径</label>
        <input id="articlePath" value="D:/桌面/COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究.docx">
        <div class="row">
          <button onclick="learnArticleDocument()">按文章生成建模修正方案</button>
        </div>
      </details>
      <details class="tool-section" id="tool-matlab" data-tool-group="model-generation">
        <summary class="tool-title">模型生成与修改</summary>
        <label for="matlabPath">.m 路径</label>
        <input id="matlabPath" value="../acoustic_rectangular_cavity/build_acoustic_rectangular_cavity.m">
        <label for="codeRequirement">COMSOL 建模需求</label>
        <textarea id="codeRequirement">结合已学习案例和文章知识，生成一个 COMSOL 模型构建脚本，要求同时输出 LiveLink MATLAB 代码和 Java 代码，并标注需要人工复核的边界选择、材料和物理场。</textarea>
        <label for="existingComsolContent">现有 MATLAB/Java/模型摘要内容</label>
        <textarea id="existingComsolContent" placeholder="可粘贴已有 COMSOL MATLAB 脚本、Java 代码或 MPH 摘要；模型会根据学习库给出修正和完善建议。"></textarea>
        <label for="codeFilePath">代码文件路径</label>
        <input id="codeFilePath" value="generated/code/generated_comsol_model.m">
        <label for="codeInstruction">代码修改指令</label>
        <textarea id="codeInstruction" placeholder="例如：把结果导出增加为 CSV；或说明需要修改的 COMSOL 建模逻辑。"></textarea>
        <label for="findText">查找文本</label>
        <textarea id="findText" placeholder="可选：填写要替换的原始代码片段。"></textarea>
        <label for="replaceText">替换文本 / 追加代码</label>
        <textarea id="replaceText" placeholder="如果填写了查找文本，则作为替换内容；如果不填查找文本，则可作为追加代码。"></textarea>
        <label for="codeOutputPath">输出路径</label>
        <input id="codeOutputPath" value="generated/code/generated_comsol_model.codex_edit.m">
        <div class="row">
          <button onclick="inspectMatlab()">解析 MATLAB</button>
          <button class="primary" onclick="generateComsolCode()">生成 MATLAB + Java</button>
          <button onclick="readCodeFile()">读取代码</button>
          <button class="warning" onclick="modifyCodeFile()">修改代码并输出</button>
        </div>
        <label for="stagedRequirement">分步建模需求</label>
        <textarea id="stagedRequirement">请将当前 COMSOL 建模任务拆分为物理场、材料、数据与结构、网格、求解、结果导出，并在每一步等待我批准后继续。</textarea>
        <label for="stagedWorkflowPath">分步任务文件</label>
        <input id="stagedWorkflowPath" value="">
        <label for="approvalComment">审批意见</label>
        <textarea id="approvalComment" placeholder="例如：物理场正确，可以继续；或说明需要修改的地方。"></textarea>
        <div class="row">
          <button onclick="createStagedWorkflow()">创建分步建模任务</button>
          <button class="primary" onclick="approveStagedStep(true)">批准当前步骤</button>
          <button onclick="approveStagedStep(false)">退回修改</button>
          <button class="warning" onclick="finalizeStagedWorkflow()">生成完整建模包</button>
        </div>
        <div class="staged-dashboard">
          <label for="stagedWorkflowSelect">已保存任务</label>
          <select id="stagedWorkflowSelect" onchange="resumeSelectedStagedWorkflow()"><option value="">选择要恢复的任务</option></select>
          <div class="row">
            <button onclick="refreshStagedWorkflows(true)">刷新/恢复任务</button>
            <button onclick="retryFailedStagedWorkflow()">从失败阶段重提</button>
            <button onclick="downloadStagedWorkflowPackage()">下载任务包</button>
          </div>
          <div class="progress-card" id="stagedProgressCard">
            <div class="progress-head"><span id="stagedProgressTitle">尚未创建自动建模任务</span><span id="stagedProgressCount">0/10</span></div>
            <div class="progress-bar"><div class="progress-fill" id="stagedProgressFill"></div></div>
            <div class="workflow-meta">
              <div>状态<strong id="stagedWorkflowStatus">等待任务</strong></div>
              <div>风险等级<strong id="stagedWorkflowRisk">-</strong></div>
              <div>物理场<strong id="stagedWorkflowPhysics">-</strong></div>
              <div>缺失信息<strong id="stagedWorkflowMissing">-</strong></div>
            </div>
            <ol class="progress-steps" id="stagedProgressSteps"></ol>
            <div id="stagedWorkflowNotice" class="workflow-ok">页面刷新后可从上方列表恢复当前合同和进度。</div>
          </div>
        </div>
      </details>
      <details class="tool-section" id="tool-constraints" data-tool-group="model-constraints">
        <summary class="tool-title">模型约束</summary>
        <textarea id="constraints"></textarea>
        <div class="row">
          <button onclick="loadDefaults()">载入示例</button>
          <button onclick="validateConstraints()">校验</button>
          <button class="warning" onclick="generateMatlab()">生成 MATLAB</button>
        </div>
      </details>
      <details class="tool-section" id="tool-reference" data-tool-group="reference">
        <summary class="tool-title">物理参考与对照</summary>
        <label for="referenceCaseType">参考案例类型</label>
        <select id="referenceCaseType" onchange="loadReferenceDefaults()">
          <option value="laminar_pipe_poiseuille">圆管层流压降</option>
          <option value="thermoacoustic_open_tube">热声开开管</option>
          <option value="flow_heat_channel">流热通道</option>
          <option value="acoustic_structure_cantilever">声-结构悬臂梁</option>
          <option value="electrochemical_nernst">电化学 Nernst 平衡</option>
          <option value="particle_stokes_settling">颗粒 Stokes 沉降</option>
          <option value="rf_half_wave_resonator">射频半波谐振腔</option>
          <option value="acoustic_rectangular_cavity">二维声学矩形腔</option>
        </select>
        <label for="referenceParameters">SI 参数 JSON</label>
        <textarea id="referenceParameters">{"length_m":1,"diameter_m":0.01,"flow_rate_m3_s":1e-5,"viscosity_pa_s":0.001,"density_kg_m3":1000}</textarea>
        <label for="referenceResultKey">参考结果字段</label>
        <input id="referenceResultKey" value="pressure_drop_pa">
        <label for="observedComsolValue">COMSOL 观测值</label>
        <input id="observedComsolValue" inputmode="decimal" placeholder="从结果或导出表填入数值">
        <label for="observedComsolUnit">观测单位</label>
        <input id="observedComsolUnit" value="Pa" placeholder="例如 Pa、Hz、K、m/s 或 V">
        <div class="row">
          <input id="referenceComparisonThreshold" aria-label="参考比较误差阈值百分比" value="5" inputmode="decimal">
          <button onclick="compareReferenceObservation()">对照 COMSOL 结果</button>
        </div>
        <label for="comsolResultsCsvPath">COMSOL 结果 CSV</label>
        <input id="comsolResultsCsvPath" placeholder="含 name,value 列的导出 CSV 路径">
        <label for="comsolObservedResultName">CSV 结果名称</label>
        <input id="comsolObservedResultName" value="pressure_drop_pa">
        <label for="workchainReportPaths">工作链参考报告路径</label>
        <textarea id="workchainReportPaths" placeholder="每行一个已保存的参考报告 JSON 路径"></textarea>
        <div class="row">
          <button onclick="assembleReferenceWorkchain()">生成工作链包</button>
          <button onclick="showReferenceWorkchains()">查看工作链包</button>
        </div>
        <label for="workchainPackagePath">工作链包路径</label>
        <input id="workchainPackagePath" placeholder="要验证的工作链包 JSON 路径">
        <div class="row">
          <button onclick="validateReferenceWorkchain()">验证工作链包</button>
          <button onclick="archiveReferenceWorkchain()">导出工作链 ZIP</button>
        </div>
        <label for="workchainArchivePath">工作链 ZIP 路径</label>
        <input id="workchainArchivePath" placeholder="要验证的工作链 ZIP 路径">
        <div class="row">
          <button onclick="validateReferenceWorkchainArchive()">验证工作链 ZIP</button>
        </div>
        <div class="row">
          <button onclick="compareReferenceResultsCsv()">从 CSV 对照</button>
          <button onclick="showReferenceReports()">查看参考报告</button>
        </div>
        <div class="row">
          <button onclick="evaluateReferenceCase()">计算物理参考</button>
        </div>
      </details>
      <details class="tool-section" id="tool-closure-checks" data-tool-group="training-closure">
        <summary class="tool-title">训练闭环检查</summary>
        <label for="meshRecords">网格记录 JSON</label>
        <textarea id="meshRecords">[{"hmax_m":0.01,"dofs":100,"output":10},{"hmax_m":0.005,"dofs":400,"output":10.08},{"hmax_m":0.0025,"dofs":1600,"output":10.085}]</textarea>
        <div class="row">
          <input id="meshOutputName" aria-label="网格收敛输出名称" value="quantity_of_interest">
          <input id="meshThreshold" aria-label="网格收敛阈值百分比" value="1" inputmode="decimal">
          <button onclick="checkMeshConvergence()">检查网格收敛</button>
        </div>
        <label for="coverageRanges">参数覆盖范围 JSON</label>
        <textarea id="coverageRanges">{"k":[10,50],"Q":[1000,10000]}</textarea>
        <div class="row">
          <input id="coverageBins" aria-label="参数覆盖分箱数" value="5" inputmode="numeric">
          <button onclick="checkParameterCoverage()">检查参数覆盖</button>
          <button onclick="checkHoldoutIndependence()">检查留出独立性</button>
        </div>
        <label for="augmentationCsvPath">补充 COMSOL CSV</label>
        <input id="augmentationCsvPath" placeholder="补充样本 CSV 路径">
        <label for="previousHoldoutCsvPath">旧留出集 CSV</label>
        <input id="previousHoldoutCsvPath" placeholder="重训前的留出集 CSV 路径">
        <label for="freshHoldoutCsvPath">新留出集 CSV</label>
        <input id="freshHoldoutCsvPath" placeholder="未参与训练的新 COMSOL 扫描 CSV 路径">
        <div class="row">
          <button onclick="prepareAugmentationRetrain()">准备补充样本重训</button>
        </div>
      </details>
      <details class="tool-section" id="tool-training" data-tool-group="training">
        <summary class="tool-title">训练与代理预测</summary>
        <label for="csvPath">CSV 路径</label>
        <input id="csvPath" value="examples/sample_comsol_data.csv">
        <label for="inputs">输入列</label>
        <input id="inputs" value="k Q h L">
        <label for="outputs">输出列</label>
        <input id="outputs" value="Tmax Tavg">
        <label for="modelName">模型文件名</label>
        <input id="modelName" value="thermal_surrogate.joblib">
        <div class="row">
          <button class="primary" onclick="queueThermalSweepTraining()">一键执行传热扫描训练</button>
          <button onclick="prepareThermalSweep()">生成传热扫描脚本</button>
          <button onclick="inspectTrainingCsv()">自动分析 CSV</button>
          <button onclick="autoTrainModel()">自动训练</button>
          <button class="primary" onclick="trainModel()">训练模型</button>
        </div>
        <label for="holdoutCsvPath">独立 COMSOL 留出集 CSV</label>
        <input id="holdoutCsvPath" placeholder="必须是未参与训练的新 COMSOL 扫描数据">
        <label for="physicalScope">物理适用范围</label>
        <textarea id="physicalScope" placeholder="说明物理场、几何、材料、边界条件、研究类型和允许的参数变化。"></textarea>
        <label for="relativeErrorThreshold">留出集最大相对误差阈值 (%)</label>
        <input id="relativeErrorThreshold" value="5" inputmode="decimal">
        <div class="row">
          <button class="primary" onclick="trainWithComsolHoldout()">独立 COMSOL 验证训练</button>
          <button onclick="showSurrogateRegistry()">查看已验证模型</button>
          <button onclick="showClosureAudit()">查看闭环审计</button>
        </div>
        <label for="registeredModelId">已验证模型 ID</label>
        <input id="registeredModelId" placeholder="先从代理模型注册表复制 ID">
        <label for="registeredInputs">预测输入 JSON</label>
        <textarea id="registeredInputs" placeholder='例如：{"k": 16, "Q": 8000, "h": 35, "L": 0.05}'></textarea>
        <div class="row">
          <button class="primary" onclick="predictRegisteredSurrogate()">受控代理预测</button>
          <button onclick="createRegisteredAugmentationPlan()">生成补充 COMSOL 工况</button>
        </div>
        <label for="thermalSurrogateModel">已验证二维传热模型</label>
        <input id="thermalSurrogateModel" value="">
        <div class="row">
          <input id="thermalL" aria-label="板长 L (m)" value="0.06" title="板长 L，单位 m">
          <input id="thermalW" aria-label="板宽 W (m)" value="0.0225" title="板宽 W，单位 m">
          <input id="thermalK" aria-label="导热系数 (W/(m K))" value="40" title="导热系数，单位 W/(m K)">
        </div>
        <div class="row">
          <input id="thermalHot" aria-label="高温端 (K)" value="353.15" title="高温端温度，单位 K">
          <input id="thermalCold" aria-label="低温端 (K)" value="283.15" title="低温端温度，单位 K">
          <button class="primary" onclick="predictThermalPlate()">已验证模型快速预测</button>
        </div>
        <label for="experimentalTemperatureCsv">真实温度实验 CSV</label>
        <input id="experimentalTemperatureCsv" value="examples/experimental_temperature_measurements_template.csv">
        <div class="row">
          <button class="primary" onclick="runExperimentalValidation()">执行三方验证</button>
          <button onclick="refreshExperimentalValidationStatus(true)">查看实验状态</button>
        </div>
        <div class="hint" id="experimentalValidationStatus">实验验证状态：正在读取</div>
      </details>
      <details class="tool-section" id="tool-execution" data-tool-group="execution">
        <summary class="tool-title">训练与任务执行</summary>
        <label for="executionRequirement">建模任务</label>
        <textarea id="executionRequirement">建立母线板焦耳热标杆模型：电流场与固体传热通过 Joule Heating 耦合，输出温度与电流密度，并准备参数扫描 CSV。</textarea>
        <div class="row">
          <button class="primary" onclick="createJouleHeatBenchmark()">创建焦耳热标杆</button>
          <button onclick="matchValidatedTemplate()">匹配已验证模板</button>
          <button onclick="deriveAndQueueMatchedTemplate()">按文本改参数并入队</button>
          <button onclick="createExecutionJob()">创建普通任务</button>
        </div>
        <div class="row">
          <button onclick="processNextExecutionJob()">处理下一任务</button>
          <button onclick="refreshExecutionJobs()">刷新任务状态</button>
          <button onclick="showRecentArtifacts()">查看最近结果</button>
        </div>
        <div class="hint">任务默认只生成并校验脚本；配置 MATLAB LiveLink 路径并显式启用执行节点后，才会调用本机 COMSOL 许可证。</div>
      </details>
      <details class="tool-section" id="tool-dac-p0" data-tool-group="dac-p0-evidence" open>
        <summary class="tool-title">DAC P0 第三方盲测</summary>
        <div class="progress-card">
          <div class="progress-head"><span>外部作者提交</span><strong id="dacP0AuthorState">读取中</strong></div>
          <div class="progress-head"><span>独立裁决提交</span><strong id="dacP0JudgeState">读取中</strong></div>
          <div class="progress-head"><span>密封盲测任务</span><strong id="dacP0TaskState">读取中</strong></div>
          <div class="progress-head"><span>四方法实测记录</span><strong id="dacP0ResponseState">读取中</strong></div>
          <div class="progress-head"><span>P0 论文证据门</span><strong id="dacP0GateState">读取中</strong></div>
          <div class="hint" id="dacP0NextState">正在读取 P0 采集活动。</div>
        </div>
        <div class="row">
          <button onclick="openDacP0Intake()">打开第三方采集入口</button>
          <button onclick="refreshDacP0Status(true)">刷新 P0 状态</button>
          <button onclick="showDacP0Evidence()">查看详细判定</button>
        </div>
        <div class="hint">只有项目组外作者与不同裁决者提交的记录才能计入论文；内部先导结果不会混入主结果。</div>
      </details>
      <details class="tool-section" id="tool-dac-p1" data-tool-group="dac-p1-scenarios" open>
        <summary class="tool-title">DAC P1 EDA 设计任务</summary>
        <div class="progress-card">
          <div class="progress-head"><span>主场景合同</span><strong id="dacP1ScenarioState">读取中</strong></div>
          <div class="progress-head"><span>EDA 环节覆盖</span><strong id="dacP1StageState">读取中</strong></div>
          <div class="progress-head"><span>任务定义门</span><strong id="dacP1DefinitionState">读取中</strong></div>
          <div class="progress-head"><span>冻结后新 COMSOL 实验</span><strong id="dacP1FreshState">读取中</strong></div>
          <div class="progress-head"><span>双案例投稿实验门</span><strong id="dacP1SubmissionState">读取中</strong></div>
          <div class="hint" id="dacP1EvidenceState">正在读取 P1 场景合同。</div>
        </div>
        <div class="row">
          <button onclick="refreshDacP1Status(true)">刷新 P1 状态</button>
          <button onclick="showDacP1Evidence()">查看完整证据</button>
        </div>
        <div class="hint">合同定义完成与投稿实验完成分别显示；历史保留集不会显示为冻结后的新实验。</div>
      </details>
      <details class="tool-section" id="tool-dac-p2" data-tool-group="dac-p2-comparison" open>
        <summary class="tool-title">DAC P2 方法对照与消融</summary>
        <div class="progress-card">
          <div class="progress-head"><span>冻结任务</span><strong id="dacP2TaskState">读取中</strong></div>
          <div class="progress-head"><span>四方法实测</span><strong id="dacP2ResponseState">读取中</strong></div>
          <div class="progress-head"><span>三项消融</span><strong id="dacP2AblationState">读取中</strong></div>
          <div class="progress-head"><span>P2 开发证据门</span><strong id="dacP2DevelopmentState">读取中</strong></div>
          <div class="progress-head"><span>第三方主结果门</span><strong id="dacP2PublicationState">读取中</strong></div>
          <div class="hint" id="dacP2EvidenceState">正在读取 P2 冻结比较状态。</div>
        </div>
        <div class="row">
          <button onclick="refreshDacP2Status(true)">刷新 P2 状态</button>
          <button onclick="showDacP2Evidence()">查看详细证据</button>
        </div>
        <div class="hint">项目组编写的 24 条任务用于开发对照；只有在 P0 密封第三方任务上复跑后，结果才能进入 DAC 主结果。</div>
      </details>
      <details class="tool-section" id="tool-dac-p3" data-tool-group="dac-p3-prospective" open>
        <summary class="tool-title">DAC P3 前瞻多案例评测</summary>
        <div class="progress-card">
          <div class="progress-head"><span>协议与统计管线</span><strong id="dacP3InfrastructureState">读取中</strong></div>
          <div class="progress-head"><span>外部密封任务</span><strong id="dacP3TaskState">读取中</strong></div>
          <div class="progress-head"><span>案例族隔离</span><strong id="dacP3IsolationState">读取中</strong></div>
          <div class="progress-head"><span>重复实测记录</span><strong id="dacP3ResponseState">读取中</strong></div>
          <div class="progress-head"><span>P3 主结果门</span><strong id="dacP3MainState">读取中</strong></div>
          <div class="hint" id="dacP3EvidenceState">正在读取 P3 前瞻评测状态。</div>
        </div>
        <div class="row">
          <button onclick="refreshDacP3Status(true)">刷新 P3 状态</button>
          <button onclick="prepareDacP3()">检查并密封 P3</button>
          <button onclick="showDacP3Evidence()">查看评测协议</button>
        </div>
        <div class="hint">两种 LLM 各对每条任务独立运行 3 次；确定性方法各运行 1 次，共需 192 条观测。任务必须来自项目组外作者，并与全部开发案例族隔离。</div>
      </details>
      <details class="tool-section" id="tool-dac-p4" data-tool-group="dac-p4-submission" open>
        <summary class="tool-title">DAC P4 双盲稿件与复现包</summary>
        <div class="progress-card">
          <div class="progress-head"><span>格式与页面检查</span><strong id="dacP4FormatState">读取中</strong></div>
          <div class="progress-head"><span>双盲检查</span><strong id="dacP4BlindState">读取中</strong></div>
          <div class="progress-head"><span>相关工作与 AI 声明</span><strong id="dacP4WritingState">读取中</strong></div>
          <div class="progress-head"><span>匿名复现包</span><strong id="dacP4PackageState">读取中</strong></div>
          <div class="progress-head"><span>P3 外部主结果</span><strong id="dacP4ExternalState">读取中</strong></div>
          <div class="progress-head"><span>P4 本机基础设施门</span><strong id="dacP4InfrastructureState">读取中</strong></div>
          <div class="progress-head"><span>P4 最终投稿门</span><strong id="dacP4FinalState">读取中</strong></div>
          <div class="hint" id="dacP4EvidenceState">正在读取 P4 投稿准备状态。</div>
        </div>
        <div class="row">
          <button onclick="refreshDacP4Status(true)">刷新 P4 状态</button>
          <button onclick="showDacP4Evidence()">查看投稿检查</button>
        </div>
        <div class="hint">本机稿件完成不会自动开放投稿；P3 独立结果和作者逐条人工核对仍是最终投稿门的必需条件。</div>
      </details>
      <details class="tool-section" id="tool-p3" data-tool-group="p3-design" open>
        <summary class="tool-title">P3 母排设计优化</summary>
        <div class="progress-card">
          <div class="progress-head"><span>固定电流 COMSOL 闭环</span><strong id="p3ComsolState">读取中</strong></div>
          <div class="hint" id="p3BaselineState">基准电流：读取中</div>
          <div class="progress-head"><span>真实验证 Pareto 方案</span><strong id="p3ParetoState">读取中</strong></div>
          <div class="progress-head"><span>代理模型发布</span><strong id="p3SurrogateState">读取中</strong></div>
          <div class="hint" id="p3EvaluationState">正在读取独立域内与越界测试。</div>
        </div>
        <div class="row">
          <button onclick="refreshP3Status(true)">刷新 P3 状态</button>
          <button onclick="showP3Evidence()">查看完整证据</button>
        </div>
        <div class="hint">代理模型未通过发布门槛时，平台保留真实 COMSOL Pareto 结果，但不开放该代理模型的数值预测。</div>
      </details>
      <details class="tool-section" id="tool-p4" data-tool-group="p4-adaptive" open>
        <summary class="tool-title">P4 自适应代理修复</summary>
        <div class="progress-card">
          <div class="progress-head"><span>自适应 COMSOL 补样</span><strong id="p4AdaptiveState">读取中</strong></div>
          <div class="hint" id="p4TrainingState">训练集：读取中</div>
          <div class="progress-head"><span>独立终评执行</span><strong id="p4ComsolState">读取中</strong></div>
          <div class="progress-head"><span>预测精度</span><strong id="p4AccuracyState">读取中</strong></div>
          <div class="progress-head"><span>安全放行覆盖率</span><strong id="p4CoverageState">读取中</strong></div>
          <div class="progress-head"><span>代理模型发布</span><strong id="p4ReleaseState">读取中</strong></div>
          <div class="hint" id="p4EvaluationState">正在读取全新封存最终集。</div>
        </div>
        <div class="row">
          <button onclick="refreshP4Status(true)">刷新 P4 状态</button>
          <button onclick="showP4Evidence()">查看完整证据</button>
        </div>
        <div class="hint">预测精度达标不等于可以安全发布；发布还要求保守门控覆盖足够多的域内设计。</div>
      </details>
      <details class="tool-section" id="tool-p5" data-tool-group="p5-conformal" open>
        <summary class="tool-title">P5 单侧安全校准</summary>
        <div class="progress-card">
          <div class="progress-head"><span>冻结校准方法</span><strong id="p5MethodState">读取中</strong></div>
          <div class="progress-head"><span>全新独立终评</span><strong id="p5ComsolState">读取中</strong></div>
          <div class="progress-head"><span>安全放行</span><strong id="p5CoverageState">读取中</strong></div>
          <div class="progress-head"><span>false-safe</span><strong id="p5FalseSafeState">读取中</strong></div>
          <div class="progress-head"><span>代理模型发布</span><strong id="p5ReleaseState">读取中</strong></div>
          <div class="hint" id="p5EvaluationState">正在读取 P5 封存终评。</div>
        </div>
        <div class="row">
          <button onclick="refreshP5Status(true)">刷新 P5 状态</button>
          <button onclick="showP5Evidence()">查看完整证据</button>
        </div>
        <div class="hint">发布资格只覆盖声明的七变量域和当前固定物理假设；越界或改变材料、边界与物理场时仍调用 COMSOL。</div>
      </details>
      <details class="tool-section" id="tool-p6" data-tool-group="p6-evidence" open>
        <summary class="tool-title">P6 外部证据与双执行路径</summary>
        <div class="progress-card">
          <div class="progress-head"><span>Java 双执行路径</span><strong id="p6JavaState">读取中</strong></div>
          <div class="progress-head"><span>本机迁移预检</span><strong id="p6LocalState">读取中</strong></div>
          <div class="progress-head"><span>温度实物实验</span><strong id="p6ExperimentState">读取中</strong></div>
          <div class="progress-head"><span>人工/外部模型对照</span><strong id="p6BaselineState">读取中</strong></div>
          <div class="progress-head"><span>目标电脑验收</span><strong id="p6DestinationState">读取中</strong></div>
          <div class="progress-head"><span>P6 外部证据门</span><strong id="p6ReleaseState">读取中</strong></div>
          <div class="hint" id="p6EvidenceState">正在读取 P6 证据状态。</div>
        </div>
        <div class="row">
          <button onclick="refreshP6Status(true)">刷新 P6 状态</button>
          <button onclick="showP6Evidence()">查看完整证据</button>
        </div>
        <div class="hint">模板行和合成数据不计为外部证据。实物测量、人工参与和目标电脑执行完成后才会关闭 P6 投稿门。</div>
      </details>
      <details class="tool-section" id="tool-p7" data-tool-group="p7-multicase" open>
        <summary class="tool-title">P7 多 EDA 案例验证</summary>
        <div class="progress-card">
          <div class="progress-head"><span>主案例验收</span><strong id="p7MainState">读取中</strong></div>
          <div class="progress-head"><span>物理类型覆盖</span><strong id="p7PhysicsState">读取中</strong></div>
          <div class="progress-head"><span>独立保留集</span><strong id="p7HoldoutState">读取中</strong></div>
          <div class="progress-head"><span>扩展案例</span><strong id="p7ExtensionState">读取中</strong></div>
          <div class="progress-head"><span>P7 验收门</span><strong id="p7ReleaseState">读取中</strong></div>
          <div class="hint" id="p7EvidenceState">正在读取 P7 多案例证据。</div>
        </div>
        <div class="row">
          <button onclick="refreshP7Status(true)">刷新 P7 状态</button>
          <button onclick="showP7Evidence()">查看完整证据</button>
        </div>
        <div class="hint">母排为当前项目新完成的 COMSOL 闭环；其余案例按保存的独立 COMSOL 保留集证据单独标记，不冒充本次重新求解。</div>
      </details>
      <details class="tool-section" id="tool-results" data-tool-group="results">
        <summary class="tool-title">结果与知识库</summary>
        <pre id="raw" class="raw">{}</pre>
      </details>
    </aside>
  </div>

  <script>
    const messages = document.getElementById("messages");
    const raw = document.getElementById("raw");
    const statusBox = document.getElementById("status");
    const nodeStatus = document.getElementById("nodeStatus");
    const constraints = document.getElementById("constraints");
    const STAGED_WORKFLOW_STORAGE_KEY = "comsol_training_active_staged_workflow";
    const ASSISTANT_MODE_STORAGE_KEY = "comsol_training_assistant_mode";
    let lastFileSummary = null;
    let activeStagedWorkflowPath = "";
    let assistantConfig = null;
    let lastFailedTask = null;
    let observerArtifacts = [];
    let p3Status = null;
    let p4Status = null;
    let p5Status = null;
    let p6Status = null;
    let p7Status = null;
    let dacP0Status = null;
    let dacP1Status = null;
    let dacP2Status = null;
    let dacP3Status = null;
    let dacP4Status = null;
    const observer3dState = {
      triangles: [], url: "", rotationX: -0.48, rotationY: 0.65, zoom: 1,
      dragging: false, lastX: 0, lastY: 0, mode: "3d"
    };

    function stagedWorkflowPathInput() {
      return document.getElementById("stagedWorkflowPath");
    }

    function syncStagedWorkflowPath(path) {
      const value = String(path || "").trim();
      if (!value) return;
      activeStagedWorkflowPath = value;
      window.localStorage.setItem(STAGED_WORKFLOW_STORAGE_KEY, value);
      const input = stagedWorkflowPathInput();
      if (input) input.value = value;
    }

    function activeWorkflowPath() {
      const input = stagedWorkflowPathInput();
      return String(activeStagedWorkflowPath || (input ? input.value : "") || "").trim();
    }

    function hasActiveStagedWorkflow() {
      return Boolean(activeWorkflowPath());
    }

    function renderStagedWorkflowDashboard(workflow) {
      if (!workflow) return;
      const steps = workflow.steps || [];
      const done = steps.filter(step => String(step.status || "") === "approved").length;
      const total = steps.length || 10;
      const summary = workflow.contract_summary || {};
      const missing = summary.missing_information || [];
      const conflicts = workflow.conflicts || [];
      document.getElementById("stagedProgressTitle").textContent = workflow.requirement || workflow.workflow_id || "自动建模任务";
      document.getElementById("stagedProgressCount").textContent = `${done}/${total}`;
      document.getElementById("stagedProgressFill").style.width = `${Math.round(100 * done / Math.max(1, total))}%`;
      document.getElementById("stagedWorkflowStatus").textContent = workflow.status || "unknown";
      document.getElementById("stagedWorkflowRisk").textContent = summary.risk_level || "-";
      document.getElementById("stagedWorkflowPhysics").textContent = (summary.physics_interfaces || []).join("、") || "待选择";
      document.getElementById("stagedWorkflowMissing").textContent = missing.length ? `${missing.length} 项` : "0 项";
      document.getElementById("stagedProgressSteps").innerHTML = steps.map((step, index) => {
        const cls = step.status === "approved" ? "done" : (index === Number(workflow.current_step || 0) ? "active" : "");
        return `<li class="${cls}">${escapeHtml(step.title || step.id || "步骤")}：<code>${escapeHtml(step.status || "pending")}</code></li>`;
      }).join("");
      const notice = document.getElementById("stagedWorkflowNotice");
      if (conflicts.length || missing.length) {
        const items = conflicts.map(item => item.message).concat(missing.map(item => item.question || item.field));
        notice.className = "workflow-warning";
        notice.textContent = `当前阻断项：${items.join("；")}`;
      } else {
        notice.className = "workflow-ok";
        notice.textContent = workflow.status === "completed" ? "执行与物理验证证据齐全，任务已完成。" : "合同已保存；页面刷新或服务重启后可以继续当前阶段。";
      }
    }

    async function refreshStagedWorkflows(showMessage = false) {
      const data = await requestGet("/api/staged-workflows?limit=50");
      const select = document.getElementById("stagedWorkflowSelect");
      const rows = data.workflows || [];
      select.innerHTML = `<option value="">选择要恢复的任务</option>` + rows.map(item =>
        `<option value="${escapeHtml(item.path || "")}">${escapeHtml(item.workflow_id || "workflow")} · ${escapeHtml(item.status || "")}</option>`
      ).join("");
      if (activeWorkflowPath()) select.value = activeWorkflowPath();
      if (showMessage) addMessage("assistant", `<h3>已保存自动建模任务</h3><p>共找到 ${escapeHtml(String(rows.length))} 个任务，可选择后恢复合同和十阶段进度。</p>`);
      return data;
    }

    async function resumeSelectedStagedWorkflow() {
      const path = document.getElementById("stagedWorkflowSelect").value || activeWorkflowPath();
      if (!path) return null;
      syncStagedWorkflowPath(path);
      const data = await requestGet(`/api/staged-workflow?path=${encodeURIComponent(path)}`);
      if (data.ok) {
        renderStagedWorkflowDashboard(data.workflow || {});
        addMessage("assistant", summarizeStagedWorkflowResponse(data));
      }
      return data;
    }

    async function retryFailedStagedWorkflow() {
      const data = await request("/api/staged-workflow/retry-failed", {workflow_path: activeWorkflowPath()});
      if (data.ok) renderStagedWorkflowDashboard(data.workflow || {});
      addMessage("assistant", summarizeStagedWorkflowResponse(data));
      return data;
    }

    function downloadStagedWorkflowPackage() {
      const path = activeWorkflowPath();
      if (!path) {
        addMessage("assistant", "<h3>没有可下载的任务</h3><p>请先创建或恢复一个自动建模任务。</p>");
        return;
      }
      window.location.href = `/api/staged-workflow/download?path=${encodeURIComponent(path)}`;
    }

    if (activeStagedWorkflowPath) {
      syncStagedWorkflowPath(activeStagedWorkflowPath);
    }

    function setStatus(text, kind) {
      statusBox.textContent = text;
      statusBox.className = "status" + (kind ? " " + kind : "");
    }

    function assistantProviderConfig(provider) {
      return assistantConfig?.providers?.[provider || assistantConfig?.active_provider] || {};
    }

    function assistantProviderLabel(provider) {
      if (assistantProviderConfig(provider).label) return assistantProviderConfig(provider).label;
      if (provider === "codex_local") return "本机 Codex（免密钥）";
      return provider === "deepseek" ? "DeepSeek" : "Codex / OpenAI";
    }

    function applyAssistantConfig(config) {
      assistantConfig = config;
      const mode = config.mode || "offline";
      window.localStorage.setItem(ASSISTANT_MODE_STORAGE_KEY, mode);
      const provider = config.active_provider || "openai";
      document.getElementById("offlineModeButton").classList.toggle("active", mode === "offline");
      document.getElementById("apiModeButton").classList.toggle("active", mode === "api");
      document.getElementById("headerAssistantProvider").value = provider;
      document.getElementById("assistantMode").value = mode;
      document.getElementById("assistantProvider").value = provider;
      document.getElementById("assistantTimeout").value = Number(config.timeout_seconds || 120);
      document.getElementById("assistantAutoFallback").checked = Boolean(config.auto_fallback);
      const current = assistantProviderConfig(provider);
      const summary = mode === "offline"
        ? "本地离线处理，不发送数据"
        : `${assistantProviderLabel(provider)} · ${current.model || "未设置模型"}${current.requires_api_key === false ? (current.available ? " · 已登录可用" : " · 本机不可用") : (current.api_key_configured ? " · 密钥已配置" : " · 待配置密钥")}`;
      document.getElementById("assistantModeSummary").textContent = summary;
      document.getElementById("apiFallbackButton").textContent = `交给 ${assistantProviderLabel(provider)} 完善`;
      renderAssistantProviderFields();
    }

    async function loadAssistantConfig() {
      try {
        const response = await fetch("/api/assistant/config");
        const data = await response.json();
        if (!data.ok) throw new Error(data.error || "无法读取 AI 设置");
        applyAssistantConfig(data.config);
      } catch (error) {
        const fallback = {
          mode: "offline",
          active_provider: "codex_local",
          auto_fallback: false,
          timeout_seconds: 120,
          providers: {
            codex_local: {label: "本机 Codex（免密钥）", base_url: "local://codex", model: "default", reasoning_effort: "medium", api_key_configured: false, available: false, requires_api_key: false},
            openai: {label: "Codex / OpenAI", base_url: "https://api.openai.com/v1", model: "gpt-6-sol", reasoning_effort: "medium", api_key_configured: false},
            deepseek: {label: "DeepSeek", base_url: "https://api.deepseek.com", model: "deepseek-flash", reasoning_effort: "medium", api_key_configured: false}
          }
        };
        applyAssistantConfig(fallback);
        setStatus("local service offline", "bad");
        document.getElementById("assistantModeSummary").textContent = "离线界面已启用；本地服务未连接";
      }
    }

    function renderAssistantProviderFields() {
      if (!assistantConfig) return;
      const provider = document.getElementById("assistantProvider").value || assistantConfig.active_provider;
      const config = assistantProviderConfig(provider);
      document.getElementById("assistantBaseUrl").value = config.base_url || "";
      document.getElementById("assistantBaseUrl").disabled = provider === "codex_local";
      document.getElementById("assistantModel").value = config.model || "";
      document.getElementById("assistantReasoning").value = config.reasoning_effort || "medium";
      document.getElementById("assistantApiKey").value = "";
      document.getElementById("assistantApiKey").disabled = provider === "codex_local";
      document.getElementById("assistantClearKey").checked = false;
      document.getElementById("assistantClearKey").disabled = provider === "codex_local";
      document.getElementById("assistantKeyState").textContent = provider === "codex_local"
        ? (config.available ? "本机 Codex 已登录，可直接使用" : "未检测到可用的本机 Codex")
        : (config.api_key_configured ? "已配置本机密钥；留空保存不会覆盖" : "尚未配置密钥");
    }

    async function postAssistantConfig(payload) {
      const response = await fetch("/api/assistant/config", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      renderJson(data);
      if (!data.ok) throw new Error(data.error || "AI 设置保存失败");
      applyAssistantConfig(data.config);
      return data;
    }

    async function setAssistantModeQuick(mode) {
      const requestedMode = mode === "api" ? "api" : "offline";
      const previousConfig = assistantConfig ? JSON.parse(JSON.stringify(assistantConfig)) : null;
      if (!assistantConfig) {
        await loadAssistantConfig();
      }
      if (assistantConfig) {
        applyAssistantConfig({...assistantConfig, mode: requestedMode});
      }
      try {
        const data = await postAssistantConfig({mode: requestedMode});
        const provider = data.config.active_provider;
        if (requestedMode === "api" && !assistantProviderConfig(provider).api_key_configured) {
          openAssistantSettings();
          addMessage("assistant", `<h3>还差 API 密钥</h3><p>已切换到 API 模式。请在右侧保存 ${escapeHtml(assistantProviderLabel(provider))} 的密钥，然后测试连接。</p>`);
        }
      } catch (error) {
        if (requestedMode === "offline") {
          window.localStorage.setItem(ASSISTANT_MODE_STORAGE_KEY, "offline");
          setStatus("local service offline", "bad");
          document.getElementById("assistantModeSummary").textContent = "已切换离线界面；请重新启动本地服务以执行任务";
          addMessage("assistant", `<h3>已切换到离线界面</h3><p>本地服务当前未连接，因此建模、文件读取和训练操作暂时不可执行。请运行 <code>start_windows.bat</code> 恢复本地服务。</p>`);
        } else {
          if (previousConfig) applyAssistantConfig(previousConfig);
          addMessage("assistant", `<h3>API 模式切换失败</h3><p>${escapeHtml(error.message)}</p>`);
        }
      }
    }

    async function setAssistantProviderQuick(provider) {
      try {
        const data = await postAssistantConfig({active_provider: provider});
        if (data.config.mode === "api" && !assistantProviderConfig(provider).api_key_configured) openAssistantSettings();
      } catch (error) {
        addMessage("assistant", `<h3>API 切换失败</h3><p>${escapeHtml(error.message)}</p>`);
      }
    }

    function openAssistantSettings() {
      const section = document.getElementById("tool-ai");
      section.open = true;
      setToolsCollapsed(false);
      section.scrollIntoView({behavior: "smooth", block: "start"});
    }

    async function saveAssistantSettings(silent) {
      if (!assistantConfig) await loadAssistantConfig();
      const provider = document.getElementById("assistantProvider").value;
      const apiKey = document.getElementById("assistantApiKey").value.trim();
      const providerPayload = {
        model: document.getElementById("assistantModel").value.trim(),
        reasoning_effort: document.getElementById("assistantReasoning").value,
        clear_api_key: document.getElementById("assistantClearKey").checked
      };
      if (provider !== "codex_local") providerPayload.base_url = document.getElementById("assistantBaseUrl").value.trim();
      if (apiKey) providerPayload.api_key = apiKey;
      try {
        setStatus("saving AI settings", "");
        const data = await postAssistantConfig({
          mode: document.getElementById("assistantMode").value,
          active_provider: provider,
          auto_fallback: document.getElementById("assistantAutoFallback").checked,
          timeout_seconds: Number(document.getElementById("assistantTimeout").value || 120),
          providers: {[provider]: providerPayload}
        });
        document.getElementById("assistantApiKey").value = "";
        setStatus("AI settings saved", "ok");
        if (!silent) addMessage("assistant", `<h3>AI 接入设置已保存</h3><p>当前模式：${data.config.mode === "api" ? "API" : "离线"}；提供方：${escapeHtml(assistantProviderLabel(data.config.active_provider))}。</p>`);
        return data;
      } catch (error) {
        setStatus("AI settings failed", "bad");
        addMessage("assistant", `<h3>AI 设置保存失败</h3><p>${escapeHtml(error.message)}</p>`);
        throw error;
      }
    }

    async function testAssistantConnection() {
      try {
        const saved = await saveAssistantSettings(true);
        const provider = saved.config.active_provider;
        const data = await request("/api/assistant/test", {provider});
        if (data.ok) addMessage("assistant", summarizeRemoteAssistant(data, "API 连接测试"));
        else addMessage("assistant", `<h3>API 连接测试失败</h3><p>${escapeHtml(data.error || "未知错误")}</p>`);
      } catch (error) {
        // saveAssistantSettings already displayed a useful error.
      }
    }

    function redactForRemote(value, depth = 0) {
      if (depth > 8) return "[层级过深，已省略]";
      if (Array.isArray(value)) return value.slice(0, 50).map(item => redactForRemote(item, depth + 1));
      if (value && typeof value === "object") {
        const result = {};
        Object.entries(value).forEach(([key, item]) => {
          if (/(api.?key|token|secret|password|authorization|credential)/i.test(key)) result[key] = "[已隐藏]";
          else result[key] = redactForRemote(item, depth + 1);
        });
        return result;
      }
      if (typeof value === "string" && value.length > 4000) return value.slice(0, 4000) + "\n[内容已截断]";
      return value;
    }

    function rememberFailedTask(path, body, data) {
      lastFailedTask = {
        endpoint: path,
        request: redactForRemote(body || {}),
        failure: redactForRemote({error: data.error || "", message: data.message || "", work_feedback: data.work_feedback || null})
      };
      const bar = document.getElementById("apiFallbackBar");
      document.getElementById("apiFallbackText").textContent = `本地任务 ${path} 失败，可交给远程 AI 分析并补充方案。`;
      bar.classList.add("visible");
      if (assistantConfig?.mode === "api" && assistantConfig.auto_fallback && assistantProviderConfig().api_key_configured) {
        window.setTimeout(() => completeLastFailureWithApi(true), 0);
      }
    }

    function dismissApiFallback() {
      document.getElementById("apiFallbackBar").classList.remove("visible");
    }

    async function completeLastFailureWithApi(automatic) {
      if (!lastFailedTask) return;
      if (!assistantConfig || !assistantProviderConfig().api_key_configured) {
        openAssistantSettings();
        addMessage("assistant", "<h3>需要配置 API</h3><p>请先保存当前提供方的 API 密钥，再转交失败任务。</p>");
        return;
      }
      dismissApiFallback();
      const task = `分析并完善本地失败任务：${lastFailedTask.endpoint}`;
      const data = await request("/api/assistant/complete", {task, context: lastFailedTask});
      if (data.ok) addMessage("assistant", summarizeRemoteAssistant(data, automatic ? "API 自动补充" : "API 任务补充"));
      else addMessage("assistant", `<h3>远程补充失败</h3><p>${escapeHtml(data.error || "未知错误")}</p>`);
    }

    function summarizeRemoteAssistant(data, title) {
      const answer = escapeHtml(data.answer || "")
        .split(/\n\s*\n/)
        .map(part => `<p>${part.replace(/\n/g, "<br>")}</p>`)
        .join("");
      return `<h3>${escapeHtml(title || "远程 AI 回复")}</h3><p><code>${escapeHtml(data.provider_label || data.provider || "API")}</code> · <code>${escapeHtml(data.model || "")}</code></p>${answer}`;
    }

    async function refreshNodeStatus() {
      try {
        const response = await fetch("/api/health");
        const data = await response.json();
        const worker = data.execution_worker || {};
        const node = data.execution_node || {};
        const surrogate = data.surrogate_runtime || {};
        const queue = worker.queue || {};
        const workerText = worker.online ? "执行 worker 在线" : "执行 worker 未运行";
        const serverText = node.server_reachable ? "COMSOL 已连接" : "COMSOL 未连接";
        const queueText = `队列 ${Number(queue.queued || 0)}，复核 ${Number(queue.awaiting_review || 0)}`;
        const surrogateText = !surrogate.available
          ? "代理未审计"
          : surrogate.healthy
            ? `代理 ${Number(surrogate.passed || 0)}/${Number(surrogate.validated_models || 0)}`
            : surrogate.state === "stale"
              ? "代理待重审"
              : "代理异常";
        nodeStatus.textContent = `本地节点：${workerText} | ${serverText} | ${queueText} | ${surrogateText}`;
      } catch (error) {
        nodeStatus.textContent = "本地节点：状态检查失败";
      }
    }

    function formatArtifactBytes(value) {
      const bytes = Number(value || 0);
      if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
      if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${bytes} B`;
    }

    function showObserverMode(mode) {
      const artifact = observerArtifacts[Number(document.getElementById("observerArtifactSelect").value) || 0];
      const canvas = document.getElementById("observer3dCanvas");
      const image = document.getElementById("observerImage");
      const empty = document.getElementById("observerEmpty");
      const hint = document.getElementById("observer3dHint");
      const use3d = mode === "3d" && artifact?.three_d_available && observer3dState.triangles.length;
      const useImage = mode === "image" && artifact?.preview_available;
      observer3dState.mode = use3d ? "3d" : useImage ? "image" : mode;
      canvas.style.display = use3d ? "block" : "none";
      image.style.display = useImage ? "block" : "none";
      hint.style.display = use3d ? "block" : "none";
      empty.style.display = use3d || useImage ? "none" : "block";
      document.getElementById("observer3dModeButton").classList.toggle("active", use3d);
      document.getElementById("observerImageModeButton").classList.toggle("active", useImage);
      if (use3d) renderObserver3d();
    }

    async function loadObserver3d(artifact) {
      if (!artifact?.three_d_available || !artifact.stl_url) return false;
      const versionedUrl = `${artifact.stl_url}&v=${encodeURIComponent(artifact.updated_at || Date.now())}`;
      if (observer3dState.url === versionedUrl && observer3dState.triangles.length) return true;
      const response = await fetch(versionedUrl, {cache: "no-store"});
      if (!response.ok) throw new Error(`STL 加载失败 (${response.status})`);
      observer3dState.triangles = parseStl(await response.arrayBuffer());
      observer3dState.url = versionedUrl;
      resetObserver3dView(false);
      return observer3dState.triangles.length > 0;
    }

    function parseStl(buffer) {
      const view = new DataView(buffer);
      const triangles = [];
      const count = buffer.byteLength >= 84 ? view.getUint32(80, true) : 0;
      const binary = count > 0 && 84 + count * 50 <= buffer.byteLength;
      if (binary) {
        const step = Math.max(1, Math.ceil(count / 18000));
        for (let index = 0; index < count; index += step) {
          const base = 84 + index * 50 + 12;
          const triangle = [];
          for (let vertex = 0; vertex < 3; vertex += 1) {
            const offset = base + vertex * 12;
            triangle.push([view.getFloat32(offset, true), view.getFloat32(offset + 4, true), view.getFloat32(offset + 8, true)]);
          }
          triangles.push(triangle);
        }
      } else {
        const text = new TextDecoder().decode(buffer);
        const values = [...text.matchAll(/vertex\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)/g)]
          .map(match => [Number(match[1]), Number(match[2]), Number(match[3])]);
        for (let index = 0; index + 2 < values.length; index += 3) triangles.push(values.slice(index, index + 3));
      }
      if (!triangles.length) throw new Error("STL 中没有可显示的三角面。");
      const points = triangles.flat();
      const minimum = [0, 1, 2].map(axis => Math.min(...points.map(point => point[axis])));
      const maximum = [0, 1, 2].map(axis => Math.max(...points.map(point => point[axis])));
      const center = minimum.map((value, axis) => (value + maximum[axis]) / 2);
      const span = Math.max(...maximum.map((value, axis) => value - minimum[axis])) || 1;
      return triangles.map(triangle => triangle.map(point => point.map((value, axis) => (value - center[axis]) * 2 / span)));
    }

    function transformObserverPoint(point) {
      const cy = Math.cos(observer3dState.rotationY), sy = Math.sin(observer3dState.rotationY);
      const cx = Math.cos(observer3dState.rotationX), sx = Math.sin(observer3dState.rotationX);
      const x = point[0] * cy + point[2] * sy;
      const z1 = -point[0] * sy + point[2] * cy;
      const y = point[1] * cx - z1 * sx;
      const z = point[1] * sx + z1 * cx;
      return [x, y, z];
    }

    function renderObserver3d() {
      const canvas = document.getElementById("observer3dCanvas");
      if (!observer3dState.triangles.length || canvas.style.display === "none") return;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(1, canvas.clientWidth), height = Math.max(1, canvas.clientHeight);
      if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
        canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
      }
      const context = canvas.getContext("2d");
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);
      const scale = Math.min(width, height) * .42 * observer3dState.zoom;
      const faces = observer3dState.triangles.map(triangle => {
        const rotated = triangle.map(transformObserverPoint);
        const projected = rotated.map(point => {
          const perspective = 3.8 / Math.max(1.7, 3.8 - point[2] * .45);
          return [width / 2 + point[0] * scale * perspective, height / 2 - point[1] * scale * perspective];
        });
        const a = rotated[0], b = rotated[1], c = rotated[2];
        const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2];
        const vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
        const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
        const length = Math.hypot(nx, ny, nz) || 1;
        const light = Math.max(.18, Math.min(1, .52 + (nx * -.3 + ny * .45 + nz * .82) / length * .48));
        return {projected, depth: (a[2] + b[2] + c[2]) / 3, light};
      }).sort((left, right) => left.depth - right.depth);
      context.lineJoin = "round";
      for (const face of faces) {
        const green = Math.round(104 + face.light * 82);
        const blue = Math.round(111 + face.light * 70);
        context.beginPath();
        context.moveTo(face.projected[0][0], face.projected[0][1]);
        context.lineTo(face.projected[1][0], face.projected[1][1]);
        context.lineTo(face.projected[2][0], face.projected[2][1]);
        context.closePath();
        context.fillStyle = `rgb(${Math.round(30 + face.light * 35)}, ${green}, ${blue})`;
        context.fill();
        context.strokeStyle = "rgba(15, 76, 70, .22)";
        context.lineWidth = .45;
        context.stroke();
      }
    }

    function resetObserver3dView(render = true) {
      observer3dState.rotationX = -0.48;
      observer3dState.rotationY = 0.65;
      observer3dState.zoom = 1;
      if (render) renderObserver3d();
    }

    function initializeObserver3dControls() {
      const canvas = document.getElementById("observer3dCanvas");
      canvas.addEventListener("pointerdown", event => {
        observer3dState.dragging = true; observer3dState.lastX = event.clientX; observer3dState.lastY = event.clientY;
        canvas.classList.add("dragging"); canvas.setPointerCapture(event.pointerId);
      });
      canvas.addEventListener("pointermove", event => {
        if (!observer3dState.dragging) return;
        observer3dState.rotationY += (event.clientX - observer3dState.lastX) * .012;
        observer3dState.rotationX += (event.clientY - observer3dState.lastY) * .012;
        observer3dState.lastX = event.clientX; observer3dState.lastY = event.clientY; renderObserver3d();
      });
      const endDrag = () => { observer3dState.dragging = false; canvas.classList.remove("dragging"); };
      canvas.addEventListener("pointerup", endDrag); canvas.addEventListener("pointercancel", endDrag);
      canvas.addEventListener("wheel", event => {
        event.preventDefault();
        observer3dState.zoom = Math.max(.45, Math.min(3.5, observer3dState.zoom * Math.exp(-event.deltaY * .001)));
        renderObserver3d();
      }, {passive: false});
      window.addEventListener("resize", renderObserver3d);
    }

    async function selectObserverArtifact(indexValue) {
      const artifact = observerArtifacts[Number(indexValue) || 0];
      const image = document.getElementById("observerImage");
      const canvas = document.getElementById("observer3dCanvas");
      const empty = document.getElementById("observerEmpty");
      const exportButton = document.getElementById("observerExportButton");
      const export3dButton = document.getElementById("observer3dExportButton");
      const tools = document.getElementById("observerViewTools");
      exportButton.disabled = !artifact || exportButton.dataset.allowed === "false";
      export3dButton.disabled = !artifact || export3dButton.dataset.allowed === "false";
      if (!artifact) {
        image.style.display = "none"; canvas.style.display = "none"; tools.style.display = "none";
        image.removeAttribute("src");
        empty.style.display = "block";
        document.getElementById("observerModelName").textContent = "尚未发现 MPH 模型";
        document.getElementById("observerModelMeta").textContent = "MATLAB/COMSOL 执行完成后将自动出现";
        return;
      }
      document.getElementById("observerModelName").textContent = artifact.name || "COMSOL 模型";
      document.getElementById("observerModelMeta").textContent = `${formatArtifactBytes(artifact.size_bytes)} · ${new Date(artifact.updated_at).toLocaleString()} · ${artifact.three_d_available ? "三维可交互" : "等待三维导出"}`;
      tools.style.display = artifact.preview_available || artifact.three_d_available ? "flex" : "none";
      document.getElementById("observer3dModeButton").style.display = artifact.three_d_available ? "block" : "none";
      document.getElementById("observerImageModeButton").style.display = artifact.preview_available ? "block" : "none";
      if (artifact.preview_available) {
        image.onerror = () => {
          image.style.display = "none"; empty.style.display = "block";
          empty.innerHTML = "<strong>结果图加载失败</strong>请点击刷新模型重试。";
        };
        image.src = `${artifact.preview_url}&v=${encodeURIComponent(artifact.updated_at || Date.now())}`;
      } else {
        image.removeAttribute("src");
      }
      if (artifact.three_d_available) {
        empty.style.display = "block"; empty.innerHTML = "<strong>正在加载三维模型</strong>正在解析 COMSOL 导出的 STL 几何。";
        try {
          await loadObserver3d(artifact);
          showObserverMode("3d");
          return;
        } catch (error) {
          empty.innerHTML = `<strong>三维模型加载失败</strong>${escapeHtml(error.message || error)}`;
        }
      }
      if (!artifact.preview_available) {
        image.style.display = "none";
        canvas.style.display = "none";
        empty.style.display = "block";
        empty.innerHTML = `<strong>MPH 模型已生成</strong><code>${escapeHtml(artifact.name || "")}</code><br>点击“生成/更新三维”即可直接由 COMSOL 导出可交互几何。`;
        return;
      }
      showObserverMode("image");
    }

    async function refreshComsolObserver(showProgress = false) {
      const refreshStatus = document.getElementById("observerRefreshStatus");
      if (showProgress) refreshStatus.textContent = "正在刷新模型与端口状态...";
      try {
        const response = await fetch("/api/comsol/observer", {cache: "no-store"});
        const data = await response.json();
        const connection = data.connection || {};
        const dot = document.getElementById("observerConnectionDot");
        const connectButton = document.getElementById("comsolConnectButton");
        const exportButton = document.getElementById("observerExportButton");
        const export3dButton = document.getElementById("observer3dExportButton");
        dot.className = `connection-dot ${connection.reachable ? "online" : "offline"}`;
        document.getElementById("observerConnectionState").textContent = connection.reachable ? "COMSOL 已连接" : "连接 COMSOL";
        document.getElementById("observerConnectionAddress").textContent = `${connection.host || "localhost"}:${Number(connection.port || 2036)} · ${connection.reachable ? "端口已连接" : "端口未连接"}`;
        connectButton.title = connection.reachable ? "COMSOL 已连接；点击重新检测" : "点击启动或复用 COMSOL mphserver";
        exportButton.dataset.allowed = String(Boolean(connection.preview_export_allowed));
        export3dButton.dataset.allowed = String(Boolean(connection.preview_export_allowed));
        document.getElementById("observerExecutionState").textContent = connection.external_execution_allowed
          ? "完整 MATLAB/COMSOL 执行已启用"
          : connection.preview_export_allowed
            ? "按需预览导出已启用；完整建模与求解关闭"
            : "外部执行当前关闭；历史模型仍可观测";
        observerArtifacts = Array.isArray(data.artifacts) ? data.artifacts : [];
        const select = document.getElementById("observerArtifactSelect");
        const previousPath = observerArtifacts[Number(select.value) || 0]?.path;
        select.innerHTML = observerArtifacts.length
          ? observerArtifacts.map((artifact, index) => `<option value="${index}">${escapeHtml(artifact.name)}</option>`).join("")
          : '<option value="0">尚未发现模型</option>';
        let selectedIndex = observerArtifacts.findIndex(artifact => artifact.path === previousPath);
        if (selectedIndex < 0) selectedIndex = 0;
        select.value = String(selectedIndex);
        document.getElementById("observerArtifactCount").textContent = `共发现 ${observerArtifacts.length} 个 MPH 文件；按更新时间排序`;
        selectObserverArtifact(selectedIndex);
        refreshStatus.textContent = `上次刷新：${new Date().toLocaleTimeString()} · 自动刷新每 ${Number(data.refresh_seconds || 5)} 秒`;
      } catch (error) {
        refreshStatus.textContent = `刷新失败：${error.message || error}`;
      }
    }

    async function connectComsolServer() {
      const button = document.getElementById("comsolConnectButton");
      const state = document.getElementById("observerConnectionState");
      const message = document.getElementById("observerConnectMessage");
      button.disabled = true;
      state.textContent = "正在连接 COMSOL...";
      message.textContent = "正在启动或复用本机 mphserver，请稍候。";
      try {
        const response = await fetch("/api/comsol/connect", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: "{}"
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.message || data.error || "COMSOL 连接失败");
        }
        message.textContent = data.message || "COMSOL 端口连接成功。";
        await refreshComsolObserver(true);
        await refreshNodeStatus();
      } catch (error) {
        message.textContent = `连接失败：${error.message || error}`;
        await refreshComsolObserver(true);
      } finally {
        button.disabled = false;
      }
    }

    async function exportSelectedComsolPreview() {
      const select = document.getElementById("observerArtifactSelect");
      const artifact = observerArtifacts[Number(select.value) || 0];
      const button = document.getElementById("observerExportButton");
      const message = document.getElementById("observerExportMessage");
      if (!artifact) {
        message.textContent = "请先选择一个 MPH 模型。";
        return;
      }
      const originalText = button.textContent;
      button.disabled = true;
      button.textContent = "COMSOL 正在导出...";
      message.textContent = "正在打开模型并导出结果图；没有结果图时会导出几何图。";
      try {
        const response = await fetch("/api/comsol/export-preview", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({path: artifact.path})
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.message || data.error || "COMSOL 预览导出失败");
        }
        message.textContent = `${data.message || "预览导出完成"} 用时 ${Number(data.preview?.duration_seconds || 0).toFixed(1)} 秒。`;
        await refreshComsolObserver(true);
      } catch (error) {
        message.textContent = `导出失败：${error.message || error}`;
      } finally {
        button.textContent = originalText;
        button.disabled = false;
      }
    }

    async function exportSelectedComsol3d() {
      const select = document.getElementById("observerArtifactSelect");
      const artifact = observerArtifacts[Number(select.value) || 0];
      const button = document.getElementById("observer3dExportButton");
      const message = document.getElementById("observerExportMessage");
      if (!artifact) {
        message.textContent = "请先选择一个 MPH 模型。";
        return;
      }
      const originalText = button.textContent;
      button.disabled = true;
      button.textContent = "正在生成三维...";
      message.textContent = "COMSOL 正在读取最终几何并导出 STL，通常需要 10–30 秒。";
      try {
        const response = await fetch("/api/comsol/export-3d", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({path: artifact.path})
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.message || data.error || "COMSOL 三维导出失败");
        }
        observer3dState.url = "";
        observer3dState.triangles = [];
        message.textContent = `${data.message || "三维导出完成"} ${formatArtifactBytes(data.preview?.size_bytes)}，用时 ${Number(data.preview?.duration_seconds || 0).toFixed(1)} 秒。`;
        await refreshComsolObserver(true);
      } catch (error) {
        message.textContent = `三维导出失败：${error.message || error}`;
      } finally {
        button.textContent = originalText;
        button.disabled = false;
      }
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function addMessage(role, html) {
      const message = document.createElement("div");
      message.className = "message " + role;
      const avatar = role === "user" ? "你" : "AI";
      message.innerHTML = `<div class="avatar">${avatar}</div><div class="bubble">${html}</div>`;
      messages.appendChild(message);
      jumpToLatestMessage();
    }

    function startProgressCard(title, steps) {
      const message = document.createElement("div");
      message.className = "message assistant";
      const stepHtml = steps
        .map((step, index) => `<li data-step="${index}">${escapeHtml(step)}</li>`)
        .join("");
      message.innerHTML = `
        <div class="avatar">AI</div>
        <div class="bubble">
          <div class="progress-card">
            <div class="progress-head">
              <strong>${escapeHtml(title)}</strong>
              <span class="progress-percent">0%</span>
            </div>
            <div class="progress-bar"><div class="progress-fill"></div></div>
            <ol class="progress-steps">${stepHtml}</ol>
            <div class="status progress-detail">正在准备...</div>
          </div>
        </div>`;
      messages.appendChild(message);
      jumpToLatestMessage();
      return {
        message,
        steps,
        update(percent, activeIndex, detail) {
          const bounded = Math.max(0, Math.min(100, Number(percent) || 0));
          message.querySelector(".progress-fill").style.width = `${bounded}%`;
          message.querySelector(".progress-percent").textContent = `${Math.round(bounded)}%`;
          message.querySelector(".progress-detail").textContent = detail || "";
          message.querySelectorAll(".progress-steps li").forEach((item, index) => {
            item.classList.toggle("done", index < activeIndex);
            item.classList.toggle("active", index === activeIndex);
          });
          jumpToLatestMessage();
        },
        finish(detail) {
          this.update(100, steps.length, detail || "已完成");
        }
      };
    }

    function renderServerProgress(progress) {
      if (!Array.isArray(progress) || !progress.length) return "";
      const rows = progress
        .map(item => `<li><strong>${escapeHtml(item.percent || 0)}%</strong> ${escapeHtml(item.label || "")}<br><span>${escapeHtml(item.detail || "")}</span></li>`)
        .join("");
      return `<h3>加载进度</h3><ul>${rows}</ul>`;
    }

    function jumpToLatestMessage() {
      const latest = messages.lastElementChild;
      if (latest) {
        latest.scrollIntoView({behavior: "smooth", block: "end"});
      }
      requestAnimationFrame(() => {
        messages.scrollTop = messages.scrollHeight;
      });
    }

    function renderJson(data) {
      raw.textContent = JSON.stringify(data, null, 2);
    }

    function isLowValueWorkFeedback(feedback) {
      const endpoint = String(feedback.endpoint || "");
      const stagedEndpoints = new Set(["/api/staged-workflow", "/api/approve-staged-step", "/api/finalize-staged-workflow"]);
      if (stagedEndpoints.has(endpoint)) return true;
      if (endpoint === "/api/instruction") return true;
      const summary = String(feedback.summary || "").trim();
      const nextSteps = feedback.next_steps || [];
      const onlyGenericNext = nextSteps.length === 1 && String(nextSteps[0] || "").trim() === "继续执行下一步建模或训练任务。";
      return (!summary || summary === "操作已完成。") && onlyGenericNext;
    }

    function summarizeWorkFeedback(data) {
      const feedback = data.work_feedback;
      if (!feedback) return "";
      if (isLowValueWorkFeedback(feedback)) return "";
      const details = feedback.details || {};
      const next = (feedback.next_steps || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const detailLines = [];
      if (details.summary_kind) detailLines.push(`<li>摘要类型：<code>${escapeHtml(details.summary_kind)}</code></li>`);
      if (details.summary_name) detailLines.push(`<li>对象：<code>${escapeHtml(details.summary_name)}</code></li>`);
      if (details.output_path) detailLines.push(`<li>输出：<code>${escapeHtml(details.output_path)}</code></li>`);
      if (details.training_report) {
        detailLines.push(`<li>训练报告：<code>${escapeHtml(JSON.stringify(details.training_report))}</code></li>`);
      }
      return `<h3>本次工作反馈</h3><p>${escapeHtml(feedback.summary || "")}</p>${detailLines.length ? `<ul>${detailLines.join("")}</ul>` : ""}${next ? `<h3>建议下一步</h3><ul>${next}</ul>` : ""}`;
    }

    async function request(path, body) {
      setStatus("running", "");
      let data;
      try {
        const response = await fetch(path, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(body)
        });
        data = await response.json();
      } catch (error) {
        data = {ok: false, error: `无法连接本地服务：${error.message}`};
      }
      renderJson(data);
      setStatus(data.ok === false ? "failed" : "done", data.ok === false ? "bad" : "ok");
      if (data.ok === false && !path.startsWith("/api/assistant/")) rememberFailedTask(path, body, data);
      const workFeedback = summarizeWorkFeedback(data);
      if (workFeedback) addMessage("assistant", workFeedback);
      jumpToLatestMessage();
      return data;
    }

    async function requestGet(path) {
      setStatus("running", "");
      let data;
      try {
        const response = await fetch(path, {cache: "no-store"});
        data = await response.json();
      } catch (error) {
        data = {ok: false, error: `无法连接本地服务：${error.message}`};
      }
      renderJson(data);
      setStatus(data.ok === false ? "failed" : "done", data.ok === false ? "bad" : "ok");
      jumpToLatestMessage();
      return data;
    }

    function summarizeInstructionResponse(data) {
      if (!data.ok) {
        return `<h3>执行失败</h3><p>${escapeHtml(data.error || "未知错误")}</p>`;
      }
      const response = data.response || {};
      if (response.assistant_message) {
        const paragraphs = escapeHtml(response.assistant_message)
          .split(/\n\s*\n/)
          .map(part => `<p>${part.replace(/\n/g, "<br>")}</p>`)
          .join("");
        const sections = (response.explanation_sections || []).map(section => {
          const items = (section.items || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
          return `<h3>${escapeHtml(section.title || "说明")}</h3><ul>${items}</ul>`;
        }).join("");
        const policy = response.response_policy
          ? `<h3>回答规则</h3><ul><li>${escapeHtml(response.response_policy.general_rule || "")}</li><li>${escapeHtml(response.response_policy.theory_rule || "")}</li><li>${escapeHtml(response.response_policy.physics_rule || "")}</li></ul>`
          : "";
        const correctionMemory = response.correction_memory
          ? `<h3>纠错记忆</h3><ul><li>正确物理场：<code>${escapeHtml(response.correction_memory.corrected_physics || "")}</code></li><li>纠错记忆数量：${escapeHtml(response.correction_memory.correction_count || 0)}</li></ul>`
          : "";
        const clarification = (response.clarifying_questions || []).length
          ? `<h3>需要你补充</h3><ul>${response.clarifying_questions.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
          : "";
        const assumptions = (response.assumptions || []).length
          ? `<h3>当前假设</h3><ul>${response.assumptions.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
          : "";
        const risks = (response.risk_flags || []).length
          ? `<h3>风险提示</h3><ul>${response.risk_flags.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
          : "";
        const intents = (response.intent || []).map(item => `<code>${escapeHtml(item)}</code>`).join(" ");
        const tool = response.suggested_tool ? `<p>建议工具：<code>${escapeHtml(response.suggested_tool)}</code></p>` : "";
        return `<h3>COMSOL 训练讲解</h3>${paragraphs}${correctionMemory}${clarification}${assumptions}${risks}${policy}${sections}<h3>识别到的任务</h3><p>${intents}</p>${tool}`;
      }
      const intents = (response.intent || []).map(item => `<code>${escapeHtml(item)}</code>`).join(" ");
      const feedback = (response.feedback || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const next = (response.next_actions || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      return `<h3>我理解到的任务</h3><p>${intents || "<code>general</code>"}</p><ul>${feedback}</ul>${next ? `<h3>下一步</h3><ul>${next}</ul>` : ""}`;
    }

    function summarizeFileResponse(data) {
      if (!data.ok) {
        return `<h3>读取失败</h3><p>${escapeHtml(data.error || "未知错误")}</p>`;
      }
      const summary = data.summary;
      const details = summary.details || {};
      if (summary.kind === "file_collection") {
        const files = (summary.files || []).map(file =>
          `<li><code>${escapeHtml(file.name)}</code> - ${escapeHtml(file.kind)} (${file.size_bytes} bytes)</li>`
        ).join("");
        const kinds = Object.entries(details.kinds || {})
          .map(([kind, count]) => `<code>${escapeHtml(kind)}</code>: ${count}`)
          .join(" ");
        return `<h3>已读取多个文件</h3><p>数量：${details.count || 0}</p><p>${kinds}</p><ul>${files}</ul>${pdfSimpleSummariesFromFiles(summary.files || [])}`;
      }
      let lines = [
        `<li>文件：<code>${escapeHtml(summary.name)}</code></li>`,
        `<li>类型：<code>${escapeHtml(summary.kind)}</code></li>`,
        `<li>大小：${summary.size_bytes} bytes</li>`
      ];
      if (summary.kind === "matlab_livelink") {
        lines.push(`<li>参数数量：${details.parameters || 0}</li>`);
      }
      if (summary.kind === "csv_table") {
        lines.push(`<li>列：<code>${escapeHtml((details.columns || []).join(", "))}</code></li>`);
      }
      const pdfSummaries = summary.kind === "pdf_document" ? pdfSimpleSummariesFromFiles([summary]) : "";
      return `<h3>文件已读取</h3><ul>${lines.join("")}</ul>${pdfSummaries}<h3>预览</h3><p>${escapeHtml(summary.preview || "").slice(0, 1200)}</p>`;
    }

    function pdfSimpleSummariesFromFiles(files) {
      const rows = (files || [])
        .filter(file => file && file.kind === "pdf_document")
        .map(file => {
          const details = file.details || {};
          const summary = details.simple_summary || `${file.name || "PDF"}: 已识别为 PDF 文件，但当前没有提取到简单总结。`;
          return `<li><code>${escapeHtml(file.name || "")}</code><br>${escapeHtml(summary)}</li>`;
        })
        .join("");
      return rows ? `<h3>每个 PDF 文件的简单总结</h3><ul>${rows}</ul>` : "";
    }

    function summarizeGeneric(title, data) {
      if (!data.ok) {
        return `<h3>${title}失败</h3><p>${escapeHtml(data.error || "未知错误")}</p>`;
      }
      return `<h3>${title}完成</h3><p><code>${escapeHtml(JSON.stringify(data).slice(0, 700))}</code></p>`;
    }

    function summarizeComsolCodeResponse(data) {
      if (!data.ok) {
        return summarizeGeneric("COMSOL MATLAB + Java 生成", data);
      }
      const plan = data.plan || {};
      const outputs = data.outputs || {};
      const guidance = (data.theory_guidance || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const refinements = (data.refinement_suggestions || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const review = data.existing_content_review || {};
      const checks = review.checks || {};
      const reviewRows = Object.entries(checks)
        .map(([key, value]) => `<li>${escapeHtml(key)}：${value ? "已包含" : "缺失或未识别"}</li>`)
        .join("");
      const domains = (plan.inferred_domains || []).map(item => `<code>${escapeHtml(item)}</code>`).join(" ");
      const matches = (plan.matched_cases || [])
        .slice(0, 5)
        .map(item => `<li>${escapeHtml(item.title || "")}，score=${escapeHtml(item.score || 0)}</li>`)
        .join("");
      const limits = (plan.limitations || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      return `<h3>COMSOL MATLAB + Java 代码已生成</h3><ul><li>MATLAB：<code>${escapeHtml(outputs.matlab || "")}</code></li><li>Java：<code>${escapeHtml(outputs.java || "")}</code></li><li>理论指导报告：<code>${escapeHtml(outputs.guidance || "")}</code></li><li>推断物理域：${domains || "<code>unknown</code>"}</li></ul>${matches ? `<h3>引用的案例记忆</h3><ul>${matches}</ul>` : ""}${guidance ? `<h3>理论指导</h3><ul>${guidance}</ul>` : ""}${reviewRows ? `<h3>现有内容检查</h3><ul>${reviewRows}</ul>` : ""}${refinements ? `<h3>调整和完善建议</h3><ul>${refinements}</ul>` : ""}${limits ? `<h3>复核提醒</h3><ul>${limits}</ul>` : ""}<h3>学习过程/判断依据</h3><ul><li>先用需求检索案例记忆库，提取相似案例、参数、输出量和建模步骤。</li><li>再把推断出的物理场映射为 COMSOL LiveLink MATLAB 和 Java API 模板。</li><li>如果提供了现有脚本或模型摘要，会检查参数、几何、物理场、材料、网格、研究、结果和边界选择是否完整。</li><li>边界选择、材料属性和具体几何序列保留复核标注，便于后续用真实案例脚本修正。</li></ul>`;
    }

    function summarizeLearningResponse(data) {
      if (!data.ok) {
        return `<h3>学习总结失败</h3><p>${escapeHtml(data.error || "未知错误")}</p>`;
      }
      const summary = data.summary || {};
      const groups = summary.groups || {};
      const counts = Object.entries(groups)
        .map(([name, items]) => `<li><code>${escapeHtml(name)}</code>: ${Array.isArray(items) ? items.length : 0}</li>`)
        .join("");
      const recommendations = (summary.recommendations || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const workflow = (summary.workflow || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const pdfSummaries = pdfSimpleSummariesFromLearning(summary);
      const memory = data.memory || {};
      const memoryHtml = memory.path
        ? `<h3>记忆库写入</h3><ul><li>条目：${escapeHtml(memory.entry_title || "")}</li><li>案例总数：${escapeHtml(memory.case_count || 0)}</li><li>质量分：${escapeHtml((memory.quality || {}).score || 0)}/100</li><li>路径：<code>${escapeHtml(memory.path)}</code></li></ul>`
        : "";
      return `<h3>COMSOL 文件学习总结</h3><ul>${counts}</ul>${pdfSummaries}${memoryHtml}<h3>建议</h3><ul>${recommendations}</ul><h3>实现路径</h3><ul>${workflow}</ul>`;
    }

    function pdfSimpleSummariesFromLearning(summary) {
      const rows = (summary.pdf_simple_summaries || [])
        .map(item => `<li><code>${escapeHtml(item.name || "")}</code><br>${escapeHtml(item.summary || "")}</li>`)
        .join("");
      return rows ? `<h3>每个 PDF 文件的简单总结</h3><ul>${rows}</ul>` : "";
    }

    function summarizeCaseLearningResponse(data) {
      if (!data.ok) {
        return `<h3>案例学习失败</h3><p>${escapeHtml(data.error || "未知错误")}</p>`;
      }
      const card = data.card || {};
      const summary = data.summary || {};
      const fileSummary = card.file_summary || {};
      const caseContent = card.case_content || {};
      const contentTotals = caseContent.totals || {};
      const logic = (summary.learned_modeling_logic || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const trace = (summary.learning_trace || []).map(item => `<li><strong>${escapeHtml(item.step || "")}</strong><br><span>证据：${escapeHtml(item.evidence || "")}</span><br><span>判断：${escapeHtml(item.judgement || "")}</span></li>`).join("");
      const assets = (summary.reusable_assets || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const next = (summary.next_actions || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const params = (card.parameters || [])
        .slice(0, 20)
        .map(item => `<li><code>${escapeHtml(item.name)}</code> = <code>${escapeHtml(item.value || "")}</code> ${escapeHtml(item.description || "")}</li>`)
        .join("");
      const outputs = data.outputs || {};
      const memory = data.memory || {};
      const contentSections = ["geometry", "physics", "materials", "mesh", "studies", "results", "boundary_conditions"]
        .map(key => {
          const values = (caseContent[key] || []).slice(0, 10).map(item => `<code>${escapeHtml(item)}</code>`).join(" ");
          return values ? `<li>${escapeHtml(key)}：${values}</li>` : "";
        })
        .join("");
      const theoryKeywords = (caseContent.theory_keywords || []).map(item => `<code>${escapeHtml(item)}</code>`).join(" ");
      const sourceEvidence = (caseContent.source_extracts || [])
        .slice(0, 6)
        .map(item => `<li><code>${escapeHtml(item.name || "")}</code>：内容证据 ${escapeHtml(item.evidence_score || 0)} 条</li>`)
        .join("");
      const contentHtml = contentTotals.model_tree_items || contentSections || theoryKeywords
        ? `<h3>读取到的案例内容</h3><ul><li>模型树证据：${escapeHtml(contentTotals.model_tree_items || 0)} 条</li><li>已检查内容文件：${escapeHtml(contentTotals.source_files_checked || 0)} 个</li>${theoryKeywords ? `<li>理论关键词：${theoryKeywords}</li>` : ""}${contentSections}</ul>${sourceEvidence ? `<h3>文件内容证据</h3><ul>${sourceEvidence}</ul>` : ""}`
        : "";
      const alignment = card.knowledge_alignment || {};
      const externalCases = (alignment.case_matches || []).slice(0, 5).map(item => `<li><code>${escapeHtml(item.title || "")}</code> score=${escapeHtml(item.score || "")} 字段：${escapeHtml((item.supported_fields || []).join(", ") || "仅主题匹配")}</li>`).join("");
      const docMatches = (alignment.docs_matches || []).slice(0, 5).map(item => `<li><code>${escapeHtml(item.document || "")}</code> 第 ${escapeHtml(item.page || "")} 页，模块：${escapeHtml(item.module || "")}</li>`).join("");
      const improvements = (alignment.training_improvements || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const alignmentHtml = externalCases || docMatches || improvements
        ? `<h3>总知识库对齐</h3>${externalCases ? `<h3>相似 COMSOL 案例</h3><ul>${externalCases}</ul>` : ""}${docMatches ? `<h3>官方文档校对</h3><ul>${docMatches}</ul>` : ""}${improvements ? `<h3>训练完善建议</h3><ul>${improvements}</ul>` : ""}`
        : "";
      const pdfSummaries = pdfSimpleSummariesFromLearning(card);
      return `<h3>案例学习完成</h3><p>${escapeHtml(summary.summary || "")}</p><ul><li>训练阶段：<code>${escapeHtml(card.training_stage || "")}</code></li><li>文件数：${escapeHtml(fileSummary.count || 0)}</li><li>MATLAB：${escapeHtml(fileSummary.matlab_files || 0)}，Java：${escapeHtml(fileSummary.java_files || 0)}，PDF：${escapeHtml(fileSummary.pdf_files || 0)}，MPH：${escapeHtml(fileSummary.mph_files || 0)}，CSV：${escapeHtml(fileSummary.csv_files || 0)}</li><li>记忆库案例数：${escapeHtml(memory.case_count || 0)}</li></ul>${contentHtml}${pdfSummaries}${trace ? `<h3>学习过程/判断依据</h3><ul>${trace}</ul>` : ""}${alignmentHtml}${logic ? `<h3>学到的建模逻辑</h3><ul>${logic}</ul>` : ""}${params ? `<h3>提取参数</h3><ul>${params}</ul>` : ""}${assets ? `<h3>可复用资产</h3><ul>${assets}</ul>` : ""}${next ? `<h3>下一步</h3><ul>${next}</ul>` : ""}<h3>输出文件</h3><ul><li>JSON：<code>${escapeHtml(outputs.json || "")}</code></li><li>Markdown：<code>${escapeHtml(outputs.markdown || "")}</code></li><li>Index：<code>${escapeHtml(outputs.index || "")}</code></li></ul>`;
    }

    function summarizeArticleLearningResponse(data) {
      if (!data.ok) {
        return `<h3>文章学习失败</h3><p>${escapeHtml(data.error || "未知错误")}</p>`;
      }
      const card = data.card || {};
      const plan = card.memory_assisted_model_plan || {};
      const params = (card.parameters || []).map(item => `<li><code>${escapeHtml(item.name)}</code> = <code>${escapeHtml(item.value || "")}</code> ${escapeHtml(item.role || "")}</li>`).join("");
      const corrections = (card.correction_strategy || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const matches = (plan.matched_cases || []).slice(0, 6).map(item => `<li><code>${escapeHtml(item.title || "")}</code> score=${escapeHtml(item.score || "")}</li>`).join("");
      const steps = (plan.recommended_modeling_steps || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const outputs = (plan.validation_outputs || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const files = data.outputs || {};
      return `<h3>文章驱动建模方案已生成</h3><p>${escapeHtml(card.summary || "")}</p><h3>文章参数</h3><ul>${params}</ul><h3>文章修正要求</h3><ul>${corrections}</ul>${matches ? `<h3>记忆库匹配案例</h3><ul>${matches}</ul>` : ""}<h3>COMSOL 建模步骤</h3><ul>${steps}</ul><h3>验证输出</h3><ul>${outputs}</ul><h3>输出文件</h3><ul><li>JSON：<code>${escapeHtml(files.json || "")}</code></li><li>Markdown：<code>${escapeHtml(files.markdown || "")}</code></li></ul>`;
    }

    function summarizePlanResponse(data) {
      if (!data.ok) {
        return `<h3>建模方案生成失败</h3><p>${escapeHtml(data.error || "未知错误")}</p>`;
      }
      const plan = data.plan || {};
      const domains = (plan.inferred_domains || []).map(item => `<code>${escapeHtml(item)}</code>`).join(" ");
      const cases = (plan.matched_cases || [])
        .map(item => `<li><code>${escapeHtml(item.title)}</code> score=${escapeHtml(item.score)}</li>`)
        .join("");
      const steps = (plan.recommended_modeling_steps || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const params = (plan.candidate_parameters || [])
        .slice(0, 12)
        .map(item => `<li><code>${escapeHtml(item.name)}</code> ${escapeHtml(item.value || "")}</li>`)
        .join("");
      const outputs = (plan.candidate_outputs || []).map(item => `<code>${escapeHtml(item)}</code>`).join(" ");
      const limitations = (plan.limitations || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const externalCases = (plan.external_case_matches || []).slice(0, 5).map(item => `<li><code>${escapeHtml(item.title || "")}</code> score=${escapeHtml(item.score || "")}</li>`).join("");
      const docMatches = (plan.official_doc_matches || []).slice(0, 5).map(item => `<li><code>${escapeHtml(item.document || "")}</code> 第 ${escapeHtml(item.page || "")} 页</li>`).join("");
      return `<h3>COMSOL 建模方案</h3><p>${domains || "<code>general_multiphysics</code>"}</p>${cases ? `<h3>本地记忆匹配案例</h3><ul>${cases}</ul>` : ""}${externalCases ? `<h3>总案例库参考</h3><ul>${externalCases}</ul>` : ""}${docMatches ? `<h3>官方文档参考</h3><ul>${docMatches}</ul>` : ""}<h3>建模步骤</h3><ul>${steps}</ul>${params ? `<h3>候选参数</h3><ul>${params}</ul>` : ""}<h3>建议输出</h3><p>${outputs}</p><h3>限制</h3><ul>${limitations}</ul>`;
    }

    async function loadDefaults() {
      const response = await fetch("/api/default-constraints");
      const data = await response.json();
      constraints.value = JSON.stringify(data, null, 2);
      renderJson(data);
      setStatus("loaded", "ok");
      addMessage("assistant", "<h3>已载入示例约束</h3><p>你可以在右侧修改参数范围、边界条件和输出表达式，然后让我校验或生成 MATLAB 脚本。</p>");
    }

    async function sendPrompt() {
      const prompt = document.getElementById("prompt");
      const text = prompt.value.trim();
      if (!text) return;
      addMessage("user", escapeHtml(text));
      prompt.value = "";
      if (hasActiveStagedWorkflow()) {
        if (isRevisionMessage(text)) {
          await approveStagedStep(false, text);
          return;
        }
        if (isApprovalMessage(text)) {
          await approveStagedStep(true, text);
          return;
        }
      }
      if (looksLikeStagedModelingTask(text)) {
        await createStagedWorkflow(text);
        return;
      }
      if (assistantConfig?.mode === "api") {
        const data = await request("/api/assistant/complete", {
          task: text,
          context: lastFileSummary ? {file_summary: redactForRemote(lastFileSummary)} : {source: "当前对话"}
        });
        if (data.ok) addMessage("assistant", summarizeRemoteAssistant(data, "API 助手回复"));
        else addMessage("assistant", `<h3>API 请求失败</h3><p>${escapeHtml(data.error || "未知错误")}</p><p>你可以切回离线模式继续使用本地功能，或检查 AI 接入设置。</p>`);
        return;
      }
      const data = await request("/api/instruction", {instruction: text, file_summary: lastFileSummary});
      addMessage("assistant", summarizeInstructionResponse(data));
    }

    async function planModelFromPrompt() {
      const prompt = document.getElementById("prompt");
      const text = prompt.value.trim() || "根据已经学习的案例构建 COMSOL 模型，并给出建模、理论、约束和分析路径。";
      addMessage("user", escapeHtml(text));
      prompt.value = "";
      const data = await request("/api/plan-model", {requirement: text});
      addMessage("assistant", summarizePlanResponse(data));
      return data;
    }

    function useTemplate(text) {
      document.getElementById("prompt").value = text;
      document.getElementById("prompt").focus();
    }

    function selectThreadMode(mode) {
      document.querySelectorAll(".thread").forEach(button => {
        button.classList.toggle("active", button.dataset.mode === mode);
      });
      const config = {
        chat: {
          target: null,
          prompt: "请作为 COMSOL 训练助手，解释当前任务应该如何拆分为案例学习、建模、约束和训练步骤。",
          message: "<h3>当前会话</h3><p>这里用于连续对话。我会保留已读文件上下文，并把后续问题理解为 COMSOL 案例学习、自动建模或代理模型训练任务。</p>"
        },
        modeling: {
          target: "tool-constraints",
          prompt: "根据当前约束和已学习案例，生成 COMSOL 自动建模方案，并说明参数、几何、材料、物理场、网格、研究和结果导出顺序。",
          message: "<h3>自动建模</h3><p>这个模式会优先使用右侧约束 JSON、本地案例记忆和 LiveLink MATLAB 生成能力。适合让模型给出建模方案或生成 MATLAB 建模脚本。</p>"
        },
        reading: {
          target: "tool-files",
          prompt: "请读取右侧多个文件，并总结它们对 COMSOL 建模理论、参数约束、案例学习和后续训练的作用。",
          message: "<h3>文件阅读</h3><p>这个模式对应右侧文件工具。可以一次读取 MATLAB、Java、PDF、MPH、CSV、JSON 等文件，并生成学习总结。</p>"
        },
        training: {
          target: "tool-training",
          prompt: "根据 CSV 数据训练 COMSOL 代理模型，对比候选模型，输出 RMSE、MAE、R2、样本预测和后续改进建议。",
          message: "<h3>代理模型训练</h3><p>这个模式对应右侧训练工具。需要 CSV 参数扫描数据；没有 CSV 时，应先从案例学习和 COMSOL 参数扫描开始。</p>"
        },
        execution: {
          target: "tool-execution",
          prompt: "创建并处理母线板焦耳热标杆任务，先生成 MATLAB/Java 建模文件和执行包装脚本，再检查本机 COMSOL 执行节点配置。",
          message: "<h3>任务中心</h3><p>这里管理可迁移的 COMSOL 任务。当前电脑作为执行节点；未来只需把执行节点迁到 Windows 服务器，网页和任务记录可以保留。</p>"
        }
      }[mode];
      if (!config) return;
      useTemplate(config.prompt);
      if (config.target) {
        document.getElementById(config.target)?.scrollIntoView({behavior: "smooth", block: "start"});
      }
      addMessage("assistant", config.message);
    }

    function summarizeExecutionJob(data) {
      if (!data.ok) return summarizeGeneric("执行任务", data);
      const job = data.job;
      if (!job) return "<h3>任务中心</h3><p>当前没有可处理的排队任务。</p>";
      const result = job.result || {};
      const outputs = ((result.generated_code || {}).outputs || {});
      const readiness = result.execution_readiness || {};
      const artifact = result.model_artifact || {};
      const resultCsv = result.result_artifact || {};
      const validation = result.result_validation || {};
      const trainingDataset = result.training_dataset || {};
      const mergedTrainingDataset = result.merged_training_dataset || {};
      const trainingModel = result.training_model || {};
      const trainingReport = result.training_report || {};
      const augmentationDataset = result.augmentation_dataset || {};
      const holdoutDataset = result.holdout_dataset || {};
      const holdoutValidation = trainingReport.holdout_validation || {};
      const modelCard = result.model_card || {};
      const diagnosis = result.diagnosis || {};
      const validationChecks = (validation.checks || []).map(check => `${check.name}: ${check.passed ? "通过" : "未通过"}`).join("；");
      const diagnosisActions = (diagnosis.actions || []).map(action => `<li>${escapeHtml(action)}</li>`).join("");
      const defaultStatusAdvice = {
        queued: "任务已进入队列，等待执行节点处理。",
        awaiting_model_review: "请核对命名选择集、边界条件和单位；确认后可批准执行复核。",
        awaiting_execution_approval: "模型复核已通过，当前执行节点尚未允许外部 MATLAB/COMSOL 调用。",
        awaiting_execution_configuration: "执行文件已准备，但执行节点配置尚未完成。",
        completed: "MATLAB LiveLink 与 COMSOL 执行已完成，请查看 MPH 输出和日志。",
        failed: "执行失败，请先查看任务日志和错误信息。"
      }[job.status] || "正在处理任务。";
      const statusAdvice = job.job_type === "thermal_sweep_training" && job.status === "completed"
        ? "COMSOL 参数扫描、CSV 检查和本地代理模型训练已完成，可查看训练数据、模型文件与误差指标。"
        : defaultStatusAdvice;
      const reviewAction = job.status === "awaiting_model_review"
        ? `<p><button class="primary" onclick='approveExecutionReview(${JSON.stringify(job.id || "")})'>批准执行复核并继续</button></p>`
        : "";
      const retryAction = job.status === "failed" && diagnosis.retry_recommended
        ? `<p><button class="primary" onclick='retryExecutionJob(${JSON.stringify(job.id || "")})'>重新排队</button></p>`
        : "";
      const augmentationRetrainAction = job.job_type === "thermal_augmentation" && job.status === "completed" && augmentationDataset.path
        ? `<p><button class="primary" onclick='queueThermalAugmentationRetrain(${JSON.stringify(job.id || "")})'>合并样本并进行独立验证重训</button></p>`
        : "";
      const diagnosisHtml = diagnosis.kind
        ? `<h3>${escapeHtml(diagnosis.title || "失败诊断")}</h3><p>${escapeHtml(diagnosis.summary || "")}</p>${diagnosisActions ? `<ul>${diagnosisActions}</ul>` : ""}`
        : "";
      return `<h3>COMSOL 执行任务</h3><p>${escapeHtml(statusAdvice)}</p><ul><li>编号：<code>${escapeHtml(job.id || "")}</code></li><li>状态：<code>${escapeHtml(job.status || "")}</code></li><li>类型：${escapeHtml(job.job_type || "")}</li><li>日志：<code>${escapeHtml(job.log_path || "")}</code></li>${artifact.path ? `<li>MPH：<code>${escapeHtml(artifact.path)}</code></li>` : ""}${artifact.size_bytes ? `<li>模型大小：<code>${escapeHtml(String(artifact.size_bytes))} bytes</code></li>` : ""}${artifact.execution_duration_seconds ? `<li>执行耗时：<code>${escapeHtml(String(artifact.execution_duration_seconds))} s</code></li>` : ""}${resultCsv.path ? `<li>结果 CSV：<code>${escapeHtml(resultCsv.path)}</code></li>` : ""}${resultCsv.size_bytes ? `<li>CSV 大小：<code>${escapeHtml(String(resultCsv.size_bytes))} bytes</code></li>` : ""}${augmentationDataset.path ? `<li>补充 COMSOL 样本：<code>${escapeHtml(augmentationDataset.path)}</code>，${escapeHtml(String(augmentationDataset.sample_count || 0))} 组</li>` : ""}${mergedTrainingDataset.path ? `<li>合并训练数据：<code>${escapeHtml(mergedTrainingDataset.path)}</code>，${escapeHtml(String(mergedTrainingDataset.rows || 0))} 组</li>` : ""}${trainingDataset.path ? `<li>训练数据：<code>${escapeHtml(trainingDataset.path)}</code>，${escapeHtml(String(trainingDataset.sample_count || 0))} 组</li>` : ""}${holdoutDataset.path ? `<li>独立 COMSOL 验证：<code>${escapeHtml(holdoutDataset.path)}</code>，${escapeHtml(String(holdoutDataset.sample_count || holdoutDataset.rows || 0))} 组</li>` : ""}${trainingModel.path ? `<li>代理模型：<code>${escapeHtml(trainingModel.path)}</code></li>` : ""}${modelCard.markdown_path ? `<li>模型卡片：<code>${escapeHtml(modelCard.markdown_path)}</code></li>` : ""}${trainingReport.best_model ? `<li>训练结果：<code>${escapeHtml(trainingReport.best_model)}</code>，RMSE=<code>${escapeHtml(String(trainingReport.test_rmse))}</code></li>` : ""}${holdoutValidation.max_absolute_error ? `<li>独立验证：<code>${holdoutValidation.passed ? "通过" : "未通过"}</code>，最大绝对误差=<code>${escapeHtml(JSON.stringify(holdoutValidation.max_absolute_error))}</code></li>` : ""}${validation.kind ? `<li>物理校验：<code>${validation.passed ? "通过" : "未通过"}</code>${validationChecks ? `，${escapeHtml(validationChecks)}` : ""}</li>` : ""}${artifact.next_action ? `<li>建议：${escapeHtml(artifact.next_action)}</li>` : ""}${result.next_action ? `<li>下一动作：${escapeHtml(result.next_action)}</li>` : ""}${result.approved_package_path ? `<li>批准建模包：<code>${escapeHtml(result.approved_package_path)}</code></li>` : ""}${readiness.next_action ? `<li>任务动作：<code>${escapeHtml(readiness.next_action)}</code></li>` : ""}${outputs.matlab ? `<li>MATLAB：<code>${escapeHtml(outputs.matlab)}</code></li>` : ""}${outputs.java ? `<li>Java：<code>${escapeHtml(outputs.java)}</code></li>` : ""}${result.runner_path ? `<li>执行包装：<code>${escapeHtml(result.runner_path)}</code></li>` : ""}</ul>${diagnosisHtml}${augmentationRetrainAction}${reviewAction}${retryAction}${job.error ? `<h3>原始错误</h3><pre>${escapeHtml(job.error)}</pre>` : ""}`;
    }

    async function createJouleHeatBenchmark() {
      const data = await request("/api/jobs/joule-heat-benchmark", {});
      addMessage("assistant", summarizeExecutionJob(data));
      return data;
    }

    async function createExecutionJob() {
      const requirement = document.getElementById("executionRequirement").value.trim();
      const data = await request("/api/jobs", {requirement});
      addMessage("assistant", summarizeExecutionJob(data));
      return data;
    }

    async function matchValidatedTemplate() {
      const requirement = document.getElementById("executionRequirement").value.trim();
      const data = await request("/api/jobs/match-template", {requirement});
      if (data.ok && data.template_match) {
        const match = data.template_match;
        addMessage("assistant", `<h3>已验证模板匹配</h3><p>${escapeHtml(match.reason || "")}</p><ul><li>模板：<code>${escapeHtml(match.template_name || "")}</code></li><li>置信度：<code>${escapeHtml(String(match.confidence || ""))}</code></li><li>仍需确认：${escapeHtml((match.required_information || []).join("、"))}</li></ul>`);
      }
      addMessage("assistant", summarizeExecutionJob(data));
      return data;
    }

    async function deriveAndQueueMatchedTemplate() {
      const requirement = document.getElementById("executionRequirement").value.trim();
      const data = await request("/api/templates/match-extract-derive-and-queue", {requirement});
      if (data.ok) {
        const normalized = (data.provenance || []).map(item =>
          `<li><code>${escapeHtml(item.parameter)}</code>：${escapeHtml(String(item.source_value))} ${escapeHtml(item.source_unit || "")} -> ${escapeHtml(String(item.normalized_value))} ${escapeHtml(item.normalized_unit || "")}</li>`
        ).join("");
        addMessage("assistant", `<h3>参数已提取并入队</h3><p>${escapeHtml(data.template_match?.template_name || "已验证模板")}</p><ul>${normalized || "<li>未提取到参数</li>"}</ul>`);
      }
      addMessage("assistant", summarizeExecutionJob(data));
      return data;
    }

    async function processNextExecutionJob() {
      const data = await request("/api/jobs/process-next", {});
      addMessage("assistant", summarizeExecutionJob(data));
      return data;
    }

    async function refreshExecutionJobs() {
      const response = await fetch("/api/jobs");
      const data = await response.json();
      renderJson(data);
      const jobs = (data.jobs || []).slice(0, 8).map(job => `<li><code>${escapeHtml(job.id || "")}</code>：<code>${escapeHtml(job.status || "")}</code></li>`).join("");
      addMessage("assistant", `<h3>任务队列</h3><ul>${jobs || "<li>暂无任务</li>"}</ul>`);
      return data;
    }

    async function showRecentArtifacts() {
      const response = await fetch("/api/artifacts/recent?limit=8");
      const data = await response.json();
      renderJson(data);
      if (!data.ok) {
        addMessage("assistant", summarizeGeneric("最近结果", data));
        return data;
      }
      const summary = data.summary || {};
      const rows = (summary.recent || []).map(item => {
        const values = Object.entries(item.result_values || {})
          .map(([name, value]) => `<code>${escapeHtml(name)}=${escapeHtml(String(value))}</code>`)
          .join(" ");
        return `<li><strong>${escapeHtml(item.physics || "COMSOL")}</strong>：${values || "<code>无数值输出</code>"}<br><code>${escapeHtml(item.mph_path || "")}</code></li>`;
      }).join("");
      addMessage("assistant", `<h3>最近模型结果</h3><p>完成 ${escapeHtml(String(summary.completed_count || 0))} 项，失败 ${escapeHtml(String(summary.failed_count || 0))} 项。</p><ul>${rows || "<li>暂无已验证结果</li>"}</ul>`);
      return data;
    }

    function clearChat() {
      messages.innerHTML = "";
      addWelcome();
    }

    function addWelcome() {
      addMessage("assistant", "<h3>你好，我是 COMSOL 智能建模助手。</h3><p>你可以像和 Codex 对话一样描述任务。我会围绕 COMSOL 案例学习、理论总结、约束整理、LiveLink MATLAB 建模和代理模型训练给出解释、判断依据和下一步操作。</p><p>自动建模与步骤确认会优先进入本地可审计流程；普通问答使用当前选择的助手。本地任务失败后，你可以把脱敏后的失败摘要交给 Codex 或 DeepSeek 补充。</p><p>如果你先读取多个案例文件，我会把当前文件上下文带入后续对话；如果本地案例记忆里有相似案例，我也会主动引用。</p>");
    }

    function initializeCaseFieldSync() {
      syncCaseTitleFromCaseDir();
      refreshStagedWorkflows(false).then(() => {
        if (activeWorkflowPath()) resumeSelectedStagedWorkflow();
      });
    }

    async function inspectMatlab() {
      const data = await request("/api/inspect-matlab", {path: document.getElementById("matlabPath").value});
      addMessage("assistant", summarizeGeneric("MATLAB 解析", data));
      return data;
    }

    function summarizeCodeReadResponse(data) {
      if (!data.ok) return summarizeGeneric("代码读取", data);
      const code = data.code || {};
      const analysis = code.analysis || {};
      const features = analysis.comsol_features || {};
      const featureRows = Object.entries(features)
        .map(([key, values]) => `<li>${escapeHtml(key)}：${escapeHtml((values || []).length)} 项</li>`)
        .join("");
      const suggestions = (analysis.suggestions || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      return `<h3>代码已读取</h3><ul><li>路径：<code>${escapeHtml(code.path || "")}</code></li><li>类型：<code>${escapeHtml(code.kind || "")}</code></li><li>行数：${escapeHtml(code.line_count || 0)}</li><li>COMSOL API：<code>${analysis.has_comsol_api ? "yes" : "no"}</code></li></ul>${featureRows ? `<h3>COMSOL 代码线索</h3><ul>${featureRows}</ul>` : ""}${suggestions ? `<h3>修改建议</h3><ul>${suggestions}</ul>` : ""}<h3>代码预览</h3><pre>${escapeHtml(code.preview || "").slice(0, 4000)}</pre>`;
    }

    function summarizeCodeEditResponse(data) {
      if (!data.ok) return summarizeGeneric("代码修改", data);
      const edit = data.edit || {};
      const summary = (edit.summary || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const after = edit.analysis_after || {};
      return `<h3>代码修改完成</h3><ul><li>源文件：<code>${escapeHtml(edit.source_path || "")}</code></li><li>输出文件：<code>${escapeHtml(edit.output_path || "")}</code></li><li>备份文件：<code>${escapeHtml(edit.backup_path || "")}</code></li><li>修改模式：<code>${escapeHtml(edit.mode || "")}</code></li><li>替换次数：${escapeHtml(edit.replacements || 0)}</li><li>COMSOL API：<code>${after.has_comsol_api ? "yes" : "no"}</code></li></ul>${summary ? `<h3>修改摘要</h3><ul>${summary}</ul>` : ""}<h3>输出预览</h3><pre>${escapeHtml(edit.preview || "").slice(0, 4000)}</pre>`;
    }

    async function readCodeFile() {
      const data = await request("/api/read-code", {
        path: document.getElementById("codeFilePath").value
      });
      addMessage("assistant", summarizeCodeReadResponse(data));
      return data;
    }

    async function modifyCodeFile() {
      const findText = document.getElementById("findText").value;
      const replaceText = document.getElementById("replaceText").value;
      const data = await request("/api/modify-code", {
        path: document.getElementById("codeFilePath").value,
        instruction: document.getElementById("codeInstruction").value,
        find_text: findText,
        replace_text: findText ? replaceText : "",
        append_text: findText ? "" : replaceText,
        output_path: document.getElementById("codeOutputPath").value
      });
      addMessage("assistant", summarizeCodeEditResponse(data));
      return data;
    }

    function currentWorkflowStep(workflow) {
      const steps = workflow.steps || [];
      const index = Number(workflow.current_step || 0);
      return steps[index] || steps[steps.length - 1] || {};
    }

    function workflowHasProblemStatus(workflow) {
      const problemStatuses = new Set(["needs_revision", "failed", "error", "build_failed", "mesh_failed", "solve_failed", "validation_failed"]);
      const status = String(workflow.status || "");
      if (problemStatuses.has(status)) return true;
      return (workflow.steps || []).some(item => problemStatuses.has(String(item.status || "")));
    }

    function shouldShowStagedStatuses(workflow) {
      return workflowHasProblemStatus(workflow);
    }

    function shouldShowStagedProposal(workflow, step) {
      return workflowHasProblemStatus(workflow) || String(step.status || "") === "needs_revision";
    }

    function stagedWorkflowLead(workflow, step) {
      if (workflowHasProblemStatus(workflow)) {
        return `这一步需要修正。我先指出问题和依据，修正后再继续。`;
      }
      if (String(workflow.status || "") === "approved_for_generation") {
        return "建模决策和静态审计阶段已确认，正在生成 COMSOL 建模包。";
      }
      if (String(workflow.status || "") === "generated") {
        return "建模包已经生成，下一阶段是 COMSOL 构建、网格、求解和物理验证。";
      }
      if (String(workflow.status || "") === "completed") {
        return "COMSOL 执行和物理验证证据已经齐全，任务已完成。";
      }
      return `我先处理“${escapeHtml(step.title || "当前步骤")}”。你确认正确后，我再继续下一步。`;
    }

    function summarizeStagedWorkflowResponse(data) {
      if (!data.ok) return summarizeGeneric("分步建模任务", data);
      const workflow = data.workflow || {};
      const step = currentWorkflowStep(workflow);
      const outputs = workflow.outputs || {};
      if (outputs.workflow) {
        syncStagedWorkflowPath(outputs.workflow);
      }
      const proposal = (step.proposal || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const evidence = (step.evidence || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const questions = (step.approval_questions || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const statuses = (workflow.steps || []).map(item => `<li>${escapeHtml(item.index + 1)}. ${escapeHtml(item.title)}：<code>${escapeHtml(item.status)}</code></li>`).join("");
      const statusHtml = shouldShowStagedStatuses(workflow) && statuses ? `<h3>步骤状态</h3><ul>${statuses}</ul>` : "";
      const proposalHtml = shouldShowStagedProposal(workflow, step) && proposal ? `<h3>当前步骤建议</h3><ul>${proposal}</ul>` : "";
      const judgmentHtml = !shouldShowStagedProposal(workflow, step) && proposal ? `<h3>我的判断</h3><ul>${proposal}</ul>` : "";
      const diagnosticMeta = workflowHasProblemStatus(workflow) ? `<ul><li>状态：<code>${escapeHtml(workflow.status || "")}</code></li><li>任务文件：<code>${escapeHtml(outputs.workflow || "")}</code></li></ul>` : "";
      return `<h3>${escapeHtml(step.title || "分步建模")}</h3><p>${stagedWorkflowLead(workflow, step)}</p>${diagnosticMeta}${statusHtml}${proposalHtml}${judgmentHtml}${evidence ? `<h3>判断依据</h3><ul>${evidence}</ul>` : ""}${questions ? `<h3>请你确认</h3><ul>${questions}</ul>` : ""}`;
    }

    function summarizeFinalPackageResponse(data) {
      if (!data.ok) return summarizeGeneric("完整建模包", data);
      const outputs = data.outputs || {};
      const pkg = data.package || {};
      const readiness = ((pkg.generated_code || {}).generation_readiness || {});
      const handoff = pkg.execution_handoff || {};
      const material = pkg.material_readiness || {};
      const overall = pkg.modeling_readiness || {};
      const sequence = (pkg.modeling_sequence || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const checks = (pkg.verification_checklist || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const unresolved = (handoff.unresolved_requirements || readiness.unresolved_requirements || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const queueAction = outputs.json && handoff.ready_to_solve
        ? `<p><button class="primary" onclick='queueStagedPackageExecution(${JSON.stringify(outputs.json)})'>加入执行队列</button></p>`
        : "";
      const materialRisks = (material.risks || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const materialNotice = materialRisks ? `<h3>材料物性仍需确认</h3><ul>${materialRisks}</ul>` : "";
      const overallBlockers = (overall.blockers || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const overallNotice = overallBlockers ? `<h3>整体建模就绪检查</h3><p>可进入完整建模：<code>${escapeHtml(overall.ready_for_modeling || false)}</code></p><ul>${overallBlockers}</ul>` : "";
      const handoffNotice = !handoff.ready_to_solve && handoff.next_action ? `<p>下一步：<code>${escapeHtml(handoff.next_action)}</code></p>` : "";
      return `<h3>完整 COMSOL 建模包已生成</h3><ul><li>MATLAB：<code>${escapeHtml(outputs.matlab || "")}</code></li><li>Java：<code>${escapeHtml(outputs.java || "")}</code></li><li>验证报告：<code>${escapeHtml(outputs.verification || "")}</code></li><li>JSON：<code>${escapeHtml(outputs.json || "")}</code></li><li>Markdown：<code>${escapeHtml(outputs.markdown || "")}</code></li><li>可打开：<code>${escapeHtml(handoff.ready_to_open || readiness.ready_to_open || false)}</code></li><li>可直接求解：<code>${escapeHtml(handoff.ready_to_solve || false)}</code></li></ul>${handoffNotice}${overallNotice}${materialNotice}${queueAction}${unresolved ? `<h3>求解前必须完成</h3><ul>${unresolved}</ul>` : ""}${sequence ? `<h3>最终建模顺序</h3><ul>${sequence}</ul>` : ""}${checks ? `<h3>求解前复核清单</h3><ul>${checks}</ul>` : ""}`;
    }

    function looksLikeStagedModelingTask(text) {
      const value = String(text || "").toLowerCase();
      const hasComsol = value.includes("comsol") || value.includes("建模") || value.includes("模型");
      const hasModeling = value.includes("物理场") || value.includes("材料") || value.includes("求解") || value.includes("网格") || value.includes("边界") || value.includes("study") || value.includes("solver") || value.includes("physics");
      const asksBuild = value.includes("建立") || value.includes("构建") || value.includes("生成") || value.includes("完成") || value.includes("build") || value.includes("create") || value.includes("model");
      return hasComsol && (hasModeling || asksBuild);
    }

    function isApprovalMessage(text) {
      return /(批准|同意|正确|可以|继续|下一步|进行下一步|继续工作|通过|确认|不需要|无需|不用|没问题|没有问题|approve|yes|ok|continue)/i.test(String(text || ""));
    }

    function isRevisionMessage(text) {
      return /(退回|不正确|错误|修改|重做|不通过|需要改|不是|不对|revise|wrong|no)/i.test(String(text || ""));
    }

    async function createStagedWorkflow(requirementText) {
      const requirement = requirementText || document.getElementById("codeRequirement").value || document.getElementById("prompt").value;
      const data = await request("/api/staged-workflow", {requirement});
      if (data.ok) {
        syncStagedWorkflowPath((data.workflow || {}).outputs?.workflow || "");
        renderStagedWorkflowDashboard(data.workflow || {});
        await refreshStagedWorkflows(false);
      }
      addMessage("assistant", summarizeStagedWorkflowResponse(data));
      return data;
    }

    async function approveStagedStep(approved, commentText) {
      syncStagedWorkflowPath(activeWorkflowPath());
      const data = await request("/api/approve-staged-step", {
        workflow_path: activeWorkflowPath(),
        approved,
        comment: commentText || ""
      });
      addMessage("assistant", summarizeStagedWorkflowResponse(data));
      const workflow = data.workflow || {};
      if (data.ok) renderStagedWorkflowDashboard(workflow);
      if (data.ok && workflow.status === "approved_for_generation") {
        await finalizeStagedWorkflow();
      }
      return data;
    }

    async function finalizeStagedWorkflow() {
      const data = await request("/api/finalize-staged-workflow", {
        workflow_path: activeWorkflowPath()
      });
      if (data.ok) {
        const refreshed = await requestGet(`/api/staged-workflow?path=${encodeURIComponent(activeWorkflowPath())}`);
        if (refreshed.ok) renderStagedWorkflowDashboard(refreshed.workflow || {});
      }
      addMessage("assistant", summarizeFinalPackageResponse(data));
      return data;
    }

    async function queueStagedPackageExecution(packagePath) {
      const data = await request("/api/staged-workflow/queue-execution", {package_path: packagePath});
      addMessage("assistant", summarizeExecutionJob(data));
      return data;
    }

    async function approveExecutionReview(jobId) {
      const reviewed = await request(`/api/jobs/${encodeURIComponent(jobId)}/approve-review`, {});
      if (!reviewed.ok) {
        addMessage("assistant", summarizeExecutionJob(reviewed));
        return reviewed;
      }
      addMessage("assistant", summarizeExecutionJob(reviewed));
      window.setTimeout(refreshExecutionJobs, 1200);
      return reviewed;
    }

    async function retryExecutionJob(jobId) {
      const data = await request(`/api/jobs/${encodeURIComponent(jobId)}/retry`, {});
      addMessage("assistant", summarizeExecutionJob(data));
      if (data.ok) window.setTimeout(refreshExecutionJobs, 1200);
      return data;
    }

    function splitPathList(value) {
      return String(value || "")
        .split(/\r?\n|;/)
        .map(item => item.trim())
        .filter(Boolean);
    }

    function normalizePathForUi(path) {
      return String(path || "").replaceAll("\\", "/").replace(/\/+$/, "");
    }

    function pathLooksLikeFile(path) {
      const name = normalizePathForUi(path).split("/").pop() || "";
      return /\.[A-Za-z0-9]{1,8}$/.test(name);
    }

    function parentDirectory(path) {
      const normalized = normalizePathForUi(path);
      if (!normalized) return "";
      const parts = normalized.split("/");
      if (pathLooksLikeFile(normalized)) {
        parts.pop();
      }
      return parts.join("/");
    }

    function commonDirectory(paths) {
      const dirs = paths.map(parentDirectory).filter(Boolean);
      if (!dirs.length) return "";
      const splitDirs = dirs.map(dir => dir.split("/"));
      const common = [];
      for (let index = 0; index < splitDirs[0].length; index += 1) {
        const part = splitDirs[0][index];
        if (splitDirs.every(items => items[index] === part)) {
          common.push(part);
        } else {
          break;
        }
      }
      return common.join("/");
    }

    function baseName(path) {
      const normalized = normalizePathForUi(path);
      return normalized.split("/").filter(Boolean).pop() || "";
    }

    function stripExtension(name) {
      return String(name || "").replace(/\.[A-Za-z0-9]{1,8}$/, "");
    }

    function caseTitleFromPath(path) {
      const name = stripExtension(baseName(path));
      return name.replace(/[^\p{L}\p{N}_-]+/gu, "_").replace(/^_+|_+$/g, "") || "comsol_case";
    }

    function setCaseFields(caseDir, caseTitle) {
      const caseDirInput = document.getElementById("caseDir");
      const caseTitleInput = document.getElementById("caseTitle");
      if (caseDir) caseDirInput.value = caseDir;
      if (caseTitle) caseTitleInput.value = caseTitle;
    }

    function setInputValue(id, value, force = false) {
      const input = document.getElementById(id);
      if (input && (value || force)) input.value = value || "";
    }

    function setTextareaValue(id, value, force = false) {
      const input = document.getElementById(id);
      if (input && (value || force)) input.value = value || "";
    }

    function extensionOf(path) {
      const name = baseName(path).toLowerCase();
      const match = name.match(/(\.[a-z0-9]+)$/);
      return match ? match[1] : "";
    }

    function firstPathByExtension(paths, extensions) {
      const wanted = new Set(extensions);
      return paths.find(path => wanted.has(extensionOf(path))) || "";
    }

    function pathsByExtension(paths, extensions) {
      const wanted = new Set(extensions);
      return paths.filter(path => wanted.has(extensionOf(path)));
    }

    function isDefaultGeneratedPath(value) {
      const text = String(value || "");
      return !text || text.includes("generated_comsol_model") || text.includes(".codex_edit");
    }

    function fillRightPanelFromSelection(paths) {
      if (!paths.length) return;
      const normalized = paths.map(normalizePathForUi).filter(Boolean);
      const dir = normalized.length > 1 ? commonDirectory(normalized) : parentDirectory(normalized[0]);
      const titleSource = dir || normalized[0];
      const caseTitle = caseTitleFromPath(titleSource);
      const matlabPath = firstPathByExtension(normalized, [".m"]);
      const javaPath = firstPathByExtension(normalized, [".java"]);
      const csvPath = firstPathByExtension(normalized, [".csv"]);
      const jsonPath = firstPathByExtension(normalized, [".json"]);
      const codeSourcePath = matlabPath || javaPath || firstPathByExtension(normalized, [".txt", ".md"]);
      syncRelatedFieldsFromPaths(normalized);
      if (codeSourcePath) setInputValue("codeFilePath", codeSourcePath);
      if (isDefaultGeneratedPath(document.getElementById("codeOutputPath")?.value)) {
        setInputValue("codeOutputPath", `generated/code/${caseTitle}.codex_edit.m`);
      }
      if (jsonPath && /constraint|约束|config/i.test(baseName(jsonPath))) {
        setCaseSyncInfo([document.getElementById("caseSyncInfo")?.value || "", `约束文件：${baseName(jsonPath)}`]);
      }
      setTextareaValue(
        "codeRequirement",
        `结合案例《${caseTitle}》的文件证据，读取 PDF、MATLAB、Java、MPH 和数据文件，判断物理场、材料、几何、边界条件、网格、研究类型和结果输出，并生成可复核的 COMSOL MATLAB/Java 建模代码。`,
        true
      );
      setTextareaValue(
        "stagedRequirement",
        `针对案例《${caseTitle}》分步完成 COMSOL 建模：先判断物理场，再确认材料、几何结构、边界条件、网格、求解和结果导出；每一步等待我确认后继续。`,
        true
      );
      const selectedSummary = [
        `案例名称：${caseTitle}`,
        dir ? `案例目录：${dir}` : "",
        matlabPath ? `MATLAB 文件：${matlabPath}` : "",
        javaPath ? `Java 文件：${javaPath}` : "",
        csvPath ? `CSV 文件：${csvPath}` : "",
        jsonPath ? `JSON/约束文件：${jsonPath}` : "",
      ].filter(Boolean).join("\\n");
      setTextareaValue("existingComsolContent", selectedSummary, true);
    }

    function setCaseSyncInfo(parts) {
      const info = document.getElementById("caseSyncInfo");
      if (info) info.value = parts.filter(Boolean).join("；") || "等待选择文件或输入路径";
    }

    function syncCaseTitleFromCaseDir() {
      const dir = normalizePathForUi(document.getElementById("caseDir").value);
      if (!dir) return;
      const caseTitle = caseTitleFromPath(dir);
      setCaseFields(dir, caseTitle);
      setInputValue("modelName", `${caseTitle}_surrogate.joblib`);
      setCaseSyncInfo([`案例目录已关联：${dir}`, `案例名称：${caseTitle}`]);
    }

    function syncRelatedFieldsFromPaths(paths) {
      if (!paths.length) return;
      const dir = paths.length > 1 ? commonDirectory(paths) : parentDirectory(paths[0]);
      const titleSource = dir || parentDirectory(paths[0]) || paths[0];
      const caseTitle = caseTitleFromPath(titleSource);
      const matlabPath = firstPathByExtension(paths, [".m"]);
      const csvPath = firstPathByExtension(paths, [".csv"]);
      setCaseFields(dir, caseTitle);
      setInputValue("matlabPath", matlabPath);
      setInputValue("csvPath", csvPath);
      setInputValue("modelName", `${caseTitle}_surrogate.joblib`);
      setCaseSyncInfo([
        dir ? `案例目录已关联：${dir}` : "",
        matlabPath ? `MATLAB：${baseName(matlabPath)}` : "",
        csvPath ? `CSV：${baseName(csvPath)}` : "",
        `模型文件：${caseTitle}_surrogate.joblib`,
      ]);
    }

    function syncRightPanelFromSummary(summary) {
      if (!summary) return;
      const files = summary.kind === "file_collection" ? (summary.files || []) : [summary];
      const names = files.map(file => file.name || "").filter(Boolean);
      if (names.length && !splitPathList(document.getElementById("filePath").value).length) {
        fillRightPanelFromSelection(names);
      }
      const scriptFiles = files.filter(file => ["matlab_livelink", "matlab_text", "comsol_java", "text", "json"].includes(file.kind));
      const preview = scriptFiles
        .map(file => {
          const details = file.details || {};
          const extract = details.content_extract || {};
          const physics = (extract.physics || []).slice(0, 8).join(", ");
          const studies = (extract.studies || []).slice(0, 8).join(", ");
          return [
            `文件：${file.name || ""}`,
            `类型：${file.kind || ""}`,
            physics ? `物理场证据：${physics}` : "",
            studies ? `研究类型证据：${studies}` : "",
            file.preview ? `预览：${String(file.preview).slice(0, 1200)}` : "",
          ].filter(Boolean).join("\\n");
        })
        .join("\\n\\n---\\n\\n");
      if (preview) setTextareaValue("existingComsolContent", preview, true);
      const csvSummary = findCsvSummary(summary);
      if (csvSummary?.name && !document.getElementById("csvPath").value) {
        setInputValue("csvPath", csvSummary.name);
      }
      syncTrainingColumnsFromSummary(summary);
    }

    function syncTrainingColumnsFromSummary(summary) {
      const csvSummary = findCsvSummary(summary);
      const columns = csvSummary?.details?.columns || [];
      if (!columns.length) return;
      const outputKeywords = /(out|output|result|target|tmax|tavg|temp|temperature|stress|strain|disp|pressure|velocity|flux|current|voltage|loss|power|force|volume|area|error|max|min|avg)/i;
      const outputs = columns.filter(name => outputKeywords.test(String(name)));
      const inputs = columns.filter(name => !outputs.includes(name));
      if (inputs.length) setInputValue("inputs", inputs.join(" "));
      if (outputs.length) setInputValue("outputs", outputs.join(" "));
      setCaseSyncInfo([
        document.getElementById("caseSyncInfo")?.value || "",
        `训练列已关联：输入 ${inputs.length || 0} 个，输出 ${outputs.length || 0} 个`,
      ]);
    }

    function findCsvSummary(summary) {
      if (!summary) return null;
      if (summary.kind === "csv_table") return summary;
      if (summary.kind === "file_collection") {
        return (summary.files || []).find(file => file.kind === "csv_table") || null;
      }
      return null;
    }

    function syncCaseFieldsFromPaths() {
      const paths = splitPathList(document.getElementById("filePath").value);
      if (!paths.length) return;
      fillRightPanelFromSelection(paths);
    }

    function syncCaseFieldsFromUpload() {
      const files = Array.from(document.getElementById("uploadFile").files || []);
      if (!files.length) return;
      const relativePaths = files
        .map(file => file.webkitRelativePath || "")
        .filter(Boolean);
      if (relativePaths.length) {
        const dir = relativePaths.length > 1 ? commonDirectory(relativePaths) : parentDirectory(relativePaths[0]);
        fillRightPanelFromSelection(relativePaths);
        return;
      }
      const names = files.map(file => file.name || "").filter(Boolean);
      const firstName = names[0] || "comsol_case";
      const caseTitle = caseTitleFromPath(firstName);
      setCaseFields("", caseTitle);
      setInputValue("matlabPath", firstPathByExtension(names, [".m"]));
      setInputValue("csvPath", firstPathByExtension(names, [".csv"]));
      setInputValue("modelName", `${caseTitle}_surrogate.joblib`);
      fillRightPanelFromSelection(names);
      setCaseSyncInfo([
        `已选择 ${files.length} 个上传文件`,
        firstPathByExtension(names, [".m"]) ? `MATLAB：${firstPathByExtension(names, [".m"])}` : "",
        firstPathByExtension(names, [".csv"]) ? `CSV：${firstPathByExtension(names, [".csv"])}` : "",
      ]);
    }

    async function readFilePath() {
      syncCaseFieldsFromPaths();
      const paths = splitPathList(document.getElementById("filePath").value);
      const endpoint = paths.length > 1 ? "/api/read-files" : "/api/read-file";
      const body = paths.length > 1 ? {paths} : {path: paths[0] || ""};
      const data = await request(endpoint, body);
      if (data.ok) {
        lastFileSummary = data.summary;
        syncRightPanelFromSummary(lastFileSummary);
      }
      addMessage("assistant", summarizeFileResponse(data));
      return data;
    }

    async function uploadPayload(file) {
      if (!/\.(pdf|mph)$/i.test(file.name || "")) {
        return {name: file.name, content: await file.text()};
      }
      const bytes = new Uint8Array(await file.arrayBuffer());
      let binary = "";
      for (let offset = 0; offset < bytes.length; offset += 32768) {
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
      }
      return {name: file.name, content_base64: btoa(binary)};
    }

    async function readUploadedFile() {
      syncCaseFieldsFromUpload();
      const files = Array.from(document.getElementById("uploadFile").files);
      if (!files.length) {
        const data = {ok: false, error: "No file selected"};
        renderJson(data);
        setStatus("failed", "bad");
        addMessage("assistant", summarizeFileResponse(data));
        return;
      }
      const payloadFiles = [];
      for (const file of files) {
        payloadFiles.push(await uploadPayload(file));
      }
      const endpoint = payloadFiles.length > 1 ? "/api/read-uploaded-files" : "/api/read-uploaded-file";
      const body = payloadFiles.length > 1 ? {files: payloadFiles} : payloadFiles[0];
      const data = await request(endpoint, body);
      if (data.ok) {
        lastFileSummary = data.summary;
        syncRightPanelFromSummary(lastFileSummary);
      }
      addMessage("assistant", summarizeFileResponse(data));
      return data;
    }

    async function buildLearningSummary() {
      if (!lastFileSummary) {
        const data = {ok: false, error: "No file summary available. Read one or more files first."};
        renderJson(data);
        setStatus("failed", "bad");
        addMessage("assistant", summarizeLearningResponse(data));
        return data;
      }
      const data = await request("/api/learning-summary", {
        file_summary: lastFileSummary,
        remember: true,
        title: document.getElementById("caseTitle").value,
      });
      addMessage("assistant", summarizeLearningResponse(data));
      return data;
    }

    function enhanceCaseLearningHtml(data, html) {
      if (!data || !data.ok) return html;
      const card = data.card || {};
      const deep = card.deep_learning_plan || {};
      const principles = card.modeling_principles || {};
      const extension = card.case_extension || {};
      const progressHtml = renderServerProgress(card.learning_progress || []);
      if (!deep.kind && !principles.kind && !extension.kind && !progressHtml) return html;
      const principleRows = ["core_sequence", "physics_reasoning", "automation_evidence", "verification_logic"]
        .map(key => {
          const rows = (principles[key] || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
          return rows ? `<h3>${escapeHtml(key)}</h3><ul>${rows}</ul>` : "";
        })
        .join("");
      const principlesHtml = principles.kind
        ? `<h3>建模原理学习结果</h3><p>准备度：<code>${escapeHtml(principles.readiness || "")}</code></p>${principleRows}`
        : "";
      const deepInputs = (deep.candidate_inputs || []).slice(0, 16).map(item => `<code>${escapeHtml(item)}</code>`).join(" ");
      const deepOutputs = (deep.candidate_outputs || []).slice(0, 16).map(item => `<code>${escapeHtml(item)}</code>`).join(" ");
      const deepWorkflow = (deep.workflow || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const deepModels = (deep.model_candidates || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const deepLimits = (deep.limitations || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const deepHtml = deep.kind
        ? `<h3>深度学习训练能力</h3><ul><li>准备度：<code>${escapeHtml(deep.readiness || "")}</code></li><li>准备度评分：${escapeHtml(deep.readiness_score || 0)}</li><li>候选输入：${deepInputs || "<code>未识别</code>"}</li><li>候选输出：${deepOutputs || "<code>未识别</code>"}</li></ul>${deepModels ? `<h3>候选训练模型</h3><ul>${deepModels}</ul>` : ""}${deepWorkflow ? `<h3>训练流程</h3><ul>${deepWorkflow}</ul>` : ""}${deepLimits ? `<h3>训练限制</h3><ul>${deepLimits}</ul>` : ""}`
        : "";
      const extensionRows = [
        ["transferable_knowledge", "可迁移知识"],
        ["extension_questions", "延伸问题"],
        ["new_model_directions", "新建模方向"],
        ["parameter_sweep_ideas", "参数扫描想法"],
        ["code_generation_ideas", "代码生成思路"],
        ["risk_checks", "复核风险"]
      ].map(([key, title]) => {
        const rows = (extension[key] || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
        return rows ? `<h3>${escapeHtml(title)}</h3><ul>${rows}</ul>` : "";
      }).join("");
      const extensionHtml = extension.kind
        ? `<h3>思考与延伸</h3><p>准备度：<code>${escapeHtml(extension.readiness || "")}</code>，评分：${escapeHtml(extension.readiness_score || 0)}</p>${extensionRows}`
        : "";
      return `${html}${progressHtml}${principlesHtml}${extensionHtml}${deepHtml}`;
    }

    function summarizeKnowledgeSystemResponse(data) {
      if (!data.ok) {
        return summarizeGeneric("知识体系构建", data);
      }
      const system = data.knowledge_system || {};
      const domains = (system.domains || [])
        .slice(0, 10)
        .map(domain => {
          const physics = (domain.core_physics || []).slice(0, 5).map(item => `<code>${escapeHtml(item.name)}</code>`).join(" ");
          const outputs = (domain.typical_outputs || []).slice(0, 5).map(item => `<code>${escapeHtml(item.name)}</code>`).join(" ");
          return `<li><strong>${escapeHtml(domain.domain || "")}</strong>：案例 ${escapeHtml(domain.case_count || 0)} 个；物理场 ${physics || "<code>未识别</code>"}；输出 ${outputs || "<code>未识别</code>"}</li>`;
        })
        .join("");
      const workflow = (system.global_modeling_workflow || [])
        .map(item => `<li><strong>${escapeHtml(item.stage || "")}</strong>：${escapeHtml(item.description || "")}</li>`)
        .join("");
      const strategy = (system.training_strategy || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const gaps = (system.common_gaps || []).slice(0, 8).map(item => `<li>${escapeHtml(item.gap || "")} × ${escapeHtml(item.count || 0)}</li>`).join("");
      return `<h3>COMSOL 自主知识体系已形成</h3><p>${escapeHtml(system.capability_summary || "")}</p><ul><li>案例数量：${escapeHtml(system.case_count || 0)}</li><li>领域数量：${escapeHtml(system.domain_count || 0)}</li><li>记忆库：<code>${escapeHtml(data.memory_path || "")}</code></li></ul>${domains ? `<h3>领域知识结构</h3><ul>${domains}</ul>` : ""}${workflow ? `<h3>全局建模流程</h3><ul>${workflow}</ul>` : ""}${strategy ? `<h3>训练与完善策略</h3><ul>${strategy}</ul>` : ""}${gaps ? `<h3>常见缺口</h3><ul>${gaps}</ul>` : ""}`;
    }

    async function buildKnowledgeSystem() {
      const progress = startProgressCard("知识体系构建进度", [
        "读取案例记忆库",
        "归纳领域、参数和物理场",
        "形成全局建模流程",
        "整理训练策略和常见缺口"
      ]);
      progress.update(15, 0, "正在读取本地案例记忆库...");
      window.setTimeout(() => progress.update(38, 1, "正在统计领域、物理场、参数和结果输出..."), 120);
      window.setTimeout(() => progress.update(68, 2, "正在归纳 COMSOL 建模工作流..."), 260);
      const data = await request("/api/knowledge-system", {});
      progress.finish(data.ok ? "知识体系已刷新，可用于后续建模方案和代码生成。" : "知识体系构建失败，请查看错误信息。");
      addMessage("assistant", summarizeKnowledgeSystemResponse(data));
      return data;
    }

    async function learnCaseDirectory() {
      syncCaseTitleFromCaseDir();
      const progress = startProgressCard("案例学习加载进度", [
        "读取案例目录",
        "扫描 PDF/MATLAB/Java/MPH/CSV 文件",
        "抽取 COMSOL 模型树、参数和物理场证据",
        "生成深度学习训练计划",
        "写入案例记忆库并输出总结"
      ]);
      progress.update(8, 0, "正在读取右侧案例目录和案例名称...");
      window.setTimeout(() => progress.update(24, 1, "正在扫描案例文件类型和数量..."), 120);
      window.setTimeout(() => progress.update(46, 2, "正在提取参数、几何、物理场、网格、研究和结果线索..."), 280);
      window.setTimeout(() => progress.update(68, 3, "正在判断是否具备 CSV 代理模型训练条件..."), 520);
      const data = await request("/api/learn-case", {
        case_dir: document.getElementById("caseDir").value,
        title: document.getElementById("caseTitle").value,
        prompt_summary: document.getElementById("prompt").value
      });
      progress.finish(data.ok ? "案例学习已完成，已生成总结和训练能力评估。" : "案例学习失败，请查看错误信息。");
      addMessage("assistant", enhanceCaseLearningHtml(data, summarizeCaseLearningResponse(data)));
      return data;
    }

    async function learnArticleDocument() {
      const data = await request("/api/learn-article", {
        article_path: document.getElementById("articlePath").value
      });
      addMessage("assistant", summarizeArticleLearningResponse(data));
      return data;
    }

    async function validateConstraints() {
      const data = await request("/api/validate-constraints", {constraints_json: constraints.value});
      addMessage("assistant", data.ok ? "<h3>约束校验通过</h3><p>当前 JSON 可以用于生成 COMSOL LiveLink MATLAB 脚本。</p>" : summarizeGeneric("约束校验", data));
      return data;
    }

    async function generateMatlab() {
      let name = "generated_build_thermal_rectangle_surrogate.m";
      try {
        const cfg = JSON.parse(constraints.value);
        name = "generated_build_" + cfg.model_name + ".m";
      } catch (err) {}
      const data = await request("/api/generate-matlab", {constraints_json: constraints.value, output_name: name});
      const html = data.ok
        ? `<h3>MATLAB 脚本已生成</h3><p>路径：<code>${escapeHtml(data.path)}</code></p>`
        : summarizeGeneric("MATLAB 生成", data);
      addMessage("assistant", html);
      return data;
    }

    async function generateComsolCode() {
      const requirement = document.getElementById("codeRequirement").value || document.getElementById("prompt").value;
      const title = caseTitleFromPath(document.getElementById("caseTitle").value || "generated_comsol_model");
      const data = await request("/api/generate-comsol-code", {
        requirement,
        output_prefix: title || "generated_comsol_model",
        existing_content: document.getElementById("existingComsolContent").value
      });
      addMessage("assistant", summarizeComsolCodeResponse(data));
      return data;
    }

    function summarizeTrainingInspection(data) {
      if (!data.ok) {
        return summarizeGeneric("CSV 训练分析", data);
      }
      const inspection = data.inspection || {};
      const inputs = (inspection.inferred_input_columns || []).map(item => `<code>${escapeHtml(item)}</code>`).join(" ");
      const outputs = (inspection.inferred_output_columns || []).map(item => `<code>${escapeHtml(item)}</code>`).join(" ");
      const warnings = (inspection.warnings || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const limitations = (inspection.limitations || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const plan = (inspection.automation_plan || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      return `<h3>CSV 训练能力分析</h3><ul><li>行数：${escapeHtml(inspection.rows || 0)}</li><li>数值列：${escapeHtml((inspection.numeric_columns || []).length)}</li><li>可自动训练：<code>${inspection.ready_for_training ? "yes" : "no"}</code></li><li>推断输入：${inputs || "<code>未识别</code>"}</li><li>推断输出：${outputs || "<code>未识别</code>"}</li></ul>${warnings ? `<h3>数据警告</h3><ul>${warnings}</ul>` : ""}${limitations ? `<h3>限制</h3><ul>${limitations}</ul>` : ""}${plan ? `<h3>自动化计划</h3><ul>${plan}</ul>` : ""}`;
    }

    async function inspectTrainingCsv() {
      const data = await request("/api/inspect-training-csv", {
        csv_path: document.getElementById("csvPath").value,
        input_columns: document.getElementById("inputs").value,
        output_columns: document.getElementById("outputs").value
      });
      const inspection = data.inspection || {};
      if (data.ok && inspection.ready_for_training) {
        setInputValue("inputs", (inspection.inferred_input_columns || []).join(" "));
        setInputValue("outputs", (inspection.inferred_output_columns || []).join(" "));
      }
      addMessage("assistant", summarizeTrainingInspection(data));
      return data;
    }

    async function prepareThermalSweep() {
      const data = await request("/api/training/prepare-thermal-sweep", {});
      if (data.ok) {
        setInputValue("csvPath", data.csv_path || "generated/training_sweeps/thermal_plate_sweep.csv");
        setInputValue("inputs", ((data.spec || {}).inputs || []).join(" "));
        setInputValue("outputs", ((data.spec || {}).outputs || []).join(" "));
        setInputValue("modelName", "thermal_plate_surrogate.joblib");
        addMessage("assistant", `<h3>传热扫描已准备</h3><ul><li>样本数：${escapeHtml(String(data.sample_count || 0))}</li><li>MATLAB：<code>${escapeHtml(data.script_path || "")}</code></li><li>训练 CSV：<code>${escapeHtml(data.csv_path || "")}</code></li></ul>`);
      } else {
        addMessage("assistant", summarizeGeneric("传热扫描准备", data));
      }
      return data;
    }

    async function queueThermalSweepTraining() {
      const data = await request("/api/jobs/thermal-sweep-training", {});
      addMessage("assistant", summarizeExecutionJob(data));
      return data;
    }

    async function predictThermalPlate() {
      const data = await request("/api/surrogates/thermal-plate/predict", {
        model_path: document.getElementById("thermalSurrogateModel").value.trim(),
        L_m: Number(document.getElementById("thermalL").value),
        W_m: Number(document.getElementById("thermalW").value),
        k_W_mK: Number(document.getElementById("thermalK").value),
        T_hot_K: Number(document.getElementById("thermalHot").value),
        T_cold_K: Number(document.getElementById("thermalCold").value)
      });
      const validation = data.validation || {};
      if (!data.ok) {
        const out = Object.entries(data.out_of_range || {})
          .map(([name, item]) => `<li><code>${escapeHtml(name)}</code>=${escapeHtml(String(item.value))}，已验证范围 ${escapeHtml(String(item.min))} - ${escapeHtml(String(item.max))}</li>`)
          .join("");
        addMessage("assistant", `<h3>需要 COMSOL 真实求解</h3><p>${escapeHtml(data.guidance || data.error || "输入不满足代理模型适用范围。")}</p>${out ? `<ul>${out}</ul>` : ""}<p><button class="primary" onclick="createThermalAugmentationPlan()">生成补充 COMSOL 扫描计划</button></p>`);
        return data;
      }
      const prediction = data.prediction || {};
      addMessage("assistant", `<h3>二维传热快速预测</h3><p>模型：<code>${escapeHtml(data.model_name || "")}</code></p><ul><li>最高温度：<strong>${escapeHtml(Number(prediction.Tmax_K).toFixed(3))} K</strong></li><li>平均温度：<strong>${escapeHtml(Number(prediction.Tavg_K).toFixed(3))} K</strong></li><li>独立 COMSOL 验证：<code>${validation.passed ? "通过" : "未记录"}</code>，最大绝对误差 <code>${escapeHtml(JSON.stringify(validation.max_absolute_error || {}))}</code></li></ul><p>${escapeHtml(data.guidance || "")}</p>`);
      return data;
    }

    async function createThermalAugmentationPlan() {
      const data = await request("/api/surrogates/thermal-plate/augmentation-plan", {
        model_path: document.getElementById("thermalSurrogateModel").value.trim(),
        L_m: Number(document.getElementById("thermalL").value),
        W_m: Number(document.getElementById("thermalW").value),
        k_W_mK: Number(document.getElementById("thermalK").value),
        T_hot_K: Number(document.getElementById("thermalHot").value),
        T_cold_K: Number(document.getElementById("thermalCold").value)
      });
      if (!data.ok) {
        addMessage("assistant", summarizeGeneric("补充扫描计划", data));
        return data;
      }
      const plan = data.plan || {};
      const rows = (plan.recommended_comsol_samples || [])
        .map((item, index) => `<li>工况 ${index + 1}: <code>${escapeHtml(JSON.stringify(item))}</code></li>`)
        .join("");
      addMessage("assistant", `<h3>COMSOL 补充扫描计划</h3><p>${escapeHtml(plan.reason || "")}</p><ul>${rows}</ul><p>计划文件：<code>${escapeHtml(plan.path || "")}</code></p><p><button class="primary" onclick='queueThermalAugmentation(${JSON.stringify(plan.path || "")})'>执行补充 COMSOL 扫描</button></p>`);
      return data;
    }

    async function queueThermalAugmentation(planPath) {
      const data = await request("/api/surrogates/thermal-plate/augmentation-queue", {plan_path: planPath});
      addMessage("assistant", summarizeExecutionJob(data));
      return data;
    }

    async function queueThermalAugmentationRetrain(augmentationJobId) {
      const data = await request("/api/surrogates/thermal-plate/augmentation-retrain", {augmentation_job_id: augmentationJobId});
      addMessage("assistant", summarizeExecutionJob(data));
      return data;
    }

    async function autoTrainModel() {
      document.getElementById("inputs").value = document.getElementById("inputs").value.trim();
      document.getElementById("outputs").value = document.getElementById("outputs").value.trim();
      return trainModel(true);
    }

    async function trainModel() {
      const auto = arguments.length > 0 ? Boolean(arguments[0]) : false;
      const progress = startProgressCard("代理模型训练加载进度", [
        "读取 CSV 训练数据",
        "检查输入列和输出列",
        "划分训练集和测试集",
        "比较 baseline、Ridge、RandomForest、MLP",
        "保存最优模型和训练报告"
      ]);
      progress.update(10, 0, "正在读取 CSV 路径和训练列配置...");
      window.setTimeout(() => progress.update(28, 1, "正在检查缺失值、重复行和列有效性..."), 120);
      window.setTimeout(() => progress.update(48, 2, "正在划分训练集和测试集..."), 280);
      window.setTimeout(() => progress.update(72, 3, "正在训练并比较多个候选模型..."), 520);
      const data = await request("/api/train", {
        csv_path: document.getElementById("csvPath").value,
        input_columns: document.getElementById("inputs").value,
        output_columns: document.getElementById("outputs").value,
        model_name: document.getElementById("modelName").value,
        auto
      });
      progress.finish(data.ok ? "训练完成，已保存最优代理模型。" : "训练失败，请查看错误信息和数据列配置。");
      const report = data.report || {};
      const inspectionHtml = data.inspection ? summarizeTrainingInspection({ok: true, inspection: data.inspection}) : "";
      const candidateRows = (report.candidate_reports || [])
        .map(item => `<li><code>${escapeHtml(item.name)}</code> RMSE=${escapeHtml(item.test_rmse)} R2=${escapeHtml(item.test_r2)}</li>`)
        .join("");
      const summaryRows = (report.training_summary || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const recommendationRows = (report.recommendations || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const html = data.ok
        ? `<h3>训练完成</h3><p>模型：<code>${escapeHtml(data.model_path)}</code></p><p>最佳候选：<code>${escapeHtml(report.best_model)}</code></p><p>测试 RMSE：<code>${escapeHtml(report.test_rmse)}</code>，MAE：<code>${escapeHtml(report.test_mae)}</code>，R2：<code>${escapeHtml(report.test_r2)}</code></p>${inspectionHtml}${summaryRows ? `<h3>训练总结</h3><ul>${summaryRows}</ul>` : ""}${candidateRows ? `<h3>候选模型对比</h3><ul>${candidateRows}</ul>` : ""}${recommendationRows ? `<h3>后续建议</h3><ul>${recommendationRows}</ul>` : ""}`
        : summarizeGeneric("训练", data);
      addMessage("assistant", html);
      return data;
    }

    function parseClosureJson(elementId, label) {
      try {
        return JSON.parse(document.getElementById(elementId).value);
      } catch (error) {
        addMessage("assistant", `<h3>${escapeHtml(label)}格式错误</h3><p>请输入合法 JSON。</p>`);
        return null;
      }
    }

    async function checkMeshConvergence() {
      const records = parseClosureJson("meshRecords", "网格记录");
      if (!records || !Array.isArray(records)) return null;
      const data = await request("/api/training/mesh-convergence", {
        records,
        output_name: document.getElementById("meshOutputName").value.trim(),
        relative_change_threshold_percent: Number(document.getElementById("meshThreshold").value)
      });
      addMessage("assistant", data.ok ? `<h3>网格收敛检查</h3><p>结论：<strong>${data.report?.passed ? "通过" : "未通过"}</strong></p><p><code>${escapeHtml(JSON.stringify(data.report || {}))}</code></p>` : summarizeGeneric("网格收敛检查", data));
      return data;
    }

    async function checkParameterCoverage() {
      const ranges = parseClosureJson("coverageRanges", "参数覆盖范围");
      if (!ranges || Array.isArray(ranges) || typeof ranges !== "object") return null;
      const data = await request("/api/training/parameter-coverage", {
        csv_path: document.getElementById("csvPath").value,
        parameter_ranges: ranges,
        bins: Number(document.getElementById("coverageBins").value)
      });
      addMessage("assistant", data.ok ? `<h3>参数覆盖检查</h3><p>结论：<strong>${data.report?.passed ? "通过" : "存在稀疏区或越界"}</strong></p><p><code>${escapeHtml(JSON.stringify(data.report || {}))}</code></p>` : summarizeGeneric("参数覆盖检查", data));
      return data;
    }

    async function checkHoldoutIndependence() {
      const data = await request("/api/training/holdout-independence", {
        training_csv: document.getElementById("csvPath").value,
        holdout_csv: document.getElementById("holdoutCsvPath").value,
        input_columns: document.getElementById("inputs").value
      });
      addMessage("assistant", data.ok ? `<h3>留出集独立性检查</h3><p>结论：<strong>${data.report?.passed ? "通过" : "未通过"}</strong></p><p><code>${escapeHtml(JSON.stringify(data.report || {}))}</code></p>` : summarizeGeneric("留出集独立性检查", data));
      return data;
    }

    async function prepareAugmentationRetrain() {
      const data = await request("/api/training/prepare-augmentation-retrain", {
        training_csv: document.getElementById("csvPath").value,
        augmentation_csv: document.getElementById("augmentationCsvPath").value,
        previous_holdout_csv: document.getElementById("previousHoldoutCsvPath").value,
        fresh_holdout_csv: document.getElementById("freshHoldoutCsvPath").value,
        input_columns: document.getElementById("inputs").value
      });
      addMessage("assistant", data.ok ? `<h3>补充样本重训已准备</h3><p><code>${escapeHtml(JSON.stringify(data.report || {}))}</code></p>` : summarizeGeneric("补充样本重训", data));
      return data;
    }

    function loadReferenceDefaults() {
      const examples = {
        laminar_pipe_poiseuille: {length_m: 1, diameter_m: 0.01, flow_rate_m3_s: 1e-5, viscosity_pa_s: 0.001, density_kg_m3: 1000},
        thermoacoustic_open_tube: {length_m: 0.5, temperature_k: 293.15},
        flow_heat_channel: {mass_flow_rate_kg_s: 0.001, heat_capacity_j_kg_k: 4182, inlet_temperature_k: 293.15, wall_temperature_k: 333.15, heat_transfer_coefficient_w_m2_k: 120, wetted_perimeter_m: 0.02, length_m: 0.2},
        acoustic_structure_cantilever: {length_m: 0.03, width_m: 0.005, thickness_m: 0.0005, youngs_modulus_pa: 1.69e11, density_kg_m3: 2330},
        electrochemical_nernst: {standard_potential_v: 0.34, temperature_k: 298.15, electron_count: 1, oxidized_activity: 1, reduced_activity: 0.1},
        particle_stokes_settling: {particle_diameter_m: 1e-5, particle_density_kg_m3: 2500, fluid_density_kg_m3: 1000, dynamic_viscosity_pa_s: 0.001, gravity_m_s2: 9.80665},
        rf_half_wave_resonator: {length_m: 0.1, relative_permittivity: 1, relative_permeability: 1},
        acoustic_rectangular_cavity: {length_x_m: 0.4, length_y_m: 0.3, sound_speed_m_s: 343, mode_m: 1, mode_n: 0}
      };
      const type = document.getElementById("referenceCaseType").value;
      document.getElementById("referenceParameters").value = JSON.stringify(examples[type] || {}, null, 2);
      const resultKeys = {
        laminar_pipe_poiseuille: "pressure_drop_pa",
        thermoacoustic_open_tube: "fundamental_frequency_hz",
        flow_heat_channel: "outlet_temperature_k",
        acoustic_structure_cantilever: "first_bending_frequency_hz",
        electrochemical_nernst: "equilibrium_potential_v",
        particle_stokes_settling: "terminal_velocity_m_s",
        rf_half_wave_resonator: "fundamental_frequency_hz",
        acoustic_rectangular_cavity: "eigenfrequency_hz"
      };
      document.getElementById("referenceResultKey").value = resultKeys[type] || "";
      document.getElementById("comsolObservedResultName").value = resultKeys[type] || "";
      const units = {laminar_pipe_poiseuille: "Pa", thermoacoustic_open_tube: "Hz", flow_heat_channel: "K", acoustic_structure_cantilever: "Hz", electrochemical_nernst: "V", particle_stokes_settling: "m/s", rf_half_wave_resonator: "Hz", acoustic_rectangular_cavity: "Hz"};
      document.getElementById("observedComsolUnit").value = units[type] || "";
    }

    async function evaluateReferenceCase() {
      let parameters;
      try {
        parameters = JSON.parse(document.getElementById("referenceParameters").value);
      } catch (error) {
        addMessage("assistant", "<h3>物理参考参数格式错误</h3><p>请输入 JSON 对象，并使用 SI 单位，例如圆管层流的直径单位为 m、体积流量单位为 m^3/s。</p>");
        return null;
      }
      if (!parameters || Array.isArray(parameters) || typeof parameters !== "object") {
        addMessage("assistant", "<h3>物理参考参数无效</h3><p>参数必须是 JSON 对象。</p>");
        return null;
      }
      const data = await request("/api/reference-check", {
        case_type: document.getElementById("referenceCaseType").value,
        parameters_si: parameters
      });
      if (!data.ok) {
        addMessage("assistant", summarizeGeneric("物理参考计算", data));
        return data;
      }
      const report = data.report || {};
      const reference = report.reference || {};
      const assumptions = (reference.assumptions || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      addMessage("assistant", `<h3>物理参考结果</h3><p><strong>状态：</strong>仅理论/守恒基准，尚非 COMSOL 实机结果。</p><p><strong>类型：</strong><code>${escapeHtml(report.case_type || "")}</code></p><p><strong>数值：</strong><code>${escapeHtml(JSON.stringify(reference))}</code></p>${assumptions ? `<h3>适用假设</h3><ul>${assumptions}</ul>` : ""}<p><strong>COMSOL 对照：</strong>${escapeHtml(report.next_comsol_check || "")}</p>`);
      return data;
    }

    async function compareReferenceObservation() {
      const parameters = parseClosureJson("referenceParameters", "physical reference parameters");
      const observedValue = Number(document.getElementById("observedComsolValue").value);
      if (!parameters || Array.isArray(parameters) || typeof parameters !== "object" || !Number.isFinite(observedValue)) {
        addMessage("assistant", "<h3>Reference comparison information is incomplete</h3><p>Provide SI parameter JSON and a finite COMSOL observation.</p>");
        return null;
      }
      const data = await request("/api/reference-compare", {
        case_type: document.getElementById("referenceCaseType").value,
        parameters_si: parameters,
        reference_key: document.getElementById("referenceResultKey").value.trim(),
        observed_value: observedValue,
        observed_unit: document.getElementById("observedComsolUnit").value.trim(),
        relative_error_threshold_percent: Number(document.getElementById("referenceComparisonThreshold").value)
      });
      addMessage("assistant", data.ok ? `<h3>COMSOL reference comparison</h3><p><strong>${data.report?.passed ? "Within threshold" : "Outside threshold"}</strong></p><p><code>${escapeHtml(JSON.stringify(data.report || {}))}</code></p>` : summarizeGeneric("COMSOL reference comparison", data));
      return data;
    }

    async function compareReferenceResultsCsv() {
      const parameters = parseClosureJson("referenceParameters", "physical reference parameters");
      if (!parameters || Array.isArray(parameters) || typeof parameters !== "object") return null;
      const data = await request("/api/reference-compare-csv", {
        results_csv: document.getElementById("comsolResultsCsvPath").value,
        observed_result_name: document.getElementById("comsolObservedResultName").value.trim(),
        case_type: document.getElementById("referenceCaseType").value,
        parameters_si: parameters,
        reference_key: document.getElementById("referenceResultKey").value.trim(),
        observed_unit: document.getElementById("observedComsolUnit").value.trim(),
        relative_error_threshold_percent: Number(document.getElementById("referenceComparisonThreshold").value)
      });
      addMessage("assistant", data.ok ? `<h3>COMSOL CSV reference comparison</h3><p><strong>${data.report?.passed ? "Within threshold" : "Outside threshold"}</strong></p><p><code>${escapeHtml(JSON.stringify(data.report || {}))}</code></p>` : summarizeGeneric("COMSOL CSV reference comparison", data));
      return data;
    }

    async function showReferenceReports() {
      const data = await requestGet("/api/reference-reports?limit=20");
      if (!data.ok) {
        addMessage("assistant", summarizeGeneric("Reference reports", data));
        return data;
      }
      const rows = (data.reports || []).map(item => `<li><code>${escapeHtml(item.id || "")}</code><br>${escapeHtml(item.case_type || item.kind || "")}<br><code>${escapeHtml(item.path || "")}</code></li>`).join("");
      addMessage("assistant", `<h3>Reference reports</h3>${rows ? `<ul>${rows}</ul>` : "<p>No saved reference reports.</p>"}`);
      return data;
    }

    async function assembleReferenceWorkchain() {
      const paths = document.getElementById("workchainReportPaths").value.split(/\r?\n/).map(item => item.trim()).filter(Boolean);
      if (!paths.length) {
        addMessage("assistant", "<h3>Workchain package needs reports</h3><p>Provide one saved reference report path per line.</p>");
        return null;
      }
      const data = await request("/api/workchain/assemble", {reference_report_paths: paths});
      addMessage("assistant", data.ok ? `<h3>Workchain package created</h3><p><code>${escapeHtml(data.package?.path || "")}</code></p>` : summarizeGeneric("Workchain package", data));
      return data;
    }

    async function showReferenceWorkchains() {
      const data = await requestGet("/api/workchain-packages?limit=20");
      if (!data.ok) {
        addMessage("assistant", summarizeGeneric("Workchain packages", data));
        return data;
      }
      const rows = (data.packages || []).map(item => `<li><code>${escapeHtml(item.id || "")}</code><br>${escapeHtml(item.title || "")} (${escapeHtml(String(item.report_count || 0))})<br><code>${escapeHtml(item.path || "")}</code></li>`).join("");
      addMessage("assistant", `<h3>Workchain packages</h3>${rows ? `<ul>${rows}</ul>` : "<p>No saved workchain packages.</p>"}`);
      return data;
    }

    async function validateReferenceWorkchain() {
      const packagePath = document.getElementById("workchainPackagePath").value.trim();
      if (!packagePath) {
        addMessage("assistant", "<h3>Workchain package path is required</h3>");
        return null;
      }
      const data = await request("/api/workchain/validate", {package_path: packagePath});
      addMessage("assistant", data.ok ? `<h3>Workchain package validation</h3><p><strong>${data.report?.passed ? "Passed" : "Failed"}</strong></p><p><code>${escapeHtml(JSON.stringify(data.report || {}))}</code></p>` : summarizeGeneric("Workchain package validation", data));
      return data;
    }

    async function archiveReferenceWorkchain() {
      const packagePath = document.getElementById("workchainPackagePath").value.trim();
      if (!packagePath) {
        addMessage("assistant", "<h3>Workchain package path is required</h3>");
        return null;
      }
      const data = await request("/api/workchain/archive", {package_path: packagePath});
      addMessage("assistant", data.ok ? `<h3>Workchain ZIP created</h3><p><code>${escapeHtml(data.archive?.archive_path || "")}</code></p>` : summarizeGeneric("Workchain ZIP", data));
      return data;
    }

    async function validateReferenceWorkchainArchive() {
      const archivePath = document.getElementById("workchainArchivePath").value.trim();
      if (!archivePath) {
        addMessage("assistant", "<h3>Workchain archive path is required</h3>");
        return null;
      }
      const data = await request("/api/workchain/archive/validate", {archive_path: archivePath});
      addMessage("assistant", data.ok ? `<h3>Workchain ZIP validation</h3><p><strong>${data.report?.passed ? "Passed" : "Failed"}</strong></p><p><code>${escapeHtml(JSON.stringify(data.report || {}))}</code></p>` : summarizeGeneric("Workchain ZIP validation", data));
      return data;
    }

    async function trainWithComsolHoldout() {
      const holdoutPath = document.getElementById("holdoutCsvPath").value.trim();
      const scope = document.getElementById("physicalScope").value.trim();
      if (!holdoutPath) {
        addMessage("assistant", "<h3>缺少独立验证数据</h3><p>请先填写未参与训练的新 COMSOL 扫描 CSV。随机切分不能替代独立 COMSOL 留出集。</p>");
        return null;
      }
      if (!scope) {
        addMessage("assistant", "<h3>缺少物理适用范围</h3><p>请说明物理场、几何、材料、边界条件和研究类型；否则模型即使误差较小，也不能安全用于新问题。</p>");
        return null;
      }
      const threshold = Number(document.getElementById("relativeErrorThreshold").value);
      const data = await request("/api/train-with-comsol-holdout", {
        csv_path: document.getElementById("csvPath").value,
        holdout_csv_path: holdoutPath,
        input_columns: document.getElementById("inputs").value,
        output_columns: document.getElementById("outputs").value,
        model_name: document.getElementById("modelName").value,
        physical_scope: scope,
        max_relative_error_percent: threshold
      });
      if (!data.ok) {
        addMessage("assistant", summarizeGeneric("独立 COMSOL 验证训练", data));
        return data;
      }
      const validation = data.validation || {};
      const selection = data.selection || {};
      const card = data.model_card || {};
      const registry = data.registry || {};
      const registryEntry = registry.entry || {};
      const unscored = (validation.unscored_outputs || []).join("、");
      addMessage("assistant", `<h3>独立 COMSOL 验证训练完成</h3><ul><li>选定模型：<code>${escapeHtml(selection.best_model || "")}</code></li><li>训练样本：${escapeHtml(String(selection.rows || 0))}</li><li>独立留出集：${escapeHtml(String(selection.holdout_rows || 0))}</li><li>验证状态：<strong>${validation.passed ? "通过" : "未通过"}</strong></li><li>最大相对误差：<code>${escapeHtml(JSON.stringify(validation.max_relative_error_percent || {}))}</code></li><li>阈值：<code>${escapeHtml(String(validation.threshold_relative_error_percent || ""))}%</code></li><li>注册状态：<code>${escapeHtml(registryEntry.status || "")}</code></li></ul>${unscored ? `<p>以下输出包含零值，不能只用相对误差判断：<code>${escapeHtml(unscored)}</code>。请补充绝对误差判据。</p>` : ""}<p>模型卡：<code>${escapeHtml(card.markdown_path || "")}</code></p><p>${validation.passed ? "该模型仅可在模型卡记录的适用范围内用于快速比较，不是工程认证。" : "请补充 COMSOL 样本、调整模型或收紧适用范围后重新训练。"}</p>`);
      return data;
    }

    async function showSurrogateRegistry() {
      const data = await requestGet("/api/surrogates/registry");
      if (!data.ok) {
        addMessage("assistant", summarizeGeneric("代理模型注册表", data));
        return data;
      }
      const entries = ((data.registry || {}).models || []).map(item => {
        const lifecycle = item.lifecycle_status === "superseded"
          ? `<br><span>历史版本，已由 <code>${escapeHtml(item.superseded_by || "")}</code> 替代。</span>`
          : "";
        return `<li><code>${escapeHtml(item.name || item.id || "")}</code>：<strong>${escapeHtml(item.status || "")}</strong><br>ID：<code>${escapeHtml(item.id || "")}</code>${lifecycle}<br><span>${escapeHtml(item.release_note || "")}</span></li>`;
      }).join("");
      addMessage("assistant", `<h3>代理模型注册表</h3><p>路径：<code>${escapeHtml(data.path || "")}</code></p>${entries ? `<ul>${entries}</ul>` : "<p>尚无完成独立 COMSOL 验证的模型记录。</p>"}`);
      return data;
    }

    async function refreshCaseSourceStatus(showMessage = false) {
      const data = await requestGet("/api/case-sources");
      const sources = data.case_sources?.sources || [];
      const source = sources.find(item => item.id === data.case_sources?.default_source_id) || sources[0];
      if (source) {
        const state = source.available
          ? `案例源可读：${source.resolved_path}`
          : `案例源暂不可读：${source.message}`;
        setCaseSyncInfo([state]);
        if (showMessage) addMessage("assistant", `<h3>案例源检测</h3><p>${escapeHtml(state)}</p>`);
      }
      return data;
    }

    function experimentalValidationLabel(report) {
      const state = String(report?.status || "not_started");
      if (state === "passed") return `已通过（${Number(report.sample_count || 0)} 个真实工况）`;
      if (state === "failed") return `未通过（${Number(report.sample_count || 0)} 个真实工况）`;
      if (state === "awaiting_measurements") return "等待真实测量数据";
      if (state === "invalid_report") return "报告损坏，需要重新执行";
      return "尚未开始";
    }

    async function refreshExperimentalValidationStatus(showMessage = false) {
      const element = document.getElementById("experimentalValidationStatus");
      try {
        const data = await requestGet("/api/experimental-validation/status");
        const report = data.experimental_validation || {};
        element.textContent = `实验验证状态：${experimentalValidationLabel(report)}`;
        if (showMessage) {
          addMessage("assistant", `<h3>真实温度实验验证</h3><p><strong>${escapeHtml(experimentalValidationLabel(report))}</strong></p><p>${escapeHtml(report.interpretation || "请填写真实测量、95% 测量不确定度和同工况 COMSOL 值。")}</p><p>报告：<code>${escapeHtml(report.report_path || "")}</code></p>`);
        }
        return data;
      } catch (error) {
        element.textContent = "实验验证状态：读取失败";
        return null;
      }
    }

    async function runExperimentalValidation() {
      const csvPath = document.getElementById("experimentalTemperatureCsv").value.trim();
      const data = await request("/api/experimental-validation/run", {csv_path: csvPath});
      const report = data.experimental_validation || {};
      document.getElementById("experimentalValidationStatus").textContent = `实验验证状态：${experimentalValidationLabel(report)}`;
      const metrics = report.metrics ? `<pre>${escapeHtml(JSON.stringify(report.metrics, null, 2))}</pre>` : "";
      addMessage("assistant", `<h3>实验、COMSOL 与代理模型三方验证</h3><p><strong>${escapeHtml(experimentalValidationLabel(report))}</strong></p><p>${escapeHtml(report.interpretation || "")}</p>${metrics}<p>报告：<code>${escapeHtml(report.report_path || "")}</code></p>`);
      return data;
    }

    async function showClosureAudit() {
      const data = await requestGet("/api/training/closure-audit");
      if (!data.ok) {
        addMessage("assistant", summarizeGeneric("闭环审计", data));
        return data;
      }
      const audit = data.audit || {};
      const gaps = (audit.evidence_gaps || []).map(item => `<li><code>${escapeHtml(item.model_id || "")}</code> 缺少 <code>${escapeHtml(item.missing || "")}</code></li>`).join("");
      const superseded = audit.superseded_models || [];
      const activeUnvalidated = audit.active_unvalidated_models || [];
      addMessage("assistant", `<h3>训练闭环审计</h3><ul><li>计划任务：${escapeHtml(String(audit.task_total || 0))}</li><li>任务状态：<code>${escapeHtml(JSON.stringify(audit.task_statuses || {}))}</code></li><li>注册模型：${escapeHtml(String(audit.registered_models || 0))}</li><li>活动未验证模型：${escapeHtml(String(activeUnvalidated.length))}</li><li>历史替代模型：${escapeHtml(String(superseded.length))}</li><li>可在声明范围内预测：<code>${escapeHtml((audit.ready_for_scoped_prediction || []).join("、") || "无")}</code></li></ul>${gaps ? `<h3>证据缺口</h3><ul>${gaps}</ul>` : ""}<p>${escapeHtml(audit.guidance || "")}</p>`);
      return data;
    }

    async function predictRegisteredSurrogate() {
      const modelId = document.getElementById("registeredModelId").value.trim();
      let inputs;
      try {
        inputs = JSON.parse(document.getElementById("registeredInputs").value);
      } catch (error) {
        addMessage("assistant", "<h3>预测输入格式错误</h3><p>请输入 JSON 对象，例如 {&quot;k&quot;: 16, &quot;Q&quot;: 8000}。</p>");
        return null;
      }
      if (!modelId || !inputs || Array.isArray(inputs) || typeof inputs !== "object") {
        addMessage("assistant", "<h3>缺少预测信息</h3><p>请从注册表填写模型 ID，并提供与模型输入列一致的 JSON 对象。</p>");
        return null;
      }
      const data = await request("/api/surrogates/registered/predict", {model_id: modelId, inputs});
      if (!data.ok) {
        addMessage("assistant", `<h3>不能使用代理预测</h3><p>${escapeHtml(data.guidance || data.error || "该模型未满足受控预测条件。")}</p>`);
        return data;
      }
      const prediction = data.prediction || {};
      addMessage("assistant", `<h3>受控代理预测</h3><ul><li>模型 ID：<code>${escapeHtml(data.model_id || "")}</code></li><li>注册状态：<code>${escapeHtml(data.registry_status || "")}</code></li><li>预测结果：<code>${escapeHtml(JSON.stringify(prediction))}</code></li></ul><p>物理适用范围：${escapeHtml(data.declared_scope || "未记录")}</p><p>${escapeHtml(data.guidance || "")}</p>`);
      return data;
    }

    async function createRegisteredAugmentationPlan() {
      const modelId = document.getElementById("registeredModelId").value.trim();
      let inputs;
      try {
        inputs = JSON.parse(document.getElementById("registeredInputs").value);
      } catch (error) {
        addMessage("assistant", "<h3>补充工况输入格式错误</h3><p>请输入 JSON 对象，并确保字段名称与模型输入列一致。</p>");
        return null;
      }
      const data = await request("/api/surrogates/registered/augmentation-plan", {model_id: modelId, inputs});
      if (!data.ok) {
        addMessage("assistant", `<h3>不能生成补充工况</h3><p>${escapeHtml(data.error || "输入可能尚未越界，或模型未通过独立验证。")}</p>`);
        return data;
      }
      const plan = data.plan || {};
      const rows = (plan.recommended_comsol_samples || []).map((item, index) => `<li>工况 ${index + 1}：<code>${escapeHtml(JSON.stringify(item))}</code></li>`).join("");
      addMessage("assistant", `<h3>补充 COMSOL 工况已生成</h3><p>${escapeHtml(plan.reason || "")}</p><ul>${rows}</ul><p>计划文件：<code>${escapeHtml(plan.path || "")}</code></p><p>该计划需要由模型卡对应的 COMSOL 模板执行，再用新的独立留出集重新验证。</p>`);
      return data;
    }

    async function predictBusbarTemperature() {
      const voltage = Number(document.getElementById("busbarVoltage").value);
      const htc = Number(document.getElementById("busbarHtc").value);
      const data = await request("/api/benchmarks/busbar-joule-heat/predict", {
        Vtot_mV: voltage,
        htc_W_m2K: htc
      });
      if (!data.ok) {
        addMessage("assistant", summarizeGeneric("焦耳热快速预测", data));
        return data;
      }
      const prediction = data.prediction || {};
      const ranges = data.validated_ranges || {};
      addMessage("assistant", `<h3>焦耳热快速预测</h3><p>在 <code>${escapeHtml(voltage)}</code> mV 和 <code>${escapeHtml(htc)}</code> W/(m²·K) 下，预测最高温度为 <strong>${escapeHtml(Number(prediction.Tmax_C).toFixed(2))} °C</strong>。</p><p>独立 COMSOL 验证相对误差：${escapeHtml(Number(data.holdout_relative_error_percent).toFixed(2))}% 。</p><p>适用范围：电压 ${escapeHtml((ranges.Vtot_mV || []).join("-"))} mV；换热系数 ${escapeHtml((ranges.htc_W_m2K || []).join("-"))} W/(m²·K)。</p><p>${escapeHtml(data.guidance || "")}</p>`);
      return data;
    }

    async function refreshP3Status(showMessage = false) {
      try {
        const data = await requestGet("/api/p3/status");
        p3Status = data;
        const finalReport = ((data.reports || {}).final_evaluation || {});
        const counts = finalReport.counts || {};
        const metrics = finalReport.holdout_metrics || {};
        const tmax = metrics.Tmax_K || {};
        document.getElementById("p3ComsolState").textContent = data.comsol_execution_passed ? "80/80 通过" : "未完成";
        document.getElementById("p3BaselineState").textContent = data.baseline_current_A == null
          ? "固定电流基准尚未生成"
          : `基准电流 ${Number(data.baseline_current_A).toFixed(3)} A`;
        document.getElementById("p3ParetoState").textContent = `${Number(data.verified_pareto_count || 0)} 个`;
        document.getElementById("p3SurrogateState").textContent = data.surrogate_release_passed ? "通过" : "未通过，禁止发布";
        document.getElementById("p3EvaluationState").textContent = finalReport.execution_passed
          ? `独立域内 ${Number(counts.domain_holdout || 0)} 个、越界 ${Number(counts.out_of_domain || 0)} 个；Tmax RMSE ${Number(tmax.rmse || 0).toFixed(2)} K。`
          : "独立最终评估尚未完成。";
        if (showMessage) addMessage("assistant", `<h3>P3 设计优化状态</h3><p>${escapeHtml(data.policy || "")}</p><p>真实 COMSOL Pareto 方案：<strong>${escapeHtml(String(data.verified_pareto_count || 0))}</strong> 个；代理模型发布：<strong>${data.surrogate_release_passed ? "通过" : "未通过"}</strong>。</p>`);
        return data;
      } catch (error) {
        document.getElementById("p3ComsolState").textContent = "读取失败";
        if (showMessage) addMessage("assistant", `<p>P3 状态读取失败：${escapeHtml(String(error))}</p>`);
        return null;
      }
    }

    function showP3Evidence() {
      raw.textContent = JSON.stringify(p3Status || {}, null, 2);
      const section = document.getElementById("tool-results");
      if (section) section.open = true;
      addMessage("assistant", "<h3>P3 完整证据</h3><p>结构化报告已显示在右侧“结果与知识库”。其中 COMSOL 闭环、Pareto 验证和代理模型发布状态分别记录，未通过的发布门槛不会被隐藏。</p>");
    }

    async function refreshP4Status(showMessage = false) {
      try {
        const data = await requestGet("/api/p4/status");
        p4Status = data;
        const finalReport = ((data.reports || {}).final_evaluation || {});
        const counts = finalReport.counts || {};
        const metrics = finalReport.holdout_metrics || {};
        const tmax = metrics.Tmax_K || {};
        document.getElementById("p4AdaptiveState").textContent = `${Number(data.adaptive_comsol_cases || 0)}/80 完成`;
        document.getElementById("p4TrainingState").textContent = `最终训练集 ${Number(data.training_rows || 0)} 个真实 COMSOL 样本`;
        document.getElementById("p4ComsolState").textContent = data.comsol_execution_passed ? "80/80 通过" : "未完成";
        document.getElementById("p4AccuracyState").textContent = data.accuracy_passed ? "通过" : "未通过";
        document.getElementById("p4CoverageState").textContent = `${(100 * Number(data.safe_release_coverage || 0)).toFixed(2)}% / 要求 10%`;
        document.getElementById("p4ReleaseState").textContent = data.surrogate_release_passed ? "通过" : "未通过，禁止发布";
        document.getElementById("p4EvaluationState").textContent = finalReport.execution_passed
          ? `独立域内 ${Number(counts.domain_holdout || 0)} 个、越界 ${Number(counts.out_of_domain || 0)} 个；Tmax RMSE ${Number(tmax.rmse || 0).toFixed(2)} K。`
          : "独立最终评估尚未完成。";
        if (showMessage) addMessage("assistant", `<h3>P4 自适应代理修复状态</h3><p>${escapeHtml(data.policy || "")}</p><p>预测精度：<strong>${data.accuracy_passed ? "通过" : "未通过"}</strong>；安全放行覆盖率：<strong>${escapeHtml((100 * Number(data.safe_release_coverage || 0)).toFixed(2))}%</strong>；代理发布：<strong>${data.surrogate_release_passed ? "通过" : "未通过"}</strong>。</p>`);
        return data;
      } catch (error) {
        document.getElementById("p4ComsolState").textContent = "读取失败";
        if (showMessage) addMessage("assistant", `<p>P4 状态读取失败：${escapeHtml(String(error))}</p>`);
        return null;
      }
    }

    function showP4Evidence() {
      raw.textContent = JSON.stringify(p4Status || {}, null, 2);
      const section = document.getElementById("tool-results");
      if (section) section.open = true;
      addMessage("assistant", "<h3>P4 完整证据</h3><p>结构化报告已显示在右侧“结果与知识库”。精度门、越界检测、区间覆盖、安全放行覆盖和最终发布结论分别记录。</p>");
    }

    async function refreshP5Status(showMessage = false) {
      try {
        const data = await requestGet("/api/p5/status");
        p5Status = data;
        const finalReport = ((data.reports || {}).final_evaluation || {});
        const metrics = finalReport.holdout_metrics || {};
        const tmax = metrics.Tmax_K || {};
        document.getElementById("p5MethodState").textContent = data.calibration_method === "normalized_one_sided"
          ? "局部缩放单侧 95% 上界"
          : (data.calibration_method || "未冻结");
        document.getElementById("p5ComsolState").textContent = data.comsol_execution_passed ? "80/80 通过" : "未完成";
        document.getElementById("p5CoverageState").textContent = `${Number(data.released_safe_count || 0)}/60，${(100 * Number(data.safe_release_coverage || 0)).toFixed(2)}%`;
        document.getElementById("p5FalseSafeState").textContent = `${Number(data.false_safe_count || 0)} 个`;
        document.getElementById("p5ReleaseState").textContent = data.surrogate_release_passed ? "通过，受控开放" : "未通过，禁止发布";
        document.getElementById("p5EvaluationState").textContent = finalReport.execution_passed
          ? `Tmax RMSE ${Number(tmax.rmse || 0).toFixed(2)} K；域外 AUROC ${Number((finalReport.ood || {}).auroc || 0).toFixed(3)}。`
          : "P5 独立最终评估尚未完成。";
        if (showMessage) addMessage("assistant", `<h3>P5 单侧安全校准状态</h3><p>${escapeHtml(data.policy || "")}</p><p>安全放行：<strong>${escapeHtml(String(data.released_safe_count || 0))}/60</strong>；false-safe：<strong>${escapeHtml(String(data.false_safe_count || 0))}</strong>；代理发布：<strong>${data.surrogate_release_passed ? "通过" : "未通过"}</strong>。</p>`);
        return data;
      } catch (error) {
        document.getElementById("p5ComsolState").textContent = "读取失败";
        if (showMessage) addMessage("assistant", `<p>P5 状态读取失败：${escapeHtml(String(error))}</p>`);
        return null;
      }
    }

    function showP5Evidence() {
      raw.textContent = JSON.stringify(p5Status || {}, null, 2);
      const section = document.getElementById("tool-results");
      if (section) section.open = true;
      addMessage("assistant", "<h3>P5 完整证据</h3><p>结构化报告已显示在右侧“结果与知识库”。封存哈希、单侧上界覆盖、安全放行、false-safe 和发布结论均可核查。</p>");
    }

    async function refreshP6Status(showMessage = false) {
      try {
        const data = await requestGet("/api/p6/status");
        p6Status = data;
        const gates = data.gates || {};
        const javaEvidence = data.java || {};
        const experiment = data.experiment || {};
        const baseline = data.baseline_comparison || {};
        document.getElementById("p6JavaState").textContent = gates.java_dual_path
          ? `${Number(javaEvidence.java_verified_count || 0)}/6 通过`
          : "未完成";
        document.getElementById("p6LocalState").textContent = gates.current_host_preflight ? "通过" : "未通过";
        document.getElementById("p6ExperimentState").textContent = gates.temperature_experiment
          ? "通过"
          : `${Number(experiment.sample_count || 0)}/${Number(experiment.minimum_required || 5)}，等待测量`;
        document.getElementById("p6BaselineState").textContent = gates.fixed_task_external_comparison
          ? "完整"
          : `${Number(baseline.measured_row_count || 0)}/${Number(baseline.required_rows || 180)}，等待记录`;
        document.getElementById("p6DestinationState").textContent = gates.destination_host_acceptance ? "通过" : "等待目标电脑";
        document.getElementById("p6ReleaseState").textContent = data.publication_external_gate_passed ? "通过" : "等待外部证据";
        document.getElementById("p6EvidenceState").textContent = data.local_readiness_passed
          ? "本机准备已完成；缺失外部证据不会被模板或合成数据替代。"
          : "本机 P6 准备尚未完成。";
        if (showMessage) addMessage("assistant", `<h3>P6 状态</h3><p>Java 双路径：<strong>${gates.java_dual_path ? "通过" : "未通过"}</strong>；本机准备：<strong>${data.local_readiness_passed ? "通过" : "未通过"}</strong>；外部证据门：<strong>${data.publication_external_gate_passed ? "通过" : "等待数据"}</strong>。</p>`);
        return data;
      } catch (error) {
        document.getElementById("p6ReleaseState").textContent = "读取失败";
        if (showMessage) addMessage("assistant", `<p>P6 状态读取失败：${escapeHtml(String(error))}</p>`);
        return null;
      }
    }

    function showP6Evidence() {
      raw.textContent = JSON.stringify(p6Status || {}, null, 2);
      const section = document.getElementById("tool-results");
      if (section) section.open = true;
      addMessage("assistant", "<h3>P6 完整证据</h3><p>Java、实物实验、固定任务外部对照和目标电脑验收分别显示，未完成项不会被标记为通过。</p>");
    }

    async function refreshP7Status(showMessage = false) {
      try {
        const data = await requestGet("/api/p7/status");
        p7Status = data;
        const gates = data.gates || {};
        document.getElementById("p7MainState").textContent = `${Number(data.passed_main_case_count || 0)}/${Number(data.main_case_count || 0)} 通过`;
        document.getElementById("p7PhysicsState").textContent = `${Number(data.physics_family_count || 0)} 类`;
        document.getElementById("p7HoldoutState").textContent = gates.all_main_holdouts_independent ? "全部无重叠" : "未通过";
        document.getElementById("p7ExtensionState").textContent = `${Number(data.passed_extension_case_count || 0)}/${Number(data.extension_case_count || 0)} 通过`;
        document.getElementById("p7ReleaseState").textContent = data.p7_completed ? "通过" : "需要补证据";
        document.getElementById("p7EvidenceState").textContent = data.p7_completed
          ? "四个主案例已通过统一证据合同；各案例的证据等级、误差门限、哈希和样本独立性可核查。"
          : "P7 多案例验收尚未完成。";
        if (showMessage) {
          addMessage("assistant", `<h3>P7 多案例状态</h3><p>主案例：<strong>${escapeHtml(String(data.passed_main_case_count || 0))}/${escapeHtml(String(data.main_case_count || 0))}</strong>；物理类型：<strong>${escapeHtml(String(data.physics_family_count || 0))}</strong>；P7 验收：<strong>${data.p7_completed ? "通过" : "未通过"}</strong>。</p><p>本结果不改变 P6 的实物实验、人工对照和目标电脑验收状态。</p>`);
        }
        return data;
      } catch (error) {
        document.getElementById("p7ReleaseState").textContent = "读取失败";
        if (showMessage) addMessage("assistant", `<p>P7 状态读取失败：${escapeHtml(String(error))}</p>`);
        return null;
      }
    }

    function showP7Evidence() {
      raw.textContent = JSON.stringify(p7Status || {}, null, 2);
      const section = document.getElementById("tool-results");
      if (section) section.open = true;
      addMessage("assistant", "<h3>P7 完整证据</h3><p>结构化报告显示每个案例的证据等级、物理类型、训练与保留样本数、输入重叠检查、验证门限和文件 SHA-256。</p>");
    }

    async function refreshDacP0Status(showMessage = false) {
      try {
        const data = await requestGet("/api/dac2027/p0/status");
        dacP0Status = data;
        document.getElementById("dacP0AuthorState").textContent = `${Number(data.author_submissions || 0)}/24`;
        document.getElementById("dacP0JudgeState").textContent = `${Number(data.adjudicator_submissions || 0)}/24`;
        document.getElementById("dacP0TaskState").textContent = `${Number(data.measured_blind_tasks || 0)}/24`;
        document.getElementById("dacP0ResponseState").textContent = `${Number(data.measured_responses || 0)}/96`;
        document.getElementById("dacP0GateState").textContent = data.publication_gate_passed ? "通过" : "采集中";
        document.getElementById("dacP0NextState").textContent = data.next_action || "等待第三方记录。";
        if (showMessage) {
          const counts = data.measured_responses_by_method || {};
          addMessage("assistant", `<h3>DAC P0 实时状态</h3><p>外部作者：<strong>${Number(data.author_submissions || 0)}/24</strong>；独立裁决：<strong>${Number(data.adjudicator_submissions || 0)}/24</strong>；密封任务：<strong>${Number(data.measured_blind_tasks || 0)}/24</strong>；方法观测：<strong>${Number(data.measured_responses || 0)}/96</strong>。</p><p>Direct LLM ${Number(counts.direct_llm || 0)}/24，Retrieval LLM ${Number(counts.retrieval_llm || 0)}/24，Existing Selector ${Number(counts.existing_selector || 0)}/24，Contract Dependency v1.1 ${Number(counts.contract_dependency_v11 || 0)}/24。</p><p><strong>下一步：</strong>${escapeHtml(data.next_action || "")}</p>`);
        }
        return data;
      } catch (error) {
        document.getElementById("dacP0GateState").textContent = "读取失败";
        if (showMessage) addMessage("assistant", `<p>DAC P0 状态读取失败：${escapeHtml(String(error))}</p>`);
        return null;
      }
    }

    function openDacP0Intake() {
      const url = (dacP0Status && dacP0Status.intake_url) || "http://127.0.0.1:8891/";
      window.open(url, "_blank", "noopener");
      addMessage("assistant", `<p>已打开第三方盲测采集入口：<code>${escapeHtml(url)}</code>。请分别交给项目组外作者和不同裁决者填写，提交后返回这里刷新状态。</p>`);
    }

    function showDacP0Evidence() {
      raw.textContent = JSON.stringify(dacP0Status || {}, null, 2);
      const section = document.getElementById("tool-results");
      if (section) section.open = true;
      addMessage("assistant", "<h3>P0 判定规则</h3><ol><li>8 个器件族，每族包含完整、缺失和冲突三条需求，共 24 条。</li><li>作者必须来自项目团队之外；每条需求由不同 ID 的人员独立裁决。</li><li>24 条任务全部密封后，四种方法在相同文本和相同 JSON 输出合同下各运行 24 次。</li><li>只有 24 条有效任务和 96 条完整实测同时通过校验，P0 论文证据门才会通过。</li></ol>");
    }

    async function refreshDacP2Status(showMessage = false) {
      try {
        const data = await requestGet("/api/dac2027/p2/status");
        dacP2Status = data;
        const counts = data.measured_responses_by_method || {};
        document.getElementById("dacP2TaskState").textContent = `${Number(data.task_count || 0)}/24`;
        document.getElementById("dacP2ResponseState").textContent = `${Number(data.measured_response_count || 0)}/96`;
        document.getElementById("dacP2AblationState").textContent = data.ablation_completed ? "3/3 完成" : "未完成";
        document.getElementById("dacP2DevelopmentState").textContent = data.p2_development_gate_passed ? "通过" : "等待 LLM 实测";
        document.getElementById("dacP2PublicationState").textContent = data.publication_external_gate_passed ? "通过" : "等待第三方复跑";
        document.getElementById("dacP2EvidenceState").textContent = data.controlled_comparison_completed
          ? "四种方法已在同一冻结任务集上完成；结果仍属于项目内部开发证据。"
          : `Direct LLM ${Number(counts.direct_llm || 0)}/24，Retrieval LLM ${Number(counts.retrieval_llm || 0)}/24，现有选择器 ${Number(counts.existing_selector || 0)}/24，完整方法 ${Number(counts.contract_dependency_v11 || 0)}/24。`;
        if (showMessage) {
          addMessage("assistant", `<h3>DAC P2 状态</h3><p>冻结任务：<strong>${Number(data.task_count || 0)}/24</strong>；四方法记录：<strong>${Number(data.measured_response_count || 0)}/96</strong>；消融：<strong>${data.ablation_completed ? "3/3 完成" : "未完成"}</strong>。</p><p>Direct LLM ${Number(counts.direct_llm || 0)}/24，Retrieval LLM ${Number(counts.retrieval_llm || 0)}/24，现有选择器 ${Number(counts.existing_selector || 0)}/24，完整方法 ${Number(counts.contract_dependency_v11 || 0)}/24。</p><p>开发证据门：<strong>${data.p2_development_gate_passed ? "通过" : "未通过"}</strong>；第三方主结果门：<strong>${data.publication_external_gate_passed ? "通过" : "等待 P0 密封任务复跑"}</strong>。</p>`);
        }
        return data;
      } catch (error) {
        document.getElementById("dacP2DevelopmentState").textContent = "读取失败";
        if (showMessage) addMessage("assistant", `<p>DAC P2 状态读取失败：${escapeHtml(String(error))}</p>`);
        return null;
      }
    }

    function showDacP2Evidence() {
      raw.textContent = JSON.stringify(dacP2Status || {}, null, 2);
      const section = document.getElementById("tool-results");
      if (section) section.open = true;
      addMessage("assistant", "<h3>P2 证据边界</h3><p>本轮固定任务文本、JSON 输出合同、LLM 模型与推理强度，并记录所有原始输出和耗时。当前任务由项目组编写，因此只用于方法开发与管线验证；独立主结果必须等待 P0 第三方任务密封后按同一协议复跑。</p>");
    }

    async function refreshDacP3Status(showMessage = false) {
      try {
        const data = await requestGet("/api/dac2027/p3/status");
        dacP3Status = data;
        document.getElementById("dacP3InfrastructureState").textContent = data.p3_infrastructure_gate_passed ? "通过" : "未完成";
        document.getElementById("dacP3TaskState").textContent = `${Number(data.accepted_task_count || 0)}/${Number(data.required_task_count || 24)}${data.sealed_external_tasks ? " 已密封" : ""}`;
        document.getElementById("dacP3IsolationState").textContent = data.case_family_disjoint
          ? `${Number(data.accepted_family_count || 0)}/${Number(data.required_family_count || 8)} 通过`
          : "等待外部案例";
        document.getElementById("dacP3ResponseState").textContent = `${Number(data.measured_observation_count || 0)}/${Number(data.required_observation_count || 192)}`;
        document.getElementById("dacP3MainState").textContent = data.p3_main_result_gate_passed ? "通过" : "等待真实证据";
        document.getElementById("dacP3EvidenceState").textContent = data.next_action || "等待第三方盲测任务。";
        if (showMessage) {
          addMessage("assistant", `<h3>DAC P3 状态</h3><p>基础设施门：<strong>${data.p3_infrastructure_gate_passed ? "通过" : "未通过"}</strong>；外部任务：<strong>${Number(data.accepted_task_count || 0)}/${Number(data.required_task_count || 24)}</strong>；新案例族：<strong>${Number(data.accepted_family_count || 0)}/${Number(data.required_family_count || 8)}</strong>；重复观测：<strong>${Number(data.measured_observation_count || 0)}/${Number(data.required_observation_count || 192)}</strong>。</p><p>主结果门：<strong>${data.p3_main_result_gate_passed ? "通过" : "未通过"}</strong>。</p><p><strong>下一步：</strong>${escapeHtml(data.next_action || "")}</p>`);
        }
        return data;
      } catch (error) {
        document.getElementById("dacP3MainState").textContent = "读取失败";
        if (showMessage) addMessage("assistant", `<p>DAC P3 状态读取失败：${escapeHtml(String(error))}</p>`);
        return null;
      }
    }

    function showDacP3Evidence() {
      raw.textContent = JSON.stringify(dacP3Status || {}, null, 2);
      const section = document.getElementById("tool-results");
      if (section) section.open = true;
      addMessage("assistant", "<h3>P3 评测规则</h3><ol><li>24 条需求必须由项目组外作者编写，并由不同人员裁决。</li><li>8 个案例族不得与开发、验证或 P2 集合重叠。</li><li>任务先按 SHA-256 密封，再运行方法，密封后禁止改动方法。</li><li>Direct LLM 与 Retrieval LLM 各独立重复 3 次；确定性方法各运行 1 次，共 192 条观测。</li><li>报告任务共识、重复一致性、案例级结果、Wilson 95% 区间、McNemar 检验和失败分类。</li></ol>");
    }

    async function refreshDacP4Status(showMessage = false) {
      try {
        const data = await requestGet("/api/dac2027/p4/status");
        dacP4Status = data;
        const paper = data.paper || {};
        document.getElementById("dacP4FormatState").textContent = data.format_and_page_gate_passed
          ? `${Number(paper.body_page_count || 0)} 页正文 + ${Number(paper.reference_page_count || 0)} 页参考文献`
          : "未通过";
        document.getElementById("dacP4BlindState").textContent = data.double_blind_gate_passed ? "通过" : "未通过";
        document.getElementById("dacP4WritingState").textContent = data.related_work_matrix_completed && data.ai_content_statement_completed ? "完成" : "未完成";
        document.getElementById("dacP4PackageState").textContent = data.reproducibility_package_passed
          ? `${Number((data.reproducibility || {}).checked_file_count || 0)} 个文件通过`
          : "未通过";
        document.getElementById("dacP4ExternalState").textContent = data.p3_external_main_result_gate_passed
          ? "通过"
          : `${Number(data.accepted_external_task_count || 0)}/${Number(data.required_external_task_count || 24)} 任务，${Number(data.measured_external_observation_count || 0)}/${Number(data.required_external_observation_count || 192)} 观测`;
        document.getElementById("dacP4InfrastructureState").textContent = data.p4_infrastructure_gate_passed ? "通过" : "未通过";
        document.getElementById("dacP4FinalState").textContent = data.p4_final_submission_gate_passed ? "通过" : "等待 P3 与作者批准";
        document.getElementById("dacP4EvidenceState").textContent = data.next_action || "等待投稿证据。";
        if (showMessage) {
          addMessage("assistant", `<h3>DAC P4 状态</h3><p>稿件：<strong>${Number(paper.body_page_count || 0)} 页正文 + ${Number(paper.reference_page_count || 0)} 页参考文献</strong>；双盲：<strong>${data.double_blind_gate_passed ? "通过" : "未通过"}</strong>；匿名复现包：<strong>${data.reproducibility_package_passed ? "通过" : "未通过"}</strong>。</p><p>本机基础设施门：<strong>${data.p4_infrastructure_gate_passed ? "通过" : "未通过"}</strong>；最终投稿门：<strong>${data.p4_final_submission_gate_passed ? "通过" : "等待 P3 外部结果与作者人工批准"}</strong>。</p><p><strong>下一步：</strong>${escapeHtml(data.next_action || "")}</p>`);
        }
        return data;
      } catch (error) {
        document.getElementById("dacP4FinalState").textContent = "读取失败";
        if (showMessage) addMessage("assistant", `<p>DAC P4 状态读取失败：${escapeHtml(String(error))}</p>`);
        return null;
      }
    }

    function showDacP4Evidence() {
      raw.textContent = JSON.stringify(dacP4Status || {}, null, 2);
      const section = document.getElementById("tool-results");
      if (section) section.open = true;
      addMessage("assistant", "<h3>P4 投稿边界</h3><ol><li>稿件必须满足 Letter、双栏、6 页以内正文加 1 页参考文献，并通过匿名标题、元数据和个人路径扫描。</li><li>相关工作、AI 内容声明和匿名复现包均由机器状态单独验证。</li><li>P1 与 P2 只支持本机场景和开发集结论。</li><li>P3 达到 24 条外部任务、8 个隔离案例族和 192 条观测后，才可加入独立主结果。</li><li>最终 PDF 仍需作者逐条核对并记录人工批准。</li></ol>");
    }

    async function prepareDacP3() {
      const button = document.activeElement;
      if (button instanceof HTMLButtonElement) button.disabled = true;
      try {
        const data = await request("/api/dac2027/p3/prepare", {});
        raw.textContent = JSON.stringify(data, null, 2);
        const section = document.getElementById("tool-results");
        if (section) section.open = true;
        addMessage(
          "assistant",
          `<h3>P3 校验与密封</h3><p>${escapeHtml(data.message || "操作完成。")}</p>` +
          (data.sealed
            ? "<p><strong>密封成功。</strong>现在可以按冻结协议启动 192 条方法观测。</p>"
            : "<p>没有生成可用于论文主结果的密封证据。</p>")
        );
        await refreshDacP3Status(false);
      } catch (error) {
        addMessage("assistant", `<p>P3 校验与密封失败：${escapeHtml(String(error))}</p>`);
      } finally {
        if (button instanceof HTMLButtonElement) button.disabled = false;
      }
    }

    async function refreshDacP1Status(showMessage = false) {
      try {
        const data = await requestGet("/api/dac2027/p1/status");
        dacP1Status = data;
        document.getElementById("dacP1ScenarioState").textContent = `${Number(data.definition_ready_count || 0)}/${Number(data.primary_scenario_count || 0)} 完整`;
        document.getElementById("dacP1StageState").textContent = `${Number(data.eda_stage_count || 0)} 个`;
        document.getElementById("dacP1DefinitionState").textContent = data.p1_definition_completed ? "通过" : "未通过";
        document.getElementById("dacP1FreshState").textContent = `${Number(data.fresh_post_freeze_count || 0)}/2`;
        document.getElementById("dacP1SubmissionState").textContent = data.submission_two_case_experiment_completed ? "通过" : "等待新实验";
        document.getElementById("dacP1EvidenceState").textContent = data.submission_two_case_experiment_completed
          ? "母排与 MEMS 均已按冻结合同完成新 COMSOL 求解，MPH、CSV、日志、判据和文件哈希验证通过。"
          : (data.p1_definition_completed
            ? "母排与 MEMS 场景已冻结输入、约束、输出、物理场、决策和停止条件；仍需完成未通过的新 COMSOL 运行。"
            : "P1 场景合同尚未完成。");
        if (showMessage) {
          addMessage("assistant", `<h3>DAC P1 状态</h3><p>场景定义：<strong>${escapeHtml(String(data.definition_ready_count || 0))}/${escapeHtml(String(data.primary_scenario_count || 0))}</strong>；任务定义门：<strong>${data.p1_definition_completed ? "通过" : "未通过"}</strong>；冻结后新实验：<strong>${escapeHtml(String(data.fresh_post_freeze_count || 0))}/2</strong>。</p><p>投稿实验门：<strong>${data.submission_two_case_experiment_completed ? "通过" : "等待新实验"}</strong>。每项新实验都必须通过报告时间、场景编号、MPH、CSV、日志和哈希检查。</p>`);
        }
        return data;
      } catch (error) {
        document.getElementById("dacP1DefinitionState").textContent = "读取失败";
        if (showMessage) addMessage("assistant", `<p>DAC P1 状态读取失败：${escapeHtml(String(error))}</p>`);
        return null;
      }
    }

    function showDacP1Evidence() {
      raw.textContent = JSON.stringify(dacP1Status || {}, null, 2);
      const section = document.getElementById("tool-results");
      if (section) section.open = true;
      addMessage("assistant", "<h3>DAC P1 完整证据</h3><p>报告列出两个场景的设计变量、约束、输出、物理计划、工程决策、停止条件、证据等级和文件哈希，并单列冻结后的新实验门。</p>");
    }

    function setToolsCollapsed(collapsed) {
      const app = document.querySelector(".app");
      const toggle = document.getElementById("toolsToggle");
      if (!app || !toggle) return;
      app.classList.toggle("tools-collapsed", collapsed);
      toggle.textContent = collapsed ? "\u2039" : "\u203a";
      toggle.setAttribute("aria-expanded", String(!collapsed));
      toggle.setAttribute("aria-label", collapsed ? "\u5c55\u5f00\u53f3\u4fa7\u680f" : "\u6536\u56de\u53f3\u4fa7\u680f");
      toggle.title = collapsed ? "\u5c55\u5f00\u53f3\u4fa7\u680f" : "\u6536\u56de\u53f3\u4fa7\u680f";
    }

    function toggleToolsPanel() {
      const app = document.querySelector(".app");
      setToolsCollapsed(!app?.classList.contains("tools-collapsed"));
    }

    function initializeToolsPanel() {
      setToolsCollapsed(false);
      const groups = Array.from(document.querySelectorAll(".tool-section[data-tool-group]"));
      const saved = window.localStorage.getItem("comsol-tool-groups");
      let state = {};
      try { state = saved ? JSON.parse(saved) : {}; } catch (error) { state = {}; }
      groups.forEach(group => {
        const key = group.dataset.toolGroup;
        if (Object.prototype.hasOwnProperty.call(state, key)) group.open = Boolean(state[key]);
        group.addEventListener("toggle", () => {
          const next = {};
          groups.forEach(item => { next[item.dataset.toolGroup] = item.open; });
          window.localStorage.setItem("comsol-tool-groups", JSON.stringify(next));
        });
      });
    }

    document.getElementById("prompt").addEventListener("keydown", event => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        sendPrompt();
      }
    });

    addWelcome();
    initializeToolsPanel();
    initializeCaseFieldSync();
    initializeObserver3dControls();
    loadAssistantConfig();
    loadDefaults();
    refreshNodeStatus();
    refreshExperimentalValidationStatus(false);
    refreshCaseSourceStatus(false);
    refreshComsolObserver(false);
    refreshP3Status(false);
    refreshP4Status(false);
    refreshP5Status(false);
    refreshP6Status(false);
    refreshP7Status(false);
    refreshDacP0Status(false);
    refreshDacP1Status(false);
    refreshDacP2Status(false);
    refreshDacP3Status(false);
    refreshDacP4Status(false);
    window.setInterval(refreshNodeStatus, 15000);
    window.setInterval(() => refreshComsolObserver(false), 5000);
    window.setInterval(() => refreshDacP0Status(false), 10000);
    window.setInterval(() => refreshDacP2Status(false), 10000);
    window.setInterval(() => refreshDacP3Status(false), 10000);
    window.setInterval(() => refreshDacP4Status(false), 15000);
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    run(host=args.host, port=args.port, open_browser=args.open)
