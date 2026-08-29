"""Tests for artifact validation in the standalone PulseCart model service."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.model_registry import ModelNotReadyError, ModelRegistry


class ModelRegistryTests(unittest.TestCase):
    def test_registry_lists_publishable_baseline_artifact_as_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact_dir = root / "baseline-reviewed-v1"
            artifact_dir.mkdir()
            model_path = artifact_dir / "model.joblib"
            model_path.write_bytes(b"test-model-artifact")
            (artifact_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "model_version": "baseline-reviewed-v1",
                        "model_type": "tfidf_logistic_regression",
                        "dataset_version": "ds-reviewed-v1",
                        "created_at": "2026-08-28T00:00:00+00:00",
                        "artifact_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                        "test_records": 30,
                        "metrics": {"macro_f1": 0.8},
                    }
                ),
                encoding="utf-8",
            )
            registry = ModelRegistry(root)
            models = registry.list_models()
            resolved = registry.resolve()

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].status, "ready")
        self.assertEqual(resolved.model_version, "baseline-reviewed-v1")

    def test_registry_rejects_artifact_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact_dir = root / "baseline-reviewed-v1"
            artifact_dir.mkdir()
            (artifact_dir / "model.joblib").write_bytes(b"changed")
            (artifact_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "model_version": "baseline-reviewed-v1",
                        "model_type": "tfidf_logistic_regression",
                        "dataset_version": "ds-reviewed-v1",
                        "artifact_sha256": "0" * 64,
                    }
                ),
                encoding="utf-8",
            )
            registry = ModelRegistry(root)
            models = registry.list_models()

            with self.assertRaisesRegex(ModelNotReadyError, "不可用"):
                registry.resolve("baseline-reviewed-v1")

        self.assertEqual(models[0].status, "invalid")

    def test_registry_keeps_low_evidence_model_for_evaluation_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact_dir = root / "baseline-insufficient-v1"
            artifact_dir.mkdir()
            model_path = artifact_dir / "model.joblib"
            model_path.write_bytes(b"test-model-artifact")
            (artifact_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "model_version": "baseline-insufficient-v1",
                        "model_type": "tfidf_logistic_regression",
                        "dataset_version": "ds-reviewed-v1",
                        "artifact_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                        "test_records": 3,
                        "metrics": {"macro_f1": 0.22},
                    }
                ),
                encoding="utf-8",
            )
            registry = ModelRegistry(root)
            model = registry.list_models()[0]
            with self.assertRaisesRegex(ModelNotReadyError, "不可用"):
                registry.resolve("baseline-insufficient-v1")

        self.assertEqual(model.status, "evaluation_only")
        self.assertIn("Macro-F1", model.reason or "")


if __name__ == "__main__":
    unittest.main()
