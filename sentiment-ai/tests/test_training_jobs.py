"""Tests for durable PulseCart local model-training job state."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.training_jobs import TrainingJobError, TrainingJobStore


def _records() -> list[dict[str, object]]:
    rows = []
    for sentiment in ("positive", "neutral", "negative"):
        for index in range(5):
            rows.append(
                {
                    "review_id": f"{sentiment}-{index}",
                    "review_text": f"{sentiment} 人工审核评论 {index}",
                    "sentiment": sentiment,
                    "aspects": ["cleaning_effectiveness"],
                    "review_status": "approved",
                }
            )
    return rows


class TrainingJobStoreTests(unittest.TestCase):
    def test_enqueue_persists_queued_job_without_exposing_or_overwriting_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            store = TrainingJobStore(base_dir / "jobs", base_dir / "models")
            job = store.enqueue(
                dataset_version="ds-reviewed-v1",
                model_version="baseline-reviewed-v1",
                random_seed=68,
                records=_records(),
            )
            loaded = store.get(job["job_id"])

        self.assertEqual(loaded["status"], "queued")
        self.assertEqual(len(loaded["records"]), 15)
        self.assertIsNone(loaded["result"])

    def test_queue_rejects_non_human_reviewed_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            store = TrainingJobStore(base_dir / "jobs", base_dir / "models")
            records = _records()
            records[0]["review_status"] = "pending"
            with self.assertRaisesRegex(TrainingJobError, "approved"):
                store.enqueue(
                    dataset_version="ds-reviewed-v1",
                    model_version="baseline-reviewed-v1",
                    random_seed=68,
                    records=records,
                )

    def test_queue_rejects_duplicate_review_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            store = TrainingJobStore(base_dir / "jobs", base_dir / "models")
            records = _records()
            records[-1] = {**records[-1], "review_id": records[0]["review_id"]}
            with self.assertRaisesRegex(TrainingJobError, "重复 review_id"):
                store.enqueue(
                    dataset_version="ds-reviewed-v1",
                    model_version="baseline-reviewed-v1",
                    random_seed=68,
                    records=records,
                )

    def test_queue_rejects_reused_model_version_before_worker_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            store = TrainingJobStore(base_dir / "jobs", base_dir / "models")
            store.enqueue(
                dataset_version="ds-reviewed-v1",
                model_version="baseline-reviewed-v1",
                random_seed=68,
                records=_records(),
            )
            with self.assertRaisesRegex(TrainingJobError, "已关联训练任务"):
                store.enqueue(
                    dataset_version="ds-reviewed-v1",
                    model_version="baseline-reviewed-v1",
                    random_seed=68,
                    records=_records(),
                )


if __name__ == "__main__":
    unittest.main()
