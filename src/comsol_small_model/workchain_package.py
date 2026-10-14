from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4


def create_reference_workchain_package(
    report_paths: list[str | Path],
    output_dir: str | Path,
    *,
    title: str = "physics_reference_validation",
) -> dict[str, Any]:
    """Create a portable manifest that links reference reports for downstream work."""
    if not report_paths:
        raise ValueError("at least one reference report path is required")
    validated_reports: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    for raw_path in report_paths:
        path = Path(raw_path)
        if not path.is_file():
            raise ValueError(f"reference report not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != "comsol-physics-reference-report":
            raise ValueError(f"not a COMSOL physics reference report: {path}")
        report = payload.get("report", {})
        metadata = {
            "report_id": payload.get("id", path.stem),
            "source_path": str(path.resolve()),
            "created_at": payload.get("created_at", ""),
            "kind": report.get("kind", ""),
            "case_type": report.get("case_type", ""),
            "passed": report.get("passed"),
        }
        validated_reports.append((path, payload, metadata))
    package_id = f"workchain_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    package_dir = Path(output_dir) / package_id
    reports_dir = package_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=False)
    sources: list[dict[str, Any]] = []
    for index, (source_path, _payload, metadata) in enumerate(validated_reports):
        copied_name = f"{index:03d}_{source_path.name}"
        copied_path = reports_dir / copied_name
        shutil.copy2(source_path, copied_path)
        sources.append({**metadata, "path": (PurePosixPath("reports") / copied_name).as_posix()})
    manifest_path = package_dir / "manifest.json"
    manifest = {
        "schema": "comsol-physics-workchain-package",
        "schemaVersion": "1.0.0",
        "id": package_id,
        "title": title.strip() or "physics_reference_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reference_reports": sources,
        "next_actions": [
            "Review each report's assumptions and COMSOL comparison guidance.",
            "Attach actual COMSOL model, mesh, study, and result-export evidence before engineering use.",
            "Treat this package as traceability metadata, not engineering certification.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"id": package_id, "path": str(manifest_path), "report_count": len(sources), "manifest": manifest}


def list_reference_workchain_packages(output_dir: str | Path, *, limit: int = 30) -> list[dict[str, Any]]:
    source = Path(output_dir)
    if not source.is_dir():
        return []
    result = []
    paths = list(source.glob("workchain_*.json")) + list(source.glob("workchain_*/manifest.json"))
    for path in sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True)[:max(0, limit)]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        result.append({"id": payload.get("id", path.stem), "path": str(path), "title": payload.get("title", ""), "created_at": payload.get("created_at", ""), "report_count": len(payload.get("reference_reports", []))})
    return result


def validate_reference_workchain_package(package_path: str | Path) -> dict[str, Any]:
    """Verify that a workchain package and each linked reference-report artifact remain readable."""
    source = Path(package_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    errors: list[str] = []
    if payload.get("schema") != "comsol-physics-workchain-package":
        errors.append("package schema is not comsol-physics-workchain-package")
    if payload.get("schemaVersion") != "1.0.0":
        errors.append("package schemaVersion is not 1.0.0")
    sources: list[dict[str, Any]] = []
    for index, entry in enumerate(payload.get("reference_reports", [])):
        raw_path = Path(str(entry.get("path", "")))
        path = raw_path if raw_path.is_absolute() else source.parent / raw_path
        status = {"index": index, "path": str(path), "exists": path.is_file(), "valid": False}
        if not path.is_file():
            errors.append(f"reference report {index} is missing: {path}")
        else:
            report_payload = json.loads(path.read_text(encoding="utf-8"))
            status["valid"] = report_payload.get("schema") == "comsol-physics-reference-report"
            status["report_id_matches"] = report_payload.get("id") == entry.get("report_id")
            if not status["valid"]:
                errors.append(f"reference report {index} has an unexpected schema")
            if not status["report_id_matches"]:
                errors.append(f"reference report {index} id no longer matches package manifest")
        sources.append(status)
    if not payload.get("reference_reports"):
        errors.append("package contains no reference reports")
    return {"kind": "reference_workchain_package_validation", "package_path": str(source), "package_id": payload.get("id", ""), "sources": sources, "errors": errors, "passed": not errors, "guidance": "A passing package check confirms traceability links and schemas only. Review the physical assumptions and actual COMSOL evidence in each report before using results."}


def archive_reference_workchain_package(package_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Create a ZIP only after a portable workchain package passes integrity validation."""
    validation = validate_reference_workchain_package(package_path)
    if not validation["passed"]:
        raise ValueError("cannot archive an invalid workchain package: " + "; ".join(validation["errors"]))
    manifest_path = Path(package_path).resolve()
    package_dir = manifest_path.parent
    if manifest_path.name != "manifest.json" or not (package_dir / "reports").is_dir():
        raise ValueError("only portable workchain packages with manifest.json and reports/ can be archived")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    archive_base = destination / package_dir.name
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=package_dir.parent, base_dir=package_dir.name)
    return {"kind": "reference_workchain_archive", "package_id": validation["package_id"], "package_path": str(manifest_path), "archive_path": archive_path, "validation": validation}


def validate_reference_workchain_archive(archive_path: str | Path) -> dict[str, Any]:
    """Validate a portable workchain ZIP without extracting untrusted archive content."""
    source = Path(archive_path)
    errors: list[str] = []
    sources: list[dict[str, Any]] = []
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        unsafe = [name for name in names if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts]
        if unsafe:
            errors.append("archive contains unsafe member path")
        manifests = [name for name in names if name.endswith("/manifest.json")]
        if len(manifests) != 1:
            errors.append("archive must contain exactly one package manifest.json")
            manifest_name = ""
            payload: dict[str, Any] = {}
        else:
            manifest_name = manifests[0]
            payload = json.loads(archive.read(manifest_name).decode("utf-8"))
            if payload.get("schema") != "comsol-physics-workchain-package":
                errors.append("package schema is not comsol-physics-workchain-package")
            if payload.get("schemaVersion") != "1.0.0":
                errors.append("package schemaVersion is not 1.0.0")
        root = PurePosixPath(manifest_name).parent
        for index, entry in enumerate(payload.get("reference_reports", [])):
            relative = PurePosixPath(str(entry.get("path", "")).replace("\\", "/"))
            member = str(root / relative)
            status = {"index": index, "path": member, "exists": member in names, "valid": False}
            if member not in names:
                errors.append(f"reference report {index} is missing from archive")
            else:
                report_payload = json.loads(archive.read(member).decode("utf-8"))
                status["valid"] = report_payload.get("schema") == "comsol-physics-reference-report"
                status["report_id_matches"] = report_payload.get("id") == entry.get("report_id")
                if not status["valid"]:
                    errors.append(f"reference report {index} has an unexpected schema")
                if not status["report_id_matches"]:
                    errors.append(f"reference report {index} id no longer matches package manifest")
            sources.append(status)
        if not payload.get("reference_reports"):
            errors.append("package contains no reference reports")
    return {"kind": "reference_workchain_archive_validation", "archive_path": str(source), "sources": sources, "errors": errors, "passed": not errors, "guidance": "Archive validation checks package traceability and safe member paths only. It does not execute, extract, or certify any COMSOL content."}
