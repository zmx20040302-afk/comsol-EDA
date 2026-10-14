from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.p7_eda_multicase import build_p7_report


RELEASE_DIR = ROOT / "generated" / "p7" / "release"
ARCHIVE = RELEASE_DIR / "comsol_auto_modeling_p7_multicase.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate() -> dict:
    fresh = build_p7_report(ROOT)
    stored_path = ROOT / "generated" / "p7" / "p7_eda_multicase_report.json"
    if not fresh.get("p7_completed"):
        raise RuntimeError("P7 多案例验收门尚未通过。")
    if not stored_path.is_file():
        raise RuntimeError("P7 结构化报告不存在。")
    stored = json.loads(stored_path.read_text(encoding="utf-8"))
    for key in ("p7_completed", "passed_main_case_count", "physics_family_count", "gates", "cases"):
        if stored.get(key) != fresh.get(key):
            raise RuntimeError(f"P7 已保存报告与当前证据不一致：{key}")
    return fresh


def release_files(report: dict) -> list[Path]:
    fixed = [
        ROOT / "README.md",
        ROOT / "AUTO_MODELING_IMPLEMENTATION_PLAN.md",
        ROOT / "P7_COMPLETION_REPORT.md",
        ROOT / "web_app.py",
        ROOT / "configs" / "p7_eda_multicase_benchmark.json",
        ROOT / "src" / "comsol_small_model" / "p7_eda_multicase.py",
        ROOT / "scripts" / "run_p7_eda_multicase_benchmark.py",
        ROOT / "scripts" / "build_p7_release_package.py",
        ROOT / "tests" / "test_p7_eda_multicase.py",
        ROOT / "generated" / "p7" / "p7_eda_multicase_report.json",
        ROOT / "paper_draft" / "build_english_paper.py",
        ROOT / "paper_draft" / "comsol_trustworthy_surrogate_paper_draft_en.docx",
        ROOT / "paper_draft" / "comsol_trustworthy_surrogate_paper_draft_en.pdf",
    ]
    evidence: list[Path] = []
    for case in report.get("cases", []):
        for name, item in case.get("artifacts", {}).items():
            if name == "comsol_artifact":
                continue
            path = ROOT / str(item.get("path", ""))
            if path.is_file() and path.stat().st_size <= 25 * 1024 * 1024:
                evidence.append(path)
    unique = {path.resolve(): path for path in [*fixed, *evidence] if path.is_file()}
    return sorted(unique.values(), key=lambda path: path.relative_to(ROOT).as_posix())


def main() -> None:
    report = validate()
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    files = release_files(report)
    manifest = {
        "schema": "comsol-p7-multicase-release-manifest",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "p7_completed": True,
        "passed_main_cases": report["passed_main_case_count"],
        "physics_families": report["physics_family_count"],
        "passed_extension_cases": report["passed_extension_case_count"],
        "claim_boundary": report["claim_boundary"],
        "large_mph_and_logs_excluded": True,
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
        archive.writestr("P7_RELEASE_MANIFEST.json", manifest_bytes)
    summary = {
        "archive": ARCHIVE.relative_to(ROOT).as_posix(),
        "size_bytes": ARCHIVE.stat().st_size,
        "sha256": sha256(ARCHIVE),
        "file_count": len(files),
        "passed_main_cases": report["passed_main_case_count"],
        "physics_families": report["physics_family_count"],
        "passed_extension_cases": report["passed_extension_case_count"],
        "large_mph_and_logs_excluded": True,
    }
    (RELEASE_DIR / "release_manifest.json").write_bytes(manifest_bytes)
    (RELEASE_DIR / "release_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
