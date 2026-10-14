from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def request_json(base_url: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    if payload is None:
        request = Request(f"{base_url}{path}", method="GET")
    else:
        request = Request(
            f"{base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test the local COMSOL small model API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8880")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    health = request_json(base_url, "/api/health")
    material_probe = request_json(
        base_url,
        "/api/staged-workflow",
        {"requirement": "铜矩形薄板通电发热，长度100 mm，宽度50 mm"},
    )
    material_step = next(
        step for step in dict(material_probe["workflow"])["steps"] if step["id"] == "materials"
    )
    default_assumption_visible = any("默认物性假设" in str(item) for item in material_step["proposal"])
    if not default_assumption_visible:
        raise RuntimeError("material step did not expose the default-property assumption")
    material_text = "\n".join(str(item) for item in material_step["proposal"])
    if "待补充物性：当前候选参数已覆盖主要必填项" not in material_text:
        raise RuntimeError("known copper properties were not recognized as complete")
    created = request_json(
        base_url,
        "/api/staged-workflow",
        {"requirement": "铜矩形板通电发热，长度100 mm，宽度50 mm，比较不同电压下的最高温度"},
    )
    workflow = dict(created["workflow"])
    workflow_path = str(dict(workflow["outputs"])["workflow"])
    approved = 0
    while int(workflow["current_step"]) < len(workflow["steps"]) - 1:
        response = request_json(
            base_url,
            "/api/approve-staged-step",
            {"workflow_path": workflow_path, "approved": True, "comment": "API smoke test"},
        )
        workflow = dict(response["workflow"])
        approved += 1
    finalized = request_json(base_url, "/api/finalize-staged-workflow", {"workflow_path": workflow_path})
    package = dict(finalized["package"])
    handoff = dict(package["execution_handoff"])
    material_blockers = [
        str(item) for item in dict(package.get("modeling_readiness", {})).get("blockers", [])
        if str(item).startswith("材料：")
    ]
    if material_blockers:
        raise RuntimeError("known copper properties still appear as final material blockers")
    if not handoff.get("ready_to_open", False):
        raise RuntimeError("completed copper workflow did not produce an openable package")
    if handoff.get("ready_to_solve", False):
        raise RuntimeError("workflow bypassed named-selection and boundary review")
    if handoff.get("next_action") != "review_named_selections_and_boundaries":
        raise RuntimeError("unexpected next action after a complete copper workflow")
    report_markdown = Path(str(dict(finalized["outputs"])["markdown"])).read_text(encoding="utf-8")
    if "blocker: 材料：" in report_markdown:
        raise RuntimeError("final markdown report still contains copper material blockers")
    if "review_named_selections_and_boundaries" not in report_markdown:
        raise RuntimeError("final markdown report omitted the required COMSOL review action")
    if "100 mm" not in report_markdown or "50 mm" not in report_markdown:
        raise RuntimeError("final markdown report omitted the user-specified geometry dimensions")
    if not any(token in report_markdown for token in ("Parametric", "参数扫描", "不同电压")):
        raise RuntimeError("final markdown report omitted the requested voltage sweep")
    if "review-only default range 0.1-1 mV with 37 sample points" not in report_markdown:
        raise RuntimeError("final markdown report omitted the voltage-range review warning")
    matlab_path = Path(str(dict(finalized["outputs"])["matlab"]))
    matlab_code = matlab_path.read_text(encoding="utf-8")
    if "8960[kg/m^3]" not in matlab_code or "5.998e7[S/m]" not in matlab_code:
        raise RuntimeError("generated MATLAB file omitted the recognized copper default properties")
    if "100[mm]" not in matlab_code or "50[mm]" not in matlab_code:
        raise RuntimeError("generated MATLAB file omitted the user-specified geometry dimensions")
    if "geom.create('geom1', 2)" not in matlab_code or "create('r1', 'Rectangle')" not in matlab_code:
        raise RuntimeError("generated MATLAB file did not honor the two-dimensional geometry requirement")
    if "Parametric" not in matlab_code or "Vtot" not in matlab_code:
        raise RuntimeError("generated MATLAB file omitted the requested voltage sweep")
    if "range(0.1[mV],0.025[mV],1[mV])" not in matlab_code or "approved values" not in matlab_code:
        raise RuntimeError("generated MATLAB file omitted the voltage-range review warning")
    if "SolidMechanics" in matlab_code or "LaminarFlow" in matlab_code:
        raise RuntimeError("generated MATLAB file included an unapproved physics interface")
    if not all(selection in matlab_code for selection in ("sel_terminal", "sel_ground", "sel_convection")):
        raise RuntimeError("generated MATLAB file omitted named boundary-selection templates")
    if not all(token in matlab_code for token in (
        "feature('pot1').selection.named('sel_terminal')",
        "feature('gnd1').selection.named('sel_ground')",
        "feature('hf1').selection.named('sel_convection')",
        "selection('sel_terminal').geom('geom1', 1)",
        "create('pot1', 'ElectricPotential', 1)",
        "selection('sel_terminal').set([1])",
        "selection('sel_ground').set([3])",
        "selection('sel_convection').set([1 2 3 4])",
    )):
        raise RuntimeError("generated MATLAB file omitted the electrothermal boundary bindings")
    java_path = Path(str(dict(finalized["outputs"])["java"]))
    java_code = java_path.read_text(encoding="utf-8")
    if "8960[kg/m^3]" not in java_code or "5.998e7[S/m]" not in java_code:
        raise RuntimeError("generated Java file omitted the recognized copper default properties")
    if "100[mm]" not in java_code or "50[mm]" not in java_code:
        raise RuntimeError("generated Java file omitted the user-specified geometry dimensions")
    if 'geom().create("geom1", 2)' not in java_code or 'create("r1", "Rectangle")' not in java_code:
        raise RuntimeError("generated Java file did not honor the two-dimensional geometry requirement")
    if "Parametric" not in java_code or "Vtot" not in java_code:
        raise RuntimeError("generated Java file omitted the requested voltage sweep")
    if "range(0.1[mV],0.025[mV],1[mV])" not in java_code or "approved values" not in java_code:
        raise RuntimeError("generated Java file omitted the voltage-range review warning")
    if "SolidMechanics" in java_code or "LaminarFlow" in java_code:
        raise RuntimeError("generated Java file included an unapproved physics interface")
    if not all(selection in java_code for selection in ("sel_terminal", "sel_ground", "sel_convection")):
        raise RuntimeError("generated Java file omitted named boundary-selection templates")
    if not all(token in java_code for token in (
        'feature("pot1").selection().named("sel_terminal")',
        'feature("gnd1").selection().named("sel_ground")',
        'feature("hf1").selection().named("sel_convection")',
        'selection("sel_terminal").geom("geom1", 1)',
        'feature("hf1").set("HeatFluxType", "ConvectiveHeatFlux")',
        'selection("sel_terminal").set(new int[]{1})',
        'selection("sel_ground").set(new int[]{3})',
        'selection("sel_convection").set(new int[]{1, 2, 3, 4})',
    )):
        raise RuntimeError("generated Java file omitted the electrothermal boundary bindings")
    guidance_path = Path(str(dict(finalized["outputs"])["guidance"]))
    guidance_markdown = guidance_path.read_text(encoding="utf-8")
    if "待审核默认范围" not in guidance_markdown:
        raise RuntimeError("generated guidance omitted the voltage-range review warning")
    if "## 执行前确认" not in guidance_markdown or handoff.get("next_action", "") not in guidance_markdown:
        raise RuntimeError("generated guidance omitted the execution handoff")
    if "操作说明" not in guidance_markdown:
        raise RuntimeError("generated guidance omitted the user-facing next-step guidance")
    if f"待核对项数量：`{len(handoff.get('unresolved_requirements', []))}`" not in guidance_markdown:
        raise RuntimeError("generated guidance omitted the unresolved-item count")
    unresolved = list(handoff.get("unresolved_requirements", []))
    if unresolved and f"优先处理：{unresolved[0]}" not in guidance_markdown:
        raise RuntimeError("generated guidance omitted the priority unresolved item")
    if "完成条件：" not in guidance_markdown:
        raise RuntimeError("generated guidance omitted the completion condition")
    verification_path = Path(str(dict(finalized["outputs"])["verification"]))
    if str(verification_path) not in guidance_markdown:
        raise RuntimeError("generated guidance omitted the verification-record path")
    if "实际采用物理场：传热 + 电流/电磁" not in guidance_markdown:
        raise RuntimeError("generated guidance omitted the approved physics summary")
    report = {
        "kind": "local_api_smoke_test",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "health_ok": bool(health.get("ok", True)),
        "default_material_assumption_visible": default_assumption_visible,
        "final_material_blockers": material_blockers,
        "final_markdown_verified": True,
        "final_markdown_dimensions_verified": True,
        "final_markdown_voltage_sweep_verified": True,
        "final_markdown_voltage_range_warning_verified": True,
        "generated_matlab_material_verified": True,
        "generated_java_material_verified": True,
        "generated_geometry_dimensions_verified": True,
        "generated_two_dimensional_geometry_verified": True,
        "generated_voltage_sweep_verified": True,
        "generated_voltage_range_warning_verified": True,
        "generated_code_contains_only_approved_physics_verified": True,
        "generated_boundary_selection_templates_verified": True,
        "generated_boundary_feature_bindings_verified": True,
        "generated_guidance_voltage_range_warning_verified": True,
        "generated_guidance_execution_handoff_verified": True,
        "generated_guidance_next_step_explanation_verified": True,
        "generated_guidance_unresolved_count_verified": True,
        "generated_guidance_priority_item_verified": True,
        "generated_guidance_completion_condition_verified": True,
        "generated_guidance_verification_path_verified": True,
        "generated_guidance_approved_physics_verified": True,
        "workflow_path": workflow_path,
        "approved_steps": approved,
        "package_outputs": finalized["outputs"],
        "ready_to_open": handoff.get("ready_to_open", False),
        "ready_to_solve": handoff.get("ready_to_solve", False),
        "next_action": handoff.get("next_action", "unknown"),
        "unresolved_count": len(handoff.get("unresolved_requirements", [])),
    }
    destination = ROOT / "generated" / "training_runs" / f"local_api_smoke_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "local_api_smoke_test.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path), **report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
