from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "generated" / "p2" / "release"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_files() -> list[Path]:
    rows: set[Path] = set()
    for pattern in (
        "src/comsol_small_model/*.py", "scripts/*.py", "tests/*.py", "configs/*.json",
        "benchmarks/**/*.json", "benchmarks/**/*.jsonl", "case_specs/*.json",
        "paper_draft/build_english_paper.py",
    ):
        rows.update(path for path in ROOT.glob(pattern) if path.is_file())
    for name in (
        "web_app.py", "execution_worker.py", "template_catalog.json", "training_program.json",
        "training_dataset_manifest.schema.json", "requirements.txt", "requirements-lock-windows-py312.txt",
        "start_windows.bat", "start_local_8880.bat", "start_network.bat", "start_p2_release.bat",
        "README.md", "AUTO_MODELING_IMPLEMENTATION_PLAN.md", "EDA_PUBLICATION_ROADMAP.md",
        "PROJECT_READINESS.md", "RELEASE_MIGRATION_GUIDE.md",
        "generated/p1/template_maturity.json", "generated/p1/template_maturity.md",
        "generated/p2/end_to_end_benchmark.json", "generated/p2/migration_acceptance.json",
        "generated/benchmarks/controlled_repair/report.json", "generated/benchmarks/physics_selection/report.json",
        "paper_draft/comsol_trustworthy_surrogate_paper_draft_en.docx",
    ):
        path = ROOT / name
        if path.is_file(): rows.add(path)
    acoustic = ROOT / "generated" / "p1_execution_jobs" / "acoustic" / "job_20261010040946_abe0631f"
    if acoustic.is_dir():
        rows.update(path for path in acoustic.rglob("*") if path.is_file() and path.suffix.lower() in {".mph", ".csv", ".png", ".json", ".m"})
    return sorted(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = release_files()
    manifest = {
        "schema": "comsol-p2-release-manifest", "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "exclusions": ["generated/local_secrets", ".venv", "MATLAB preferences", "temporary logs", "non-demo MPH files"],
        "files": [{"path": path.relative_to(ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256(path)} for path in files],
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    archive = OUTPUT_DIR / "comsol_auto_modeling_p2_release.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
        for path in files:
            handle.write(path, path.relative_to(ROOT).as_posix())
        handle.write(manifest_path, "release_manifest.json")
    summary = {"archive": str(archive), "manifest": str(manifest_path), "file_count": len(files), "size_bytes": archive.stat().st_size, "sha256": sha256(archive)}
    (OUTPUT_DIR / "release_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
