from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "merge_power_inductor_frequency_data.py"
SPEC = importlib.util.spec_from_file_location("merge_power_inductor_frequency_data", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PowerInductorDataTests(unittest.TestCase):
    def test_merge_sorts_and_deduplicates_identical_comsol_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.csv"
            second = root / "second.csv"
            output = root / "merged.csv"
            frame = pd.DataFrame(
                [
                    {"frequency_Hz": 1000, "inductance_H": 1.1e-4, "conductance_S": 0.01},
                    {"frequency_Hz": 500, "inductance_H": 1.2e-4, "conductance_S": 0.02},
                ]
            )
            frame.to_csv(first, index=False)
            frame.iloc[[0]].to_csv(second, index=False)
            result = MODULE.merge_frequency_data([first, second], output)
            merged = pd.read_csv(output)
        self.assertEqual(result["rows"], 2)
        self.assertEqual(merged["frequency_Hz"].tolist(), [500, 1000])

    def test_merge_rejects_conflicting_rows_at_same_frequency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.csv"
            second = root / "second.csv"
            pd.DataFrame([{"frequency_Hz": 1000, "inductance_H": 1.1e-4, "conductance_S": 0.01}]).to_csv(first, index=False)
            pd.DataFrame([{"frequency_Hz": 1000, "inductance_H": 1.2e-4, "conductance_S": 0.01}]).to_csv(second, index=False)
            with self.assertRaisesRegex(ValueError, "conflicting rows"):
                MODULE.load_frequency_data([first, second])

    def test_merge_rejects_invalid_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv"
            pd.DataFrame([{"frequency_Hz": 0, "inductance_H": 1.1e-4, "conductance_S": 0.01}]).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "non-positive frequency"):
                MODULE.load_frequency_data([path])


if __name__ == "__main__":
    unittest.main()
