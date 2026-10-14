from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "benchmarks" / "end_to_end" / "tasks.jsonl"


DOMAIN_SPECS = {
    "solid_heat": {
        "domains": ["heat_transfer"],
        "interfaces": ["heat_transfer_solids"],
        "couplings": [],
        "study": "Stationary",
        "complete": [
            "建立二维铜板稳态固体传热模型，长100 mm宽50 mm，左侧300 K，右侧350 K，其余边界绝热，输出最高温度和总热流。",
            "建立一维铝杆稳态导热模型，长度200 mm，两端固定温度分别293.15 K和373.15 K，输出温度场和热流。",
            "建立二维硅芯片稳态传热模型，尺寸20 mm乘10 mm，体热源1e6 W/m3，底面300 K，其余表面对流，输出最高温度。",
            "建立三维铜块稳态传热模型，尺寸30 mm乘20 mm乘5 mm，一面350 K、对面300 K，其余绝热，输出平均温度和热通量。",
        ],
        "incomplete": [
            ("建立铜板稳态传热模型，左侧固定温度300 K、右侧固定温度350 K，输出最高温度。", ["geometry"]),
            ("建立二维稳态固体传热模型，长100 mm宽50 mm，左侧固定温度300 K、右侧固定温度350 K，输出最高温度。", ["materials"]),
            ("建立二维铜板稳态传热模型，长100 mm宽50 mm，输出最高温度和热流。", ["boundary_conditions"]),
        ],
        "parameterized": [
            "建立二维铜板稳态传热参数化模型，长100 mm宽50 mm，左侧固定温度300 K，右侧固定温度在330到370 K扫描，输出最高温度和热流。",
            "建立二维铝散热片稳态传热模型，长80 mm宽20 mm，底面350 K，环境293.15 K，对流系数5到25 W/(m2*K)扫描，输出最高温度。",
        ],
        "conflict": "建立二维铜板稳态传热模型，长度同时设为100 mm和-100 mm，左侧固定温度300 K、右侧固定温度350 K，输出最高温度。",
    },
    "electric_current": {
        "domains": ["electromagnetics"], "interfaces": ["electric_currents"], "couplings": [], "study": "Stationary",
        "complete": [
            "建立一维铜导线稳态电流模型，长度200 mm，一端1 V端子、另一端接地，输出电势和电流密度。",
            "建立二维铝导体稳态电流模型，尺寸100 mm乘20 mm，左端0.5 V、右端接地，输出压降和电流密度。",
            "建立三维铜母排稳态电流模型，长100 mm宽50 mm厚5 mm，端子电流160 A、另一端接地，输出电势和总电流。",
            "建立二维铜电阻片稳态电流模型，尺寸50 mm乘10 mm，左端端子施加电压2 V、右端接地，输出电流密度和电阻。",
        ],
        "incomplete": [
            ("建立铜导体稳态电流模型，一端1 V、另一端接地，输出电流密度。", ["geometry"]),
            ("建立一维稳态电流模型，长度200 mm，一端1 V、另一端接地，输出电流密度。", ["materials"]),
            ("建立一维铜导线稳态电流模型，长度200 mm，输出电势和电流密度。", ["boundary_conditions"]),
        ],
        "parameterized": [
            "建立一维铜导线稳态电流参数化模型，长度200 mm，一端电压0.1到1 V扫描、另一端接地，输出电流密度。",
            "建立二维铝导体稳态电流模型，尺寸100 mm乘20 mm，电导率2e7到4e7 S/m扫描，左端1 V右端接地，输出总电流。",
        ],
        "conflict": "建立一维铜导线稳态电流模型，长度200 mm，同一端子同时设置1 V和接地，另一端接地，输出电流密度。",
    },
    "electrothermal": {
        "domains": ["electromagnetics", "heat_transfer"], "interfaces": ["electric_currents", "heat_transfer_solids"], "couplings": ["electromagnetic_heating"], "study": "Stationary",
        "complete": [
            "建立三维铜母排稳态焦耳热模型，长100 mm宽50 mm厚5 mm，一端1 V另一端接地，环境293.15 K并表面对流，输出最高温度和电流密度。",
            "建立一维铜导线稳态电热耦合模型，长度200 mm，左端端子施加电压0.2 V、右端接地，一端固定温度293.15 K，输出最高温度、温升和焦耳热。",
            "建立二维镍铬加热片稳态焦耳热模型，尺寸50 mm乘10 mm，端子12 V和接地，表面对流，输出温度和耗散功率。",
            "建立三维铝连接片稳态电热耦合模型，长80 mm宽20 mm厚3 mm，端子电流100 A和接地，环境300 K，输出最高温度。",
        ],
        "incomplete": [
            ("建立铜母排稳态焦耳热模型，端子1 V和接地，表面对流，输出最高温度。", ["geometry"]),
            ("建立三维母排稳态焦耳热模型，长100 mm宽50 mm厚5 mm，端子1 V和接地，表面对流，输出最高温度。", ["materials"]),
            ("建立三维铜母排稳态焦耳热模型，长100 mm宽50 mm厚5 mm，输出最高温度和电流密度。", ["boundary_conditions"]),
        ],
        "parameterized": [
            "建立三维铜母排稳态焦耳热参数化模型，长100 mm宽50 mm厚5 mm，端子电压10到30 mV扫描、另一端接地，对流系数2到10 W/(m2*K)扫描，输出最高温度。",
            "建立二维铜加热片稳态电热耦合模型，尺寸60 mm乘10 mm，端子电流10到50 A扫描、另一端接地，环境293.15 K，输出焦耳热和温升。",
        ],
        "conflict": "建立铜母排模型，同时要求只计算电流且禁止传热，又要求焦耳热稳态最高温度，长100 mm宽50 mm厚5 mm，端子1 V和接地，输出最高温度。",
    },
    "solid_mechanics": {
        "domains": ["structural"], "interfaces": ["solid_mechanics"], "couplings": [], "study": "Stationary",
        "complete": [
            "建立二维钢悬臂梁稳态固体力学模型，长100 mm高20 mm，左端固定约束、右端施加100 N向下载荷，输出最大位移和等效应力。",
            "建立三维铝支架静力模型，尺寸80 mm乘40 mm乘5 mm，底面固定约束、顶面施加1000 N压力载荷，输出位移和反力。",
            "建立二维钛合金板平面应力模型，长120 mm宽30 mm，左端固定约束、右端施加50 MPa拉伸载荷，输出主应力。",
            "建立三维钢轴静力模型，长度200 mm直径20 mm，一端固定约束、另一端施加10 N*m扭矩载荷，输出扭转角和等效应力。",
        ],
        "incomplete": [
            ("建立钢悬臂梁稳态固体力学模型，左端固定、右端100 N载荷，输出最大位移。", ["geometry"]),
            ("建立二维悬臂梁稳态固体力学模型，长100 mm高20 mm，左端固定、右端100 N载荷，输出最大位移。", ["materials"]),
            ("建立二维钢梁稳态固体力学模型，长100 mm高20 mm，输出最大位移和应力。", ["boundary_conditions"]),
        ],
        "parameterized": [
            "建立二维钢悬臂梁稳态参数化模型，长100 mm高20 mm，左端固定约束、右端载荷10到100 N扫描，输出最大位移和应力。",
            "建立二维铝板稳态固体力学模型，长100 mm宽30 mm，左端固定约束，孔径2到8 mm扫描，右端施加100 N拉伸载荷，输出孔边最大应力。",
        ],
        "conflict": "建立二维钢悬臂梁稳态模型，长100 mm高20 mm，同一左端同时完全固定和施加自由位移，右端100 N载荷，输出位移。",
    },
    "flow_heat": {
        "domains": ["fluid", "heat_transfer"], "interfaces": ["laminar_flow", "heat_transfer_fluids"], "couplings": ["nonisothermal_flow"], "study": "Stationary",
        "complete": [
            "建立二维水流道稳态流热耦合模型，长100 mm高10 mm，入口速度0.01 m/s温度293.15 K，出口0 Pa，上下壁313.15 K无滑移，输出压降和出口温度。",
            "建立二维空气通道稳态非等温流模型，长200 mm高20 mm，入口速度0.2 m/s温度300 K，出口0 Pa，壁面350 K无滑移，输出速度和温度。",
            "建立二维水冷板稳态流热模型，长150 mm高5 mm，入口质量流量0.01 kg/s温度293 K，出口0 Pa，热壁通量1000 W/m2，输出温升和压降。",
            "建立二维油流道稳态流热耦合模型，长100 mm高8 mm，入口0.02 m/s和300 K，出口0 Pa，壁面320 K无滑移，输出最大速度和出口温度。",
        ],
        "incomplete": [
            ("建立水流道稳态流热模型，入口0.01 m/s和293 K，出口0 Pa，热壁313 K，输出压降和出口温度。", ["geometry"]),
            ("建立二维流道稳态流热模型，长100 mm高10 mm，入口0.01 m/s和293 K，出口0 Pa，热壁313 K，输出压降和出口温度。", ["materials"]),
            ("建立二维水流道稳态流热模型，长100 mm高10 mm，输出速度、压降和温度。", ["boundary_conditions"]),
        ],
        "parameterized": [
            "建立二维水流道稳态流热参数化模型，长100 mm高10 mm，入口速度0.005到0.02 m/s和293 K，出口0 Pa，壁温303到323 K，输出压降和出口温度。",
            "建立二维空气通道稳态非等温流模型，长200 mm高20 mm，入口速度0.1到0.5 m/s和300 K，出口0 Pa，壁面350 K，输出换热量。",
        ],
        "conflict": "建立二维水流道稳态流热模型，长100 mm高10 mm，同一入口同时设置速度0.01 m/s和封闭无滑移壁，出口0 Pa，输出压降和出口温度。",
    },
    "pressure_acoustics": {
        "domains": ["acoustics"], "interfaces": ["pressure_acoustics"], "couplings": [], "study": "Eigenfrequency",
        "complete": [
            "建立一维空气开开管压力声学特征频率模型，长度0.5 m，两端压力释放，声速343 m/s，输出第一非零特征频率和声压。",
            "建立二维空气矩形声腔特征频率模型，尺寸1 m乘0.5 m，刚性壁，输出前五阶特征频率和声压模态。",
            "建立一维空气闭开管压力声学特征频率模型，长度1 m，一端刚性一端压力释放，输出前三阶频率。",
            "建立三维空气声腔特征频率模型，尺寸1 m乘0.8 m乘0.6 m，刚性壁，输出前六阶声压模态。",
        ],
        "incomplete": [
            ("建立空气开开管压力声学特征频率模型，两端压力释放，输出第一阶频率。", ["geometry"]),
            ("建立一维开开管压力声学特征频率模型，长度1 m，两端压力释放，输出第一阶频率。", ["materials"]),
            ("建立一维空气管压力声学特征频率模型，长度1 m，输出第一阶频率和声压。", ["boundary_conditions"]),
        ],
        "parameterized": [
            "建立一维空气开开管压力声学参数化模型，长度1 m，另做0.5到1.5 m参数扫描，两端压力释放，声速343 m/s，输出第一特征频率。",
            "建立二维空气矩形声腔特征频率模型，宽度0.5到1 m扫描、高度0.5 m、刚性壁，输出前五阶频率。",
        ],
        "conflict": "建立一维空气管压力声学模型，长度1 m，同一端同时设置刚性壁和压力释放边界，另一端压力释放，输出特征频率。",
    },
}


