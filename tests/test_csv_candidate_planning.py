from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "plan_case_csv_candidates.py"
SPEC = importlib.util.spec_from_file_location("plan_case_csv_candidates", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _case(physics: list[str]) -> dict[str, object]:
    return {
        "title": "candidate",
        "case_dir": "",
        "file_summary": {"matlab_files": 1, "java_files": 1, "mph_files": 1, "csv_files": 0},
        "quality": {"score": 80, "checks": {"physics": True, "parameters": True, "study": True}},
        "case_content": {
            "physics": physics,
            "studies": ["Stationary"],
            "results": ["Tmax_K", "joule_power_W"],
        },
        "parameters": [{"name": "p1"}, {"name": "p2"}],
    }


class CsvCandidatePlanningTests(unittest.TestCase):
    def test_rejects_magnetic_heat_case_with_ambiguous_outputs(self) -> None:
        self.assertIsNone(MODULE._candidate(_case(["Magnetic Fields", "Heat Transfer"])))

    def test_rejects_particle_tracking_case_instead_of_guessing_fluid_outputs(self) -> None:
        self.assertIsNone(MODULE._candidate(_case(["Electrostatics", "Laminar Flow", "Particle Tracing"])))

    def test_accepts_exact_electrothermal_combination(self) -> None:
        candidate = MODULE._candidate(_case(["Electric Currents", "Heat Transfer"]))
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["domain"], "electrothermal")
        self.assertEqual(candidate["suggested_outputs"], ["Tmax_K", "joule_power_W"])

    def test_rejects_structural_electrothermal_mix_until_outputs_are_declared(self) -> None:
        self.assertIsNone(MODULE._candidate(_case(["Electric Currents", "Heat Transfer", "Solid Mechanics"])))

    def test_rejects_diluted_species_hidden_behind_laminar_flow(self) -> None:
        self.assertIsNone(MODULE._candidate(_case(["Laminar Flow", "Diluted Species"])))

    def test_rejects_supported_physics_without_explicit_output_evidence(self) -> None:
        candidate = _case(["Heat Transfer"])
        candidate["case_content"]["results"] = []
        self.assertIsNone(MODULE._candidate(candidate))


if __name__ == "__main__":
    unittest.main()
