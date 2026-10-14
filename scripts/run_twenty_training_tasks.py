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
from comsol_small_model.case_memory import audit_memory, generate_model_plan, load_memory, refresh_knowledge_system, query_memory
from comsol_small_model.code_generator import generate_comsol_code_from_memory
from comsol_small_model.file_reader import summarize_file
from comsol_small_model.geometry_parameter_knowledge import analyze_geometry_parameters
from comsol_small_model.instruction_agent import respond_to_instruction
from comsol_small_model.material_property_knowledge import analyze_material_properties
from comsol_small_model.training_roadmap import build_training_roadmap, write_training_roadmap


MEMORY = ROOT / "generated" / "case_memory" / "case_memory.json"
OUT = ROOT / "generated" / "training_runs" / f"twenty_tasks_{datetime.now().strftime('%Y%m%d%H%M%S')}"


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records = []

    def task(number: int, name: str, fn) -> None:
        try:
            result = fn()
            records.append({"task": number, "name": name, "status": "passed", "result": result})
        except Exception as exc:  # noqa: BLE001
            records.append({"task": number, "name": name, "status": "failed", "error": str(exc)})

    task(1, "读取案例记忆库", lambda: {"cases": len(load_memory(MEMORY).get("cases", []))})
    task(2, "刷新知识体系", lambda: refresh_knowledge_system(MEMORY))
    task(3, "运行质量审计", lambda: audit_memory(load_memory(MEMORY)))
    task(4, "生成训练路线", lambda: build_training_roadmap(MEMORY)["current_state"])
    task(5, "热传导案例检索", lambda: query_memory("二维稳态传导传热和对流边界", MEMORY, top_k=3))
    task(6, "结构力学案例检索", lambda: query_memory("扳手应力应变固定约束和外载荷", MEMORY, top_k=3))
    task(7, "流体案例检索", lambda: query_memory("圆柱绕流入口出口压力速度", MEMORY, top_k=3))
    task(8, "电磁案例检索", lambda: query_memory("薄膜电阻电流电势电导率", MEMORY, top_k=3))
    task(9, "电化学案例检索", lambda: query_memory("电化学抛光电解质传质电流", MEMORY, top_k=3))
    task(10, "声学案例检索", lambda: query_memory("房间特征模态声压频域", MEMORY, top_k=3))
    task(11, "热结构复合场判断", lambda: respond_to_instruction("热应力与热膨胀耦合，判断物理场和研究类型"))
    task(12, "水力压裂复合场判断", lambda: respond_to_instruction("煤层水力压裂，研究围压、孔隙压力和裂纹扩展，选择物理场"))
    task(13, "信息不足主动提问", lambda: respond_to_instruction("根据需求自动生成COMSOL模型")["clarifying_questions"])
    task(14, "边界条件推理", lambda: infer_boundary_conditions("二维水力压裂，外部围压，钻孔注入压力，裂纹扩展", ["structural", "fluid"]))
    task(15, "材料物性推理", lambda: analyze_material_properties("煤层水力压裂，考虑弹性、孔隙流和温度影响", ["structural", "fluid"], []))
    task(16, "几何参数推理", lambda: analyze_geometry_parameters("二维方形煤层，中心圆孔，孔径和围压可扫描", ["geometry", "structural"], []))
    task(17, "代表性需求建模计划", lambda: generate_model_plan("二维煤层单孔水力压裂，研究不同围压下裂纹扩展", MEMORY, top_k=5))
    task(18, "CSV 数据质量检查", lambda: summarize_file(ROOT / "examples" / "sample_comsol_data.csv").as_dict())
    task(19, "生成审查级 MATLAB/Java 骨架", lambda: generate_comsol_code_from_memory("二维煤层单孔水力压裂建模", MEMORY, OUT / "generated_code", "twenty_task_hydraulic_fracture", top_k=5).as_dict())
    task(20, "写出训练报告并刷新路线", lambda: write_training_roadmap(OUT / "roadmap", MEMORY))

    payload = {
        "kind": "twenty_training_tasks_run",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "memory_path": str(MEMORY),
        "task_count": len(records),
        "passed": sum(row["status"] == "passed" for row in records),
        "failed": sum(row["status"] == "failed" for row in records),
        "records": records,
        "interpretation": "本轮完成的是知识检索、理论判断、数据检查和代码骨架训练；没有把未经过 COMSOL 实机求解的代码标记为可求解模型。",
    }
    (OUT / "twenty_training_tasks.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = ["# 连续二十项训练任务报告", "", f"通过：{payload['passed']}；失败：{payload['failed']}", ""]
    for row in records:
        mark = "通过" if row["status"] == "passed" else "失败"
        lines.append(f"{row['task']}. {row['name']}：{mark}")
        if row["status"] == "failed":
            lines.append(f"   - 错误：{row['error']}")
    lines.extend(["", payload["interpretation"]])
    (OUT / "twenty_training_tasks.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(OUT), "passed": payload["passed"], "failed": payload["failed"]}, ensure_ascii=False))


if __name__ == "__main__":
    run()
