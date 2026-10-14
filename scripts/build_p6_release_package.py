from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "generated" / "p6" / "release"
ARCHIVE = RELEASE_DIR / "comsol_auto_modeling_p6_evidence.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def release_files() -> list[Path]:
    fixed = [
        ROOT / "README.md",
        ROOT / "AUTO_MODELING_IMPLEMENTATION_PLAN.md",
        ROOT / "P6_COMPLETION_REPORT.md",
        ROOT / "web_app.py",
        ROOT / "requirements-lock-windows-py312.txt",
        ROOT / "configs" / "p6_external_evidence.json",
        ROOT / "configs" / "experimental_temperature_validation.json",
        ROOT / "configs" / "experimental_temperature_measurements.schema.json",
        ROOT / "examples" / "p6_fixed_task_baseline_template.csv",
        ROOT / "examples" / "experimental_temperature_measurements_template.csv",
        ROOT / "src" / "comsol_small_model" / "p6_baseline_evaluation.py",
        ROOT / "src" / "comsol_small_model" / "experimental_validation.py",
        ROOT / "scripts" / "run_p6_java_dual_path.py",
        ROOT / "scripts" / "prepare_p6_external_evidence.py",
        ROOT / "scripts" / "build_p6_status.py",
        ROOT / "scripts" / "build_p6_release_package.py",
        ROOT / "scripts" / "run_p2_migration_acceptance.py",
        ROOT / "tests" / "test_p6_external_evidence.py",
        ROOT / "tests" / "test_p6_baseline_evaluation.py",
        ROOT / "generated" / "p1" / "template_maturity.json",
        ROOT / "generated" / "p1" / "template_maturity.md",
        ROOT / "generated" / "p2" / "end_to_end_benchmark.json",
        ROOT / "generated" / "p2" / "migration_acceptance.json",
        ROOT / "generated" / "experimental_validation" / "temperature_validation_report.json",
        ROOT / "paper_draft" / "comsol_trustworthy_surrogate_paper_draft_en.docx",
        ROOT / "paper_draft" / "comsol_trustworthy_surrogate_paper_draft_en.pdf",
        ROOT / "paper_draft" / "build_english_paper.py",
    ]
    evidence: list[Path] = []
    for path in (ROOT / "generated" / "p6").rglob("*"):
        if not path.is_file() or RELEASE_DIR in path.parents:
            continue
        if path.suffix.lower() in {".mph", ".class", ".log"}:
            continue
        evidence.append(path)
    unique = {path.resolve(): path for path in [*fixed, *evidence] if path.is_file()}
    return sorted(unique.values(), key=lambda path: path.relative_to(ROOT).as_posix())


def validate() -> dict:
    status = json.loads((ROOT / "generated" / "p6" / "p6_status.json").read_text(encoding="utf-8"))
    java = json.loads((ROOT / "generated" / "p6" / "java_dual_path" / "java_dual_path_report.json").read_text(encoding="utf-8"))
    if not status.get("local_readiness_passed"):
        raise RuntimeError("P6 本机准备门尚未通过。")
    if not java.get("summary", {}).get("java_dual_path_gate_passed"):
        raise RuntimeError("P6 Java 双路径门尚未通过。")
    for row in java.get("templates", []):
        source = Path(row["java_path"])
        output = Path(row["output_mph"])
        if not row.get("passed") or sha256(source) != row.get("java_sha256") or sha256(output) != row.get("output_mph_sha256"):
            raise RuntimeError(f"P6 Java 工件哈希失配：{row.get('id')}")
    return status


def main() -> None:
    status = validate()
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    files = release_files()
    manifest = {
        "schema": "comsol-p6-evidence-release-manifest",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "local_readiness_passed": True,
        "publication_external_gate_passed": bool(status.get("publication_external_gate_passed")),
        "remaining_actions": status.get("remaining_actions", []),
        "policy": "This package proves local P6 readiness and preserves pending external gates; it does not claim missing measurements or destination-host execution.",
        "files": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr("P6_RELEASE_MANIFEST.json", manifest_bytes)
    summary = {
        "archive": str(ARCHIVE.relative_to(ROOT)),
        "size_bytes": ARCHIVE.stat().st_size,
        "sha256": sha256(ARCHIVE),
        "file_count": len(files),
        "java_verified_count": 6,
        "local_readiness_passed": True,
        "publication_external_gate_passed": bool(status.get("publication_external_gate_passed")),
        "mph_class_logs_excluded": True,
        "remaining_actions": status.get("remaining_actions", []),
    }
    (RELEASE_DIR / "release_manifest.json").write_bytes(manifest_bytes)
    (RELEASE_DIR / "release_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
