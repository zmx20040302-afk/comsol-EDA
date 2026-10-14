from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.boundary_knowledge import infer_boundary_conditions


CASES = [
    {"id": "BC-01", "prompt": "悬臂梁左端固定，右端施加集中力，求位移和应力。", "expected": ["固定约束", "载荷"]},
    {"id": "BC-02", "prompt": "二维板左边界温度为 350 K，右边界绝热，求稳态温度场。", "expected": ["固定温度", "绝热"]},
    {"id": "BC-03", "prompt": "金属表面受到 1000 W/m2 热通量，另一侧与环境对流换热。", "expected": ["热通量", "对流换热"]},
    {"id": "BC-04", "prompt": "导电薄膜左端施加电压，右端接地，其他边界绝缘。", "expected": ["电压", "接地", "绝缘"]},
    {"id": "BC-05", "prompt": "流体从入口以给定速度进入，从出口以给定压力流出，壁面无滑移。", "expected": ["入口", "出口", "无滑移"]},
    {"id": "BC-06", "prompt": "煤层水力压裂外边界施加围压，钻孔内壁施加注入压力，初始孔隙压力为 0.1 MPa。", "expected": ["围压", "注入压力", "初始孔隙压力"]},
    {"id": "BC-07", "prompt": "热执行器初始温度为室温，通电后进行瞬态温升分析。", "expected": ["初始温度", "电流"]},
    {"id": "BC-08", "prompt": "利用几何对称性，只建立一半模型，对称面不允许法向位移和法向热流。", "expected": ["对称边界"]},
    {"id": "BC-09", "prompt": "两个接触零件之间允许接触和分离，接触面传递压力但不穿透。", "expected": ["接触", "不穿透"]},
    {"id": "BC-10", "prompt": "扩散问题左侧浓度固定为 1，右侧无通量，初始浓度为 0。", "expected": ["浓度", "无通量", "初始浓度"]},
]


def main() -> None:
    out_dir = ROOT / "generated" / "training_benchmarks" / "boundary_conditions"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in CASES:
        result = infer_boundary_conditions(case["prompt"])
        text = " ".join([
            str(result.get("summary", "")),
            " ".join(result.get("boundary_types", [])),
            " ".join(result.get("initial_conditions", [])),
            str(result.get("theory", "")),
            str(result.get("matlab_snippet", "")),
        ])
        missing = [label for label in case["expected"] if label.lower() not in text.lower()]
        rows.append({**case, "status": "passed" if not missing else "needs_review", "missing_expected_labels": missing, "result": result})
    report = {
        "kind": "boundary_condition_benchmark",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(rows),
        "passed": sum(row["status"] == "passed" for row in rows),
        "needs_review": sum(row["status"] == "needs_review" for row in rows),
        "cases": rows,
        "interpretation": "该基准检查边界类别和初始条件的可解释提取，不替代 COMSOL 中的真实边界编号与命名选择集核验。",
    }
    json_path = out_dir / "boundary_condition_benchmark.json"
    md_path = out_dir / "boundary_condition_benchmark.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 边界条件与初始条件判断基准", "", f"通过：{report['passed']}；待复核：{report['needs_review']}", ""]
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
