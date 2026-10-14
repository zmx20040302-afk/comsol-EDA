from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def write_reference_report(report: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    """Persist a reference calculation or comparison as a portable JSON work-chain artifact."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    artifact_id = f"reference_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    payload = {"schema": "comsol-physics-reference-report", "schemaVersion": "1.0.0", "id": artifact_id, "created_at": datetime.now(timezone.utc).isoformat(), "report": report}
    path = destination / f"{artifact_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"id": artifact_id, "path": str(path)}


def list_reference_reports(output_dir: str | Path, *, limit: int = 30) -> list[dict[str, Any]]:
    """List recent reference artifacts without loading unrelated generated files."""
    source = Path(output_dir)
    if not source.is_dir():
        return []
    reports: list[dict[str, Any]] = []
    for path in sorted(source.glob("reference_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:max(0, limit)]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        report = payload.get("report", {})
        reports.append({"id": payload.get("id", path.stem), "path": str(path), "created_at": payload.get("created_at", ""), "kind": report.get("kind", ""), "case_type": report.get("case_type", "")})
    return reports
