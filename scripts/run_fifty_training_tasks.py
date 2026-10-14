from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.boundary_knowledge import infer_boundary_conditions
from comsol_small_model.case_memory import audit_memory, generate_model_plan, load_memory, query_memory, refresh_knowledge_system
from comsol_small_model.code_generator import generate_comsol_code_from_memory
from comsol_small_model.code_workspace import read_code_file
from comsol_small_model.file_reader import summarize_file
from comsol_small_model.geometry_parameter_knowledge import analyze_geometry_parameters
from comsol_small_model.instruction_agent import respond_to_instruction
from comsol_small_model.material_property_knowledge import analyze_material_properties
from comsol_small_model.training_roadmap import build_training_roadmap, write_training_roadmap

MEMORY = ROOT / "generated" / "case_memory" / "case_memory.json"
OUT = ROOT / "generated" / "training_runs" / f"fifty_tasks_{datetime.now().strftime('%Y%m%d%H%M%S')}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []

    def add(name: str, fn) -> None:
        try:
            result = fn()
            rows.append({"task": len(rows) + 1, "name": name, "status": "passed", "result": _compact(result)})
        except Exception as exc:  # noqa: BLE001
            rows.append({"task": len(rows) + 1, "name": name, "status": "failed", "error": str(exc)})

    # 1-10: knowledge memory and retrieval.
    add("读取案例记忆", lambda: {"count": len(load_memory(MEMORY).get("cases", []))})
    add("刷新知识系统", lambda: refresh_knowledge_system(MEMORY))
    add("质量审计", lambda: audit_memory(load_memory(MEMORY)))
    add("读取训练路线", lambda: build_training_roadmap(MEMORY)["current_state"])
    add("检索传热案例", lambda: query_memory("传导传热 对流换热 温度场", MEMORY, 3))
    add("检索结构案例", lambda: query_memory("弹性模量 泊松比 固定约束 应力", MEMORY, 3))
    add("检索流体案例", lambda: query_memory("入口 出口 压力 速度 层流", MEMORY, 3))
    add("检索电磁案例", lambda: query_memory("电势 电流 电导率 电场", MEMORY, 3))
    add("检索声学案例", lambda: query_memory("声压 特征频率 模态", MEMORY, 3))
    add("检索水力压裂案例", lambda: query_memory("煤层 围压 孔隙压力 裂纹扩展", MEMORY, 3))

    # 11-20: material-property reasoning.
    material_cases = [
        ("钢板传热", "钢板稳态传热，考虑密度、导热系数和比热"),
        ("铝板瞬态冷却", "铝板瞬态冷却，材料参数随温度变化"),
        ("煤岩力学", "煤岩受压，考虑弹性模量、泊松比和抗压强度"),
        ("水流", "水在管道内流动，考虑密度和动力黏度"),
        ("油流", "油在微通道内流动，黏度随温度变化"),
        ("薄膜电阻", "薄膜电阻通电发热，考虑电导率和温度依赖"),
        ("复合材料", "复合材料导热，各向异性导热系数"),
        ("水力压裂", "煤层水力压裂，考虑弹性模量、泊松比、渗透率和断裂能"),
        ("声学介质", "空气声学，考虑密度和声速"),
        ("电化学", "电化学溶液传质，考虑扩散系数和电导率"),
    ]
    for label, prompt in material_cases:
        add(f"材料物性-{label}", lambda prompt=prompt: analyze_material_properties(prompt, [], []))

    # 21-30: geometry and parameter reasoning.
    geometry_cases = [
        "一维杆件长度和截面积可扫描",
        "二维矩形板长度宽度和厚度",
        "三维圆柱体半径和高度",
        "轴对称圆管内流动",
        "中心带圆孔的二维方形煤层",
        "带圆角的支架结构",
        "STL 导入的复杂机械零件",
        "带自然裂隙的煤层几何",
        "微通道混合器几何",
        "电阻薄膜几何和电极边界",
    ]
    for index, prompt in enumerate(geometry_cases, 21):
        add(f"几何参数-{index}", lambda prompt=prompt: analyze_geometry_parameters(prompt, [], []))

    # 31-40: coupled physics, physics selection and boundary reasoning.
    coupled_cases = [
        "焦耳热：电流产生热量并求最高温度",
        "热应力：温度变化导致结构热膨胀",
        "自然对流：温度场和速度场耦合",
        "水力压裂：固体力学、孔隙压力和裂纹扩展",
        "流固耦合：流体压力使柔性结构变形",
    ]
    for prompt in coupled_cases:
        add(f"复合物理场-{prompt[:10]}", lambda prompt=prompt: respond_to_instruction(prompt + "，选择物理场并说明判断依据"))

    boundary_cases = [
        "左端固定、右端施加载荷",
        "左边界固定温度、右边界绝热",
        "表面热通量和对流换热",
        "入口速度、出口压力和壁面无滑移",
        "电压、接地和电绝缘",
    ]
    for prompt in boundary_cases:
        add(f"边界条件-{prompt[:10]}", lambda prompt=prompt: infer_boundary_conditions(prompt))

    # 41-50: code, file, data and system checks.
    add("生成热应力计划", lambda: generate_model_plan("二维热应力和热膨胀耦合", MEMORY, 5))
    add("生成水力压裂计划", lambda: generate_model_plan("二维单孔煤层水力压裂裂纹扩展", MEMORY, 5))
    add("生成审查级 MATLAB/Java", lambda: generate_comsol_code_from_memory("二维焦耳热耦合模型", MEMORY, OUT / "joule_code", "fifty_task_joule_heat", 5).as_dict())
    add("读取最近生成代码", lambda: read_code_file(sorted((OUT / "joule_code").glob("*.m"))[0]).as_dict())
    add("检查示例 CSV", lambda: summarize_file(ROOT / "examples" / "sample_comsol_data.csv").as_dict())
    add("写出训练路线快照", lambda: write_training_roadmap(OUT / "roadmap", MEMORY))
    add("主动澄清-物理场", lambda: respond_to_instruction("选择物理场"))
    add("主动澄清-代码生成", lambda: respond_to_instruction("自动生成 COMSOL 模型"))
    add("主动澄清-代理训练", lambda: respond_to_instruction("训练 CSV 代理模型"))
    add("检查本地网页健康接口", lambda: _health_check())

    payload = {
        "kind": "fifty_training_tasks_run",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_count": len(rows),
        "passed": sum(row["status"] == "passed" for row in rows),
        "failed": sum(row["status"] == "failed" for row in rows),
        "records": rows,
        "note": "本轮完成知识检索、理论判断、边界/材料/几何推理、代码审查和系统接口验证；未把未经过 COMSOL 实机求解的代码标记为可求解。",
    }
    json_path = OUT / "fifty_training_tasks.json"
    md_path = OUT / "fifty_training_tasks.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = ["# 连续五十项训练任务报告", "", f"通过：{payload['passed']}；失败：{payload['failed']}", ""]
    for row in rows:
        lines.append(f"{row['task']}. {row['name']}：{row['status']}")
        if row["status"] == "failed":
            lines.append(f"   - {row['error']}")
    lines.extend(["", payload["note"]])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(OUT), "passed": payload["passed"], "failed": payload["failed"]}, ensure_ascii=False))


def _compact(value):
    if isinstance(value, dict):
        keep = {key: value[key] for key in ("kind", "status", "ready_to_solve", "case_count", "summary", "intent", "clarifying_questions", "risk_flags", "outputs") if key in value}
        return keep or {"keys": list(value)[:20]}
    if isinstance(value, list):
        return {"count": len(value), "sample": value[:3]}
    return value


def _health_check():
    for port in (8880, 8881, 8882):
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                if response.status == 200:
                    return {"port": port, "status": "reachable"}
        except Exception:
            continue
    raise RuntimeError("no local web health endpoint responded")


if __name__ == "__main__":
    main()
