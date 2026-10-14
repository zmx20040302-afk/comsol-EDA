from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.material_property_knowledge import analyze_material_properties


CASES = [
    {"id": "MAT-01", "prompt": "二维稳态传导传热，材料需要密度、导热系数和比热容。", "expected": ["密度", "导热系数", "比热容"]},
    {"id": "MAT-02", "prompt": "瞬态金属冷却，导热系数和比热容随温度变化。", "expected": ["导热系数", "比热容", "温度"]},
    {"id": "MAT-03", "prompt": "线弹性结构受载，材料需要弹性模量和泊松比。", "expected": ["弹性模量", "泊松比"]},
    {"id": "MAT-04", "prompt": "水在微通道中流动，需要密度和动力黏度。", "expected": ["密度", "动力黏度"]},
    {"id": "MAT-05", "prompt": "油的黏度随温度变化，分析管内流动。", "expected": ["动力黏度", "温度"]},
    {"id": "MAT-06", "prompt": "薄膜电阻通电发热，需要电导率、导热系数、密度和比热容。", "expected": ["电导率", "导热系数", "密度", "比热容"]},
    {"id": "MAT-07", "prompt": "各向异性复合材料传热，导热系数随方向变化。", "expected": ["导热系数", "方向"]},
    {"id": "MAT-08", "prompt": "煤层水力压裂，材料需要弹性模量、泊松比、抗拉强度和断裂能。", "expected": ["弹性模量", "泊松比", "抗拉强度", "断裂能"]},
    {"id": "MAT-09", "prompt": "电化学传质，溶液需要扩散系数和电导率。", "expected": ["扩散系数", "电导率"]},
    {"id": "MAT-10", "prompt": "材料在频域电磁分析中，介电参数随频率变化。", "expected": ["频率"]},
]


def main() -> None:
    out_dir = ROOT / "generated" / "training_benchmarks" / "materials"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in CASES:
        result = analyze_material_properties(case["prompt"], [], [])
        text = " ".join([
            str(result.get("summary", "")),
            " ".join(item.get("name", "") for item in result.get("required_properties", [])),
            " ".join(item.get("name", "") for item in result.get("optional_properties", [])),
            " ".join(result.get("dependencies", [])),
        ])
        missing = [item for item in case["expected"] if item.lower() not in text.lower()]
        rows.append({**case, "status": "passed" if not missing else "needs_review", "missing_expected_labels": missing, "result": result})
    report = {
        "kind": "material_property_benchmark",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(rows),
        "passed": sum(row["status"] == "passed" for row in rows),
        "needs_review": sum(row["status"] == "needs_review" for row in rows),
        "cases": rows,
        "interpretation": "该基准检查材料必需物性和依赖关系的提取，不替代具体材料牌号、实验数据和单位核验。",
    }
    json_path = out_dir / "material_property_benchmark.json"
    md_path = out_dir / "material_property_benchmark.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 材料与物性参数判断基准", "", f"通过：{report['passed']}；待复核：{report['needs_review']}", ""]
    for row in rows:
        line = f"- {row['id']}：{row['status']}；期望：{'、'.join(row['expected'])}"
        if row["missing_expected_labels"]:
            line += f"；缺失：{'、'.join(row['missing_expected_labels'])}"
        lines.append(line)
    lines.extend(["", report["interpretation"]])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "passed": report["passed"], "needs_review": report["needs_review"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
