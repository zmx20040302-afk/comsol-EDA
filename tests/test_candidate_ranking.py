from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rank_surrogate_candidates.py"
SPEC = importlib.util.spec_from_file_location("rank_surrogate_candidates", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CandidateRankingTests(unittest.TestCase):
    def test_existing_csv_is_not_recommended_for_new_first_batch(self) -> None:
        card = {
            "title": "测试焦耳热案例",
            "file_summary": {"mph_files": 1, "matlab_files": 1, "java_files": 1, "csv_files": 1},
            "case_content": {
                "physics": ["ec / ConductiveMedia", "ht / HeatTransfer"],
                "studies": ["Stationary"],
                "parameters": ["DV", "htc"],
                "results": ["Tmax_K"],
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.case.json"
            path.write_text(json.dumps(card), encoding="utf-8")
            ranked = MODULE.rank_card(path)

        self.assertNotEqual(ranked["tier"], "A")
        self.assertIn("已关联 CSV 训练证据，应优先复用或检查现有验证状态", ranked["cautions"])

    def test_material_expression_is_not_treated_as_numerical_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case_dir = Path(directory)
            (case_dir / "case.m").write_text(
                "model.material('mat1').propertyGroup('def').set('thermalconductivity', 'ht.kmean');",
                encoding="utf-8",
            )
            card = {
                "title": "材料表达式案例",
                "case_dir": str(case_dir),
                "source_files": [{"name": "case.m", "kind": "matlab_livelink"}],
                "file_summary": {"mph_files": 1, "matlab_files": 1},
                "case_content": {"physics": ["ht / HeatTransfer"], "studies": ["Stationary"], "parameters": ["k"]},
            }
            path = case_dir / "case.case.json"
            path.write_text(json.dumps(card), encoding="utf-8")
            ranked = MODULE.rank_card(path)

        self.assertEqual(ranked["detected_output_expressions"], [])
        self.assertNotEqual(ranked["tier"], "A")

    def test_nested_export_script_array_expressions_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case_dir = Path(directory)
            export_dir = case_dir / "exports"
            export_dir.mkdir()
            (export_dir / "case.m").write_text(
                "model.result.numerical('gev1').set('expr', {'cir.v_1' 'cir.v_2'});",
                encoding="utf-8",
            )
            card = {
                "title": "场路耦合案例",
                "case_dir": str(case_dir),
                "source_files": [{"name": "case.m", "kind": "matlab_livelink"}],
                "file_summary": {"mph_files": 1, "matlab_files": 1},
                "case_content": {
                    "physics": ["ec / ConductiveMedia"],
                    "studies": ["Stationary"],
                    "parameters": ["sigma"],
                },
            }
            path = case_dir / "case.case.json"
            path.write_text(json.dumps(card), encoding="utf-8")
            ranked = MODULE.rank_card(path)

        self.assertEqual(ranked["detected_output_expressions"], ["cir.v_1", "cir.v_2"])
        self.assertEqual(ranked["tier"], "A")

    def test_complex_multiphysics_case_is_not_ranked_as_automatic_tier_a(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case_dir = Path(directory)
            (case_dir / "case.m").write_text(
                "model.result.numerical('gev1').set('expr', {'ht.ntflux'});",
                encoding="utf-8",
            )
            card = {
                "title": "复杂耦合案例",
                "case_dir": str(case_dir),
                "source_files": [{"name": "case.m", "kind": "matlab_livelink"}],
                "file_summary": {"mph_files": 1, "matlab_files": 1, "csv_files": 0},
                "case_content": {
                    "physics": ["ht / HeatTransfer", "solid / SolidMechanics"],
                    "studies": ["Stationary"],
                    "parameters": ["p1", "p2"],
                },
            }
            path = case_dir / "case.case.json"
            path.write_text(json.dumps(card), encoding="utf-8")
            ranked = MODULE.rank_card(path)

        self.assertNotEqual(ranked["tier"], "A")
        self.assertIn("多物理场组合", "；".join(ranked["cautions"]))

    def test_magnetic_heat_case_is_not_ranked_as_automatic_tier_a(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case_dir = Path(directory)
            (case_dir / "case.m").write_text(
                "model.result.numerical('gev1').set('expr', {'ht.ntflux'});",
                encoding="utf-8",
            )
            card = {
                "title": "感应加热案例",
                "case_dir": str(case_dir),
                "source_files": [{"name": "case.m", "kind": "matlab_livelink"}],
                "file_summary": {"mph_files": 1, "matlab_files": 1, "csv_files": 0},
                "case_content": {
                    "physics": ["Magnetic Fields", "Heat Transfer"],
                    "studies": ["Stationary"],
                    "parameters": ["power"],
                    "results": [],
                },
            }
            path = case_dir / "case.case.json"
            path.write_text(json.dumps(card), encoding="utf-8")
            ranked = MODULE.rank_card(path)

        self.assertNotEqual(ranked["tier"], "A")
        self.assertIn("自动扫描默认输出映射", "；".join(ranked["cautions"]))


if __name__ == "__main__":
    unittest.main()
