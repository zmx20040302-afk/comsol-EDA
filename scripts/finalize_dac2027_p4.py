from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
P3_STATUS_PATH = ROOT / "generated" / "dac2027" / "p3" / "readiness_status.json"
P4_STATUS_PATH = ROOT / "generated" / "dac2027" / "p4" / "readiness_status.json"
PDF_PATH = ROOT / "paper_draft" / "dac2027_contract_guided_comsol_submission.pdf"
APPROVAL_PATH = ROOT / "generated" / "dac2027" / "p4" / "human_author_approval.json"
APPROVAL_TEMPLATE_PATH = ROOT / "generated" / "dac2027" / "p4" / "human_author_approval.template.json"
FINALIZATION_STATUS_PATH = ROOT / "generated" / "dac2027" / "p4" / "finalization_status.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def verified_p3_report(root: Path, readiness: dict) -> tuple[Path | None, str]:
    if not readiness.get("p3_main_result_gate_passed"):
        return None, "P3 main-result gate is closed"
    relative = str(readiness.get("report_path") or "").strip()
    expected = str(readiness.get("report_sha256") or "").strip().lower()
    report_path = root / relative if relative else Path()
    if not relative or not report_path.is_file():
        return None, "P3 report is missing"
    if not expected or sha256(report_path) != expected:
        return None, "P3 report hash does not match readiness state"
    report = load_json(report_path)
    if not report.get("publication_main_result"):
        return None, "P3 report is not marked as a publication main result"
    required = {
        "task_count": 24,
        "family_count": 8,
        "measured_observation_count": 192,
        "expected_observation_count": 192,
    }
    for field, expected_value in required.items():
        if int(report.get(field, 0) or 0) != expected_value:
            return None, f"P3 report {field} must equal {expected_value}"
    return report_path, ""


def approval_template(pdf_hash: str, p3_hash: str) -> dict[str, object]:
    return {
        "schema": "dac2027-p4-human-author-approval",
        "schemaVersion": "1.0.0",
        "approved": False,
        "approved_by": "",
        "approved_at": "",
        "manuscript_pdf_sha256": pdf_hash,
        "p3_report_sha256": p3_hash,
        "checks": {
            "claims_verified": False,
            "citations_verified": False,
            "double_blind_verified": False,
            "conflicts_verified": False,
            "ai_statement_verified": False,
            "authorship_verified": False,
        },
        "notes": "Review the final PDF and sealed P3 report. Set every check and approved to true, then record the human approver and ISO 8601 timestamp.",
    }


def build_finalization_status(root: Path = ROOT) -> dict[str, object]:
    p3 = load_json(root / P3_STATUS_PATH.relative_to(ROOT))
    p4 = load_json(root / P4_STATUS_PATH.relative_to(ROOT))
    pdf_path = root / PDF_PATH.relative_to(ROOT)
    report_path, error = verified_p3_report(root, p3)
    base = {
        "schema": "dac2027-p4-finalization-status",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "phase": "DAC2027-P4",
        "p3_task_count": int(p3.get("accepted_task_count", 0) or 0),
        "p3_required_task_count": int(p3.get("required_task_count", 24) or 24),
        "p3_observation_count": int(p3.get("measured_observation_count", 0) or 0),
        "p3_required_observation_count": int(p3.get("required_observation_count", 192) or 192),
        "p4_infrastructure_gate_passed": bool(p4.get("p4_infrastructure_gate_passed")),
        "p4_final_submission_gate_passed": bool(p4.get("p4_final_submission_gate_passed")),
    }
    if report_path is None:
        return {
            **base,
            "status": "blocked_by_external_evidence",
            "finalization_ready": False,
            "approval_template_generated": False,
            "reason": error,
            "next_action": "完成并密封 P3 的 24 条外部任务、8 个隔离案例族和 192 条真实观测。当前流程不会生成或代填作者批准。",
        }
    if not pdf_path.is_file():
        return {
            **base,
            "status": "blocked_by_missing_manuscript_pdf",
            "finalization_ready": False,
            "approval_template_generated": False,
            "reason": "Final manuscript PDF is missing",
            "next_action": "用稿件生成器写入封存 P3 结果并导出最终匿名 PDF。",
        }

    template = approval_template(sha256(pdf_path), sha256(report_path))
    template_path = root / APPROVAL_TEMPLATE_PATH.relative_to(ROOT)
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    approval_exists = (root / APPROVAL_PATH.relative_to(ROOT)).is_file()
    completed = bool(p4.get("p4_final_submission_gate_passed"))
    return {
        **base,
        "status": "completed" if completed else "awaiting_human_author_approval",
        "finalization_ready": True,
        "approval_template_generated": True,
        "approval_template_path": APPROVAL_TEMPLATE_PATH.relative_to(ROOT).as_posix(),
        "approval_record_exists": approval_exists,
        "manuscript_pdf_sha256": template["manuscript_pdf_sha256"],
        "p3_report_sha256": template["p3_report_sha256"],
        "reason": "" if completed else "A human author must complete every approval check against these exact hashes",
        "next_action": "投稿门已通过。" if completed else "作者核对最终 PDF、P3 主结果、引用、双盲、冲突、作者和 AI 声明后，再保存签署记录。",
    }


def main() -> int:
    status = build_finalization_status()
    FINALIZATION_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    FINALIZATION_STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
