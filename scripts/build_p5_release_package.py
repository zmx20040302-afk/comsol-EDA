from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "generated" / "p5" / "release"
ARCHIVE = RELEASE_DIR / "comsol_auto_modeling_p5_release.zip"


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
        ROOT / "P0_P5_AUDIT_REPORT.md",
        ROOT / "P3_COMPLETION_REPORT.md",
        ROOT / "P4_COMPLETION_REPORT.md",
        ROOT / "P5_COMPLETION_REPORT.md",
        ROOT / "web_app.py",
        ROOT / "requirements.txt",
        ROOT / "requirements-lock-windows-py312.txt",
        ROOT / "start_windows.bat",
        ROOT / "start_local_8880.bat",
        ROOT / "configs" / "busbar_eda_design_problem.json",
        ROOT / "configs" / "execution_node.json",
        ROOT / "src" / "comsol_small_model" / "eda_adaptive.py",
        ROOT / "src" / "comsol_small_model" / "eda_conformal.py",
        ROOT / "src" / "comsol_small_model" / "eda_design.py",
        ROOT / "src" / "comsol_small_model" / "eda_optimization.py",
        ROOT / "tests" / "test_p5_conformal_release.py",
        ROOT / "paper_draft" / "build_english_paper.py",
        ROOT / "paper_draft" / "comsol_trustworthy_surrogate_paper_draft_en.docx",
        ROOT / "paper_draft" / "comsol_trustworthy_surrogate_paper_draft_en.pdf",
    ]
    fixed.extend(sorted(ROOT.glob("scripts/*p5*.py")))
    evidence: list[Path] = []
    for path in sorted((ROOT / "generated" / "p5").rglob("*")):
        if not path.is_file() or RELEASE_DIR in path.parents:
            continue
        if path.suffix.lower() == ".mph" or path.name.endswith(".log"):
            continue
        evidence.append(path)
    files = {path.resolve(): path for path in [*fixed, *evidence] if path.is_file()}
    return sorted(files.values(), key=lambda path: path.relative_to(ROOT).as_posix())


def validate_release_inputs() -> dict:
    report_path = ROOT / "generated" / "p5" / "final_evaluation" / "p5_final_evaluation_report.json"
    sealed_path = ROOT / "generated" / "p5" / "sealed_final_design" / "sealed_design_manifest.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    sealed = json.loads(sealed_path.read_text(encoding="utf-8"))
    if not report.get("execution_passed"):
        raise RuntimeError("P5 final COMSOL execution evidence has not passed.")
    if not report.get("surrogate_release_passed") or not all(report.get("release_checks", {}).values()):
        raise RuntimeError("P5 controlled surrogate release evidence has not passed.")
    if int(report.get("counts", {}).get("false_safe_upper_95", -1)) != 0:
        raise RuntimeError("P5 release contains a false-safe design.")
    for section in ("files", "frozen_before_sealing"):
        for detail in sealed.get(section, {}).values():
            path = ROOT / detail["path"]
            if not path.is_file() or sha256(path) != detail["sha256"]:
                raise RuntimeError(f"P5 sealed artifact hash mismatch: {detail['path']}")
    return report


def main() -> None:
    report = validate_release_inputs()
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    files = release_files()
    release_decision = {
        "comsol_execution_passed": True,
        "calibration_method": report["calibration_method"],
        "domain_holdout_cases": int(report["counts"]["domain_holdout"]),
        "out_of_domain_cases": int(report["counts"]["out_of_domain"]),
        "released_safe_count": int(report["counts"]["released_safe_upper_95"]),
        "false_safe_count": int(report["counts"]["false_safe_upper_95"]),
        "safe_release_coverage": float(report["safe_release_coverage"]),
        "surrogate_release_passed": True,
        "policy": (
            "Controlled prediction is permitted only inside the declared seven-variable domain and fixed physical "
            "assumptions. Out-of-domain or changed-physics requests require COMSOL."
        ),
    }
    manifest = {
        "schema": "comsol-p5-release-manifest",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "P0-P5 source, compact COMSOL evidence, frozen P5 surrogate, manuscript and reproducibility metadata; "
            "large MPH files and transient logs are excluded."
        ),
        "release_decision": release_decision,
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
        archive.writestr("P5_RELEASE_MANIFEST.json", manifest_bytes)

    summary = {
        "archive": str(ARCHIVE.relative_to(ROOT)),
        "size_bytes": ARCHIVE.stat().st_size,
        "sha256": sha256(ARCHIVE),
        "file_count": len(files),
        "large_mph_files_excluded": True,
        **release_decision,
    }
    (RELEASE_DIR / "release_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RELEASE_DIR / "release_manifest.json").write_bytes(manifest_bytes)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
