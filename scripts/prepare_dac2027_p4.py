from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "dac2027_p4_submission.json"
PDF_PATH = ROOT / "paper_draft" / "dac2027_contract_guided_comsol_submission.pdf"
PACKAGE_MANIFEST_PATH = ROOT / "generated" / "dac2027" / "p4" / "reproducibility" / "manifest.json"
STATUS_PATH = ROOT / "generated" / "dac2027" / "p4" / "readiness_status.json"
APPROVAL_PATH = ROOT / "generated" / "dac2027" / "p4" / "human_author_approval.json"
REQUIRED_APPROVAL_CHECKS = (
    "claims_verified",
    "citations_verified",
    "double_blind_verified",
    "conflicts_verified",
    "ai_statement_verified",
    "authorship_verified",
)


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


def validate_human_approval(approval: dict, pdf_sha256: str, p3_report_sha256: str) -> dict[str, object]:
    checks = approval.get("checks", {}) if isinstance(approval.get("checks"), dict) else {}
    check_state = {name: checks.get(name) is True for name in REQUIRED_APPROVAL_CHECKS}
    fields = {
        "approved": approval.get("approved") is True,
        "approved_by": bool(str(approval.get("approved_by") or "").strip()),
        "approved_at": bool(str(approval.get("approved_at") or "").strip()),
        "manuscript_pdf_sha256": bool(pdf_sha256) and approval.get("manuscript_pdf_sha256") == pdf_sha256,
        "p3_report_sha256": bool(p3_report_sha256) and approval.get("p3_report_sha256") == p3_report_sha256,
    }
    errors = [name for name, passed in {**fields, **check_state}.items() if not passed]
    return {"passed": not errors, "fields": fields, "checks": check_state, "errors": errors}


def verify_reproducibility_package(manifest_path: Path = PACKAGE_MANIFEST_PATH) -> dict[str, object]:
    manifest = load_json(manifest_path)
    archive_info = manifest.get("archive", {}) if isinstance(manifest, dict) else {}
    archive_path = ROOT / str(archive_info.get("path", "")) if archive_info else Path()
    errors: list[str] = []
    anonymity_hits: list[str] = []
    checked = 0
    if not manifest:
        errors.append("missing or invalid package manifest")
    elif not archive_path.is_file():
        errors.append("missing reproducibility archive")
    elif sha256(archive_path) != archive_info.get("sha256"):
        errors.append("archive SHA-256 does not match manifest")
    else:
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            for item in manifest.get("files", []):
                relative = str(item.get("path", ""))
                if relative not in names:
                    errors.append(f"archive missing {relative}")
                    continue
                payload = archive.read(relative)
                actual = hashlib.sha256(payload).hexdigest()
                if actual != item.get("sha256"):
                    errors.append(f"hash mismatch for {relative}")
                else:
                    checked += 1
                if Path(relative).suffix.lower() in {".json", ".jsonl", ".md", ".py", ".txt", ".csv"}:
                    text = payload.decode("utf-8", errors="ignore")
                    username = os.environ.get("USERNAME", "").strip()
                    sensitive_literals = [str(Path.home())]
                    if len(username) >= 3:
                        sensitive_literals.extend([username, f"C:\\Users\\{username}", f"/home/{username}"])
                    for marker in sensitive_literals:
                        if marker and marker.casefold() in text.casefold():
                            anonymity_hits.append(f"{relative}: local identity marker")
                    if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text):
                        anonymity_hits.append(f"{relative}: email marker")
            if "MANIFEST.json" not in names:
                errors.append("archive missing MANIFEST.json")
    if anonymity_hits:
        errors.append("anonymous package contains personal path, account name, or email markers")
    return {
        "passed": not errors,
        "checked_file_count": checked,
        "anonymous_scan_passed": not anonymity_hits,
        "anonymous_scan_hits": anonymity_hits,
        "archive_path": archive_info.get("path", ""),
        "archive_sha256": archive_info.get("sha256", ""),
        "errors": errors,
    }


