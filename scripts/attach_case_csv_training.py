"""Attach validated COMSOL CSV and surrogate evidence to an existing case card."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from comsol_small_model.case_memory import remember_case


def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--outputs", nargs="+", required=True)
    parser.add_argument("--memory-path", type=Path, default=Path("generated/case_memory/case_memory.json"))
    args = parser.parse_args()

    card_path = args.card.resolve()
    csv_path = args.csv.resolve()
    model_path = args.model.resolve()
    validation_path = args.validation.resolve()
    if not csv_path.is_file() or not model_path.is_file() or not validation_path.is_file():
        raise FileNotFoundError("csv, model, and validation files must all exist")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        rows = sum(1 for _ in reader)
    missing = [name for name in [*args.inputs, *args.outputs] if name not in columns]
    if missing:
        raise ValueError(f"CSV missing declared columns: {', '.join(missing)}")

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation_status = str(validation.get("status", ""))
    validation_passed = validation_status.startswith("passed") or validation.get("passed") is True
    if not validation_passed:
        raise ValueError("validation does not report a passed status")
    card = json.loads(card_path.read_text(encoding="utf-8"))
    sources = list(card.get("source_files", []))
    already_attached = any(str(item.get("path", "")) == str(csv_path) for item in sources if isinstance(item, dict))
    summary = dict(card.get("file_summary", {}))
    kinds = dict(summary.get("kinds", {}))
    if not already_attached:
        kinds["csv_table"] = int(kinds.get("csv_table", 0)) + 1
    else:
        kinds["csv_table"] = max(1, int(kinds.get("csv_table", 0)))
    summary["kinds"] = kinds
    if not already_attached:
        summary["csv_files"] = int(summary.get("csv_files", 0)) + 1
    else:
        summary["csv_files"] = max(1, int(summary.get("csv_files", 0)))
    if not already_attached:
        summary["count"] = int(summary.get("count", 0)) + 1
    card["file_summary"] = summary

    content = dict(card.get("case_content", {}))
    results = list(content.get("results", []))
    for output in args.outputs:
        if output not in results:
            results.append(output)
    content["results"] = results
    card["case_content"] = content
    if not already_attached:
        sources.append({"name": csv_path.name, "kind": "csv_table", "path": str(csv_path)})
    card["source_files"] = sources
    card["training_stage"] = "surrogate_validated"
    card["gaps"] = [gap for gap in card.get("gaps", []) if "CSV" not in str(gap)]
    evidence = {
        "kind": "comsol_case_csv_training_evidence",
        "csv_path": str(csv_path),
        "rows": rows,
        "columns": columns,
        "inputs": args.inputs,
        "outputs": args.outputs,
        "model_path": str(model_path),
        "validation_path": str(validation_path),
        "validation_status": validation_status or ("passed" if validation_passed else "failed"),
        "attached_at": datetime.now(timezone.utc).isoformat(),
    }
    training_note = f"已绑定 {rows} 组 COMSOL 参数扫描 CSV，并通过独立验证，可在声明范围内用于数值代理预测。"
    if training_note not in card.setdefault("thoughts", []):
        card["thoughts"].append(training_note)
    card.setdefault("implementation_path", []).append(
        "优先复用已验证 CSV 与代理模型；超出输入范围、几何或边界条件变化时应补充 COMSOL 扫描。"
    )
    card["numerical_training"] = evidence
    card["created_at"] = datetime.now(timezone.utc).isoformat()
    card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    memory = remember_case(card, args.memory_path)
    print(json.dumps({"evidence": evidence, "memory": memory}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



