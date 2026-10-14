from __future__ import annotations

import json
import hashlib
import joblib
import tempfile
import unittest
from pathlib import Path

from comsol_small_model.instruction_agent import respond_to_instruction
from comsol_small_model.code_generator import generate_comsol_code_from_memory
from comsol_small_model.geometry_parameter_knowledge import validate_geometry_readiness
from comsol_small_model.mesh_knowledge import infer_mesh_strategy
from comsol_small_model.solver_knowledge import infer_study_solver
from comsol_small_model.result_knowledge import infer_result_exports
from comsol_small_model.modeling_readiness import assess_modeling_readiness
from comsol_small_model.closure_audit import build_closure_audit
from comsol_small_model.material_property_knowledge import validate_material_readiness
from comsol_small_model.staged_modeling import approve_current_step, create_staged_workflow, final_modeling_package
from comsol_small_model.surrogate_runtime import (
    detect_joule_rectangle_scope_changes,
    extract_joule_rectangle_prediction_inputs,
    extract_thermal_actuator_prediction_inputs,
    is_thermal_actuator_prediction_request,
    is_thermal_actuator_augmentation_request,
    is_joule_rectangle_prediction_request,
    load_surrogate_payload,
    predict_registered_surrogate,
)
from web_app import (
    _chat_code_read_result,
    _extract_heat_convection_2d_inputs,
    _extract_electric_field_concentric_cylinders_inputs,
    _extract_tapered_cantilever_force_inputs,
    _extract_lid_driven_cavity_reynolds_inputs,
    _extract_fresnel_equations_rf_inputs,
    _extract_power_inductor_frequency_inputs,
    _extract_gecko_foot_inputs,
    _gecko_foot_prediction_dialogue,
    _is_gecko_foot_request,
    _heat_convection_2d_prediction_dialogue,
    _electric_field_concentric_cylinders_prediction_dialogue,
    _is_chat_code_read_request,
    _is_heat_convection_2d_request,
    _is_electric_field_concentric_cylinders_request,
    _is_tapered_cantilever_force_request,
    _is_lid_driven_cavity_reynolds_request,
    _is_fresnel_equations_rf_request,
    _is_power_inductor_frequency_request,
    _lid_driven_cavity_reynolds_prediction_dialogue,
    _tapered_cantilever_force_prediction_dialogue,
    _fresnel_equations_rf_prediction_dialogue,
    _thermal_actuator_prediction_dialogue,
    _power_inductor_frequency_prediction_dialogue,
    _surrogate_runtime_audit_status,
)


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = ROOT / "generated" / "training_benchmarks"


