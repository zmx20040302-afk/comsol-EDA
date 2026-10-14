from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from comsol_small_model.closure_audit import build_closure_audit
from comsol_small_model.surrogate_model_card import (
    consolidate_surrogate_registries,
    mark_surrogates_superseded,
)


class SurrogateRegistryLifecycleTests(unittest.TestCase):
    def test_only_validated_model_can_replace_historical_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "models" / "surrogate_registry.json"
            registry_path.parent.mkdir()
            artifact = root / "artifact.bin"
            artifact.write_text("evidence", encoding="utf-8")
            models = [
                self._entry("old", "needs_more_comsol_evidence", False, artifact),
                self._entry("winner", "validated_for_declared_scope", True, artifact),
            ]
            registry_path.write_text(json.dumps({"models": models}), encoding="utf-8")

            result = mark_surrogates_superseded(
                registry_path,
                ["old"],
                replacement_id="winner",
                reason="winner passed a stricter independent holdout gate",
            )
            updated = json.loads(registry_path.read_text(encoding="utf-8"))["models"]
            old = next(item for item in updated if item["id"] == "old")
            winner = next(item for item in updated if item["id"] == "winner")

        self.assertEqual(result["superseded_ids"], ["old"])
        self.assertEqual(old["status"], "needs_more_comsol_evidence")
        self.assertEqual(old["lifecycle_status"], "superseded")
        self.assertEqual(old["superseded_by"], "winner")
        self.assertEqual(winner["supersedes"], ["old"])

    def test_closure_audit_separates_superseded_and_active_unvalidated_models(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            models_dir = root / "generated" / "models"
            models_dir.mkdir(parents=True)
            artifact = root / "artifact.bin"
            artifact.write_text("evidence", encoding="utf-8")
            models = [
                {
                    **self._entry("old", "needs_more_comsol_evidence", False, artifact),
                    "lifecycle_status": "superseded",
                    "superseded_by": "winner",
                },
                self._entry("needs-data", "needs_more_comsol_evidence", False, artifact),
                self._entry("winner", "validated_for_declared_scope", True, artifact),
            ]
            (models_dir / "surrogate_registry.json").write_text(
                json.dumps({"models": models}), encoding="utf-8"
            )
            program = root / "program.json"
            program.write_text('{"tasks": []}', encoding="utf-8")
            audit = build_closure_audit(root / "generated", program)

        self.assertEqual(audit["active_unvalidated_models"], ["needs-data"])
        self.assertEqual(audit["superseded_models"][0]["id"], "old")
        self.assertEqual(audit["ready_for_scoped_prediction"], ["winner"])

    def test_closure_audit_finds_artifacts_beside_relocated_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            models_dir = root / "generated" / "models"
            models_dir.mkdir(parents=True)
            artifact = models_dir / "evidence.bin"
            artifact.write_text("evidence", encoding="utf-8")
            entry = self._entry("moved", "validated_for_declared_scope", True, artifact)
            for field in ("model_path", "model_card", "validation_report"):
                entry[field] = str(Path("Z:/missing/original") / artifact.name)
            (models_dir / "surrogate_registry.json").write_text(
                json.dumps({"models": [entry]}), encoding="utf-8"
            )
            program = root / "program.json"
            program.write_text('{"tasks": []}', encoding="utf-8")

            audit = build_closure_audit(root / "generated", program)

        self.assertEqual(audit["evidence_gaps"], [])
        self.assertEqual(audit["ready_for_scoped_prediction"], ["moved"])

    def test_unvalidated_model_cannot_replace_another_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "registry.json"
            artifact = Path(directory) / "artifact.bin"
            artifact.write_text("evidence", encoding="utf-8")
            registry_path.write_text(
                json.dumps(
                    {
                        "models": [
                            self._entry("old", "needs_more_comsol_evidence", False, artifact),
                            self._entry("also-failed", "needs_more_comsol_evidence", False, artifact),
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must have passed"):
                mark_surrogates_superseded(
                    registry_path,
                    ["old"],
                    replacement_id="also-failed",
                    reason="invalid replacement",
                )

    def test_legacy_only_registry_entry_is_copied_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "models" / "surrogate_registry.json"
            canonical.parent.mkdir()
            legacy = root / "surrogate_registry.json"
            canonical.write_text('{"models": [{"id": "current"}]}', encoding="utf-8")
            legacy.write_text('{"models": [{"id": "legacy-only"}]}', encoding="utf-8")
            result = consolidate_surrogate_registries(canonical, legacy)
            models = json.loads(canonical.read_text(encoding="utf-8"))["models"]
        self.assertTrue(result["ok"])
        self.assertTrue(result["changed"])
        self.assertEqual(result["imported_ids"], ["legacy-only"])
        self.assertEqual([item["id"] for item in models], ["current", "legacy-only"])

    def test_conflicting_legacy_entry_does_not_modify_canonical_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "canonical.json"
            legacy = root / "legacy.json"
            canonical.write_text(
                '{"models": [{"id": "same", "status": "validated_for_declared_scope"}]}',
                encoding="utf-8",
            )
            original = canonical.read_bytes()
            legacy.write_text(
                '{"models": [{"id": "same", "status": "needs_more_comsol_evidence"}]}',
                encoding="utf-8",
            )
            result = consolidate_surrogate_registries(canonical, legacy)
            current = canonical.read_bytes()
        self.assertFalse(result["ok"])
        self.assertEqual(result["conflicting_ids"], ["same"])
        self.assertEqual(current, original)

    @staticmethod
    def _entry(
        model_id: str,
        status: str,
        validation_passed: bool,
        artifact: Path,
    ) -> dict:
        return {
            "id": model_id,
            "status": status,
            "validation_passed": validation_passed,
            "model_path": str(artifact),
            "model_card": str(artifact),
            "validation_report": str(artifact),
        }


if __name__ == "__main__":
    unittest.main()