def inspect_pdf(pdf_path: Path = PDF_PATH) -> dict[str, object]:
    if not pdf_path.is_file():
        return {"passed": False, "errors": ["manuscript PDF is missing"]}
    reader = PdfReader(str(pdf_path))
    texts = [(page.extract_text() or "") for page in reader.pages]
    page_sizes = [
        [round(float(page.mediabox.width), 2), round(float(page.mediabox.height), 2)]
        for page in reader.pages
    ]
    reference_pages = [index + 1 for index, text in enumerate(texts) if re.search(r"(^|\n)\s*REFERENCES\s*($|\n)", text)]
    reference_start = reference_pages[0] if reference_pages else 0
    body_pages = reference_start - 1 if reference_start else len(texts)
    reference_page_count = len(texts) - body_pages
    body_text = "\n".join(texts[:body_pages])
    metadata = reader.metadata or {}

    required_markers = {
        "abstract": "Abstract" in body_text,
        "introduction": "INTRODUCTION" in body_text,
        "contract_compiler": "CONTRACT GUIDED COMPILATION" in body_text,
        "evaluation": "DEVELOPMENT EVALUATION" in body_text,
        "related_work": "RELATED WORK" in body_text,
        "limitations": "Limitations and submission gate" in body_text,
        "ai_disclosure": "Content Generated by AI" in body_text,
        "conclusion": "Conclusion" in body_text,
        "references": bool(reference_pages),
    }
    letter = all(abs(width - 612) <= 1 and abs(height - 792) <= 1 for width, height in page_sizes)
    anonymous_title = "Anonymous submission" in body_text
    metadata_author = str(metadata.get("/Author") or "").strip()
    metadata_creator = str(metadata.get("/Creator") or "").strip()
    username = os.environ.get("USERNAME", "").strip()
    sensitive_literals = [str(Path.home())]
    if len(username) >= 3:
        sensitive_literals.extend([username, f"C:\\Users\\{username}", f"/home/{username}"])
    personal_hits = [marker for marker in sensitive_literals if marker and marker.casefold() in body_text.casefold()]
    if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", body_text):
        personal_hits.append("email marker")

    checks = {
        "page_limit": body_pages <= 6 and reference_page_count <= 1 and len(texts) <= 7,
        "references_only_final_page": bool(reference_start) and reference_start == len(texts),
        "letter_page_size": letter,
        "required_sections": all(required_markers.values()),
        "anonymous_title": anonymous_title,
        "anonymous_metadata": not metadata_author,
        "no_personal_path_or_email": not personal_hits,
    }
    errors = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not errors,
        "pdf_path": pdf_path.relative_to(ROOT).as_posix(),
        "pdf_sha256": sha256(pdf_path),
        "total_page_count": len(texts),
        "body_page_count": body_pages,
        "reference_page_count": reference_page_count,
        "reference_start_page": reference_start,
        "page_sizes_points": page_sizes,
        "required_markers": required_markers,
        "metadata": {"author": metadata_author, "creator": metadata_creator},
        "personal_marker_hits": personal_hits,
        "checks": checks,
        "errors": errors,
    }


def build_status() -> dict[str, object]:
    config = load_json(CONFIG_PATH)
    p1 = load_json(ROOT / str(config.get("evidence_dependencies", {}).get("p1_submission_gate", "")))
    p2 = load_json(ROOT / str(config.get("evidence_dependencies", {}).get("p2_development_gate", "")))
    p3 = load_json(ROOT / str(config.get("evidence_dependencies", {}).get("p3_main_result_gate", "")))
    pdf = inspect_pdf()
    package = verify_reproducibility_package()
    related_work = (ROOT / "DAC2027_RELATED_WORK_MATRIX.md").is_file()
    checklist = (ROOT / "DAC2027_SUBMISSION_CHECKLIST.md").is_file()
    ai_disclosure = bool(pdf.get("required_markers", {}).get("ai_disclosure"))
    p1_gate = bool(p1.get("submission_two_case_experiment_completed"))
    p2_gate = bool(p2.get("p2_development_gate_passed"))
    p3_gate = bool(p3.get("p3_main_result_gate_passed"))
    infrastructure = bool(pdf.get("passed") and package.get("passed") and related_work and checklist and ai_disclosure and p1_gate and p2_gate)
    approval = load_json(APPROVAL_PATH)
    approval_validation = validate_human_approval(
        approval,
        str(pdf.get("pdf_sha256") or ""),
        str(p3.get("report_sha256") or ""),
    )
    human_approval = bool(approval_validation["passed"])
    final_gate = bool(infrastructure and p3_gate and human_approval)
    status = {
        "schema": "dac2027-p4-readiness",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "phase": "DAC2027-P4",
        "title": "双盲稿件、相关工作与匿名复现包",
        "status": (
            "ready_for_submission" if final_gate else
            "awaiting_human_author_approval" if infrastructure and p3_gate else
            "awaiting_external_results_and_human_approval" if infrastructure else
            "infrastructure_incomplete"
        ),
        "p4_infrastructure_gate_passed": infrastructure,
        "p4_final_submission_gate_passed": final_gate,
        "human_author_approval_recorded": human_approval,
        "human_author_approval": approval_validation,
        "format_and_page_gate_passed": bool(pdf.get("passed")),
        "double_blind_gate_passed": bool(pdf.get("checks", {}).get("anonymous_title") and pdf.get("checks", {}).get("anonymous_metadata") and pdf.get("checks", {}).get("no_personal_path_or_email")),
        "related_work_matrix_completed": related_work,
        "ai_content_statement_completed": ai_disclosure,
        "reproducibility_package_passed": bool(package.get("passed")),
        "p1_submission_gate_passed": p1_gate,
        "p2_development_gate_passed": p2_gate,
        "p3_external_main_result_gate_passed": p3_gate,
        "accepted_external_task_count": int(p3.get("accepted_task_count", 0) or 0),
        "required_external_task_count": int(p3.get("required_task_count", 24) or 24),
        "measured_external_observation_count": int(p3.get("measured_observation_count", 0) or 0),
        "required_external_observation_count": int(p3.get("required_observation_count", 192) or 192),
        "paper": pdf,
        "reproducibility": package,
        "next_action": (
            "P4 最终投稿门已通过；上传前仍应在投稿系统中打开并复核最终 PDF。" if final_gate else
            "P3 主结果已通过；由作者逐条核对主结果、引用、双盲、冲突、作者记录和 AI 声明，并保存与当前 PDF/P3 哈希匹配的批准记录。" if infrastructure and p3_gate else
            "P4 本机稿件与匿名复现包已经通过；完成 P3 的 24 条外部任务和 192 条实测，由作者逐条核对主结果、引用、双盲信息和 AI 声明后，才可记录人工投稿批准。" if infrastructure else
            "修复稿件格式、双盲或复现包检查中的失败项。"
        ),
        "evidence_boundary": config.get("evidence_boundary", ""),
    }
    return status


def main() -> int:
    status = build_status()
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if status["p4_infrastructure_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