def build_tasks() -> list[dict]:
    rows: list[dict] = []
    for domain, spec in DOMAIN_SPECS.items():
        common = {key: spec[key] for key in ("domains", "interfaces", "couplings", "study")}
        for index, requirement in enumerate(spec["complete"], 1):
            rows.append({"id": f"{domain}-complete-{index}", "domain": domain, "category": "complete", "requirement": requirement, "expected_missing_categories": [], "expected_blocked": False, **common})
        for index, (requirement, missing) in enumerate(spec["incomplete"], 1):
            rows.append({"id": f"{domain}-incomplete-{index}", "domain": domain, "category": "incomplete", "requirement": requirement, "expected_missing_categories": missing, "expected_blocked": True, **common})
        for index, requirement in enumerate(spec["parameterized"], 1):
            rows.append({"id": f"{domain}-parameterized-{index}", "domain": domain, "category": "parameterized_or_coupled", "requirement": requirement, "expected_missing_categories": [], "expected_blocked": False, **common})
        rows.append({"id": f"{domain}-conflict-1", "domain": domain, "category": "conflict", "requirement": spec["conflict"], "expected_missing_categories": [], "expected_blocked": True, "expected_conflict": True, **common})
    return rows


def main() -> None:
    rows = build_tasks()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "task_count": len(rows), "domains": sorted({row['domain'] for row in rows})}, ensure_ascii=False))


if __name__ == "__main__":
    main()
