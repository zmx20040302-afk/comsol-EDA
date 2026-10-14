from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "generated" / "dac2027" / "p4" / "reproducibility"
ZIP_PATH = OUTPUT_DIR / "dac2027_p4_anonymous_reproducibility.zip"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"


INCLUDED_FILES = [
    "configs/dac2027_p4_submission.json",
    "configs/dac2027_p3_protocol.json",
    "DAC2027_RELATED_WORK_MATRIX.md",
    "DAC2027_SUBMISSION_CHECKLIST.md",
    "DAC2027_P1_STATUS.md",
    "DAC2027_P2_STATUS.md",
    "DAC2027_P3_STATUS.md",
    "DAC2027_P4_STATUS.md",
    "paper_draft/build_dac2027_submission.py",
    "paper_draft/dac2027_contract_guided_comsol_submission.docx",
    "paper_draft/dac2027_contract_guided_comsol_submission.pdf",
    "generated/dac2027/p1/readiness_status.json",
    "generated/dac2027/p2/readiness_status.json",
    "generated/dac2027/p2/controlled_comparison_report.json",
    "generated/dac2027/p2/ablation_report.json",
    "generated/dac2027/p3/readiness_status.json",
    "generated/dac2027/p3/infrastructure_freeze_manifest.json",
    "scripts/prepare_dac2027_p3.py",
    "scripts/run_dac2027_p3.py",
    "scripts/evaluate_dac2027_p3.py",
    "scripts/prepare_dac2027_p4.py",
    "scripts/build_dac2027_p4_package.py",
    "tests/test_dac2027_p3.py",
    "tests/test_dac2027_p4.py",
    "src/comsol_small_model/dac2027_p3_evaluation.py",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_package() -> dict[str, object]:
    missing = [relative for relative in INCLUDED_FILES if not (ROOT / relative).is_file()]
    if missing:
        raise FileNotFoundError("Missing required reproducibility files: " + ", ".join(missing))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for relative in INCLUDED_FILES:
        path = ROOT / relative
        files.append({
            "path": relative,
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        })

    manifest = {
        "schema": "dac2027-p4-anonymous-reproducibility-manifest",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "anonymous": True,
        "evidence_boundary": (
            "P1 and P2 are local development evidence. P3 remains pending until 24 external tasks, "
            "eight disjoint families, and 192 measured observations pass the frozen protocol."
        ),
        "excluded": [
            "credentials and API keys",
            "personal paths and external participant identities",
            "large MPH binaries",
            "unreviewed logs and synthetic replacement evidence",
        ],
        "files": files,
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item in files:
            archive.write(ROOT / str(item["path"]), arcname=str(item["path"]))
        archive.writestr("MANIFEST.json", manifest_bytes)

    manifest["archive"] = {
        "path": ZIP_PATH.relative_to(ROOT).as_posix(),
        "sha256": sha256(ZIP_PATH),
        "size_bytes": ZIP_PATH.stat().st_size,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    manifest = build_package()
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
