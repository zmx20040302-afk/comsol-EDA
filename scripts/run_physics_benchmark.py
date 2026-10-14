from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.instruction_agent import respond_to_instruction


CASES = [
    {"id": "TH-01", "prompt": "二维固体稳态导热，已知左侧温度和右侧对流换热，求温度分布。", "expected": ["Heat Transfer"]},
    {"id": "TH-02", "prompt": "金属板瞬态冷却，给定初始温度、环境温度和对流换热系数，求温度随时间变化。", "expected": ["Heat Transfer", "瞬态"]},
    {"id": "TH-03", "prompt": "薄膜电阻通电后发热，求电流密度、焦耳热和最高温度。", "expected": ["Electric Currents", "Heat Transfer"]},
    {"id": "TH-04", "prompt": "导体中电压驱动电流，同时计算导热和焦耳热温升。", "expected": ["Electric Currents", "Heat Transfer"]},
    {"id": "TH-05", "prompt": "受温度变化影响的金属支架热膨胀和热应力分析。", "expected": ["Heat Transfer", "Solid Mechanics"]},
    {"id": "TH-06", "prompt": "加热片向空气散热，考虑固体导热、空气流动和对流换热。", "expected": ["Heat Transfer", "Laminar Flow"]},
    {"id": "TH-07", "prompt": "封闭腔体内自然对流传热，研究温度场和速度场。", "expected": ["Heat Transfer", "Laminar Flow"]},
    {"id": "TH-08", "prompt": "电容器两端施加电压，求电势和电场分布，不考虑传热。", "expected": ["Electrostatics"]},
    {"id": "TH-09", "prompt": "一维杆件两端温度不同，求稳态温度和热流密度。", "expected": ["Heat Transfer"]},
    {"id": "TH-10", "prompt": "热电材料中电流与温度梯度共同作用，分析电势、温度和热电耦合。", "expected": ["Electric Currents", "Heat Transfer"]},
]


def main() -> None:
    out_dir = ROOT / "generated" / "training_benchmarks" / "physics_judgement"
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for case in CASES:
        response = respond_to_instruction(case["prompt"])
        message = str(response.get("assistant_message", ""))
        missing = [label for label in case["expected"] if label.lower() not in message.lower()]
        records.append({
            **case,
            "status": "passed" if not missing else "needs_review",
            "missing_expected_labels": missing,
            "intents": response.get("intent", []),
            "clarifying_questions": response.get("clarifying_questions", []),
            "risk_flags": response.get("risk_flags", []),
            "assistant_message": message,
        })
    result = {
        "kind": "physics_judgement_benchmark",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(records),
        "passed": sum(row["status"] == "passed" for row in records),
        "needs_review": sum(row["status"] == "needs_review" for row in records),
        "cases": records,
        "interpretation": "这是规则与案例知识的回归基准，不等同于神经网络训练；needs_review 样本应由用户确认后进入纠错记忆。",
    }
    json_path = out_dir / "thermal_electrical_physics_benchmark.json"
    md_path = out_dir / "thermal_electrical_physics_benchmark.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 热传导与电热物理场判断基准", "", f"通过：{result['passed']}；待复核：{result['needs_review']}", ""]
    for row in records:
        lines.append(f"- {row['id']}：{row['status']}；期望：{' + '.join(row['expected'])}")
        if row["missing_expected_labels"]:
            lines.append(f"  - 缺失：{'、'.join(row['missing_expected_labels'])}")
    lines.extend(["", result["interpretation"]])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "passed": result["passed"], "needs_review": result["needs_review"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
