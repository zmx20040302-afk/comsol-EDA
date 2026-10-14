from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from comsol_small_model.case_sources import CaseSourceUnavailableError, resolve_case_source_path
from comsol_small_model.execution_pipeline import (
    ExecutionLease,
    complete_stage,
    create_execution_evidence,
    finish_execution,
)
from comsol_small_model.physics_selection import select_modeling_intent
from comsol_small_model.physics_validation import validate_physics_results
from comsol_small_model.repair_policy import build_repair_decision
from comsol_small_model.static_model_audit import audit_generated_model_code


class P1ModelingPipelineTests(unittest.TestCase):
    def test_linux_case_source_can_use_a_windows_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            mirror = root / "mirror"
            nested = mirror / "thermal" / "case.mph"
            nested.parent.mkdir(parents=True)
            nested.write_bytes(b"mph")
            config = root / "case_sources.json"
            config.write_text(
                json.dumps({
                    "schema": "comsol-case-sources",
                    "schemaVersion": "1.0.0",
                    "sources": [{
                        "id": "lab",
                        "source_path": "/home/lab/zhangmx/案例下载/案例下载",
                        "windows_mirror": str(mirror),
                    }],
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            resolved = resolve_case_source_path(
                "/home/lab/zhangmx/案例下载/案例下载/thermal/case.mph",
                project_root=root,
                config_path=config,
            )
            self.assertEqual(resolved, nested.resolve())

    def test_unavailable_linux_case_source_reports_configuration_action(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / "case_sources.json"
            config.write_text(json.dumps({
                "schema": "comsol-case-sources", "schemaVersion": "1.0.0",
                "sources": [{"id": "lab", "source_path": "/home/lab/cases"}],
            }), encoding="utf-8")
            with self.assertRaises(CaseSourceUnavailableError) as raised:
                resolve_case_source_path("/home/lab/cases/a.mph", project_root=root, config_path=config)
            self.assertIn("SSH", str(raised.exception))

    def test_flow_heat_intent_selects_two_interfaces_coupling_and_stationary_study(self) -> None:
        result = select_modeling_intent("二维层流流道冷却，计算出口温度和压降，稳态求解")
        self.assertEqual(set(result["selected_interface_ids"]), {"laminar_flow", "heat_transfer_fluids"})
        self.assertEqual(result["coupling_ids"], ["nonisothermal_flow"])
        self.assertEqual(result["study"]["type"], "Stationary")
        self.assertFalse(result["abstained"])

    def test_static_audit_catches_all_required_injected_defects(self) -> None:
        contract = {"schemaVersion": "1.0.0"}
        code = "\n".join([
            "model.component('comp1').physics.create('ht', 'HeatTransfer', 'geom1');",
            "model.component('comp1').physics('ht').selection.set([]);",
            "model.component('comp1').physics('ht').feature('x').set('T0', 'undefined_parameter');",
            "model.result.numerical.create('gev1', 'EvalGlobal');",
            "model.result.numerical('gev1').set('expr', 'wrong.T');",
        ])
        report = audit_generated_model_code(contract, code)
        rules = {row["rule"] for row in report["findings"]}
        self.assertTrue({
            "PARAM_UNDEFINED", "SELECTION_EMPTY", "MATERIAL_MISSING", "STUDY_MISSING",
            "RESULT_VARIABLE_UNKNOWN",
        }.issubset(rules))
        self.assertFalse(report["passed"])

    def test_execution_evidence_hashes_artifacts_and_lease_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            artifact = root / "result.csv"
            artifact.write_text("value\n1\n", encoding="utf-8")
            record = create_execution_evidence("job-test", contract_sha256="abc")
            for stage in record["stages"]:
                complete_stage(record, stage["id"], artifacts=[artifact] if stage["id"] == "export_results" else [])
            finish_execution(record)
            exported = next(row for row in record["stages"] if row["id"] == "export_results")
            self.assertEqual(record["status"], "completed")
            self.assertEqual(len(exported["artifacts"][0]["sha256"]), 64)

            first = ExecutionLease(root / "execution.lock", "job-1")
            second = ExecutionLease(root / "execution.lock", "job-2")
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
            second.release()

    def test_physics_validation_accepts_balanced_flow_and_acoustic_reference(self) -> None:
        report = validate_physics_results(
            ["laminar_flow", "pressure_acoustics"],
            {
                "mass_flow_in": 0.089838,
                "mass_flow_out": 0.088617,
                "pressure_in": 0.2401,
                "pressure_out": 0.0,
                "reynolds_number": 100.0,
                "frequency": 343.0023,
                "reference_frequency": 343.0,
                "wavelength_elements": 10,
            },
        )
        self.assertTrue(report["passed"])
        self.assertEqual(report["summary"]["errors"], 0)

    def test_repair_policy_limits_retry_and_requires_approval_for_physics_change(self) -> None:
        automatic = build_repair_decision(
            "undefined variable comp1.mat1.def.mu",
            attempt=1,
            proposed_changes=[{"field": "api_reference", "before": "mu", "after": "mu_fluid"}],
        )
        self.assertTrue(automatic["auto_repair_allowed"])
        self.assertEqual(len(automatic["allowed_changes"]), 1)

        gated = build_repair_decision(
            "unknown physics interface",
            attempt=1,
            proposed_changes=[{"field": "physics_interface", "before": "A", "after": "B"}],
        )
        self.assertTrue(gated["requires_user_approval"])
        self.assertFalse(gated["auto_repair_allowed"])

        exhausted = build_repair_decision("undefined variable", attempt=3, max_attempts=3)
        self.assertFalse(exhausted["retry_allowed"])
        self.assertEqual(exhausted["next_action"], "stop_retry_limit")


if __name__ == "__main__":
    unittest.main()
