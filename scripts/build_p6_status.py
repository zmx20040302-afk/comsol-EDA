from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "p6" / "p6_status.json"


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_status() -> dict[str, Any]:
    java = _load(ROOT / "generated" / "p6" / "java_dual_path" / "java_dual_path_report.json")
    experiment = _load(ROOT / "generated" / "experimental_validation" / "temperature_validation_report.json")
    baseline = _load(ROOT / "generated" / "p6" / "baseline_evaluation" / "baseline_evaluation_report.json")
    current_migration = _load(ROOT / "generated" / "p2" / "migration_acceptance.json")
    destination_migration = _load(ROOT / "generated" / "p6" / "destination_migration_acceptance.json")
    assets = [
        ROOT / "configs" / "experimental_temperature_validation.json",
        ROOT / "configs" / "experimental_temperature_measurements.schema.json",
        ROOT / "examples" / "experimental_temperature_measurements_template.csv",
        ROOT / "configs" / "p6_external_evidence.json",
        ROOT / "examples" / "p6_fixed_task_baseline_template.csv",
    ]
    gates = {
        "java_dual_path": bool(java.get("summary", {}).get("java_dual_path_gate_passed")),
        "current_host_preflight": bool(current_migration.get("passed")),
        "evidence_acquisition_assets": all(path.is_file() for path in assets),
        "temperature_experiment": bool(experiment.get("passed")),
        "fixed_task_external_comparison": bool(baseline.get("passed")),
        "destination_host_acceptance": bool(
            destination_migration.get("passed") and destination_migration.get("host_role") == "destination"
        ),
    }
    local_gate = all(gates[name] for name in ("java_dual_path", "current_host_preflight", "evidence_acquisition_assets"))
    publication_gate = all(gates.values())
    return {
        "schema": "comsol-p6-external-evidence-status",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "P6",
        "title": "外部证据与双执行路径",
        "status": "complete" if publication_gate else ("external_evidence_pending" if local_gate else "local_preparation_incomplete"),
        "local_readiness_passed": local_gate,
        "publication_external_gate_passed": publication_gate,
        "gates": gates,
        "java": java.get("summary", {}),
        "experiment": {
            "status": experiment.get("status", "missing"),
            "sample_count": int(experiment.get("sample_count", 0)),
            "minimum_required": 5,
        },
        "baseline_comparison": {
            "status": baseline.get("status", "missing"),
            "measured_row_count": int(baseline.get("measured_row_count", 0)),
            "required_rows": 180,
        },
        "remaining_actions": [name for name, passed in gates.items() if not passed],
        "policy": "P6 local readiness and external publication evidence are separate. Missing measurements, participants or destination-host runs cannot be replaced by synthetic rows.",
    }


def main() -> int:
    report = build_status()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["local_readiness_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