class TrainingRegressionTests(unittest.TestCase):

    def test_surrogate_runtime_health_reads_persisted_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "registry.json"
            registry.write_text('{"models": []}', encoding="utf-8")
            report = {
                "overall_passed": True,
                "generated_at": "2026-09-12T00:00:00+00:00",
                "registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(),
                "registered_models": 29,
                "validated_models": 27,
                "passed": 27,
                "failed": 0,
                "missing_artifacts": 0,
                "warning_count": 0,
                "feature_name_warning_count": 0,
                "relocation_tested": True,
                "relocation_failures": 0,
            }
            path = Path(directory) / "audit.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            status = _surrogate_runtime_audit_status(path, registry)
        self.assertTrue(status["available"])
        self.assertTrue(status["healthy"])
        self.assertEqual(status["passed"], 27)
        self.assertTrue(status["relocation_tested"])

    def test_surrogate_runtime_health_rejects_stale_registry_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "registry.json"
            registry.write_text('{"models": []}', encoding="utf-8")
            report = {
                "overall_passed": True,
                "registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(),
            }
            path = Path(directory) / "audit.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            registry.write_text('{"models": [{"id": "new"}]}', encoding="utf-8")
            status = _surrogate_runtime_audit_status(path, registry)
        self.assertTrue(status["available"])
        self.assertFalse(status["healthy"])
        self.assertEqual(status["state"], "stale")
        self.assertFalse(status["audit_matches_registry"])

    def test_surrogate_runtime_health_detects_split_legacy_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / "models" / "surrogate_registry.json"
            registry.parent.mkdir()
            registry.write_text('{"models": [{"id": "canonical"}]}', encoding="utf-8")
            report = {
                "overall_passed": True,
                "registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(),
            }
            audit_path = root / "audit.json"
            audit_path.write_text(json.dumps(report), encoding="utf-8")
            legacy = root / "surrogate_registry.json"
            legacy.write_text('{"models": [{"id": "legacy-only"}]}', encoding="utf-8")
            status = _surrogate_runtime_audit_status(audit_path, registry, legacy)
        self.assertFalse(status["healthy"])
        self.assertEqual(status["state"], "registry_split")
        self.assertEqual(status["legacy_registry_conflicts"], ["legacy-only"])


    def test_gecko_foot_request_extracts_force_and_angle_units(self) -> None:
        instruction = "壁虎足响应预测，Fc=0.3 uN，Ff=0.25 uN，theta=60 度"
        self.assertTrue(_is_gecko_foot_request(instruction))
        self.assertEqual(
            _extract_gecko_foot_inputs(instruction),
            {"Fc_uN": 0.3, "Ff_uN": 0.25, "theta_deg": 60.0},
        )

    def test_gecko_foot_dialogue_reports_three_outputs(self) -> None:
        response = _gecko_foot_prediction_dialogue(
            {
                "ok": True,
                "prediction": {"max_v_Mises_Pa": 2.1e7, "max_disp_m": 3.1e-6, "max_ep1": 0.011},
                "validation": {
                    "passed": True,
                    "training_rows": 135,
                    "holdout_rows": 4,
                    "per_output_relative_validation": {
                        "max_v_Mises_Pa": {"max_relative_error_percent": 2.01},
                        "max_disp_m": {"max_relative_error_percent": 1.85},
                        "max_ep1": {"max_relative_error_percent": 1.94},
                    },
                },
                "validated_ranges": {"Fc_uN": {"min": 0.2, "max": 0.6}},
            }
        )
        self.assertIn("最大 von Mises 应力", response["assistant_message"])
        self.assertIn("最大位移", response["assistant_message"])
        self.assertIn("最大主应变", response["assistant_message"])
        self.assertIn("训练样本：135，留出样本：4", response["explanation_sections"][0]["items"])

    def test_power_inductor_request_extracts_frequency_units(self) -> None:
        instruction = "功率电感器，频率=10 kHz"
        self.assertTrue(_is_power_inductor_frequency_request(instruction))
        self.assertEqual(_extract_power_inductor_frequency_inputs(instruction), {"frequency_Hz": 10000.0})

    def test_power_inductor_dialogue_reports_prediction_and_validation(self) -> None:
        response = _power_inductor_frequency_prediction_dialogue(
            {
                "ok": True,
                "prediction": {"inductance_H": 1.14e-4, "conductance_S": 1.4e-3},
                "validation": {
                    "training_rows": 6,
                    "holdout_rows": 5,
                    "passed": True,
                    "selected_model": "log_frequency_log_output",
                    "candidate_reports": {"log_frequency_log_output": {"max_relative_error_percent": 1.414}},
                },
            }
        )
        self.assertIn("0.000114", response["assistant_message"])
        items = response["explanation_sections"][0]["items"]
        self.assertIn("训练样本：6，留出样本：5", items)
        self.assertIn("最大相对误差：1.414%", items)

    def test_power_inductor_dialogue_rejects_out_of_range_prediction(self) -> None:
        response = _power_inductor_frequency_prediction_dialogue({"ok": False})
        self.assertIn("不能外推", response["assistant_message"])

    def test_heat_convection_request_extracts_chinese_coefficient(self) -> None:
        instruction = "二维稳态传导传热，对流换热系数 h=750，预测温度"
        self.assertTrue(_is_heat_convection_2d_request(instruction))
        self.assertEqual(_extract_heat_convection_2d_inputs(instruction), {"convection_coefficient_W_m2_K": 750.0})

    def test_heat_convection_dialogue_rejects_out_of_range_prediction(self) -> None:
        response = _heat_convection_2d_prediction_dialogue({"ok": False, "out_of_range": {"convection_coefficient_W_m2_K": 1200}})
        self.assertIn("不能外推", response["assistant_message"])

    def test_heat_convection_dialogue_reports_temperature(self) -> None:
        response = _heat_convection_2d_prediction_dialogue({"ok": True, "prediction": {"temperature_at_0p6_0p2_K": 291.4, "maximum_temperature_K": 373.15}, "validation": {"per_output_relative_validation": {"temperature_at_0p6_0p2_K": {"max_relative_error_percent": 0.04}}}})
        self.assertIn("291.400 K", response["assistant_message"])
        self.assertIn("独立 COMSOL 验证", response["explanation_sections"][0]["title"])
    def test_concentric_cylinder_request_extracts_voltage(self) -> None:
        self.assertTrue(_is_electric_field_concentric_cylinders_request("同心圆柱静电场，内圆柱电势 V0=100 V"))
        self.assertEqual(_extract_electric_field_concentric_cylinders_inputs("同心圆柱电场，电压=100 V"), {"voltage_V": 100.0})

    def test_concentric_cylinder_dialogue_rejects_out_of_range_prediction(self) -> None:
        response = _electric_field_concentric_cylinders_prediction_dialogue({"ok": False, "out_of_range": {"voltage_V": 180}})
        self.assertIn("不能外推", response["assistant_message"])
    def test_fresnel_request_extracts_incident_angle(self) -> None:
        instruction = "菲涅尔反射，入射角=45 deg"
        self.assertTrue(_is_fresnel_equations_rf_request(instruction))
        self.assertEqual(_extract_fresnel_equations_rf_inputs(instruction), {"incident_angle_deg": 45.0})

    def test_fresnel_dialogue_rejects_out_of_range_prediction(self) -> None:
        response = _fresnel_equations_rf_prediction_dialogue({"ok": False, "out_of_range": {"incident_angle_deg": 80}})
        self.assertIn("不能外推", response["assistant_message"])

    def test_fresnel_dialogue_reports_two_polarizations(self) -> None:
        response = _fresnel_equations_rf_prediction_dialogue({"ok": True, "prediction": {"TE_reflectance": 0.092, "TM_reflectance": 0.00846}, "validation": {"per_output_absolute_validation": {"TE_reflectance": {"max_absolute_error": 0.003}}}})
        self.assertIn("TE 功率反射率为 0.092000", response["assistant_message"])
        self.assertIn("TM 功率反射率为 0.008460", response["assistant_message"])
    def test_lid_driven_cavity_request_extracts_reynolds_number(self) -> None:
        instruction = "顶盖驱动方腔流，Re=500"
        self.assertTrue(_is_lid_driven_cavity_reynolds_request(instruction))
        self.assertEqual(_extract_lid_driven_cavity_reynolds_inputs(instruction), {"Re": 500.0})

    def test_lid_driven_cavity_dialogue_rejects_out_of_range_prediction(self) -> None:
        response = _lid_driven_cavity_reynolds_prediction_dialogue({"ok": False, "out_of_range": {"Re": 1200}})
        self.assertIn("不能外推", response["assistant_message"])
    def test_tapered_cantilever_request_extracts_force(self) -> None:
        instruction = "锥形悬臂梁，边界力=10000000 N/m"
        self.assertTrue(_is_tapered_cantilever_force_request(instruction))
        self.assertEqual(_extract_tapered_cantilever_force_inputs(instruction), {"boundary_force_N_m": 10000000.0})

    def test_tapered_cantilever_dialogue_rejects_out_of_range_prediction(self) -> None:
        response = _tapered_cantilever_force_prediction_dialogue({"ok": False, "out_of_range": {"boundary_force_N_m": 2e7}})
        self.assertIn("不能外推", response["assistant_message"])
    def test_single_output_surrogate_prediction_keeps_output_name(self) -> None:
        from comsol_small_model.surrogate import predict

        model_path = ROOT / "generated" / "models" / "thermal_actuator_voltage_dense_poly_warningfree_tmax_surrogate.joblib"
        result = predict(model_path, [6.0, 20000.0, 400.0])

        self.assertIn("Tmax_K", result)
        self.assertGreater(result["Tmax_K"], 0.0)

    def _load(self, relative: str) -> dict:
        path = BENCHMARK_ROOT / relative
        self.assertTrue(path.is_file(), f"missing benchmark: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_physics_judgement_benchmark_has_no_review_cases(self) -> None:
        report = self._load("physics_judgement/thermal_electrical_physics_benchmark.json")
        self.assertEqual(report["needs_review"], 0)
        self.assertEqual(report["passed"], report["case_count"])

    def test_boundary_condition_benchmark_has_no_review_cases(self) -> None:
        report = self._load("boundary_conditions/boundary_condition_benchmark.json")
        self.assertEqual(report["needs_review"], 0)
        self.assertEqual(report["passed"], report["case_count"])

    def test_ambiguous_model_request_requests_missing_evidence(self) -> None:
        response = respond_to_instruction("自动生成 COMSOL 模型")
        self.assertTrue(response["clarifying_questions"])
        self.assertTrue(response["risk_flags"])

    def test_physics_answer_precedes_material_answer(self) -> None:
        response = respond_to_instruction("薄膜电阻通电发热，判断物理场和材料参数")
        self.assertIn("physics_selection", response["intent"])
        self.assertIn("物理场选择判断", response["assistant_message"])

    def test_chat_can_read_explicit_matlab_code_path(self) -> None:
        code_path = ROOT / "generated" / "staged_workflows" / "final_code" / "joule_rectangle_auto_solve.m"
        instruction = f"读取代码并分析 {code_path}"
        self.assertTrue(_is_chat_code_read_request(instruction))
        result = _chat_code_read_result(instruction)
        self.assertEqual(result["kind"], "matlab")
        self.assertTrue(result["analysis"]["has_comsol_api"])


    def test_material_readiness_blocks_missing_coupled_properties(self) -> None:
        readiness = validate_material_readiness(
            "electric current heat transfer joule heating",
            ["electromagnetics", "heat_transfer"],
            [],
        )
        self.assertFalse(readiness["ready_for_model_generation"])
        self.assertTrue(readiness["missing_required_properties"])
        self.assertTrue(readiness["risks"])

    def test_material_readiness_allows_complete_candidate_set(self) -> None:
        readiness = validate_material_readiness(
            "electric current heat transfer joule heating",
            ["electromagnetics", "heat_transfer"],
            [{"name": name} for name in ("rho", "k", "Cp", "sigma")],
        )
        self.assertTrue(readiness["ready_for_model_generation"])

    def test_known_material_profile_supplies_default_properties(self) -> None:
        readiness = validate_material_readiness(
            "copper electric current heat transfer joule heating",
            ["electromagnetics", "heat_transfer"],
            [],
        )
        self.assertTrue(readiness["ready_for_model_generation"])
        self.assertEqual(readiness["missing_required_properties"], [])
        self.assertTrue(readiness["assumptions"])

    def test_staged_material_step_shows_default_property_assumption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow = create_staged_workflow(
                "copper electric current heat transfer joule heating",
                memory_path=ROOT / "generated" / "case_memory" / "case_memory.json",
                output_dir=directory,
            )
        materials = next(step for step in workflow["steps"] if step["id"] == "materials")
        proposal = "\n".join(materials["proposal"])
        self.assertIn("默认物性假设", proposal)
        self.assertIn("temperature-dependent", proposal)

    def test_staged_material_step_exposes_readiness_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow = create_staged_workflow(
                "electric current heat transfer joule heating",
                memory_path=ROOT / "generated" / "case_memory" / "case_memory.json",
                output_dir=directory,
            )
        materials = next(step for step in workflow["steps"] if step["id"] == "materials")
        proposal = "\n".join(materials["proposal"])
        self.assertIn("物性就绪检查", proposal)
        self.assertIn("物性联动风险", proposal)

    def test_final_package_preserves_material_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow = create_staged_workflow(
                "electric current heat transfer joule heating",
                memory_path=ROOT / "generated" / "case_memory" / "case_memory.json",
                output_dir=directory,
            )
            workflow_path = Path(workflow["outputs"]["workflow"])
            for _ in range(len(workflow["steps"]) - 1):
                workflow = approve_current_step(workflow_path, approved=True, output_dir=directory)
            result = final_modeling_package(workflow_path, output_dir=directory)
            package = result["package"]
            self.assertIn("material_readiness", package)
            self.assertIn("verification_checklist", package)
            self.assertTrue(package["material_readiness"]["risks"])
            self.assertTrue(any("物性" in item for item in package["verification_checklist"]))
            self.assertFalse(package["execution_handoff"]["ready_to_solve"])
            self.assertNotEqual(package["execution_handoff"]["next_action"], "start_baseline_solve")
            unresolved = package["execution_handoff"]["unresolved_requirements"]
            self.assertEqual(len(unresolved), len(set(unresolved)))
            markdown = Path(result["outputs"]["markdown"]).read_text(encoding="utf-8")
            self.assertIn("ready_to_solve: `False`", markdown)

    def test_final_copper_package_has_no_material_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow = create_staged_workflow(
                "copper electric current heat transfer joule heating, compare different voltages, length 100 mm, width 50 mm",
                memory_path=ROOT / "generated" / "case_memory" / "case_memory.json",
                output_dir=directory,
            )
            workflow_path = Path(workflow["outputs"]["workflow"])
            for _ in range(len(workflow["steps"]) - 1):
                workflow = approve_current_step(workflow_path, approved=True, output_dir=directory)
            result = final_modeling_package(workflow_path, output_dir=directory)
            package = result["package"]
            blockers = package["modeling_readiness"]["blockers"]
            handoff = package["execution_handoff"]
            self.assertEqual([item for item in blockers if item.startswith("材料：")], [])
            self.assertTrue(handoff["ready_to_open"])
            self.assertFalse(handoff["ready_to_solve"])
            self.assertEqual(handoff["next_action"], "review_named_selections_and_boundaries")
            self.assertFalse(any("泊松比" in item for item in handoff["unresolved_requirements"]))
            self.assertEqual(package["generated_code"]["generation_readiness"]["approved_domains"], ["heat_transfer", "electromagnetics"])
            matlab_code = Path(result["outputs"]["matlab"]).read_text(encoding="utf-8")
            java_code = Path(result["outputs"]["java"]).read_text(encoding="utf-8")
            self.assertNotIn("SolidMechanics", matlab_code)
            self.assertNotIn("LaminarFlow", matlab_code)
            self.assertNotIn("SolidMechanics", java_code)
            self.assertNotIn("LaminarFlow", java_code)
            self.assertNotIn("T_melt", matlab_code)
            self.assertNotIn("U_mean", matlab_code)
            self.assertNotIn("T_melt", java_code)
            self.assertNotIn("U_mean", java_code)
            self.assertIn("geom.create('geom1', 2)", matlab_code)
            self.assertIn("geom('geom1').create('r1', 'Rectangle')", matlab_code)
            self.assertIn("mesh('mesh1').create('ftri1', 'FreeTri')", matlab_code)
            for selection in ("sel_terminal", "sel_ground", "sel_convection"):
                self.assertIn(selection, matlab_code)
                self.assertIn(selection, java_code)
            self.assertIn("feature('pot1').selection.named('sel_terminal')", matlab_code)
            self.assertIn("feature('gnd1').selection.named('sel_ground')", matlab_code)
            self.assertIn("feature('hf1').selection.named('sel_convection')", matlab_code)
            self.assertIn("cpl.create('maxop1', 'Maximum')", matlab_code)
            self.assertIn("cpl.create('aveop1', 'Average')", matlab_code)
            self.assertIn("selection('sel_terminal').geom('geom1', 1)", matlab_code)
            self.assertIn("create('pot1', 'ElectricPotential', 1)", matlab_code)
            self.assertIn("selection('sel_terminal').set([1])", matlab_code)
            self.assertIn("create('stat', 'Stationary')", matlab_code)
            self.assertNotIn("create('freq', 'Frequency')", matlab_code)
            self.assertIn("selection('sel_ground').set([3])", matlab_code)
            self.assertIn("selection('sel_convection').set([1 2 3 4])", matlab_code)
            self.assertIn('feature("pot1").selection().named("sel_terminal")', java_code)
            self.assertIn('selection("sel_terminal").geom("geom1", 1)', java_code)
            self.assertIn('feature("hf1").set("HeatFluxType", "ConvectiveHeatFlux")', java_code)
            self.assertIn('selection("sel_terminal").set(new int[]{1})', java_code)
            self.assertIn('selection("sel_ground").set(new int[]{3})', java_code)
            markdown = Path(result["outputs"]["markdown"]).read_text(encoding="utf-8")
            self.assertNotIn("blocker: 材料：", markdown)
            self.assertIn("review_named_selections_and_boundaries", markdown)
            self.assertIn("review-only default range 0.1-1 mV with 37 sample points", markdown)
            guidance = Path(result["outputs"]["guidance"]).read_text(encoding="utf-8")
            self.assertIn("## 执行前确认", guidance)
            self.assertIn("review_named_selections_and_boundaries", guidance)
            self.assertIn("核对端子、接地、对流面", guidance)
            self.assertIn(f"待核对项数量：`{len(handoff['unresolved_requirements'])}`", guidance)
            self.assertIn(f"优先处理：{handoff['unresolved_requirements'][0]}", guidance)
            self.assertIn("完成条件：逐项完成下方核对内容", guidance)
            self.assertIn(str(Path(result["outputs"]["verification"])), guidance)
            self.assertIn("实际采用物理场：传热 + 电流/电磁", guidance)

    def test_direct_code_generation_has_material_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = generate_comsol_code_from_memory(
                "electric current heat transfer joule heating",
                ROOT / "generated" / "case_memory" / "case_memory.json",
                directory,
                "material_gate",
                top_k=3,
            )
        readiness = generated.generation_readiness
        self.assertIn("material_readiness", readiness)
        self.assertIn("geometry_readiness", readiness)
        self.assertFalse(readiness["material_readiness"]["ready_for_model_generation"])
        self.assertIn("ready_for_meshing", readiness["geometry_readiness"])
        self.assertFalse(readiness["ready_to_solve"])

    def test_auto_boundary_rule_requires_explicit_rectangle_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = generate_comsol_code_from_memory(
                "copper electric current heat transfer joule heating",
                ROOT / "generated" / "case_memory" / "case_memory.json",
                directory,
                "manual_boundary_review",
                top_k=3,
            )
        self.assertIn("terminal_boundary_id", generated.matlab_code)
        self.assertNotIn("selection('sel_terminal').set([1]);", generated.matlab_code)

    def test_2d_temperature_outputs_use_surface_evaluations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = generate_comsol_code_from_memory(
                "copper electric current heat transfer joule heating, length 100 mm, width 50 mm, compare different voltages",
                ROOT / "generated" / "case_memory" / "case_memory.json",
                directory,
                "surface_temperature_results",
                top_k=3,
            )
        self.assertIn("'MaxSurface'", generated.matlab_code)
        self.assertIn("'AvSurface'", generated.matlab_code)
        self.assertNotIn("'MaxVolume'", generated.matlab_code)

    def test_direct_copper_code_generation_has_no_material_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = generate_comsol_code_from_memory(
                "copper electric current heat transfer joule heating, length 100 mm, width 50 mm",
                ROOT / "generated" / "case_memory" / "case_memory.json",
                directory,
                "copper_material_gate",
                top_k=3,
            )
        readiness = generated.generation_readiness
        unresolved = readiness["unresolved_requirements"]
        self.assertTrue(readiness["material_readiness"]["ready_for_model_generation"])
        self.assertFalse(any("材料物性" in item for item in unresolved))
        self.assertFalse(readiness["ready_to_solve"])

    def test_direct_copper_code_generation_preserves_explicit_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = generate_comsol_code_from_memory(
                "copper electric current heat transfer joule heating, length 100 mm, width 50 mm",
                ROOT / "generated" / "case_memory" / "case_memory.json",
                directory,
                "copper_geometry",
                top_k=3,
            )
        self.assertIn("100[mm]", generated.matlab_code)
        self.assertIn("50[mm]", generated.matlab_code)
        self.assertIn("100[mm]", generated.java_code)
        self.assertIn("50[mm]", generated.java_code)

    def test_direct_copper_code_generation_adds_voltage_sweep(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = generate_comsol_code_from_memory(
                "copper electric current heat transfer joule heating, compare different voltages, length 100 mm, width 50 mm",
                ROOT / "generated" / "case_memory" / "case_memory.json",
                directory,
                "copper_voltage_sweep",
                top_k=3,
            )
        self.assertIn("Parametric", generated.matlab_code)
        self.assertIn("Vtot", generated.matlab_code)
        self.assertIn("range(0.1[mV],0.025[mV],1[mV])", generated.matlab_code)
        self.assertIn("approved values", generated.matlab_code)
        self.assertIn("Parametric", generated.java_code)
        self.assertIn("Vtot", generated.java_code)
        self.assertIn("range(0.1[mV],0.025[mV],1[mV])", generated.java_code)
        self.assertIn("approved values", generated.java_code)
        self.assertTrue(any("待审核默认范围" in item for item in generated.theory_guidance))

    def test_dc_joule_heating_uses_stationary_study_even_with_retrieved_frequency_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = generate_comsol_code_from_memory(
                "copper electric current heat transfer joule heating, length 100 mm, width 50 mm, compare different voltages; retrieved note mentions modal eigenfrequency",
                ROOT / "generated" / "case_memory" / "case_memory.json",
                directory,
                "dc_joule_stationary",
                top_k=3,
            )
        self.assertIn("create('stat', 'Stationary')", generated.matlab_code)
        self.assertNotIn("create('freq', 'Frequency')", generated.matlab_code)

    def test_geometry_readiness_requires_dimensions_or_case_evidence(self) -> None:
        missing = validate_geometry_readiness("建立一个未知结构模型", [], [])
        self.assertFalse(missing["ready_for_meshing"])
        self.assertTrue(missing["missing_geometry_evidence"])

        complete = validate_geometry_readiness("二维矩形板，长度 100 mm，宽度 50 mm", ["structural"], [])
        self.assertTrue(complete["ready_for_meshing"])

    def test_mesh_strategy_follows_physics_and_singular_regions(self) -> None:
        mesh = infer_mesh_strategy("水力压裂中的流体流动与裂纹尖端", ["fluid", "structural"])
        self.assertIn("入口/出口/壁面边界层", mesh["local_refinements"])
        self.assertIn("裂纹尖端/孔洞/弱面", mesh["local_refinements"])
        self.assertTrue(mesh["checks"])

    def test_solver_strategy_distinguishes_transient_eigen_and_sweep(self) -> None:
        transient = infer_study_solver("瞬态温度变化，比较不同热流范围", ["heat_transfer"])
        self.assertEqual(transient["primary_study"], "Time Dependent")
        self.assertIn("Parametric Sweep", transient["studies"])
        eigen = infer_study_solver("音叉特征频率和模态", ["structural"])
        self.assertEqual(eigen["primary_study"], "Eigenfrequency")
        self.assertTrue(eigen["requires_eigenvalue_count"])

    def test_result_exports_follow_requested_quantities(self) -> None:
        result = infer_result_exports("焦耳热引起的温度和电流密度变化，并与实验结果对比", ["heat_transfer", "electromagnetics"])
        self.assertIn("T_max", result["outputs"])
        self.assertIn("current_density_max", result["outputs"])
        self.assertTrue(result["requires_reference_comparison"])

    def test_joule_prediction_request_requires_explicit_voltage(self) -> None:
        self.assertTrue(is_joule_rectangle_prediction_request("请预测焦耳热温度"))
        self.assertIsNone(extract_joule_rectangle_prediction_inputs("请预测焦耳热温度"))
        self.assertEqual(
            extract_joule_rectangle_prediction_inputs("在 0.5 mV 下预测焦耳热温度"),
            {"Vtot_V": 0.0005},
        )

    def test_thermal_actuator_prediction_requires_all_three_inputs(self) -> None:
        self.assertTrue(is_thermal_actuator_prediction_request("微执行器焦耳热温度预测"))
        self.assertIsNone(extract_thermal_actuator_prediction_inputs("微执行器焦耳热温度预测，DV=3 V"))
        self.assertEqual(
            extract_thermal_actuator_prediction_inputs("微执行器焦耳热温度预测，DV=3 V，htc_s=20000，htc_us=400"),
            {"DV_V": 3.0, "htc_s_W_m2K": 20000.0, "htc_us_W_m2K": 400.0},
        )

    def test_thermal_actuator_augmentation_request_accepts_complete_out_of_range_input(self) -> None:
        request = "微执行器扩展训练到 DV=6 V，htc_s=20000，htc_us=400"
        self.assertTrue(is_thermal_actuator_augmentation_request(request))
        self.assertEqual(
            extract_thermal_actuator_prediction_inputs(request),
            {"DV_V": 6.0, "htc_s_W_m2K": 20000.0, "htc_us_W_m2K": 400.0},
        )
    def test_thermal_actuator_prediction_blocks_out_of_range_inputs(self) -> None:
        registry = ROOT / "generated" / "models" / "surrogate_registry.json"
        prediction = predict_registered_surrogate(
            registry,
            "thermal_actuator_safe_tmax_surrogate",
            {"DV_V": 6.0, "htc_s_W_m2K": 20000.0, "htc_us_W_m2K": 400.0},
        )
        self.assertFalse(prediction["ok"])
        self.assertIn("DV_V", prediction["out_of_range"])
        dialogue = _thermal_actuator_prediction_dialogue(prediction)
        self.assertIn("不能给出可靠", dialogue["assistant_message"])
    def test_joule_prediction_blocks_explicit_scope_changes(self) -> None:
        self.assertEqual(detect_joule_rectangle_scope_changes("100 mm × 50 mm 铜矩形焦耳热预测"), [])
        changes = detect_joule_rectangle_scope_changes("铝板长度 120 mm、宽度 50 mm，焦耳热温度预测")
        self.assertIn("长度不是已验证的 100 mm", changes)
        self.assertIn("材料不是已验证的铜", changes)

    def test_registered_joule_prediction_retains_comsol_error_evidence(self) -> None:
        registry = ROOT / "generated" / "models" / "surrogate_registry.json"
        prediction = predict_registered_surrogate(
            registry,
            "joule_rectangle_validated_surrogate",
            {"Vtot_V": 0.0005},
        )
        self.assertTrue(prediction["ok"])
        self.assertTrue(prediction["validation"]["passed"])
        self.assertGreater(prediction["validation"]["per_output"]["Tmax_K"]["rmse"], 0.0)

    def test_registered_gecko_multioutput_prediction_uses_per_output_estimators(self) -> None:
        registry = ROOT / "generated" / "models" / "surrogate_registry.json"
        prediction = predict_registered_surrogate(
            registry,
            "gecko_foot_surrogate",
            {"Fc_uN": 0.3, "Ff_uN": 0.25, "theta_deg": 60.0},
        )
        self.assertTrue(prediction["ok"])
        self.assertEqual(
            set(prediction["prediction"]),
            {"max_v_Mises_Pa", "max_disp_m", "max_ep1"},
        )
        self.assertTrue(prediction["validation"]["passed"])
        self.assertEqual(prediction["registry_status"], "validated_for_declared_scope")

    def test_surrogate_prediction_can_use_embedded_ranges_when_csv_moves(self) -> None:
        from comsol_small_model.surrogate_runtime import predict_validated_surrogate

        source = ROOT / "generated" / "models" / "gecko_foot_surrogate.joblib"
        payload = load_surrogate_payload(source)
        payload["training_csv_path"] = str(ROOT / "generated" / "training_runs" / "missing_gecko_training.csv")
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "gecko_moved.joblib"
            joblib.dump(payload, model)
            result = predict_validated_surrogate(
                model,
                {"Fc_uN": 0.3, "Ff_uN": 0.25, "theta_deg": 60.0},
            )
        self.assertTrue(result["ok"])
        self.assertIn("max_disp_m", result["prediction"])

    def test_registered_model_bundle_can_move_without_original_absolute_paths(self) -> None:
        registry_path = ROOT / "generated" / "models" / "surrogate_registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        entry = next(item for item in registry["models"] if item["id"] == "joule_rectangle_validated_surrogate")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            relocated_entry = dict(entry)
            for field in ("model_path", "model_card_json", "validation_report"):
                source = Path(entry[field])
                if not source.is_file():
                    source = registry_path.parent / source.name
                target = destination / source.name
                target.write_bytes(source.read_bytes())
                relocated_entry[field] = str(Path("Z:/missing/original") / source.name)
            relocated_entry["model_card"] = str(Path("Z:/missing/original") / Path(entry["model_card"]).name)
            payload = load_surrogate_payload(destination / Path(entry["model_path"]).name)
            payload["training_csv_path"] = str(Path("Z:/missing/original/training.csv"))
            joblib.dump(payload, destination / Path(entry["model_path"]).name)
            relocated_registry = {"schema": registry.get("schema"), "models": [relocated_entry]}
            relocated_registry_path = destination / "surrogate_registry.json"
            relocated_registry_path.write_text(json.dumps(relocated_registry), encoding="utf-8")

            result = predict_registered_surrogate(
                relocated_registry_path,
                "joule_rectangle_validated_surrogate",
                {"Vtot_V": 0.0005},
            )

        self.assertTrue(result["ok"])
        self.assertIn("Tmax_K", result["prediction"])
        self.assertTrue(result["validation"]["passed"])

    def test_pn_junction_carrier_prediction_restores_log_scale(self) -> None:
        registry = ROOT / "generated" / "models" / "surrogate_registry.json"
        prediction = predict_registered_surrogate(
            registry,
            "pn_junction_carrier_surrogate",
            {"bias_V": 0.3},
        )
        self.assertTrue(prediction["ok"])
        self.assertGreater(prediction["prediction"]["electron_density_at_junction_cm3"], 1e12)
        self.assertGreater(prediction["prediction"]["hole_density_at_junction_cm3"], 1e12)
    def test_pn_junction_current_density_prediction_restores_negative_sign(self) -> None:
        registry = ROOT / "generated" / "models" / "surrogate_registry.json"
        prediction = predict_registered_surrogate(
            registry,
            "pn_junction_current_density_surrogate",
            {"bias_V": 0.3},
        )
        self.assertTrue(prediction["ok"])
        self.assertLess(prediction["prediction"]["current_density_at_x_2_5um_A_m2"], 0.0)
        self.assertGreater(abs(prediction["prediction"]["current_density_at_x_2_5um_A_m2"]), 1.0)
    def test_closure_audit_reads_models_registry(self) -> None:
        audit = build_closure_audit(ROOT / "generated", ROOT / "training_program.json")
        self.assertGreaterEqual(audit["registered_models"], 1)
        self.assertTrue(audit["ready_for_scoped_prediction"])

    def test_overall_modeling_readiness_collects_blockers(self) -> None:
        readiness = assess_modeling_readiness("建立一个未知结构模型", {})
        self.assertFalse(readiness["ready_for_modeling"])
        self.assertTrue(readiness["blockers"])
        self.assertEqual(readiness["next_action"], "review_blockers")
        self.assertIn("boundary", readiness)
        self.assertIn("物理场：", "；".join(readiness["blockers"]))
        self.assertNotIn("comsol_key", "；".join(readiness["blockers"]))


if __name__ == "__main__":
    unittest.main()



