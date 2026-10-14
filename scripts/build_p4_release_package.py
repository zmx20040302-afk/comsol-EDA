from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "generated" / "p4" / "release"
ARCHIVE = RELEASE_DIR / "comsol_auto_modeling_p4_evidence.zip"


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
        ROOT / "EDA_PUBLICATION_ROADMAP.md",
        ROOT / "PROJECT_READINESS.md",
        ROOT / "P3_COMPLETION_REPORT.md",
        ROOT / "P4_COMPLETION_REPORT.md",
        ROOT / "web_app.py",
        ROOT / "requirements-lock-windows-py312.txt",
        ROOT / "configs" / "busbar_eda_design_problem.json",
        ROOT / "configs" / "execution_node.json",
        ROOT / "src" / "comsol_small_model" / "eda_adaptive.py",
        ROOT / "src" / "comsol_small_model" / "eda_design.py",
        ROOT / "src" / "comsol_small_model" / "eda_optimization.py",
        ROOT / "tests" / "test_p4_adaptive.py",
        ROOT / "paper_draft" / "build_english_paper.py",
        ROOT / "paper_draft" / "comsol_trustworthy_surrogate_paper_draft_en.docx",
        ROOT / "paper_draft" / "comsol_trustworthy_surrogate_paper_draft_en.pdf",
    ]
    fixed.extend(sorted(ROOT.glob("scripts/*p4*.py")))
    evidence = []
    for path in sorted((ROOT / "generated" / "p4").rglob("*")):
        if not path.is_file() or RELEASE_DIR in path.parents:
            continue
        if path.suffix.lower() == ".mph" or path.name.endswith(".log"):
            continue
        evidence.append(path)
    files = {path.resolve(): path for path in [*fixed, *evidence] if path.is_file()}
    return sorted(files.values(), key=lambda path: path.relative_to(ROOT).as_posix())


def main() -> None:
    final_report_path = ROOT / "generated" / "p4" / "final_evaluation" / "p4_final_evaluation_report.json"
    training_report_path = ROOT / "generated" / "p4" / "adaptive_training_report.json"
    final_report = json.loads(final_report_path.read_text(encoding="utf-8"))
    training_report = json.loads(training_report_path.read_text(encoding="utf-8"))
    if not final_report.get("execution_passed"):
        raise RuntimeError("P4 final COMSOL execution evidence has not passed.")
    if not training_report.get("execution_passed"):
        raise RuntimeError("P4 adaptive COMSOL training evidence has not passed.")
    checks = final_report.get("release_checks", {})
    accuracy_passed = all(
        bool(checks.get(name))
        for name in (
            "tmax_rmse_at_most_15_K",
            "power_relative_rmse_at_most_15_percent",
            "mass_relative_rmse_at_most_10_percent",
            "all_intervals_picp_at_least_0_90",
        )
    )

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    files = release_files()
    manifest = {
        "schema": "comsol-p4-evidence-manifest",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "P4 source, compact COMSOL evidence, frozen surrogate, manuscript and reproducibility metadata; MPH and logs are excluded.",
        "release_decision": {
            "adaptive_comsol_cases": 80,
            "final_comsol_cases": 80,
            "comsol_execution_passed": True,
            "accuracy_passed": accuracy_passed,
            "safe_release_coverage": float(final_report["safe_release_coverage"]),
            "surrogate_release_passed": bool(final_report.get("surrogate_release_passed")),
            "policy": "This archive preserves a failed surrogate release decision as evidence; it does not authorize direct prediction.",
        },
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
        archive.writestr("P4_EVIDENCE_MANIFEST.json", manifest_bytes)

    summary = {
        "archive": str(ARCHIVE.relative_to(ROOT)),
        "size_bytes": ARCHIVE.stat().st_size,
        "sha256": sha256(ARCHIVE),
        "file_count": len(files),
        "large_mph_files_excluded": True,
        "comsol_execution_passed": True,
        "accuracy_passed": accuracy_passed,
        "safe_release_coverage": float(final_report["safe_release_coverage"]),
        "surrogate_release_passed": bool(final_report.get("surrogate_release_passed")),
    }
    (RELEASE_DIR / "release_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RELEASE_DIR / "release_manifest.json").write_bytes(manifest_bytes)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
