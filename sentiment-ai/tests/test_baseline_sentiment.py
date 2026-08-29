"""Tests for the reproducible reviewed-label sentiment baseline."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

from app.services.baseline_sentiment import (
    BaselineTrainingError,
    load_reviewed_records,
    predict_baseline,
    train_baseline,
)

try:
    import sklearn  # noqa: F401
except ImportError:
    SKLEARN_AVAILABLE = False
else:
    SKLEARN_AVAILABLE = True


def _write_review_data(base_dir: Path, *, status: str = "verified") -> tuple[Path, Path]:
    reviews_path = base_dir / "reviews.csv"
    tasks_path = base_dir / "tasks.jsonl"
    rows: list[dict[str, str]] = []
    tasks: list[dict[str, object]] = []
    templates = {
        "positive": "清扫干净，回充稳定，整体很满意",
        "neutral": "日常清扫够用，表现符合预期",
        "negative": "导航经常碰撞，任务中断，体验不好",
    }
    review_number = 0
    for sentiment, template in templates.items():
        for index in range(6):
            review_number += 1
            review_id = f"r-{review_number}"
            rows.append({"review_id": review_id, "review_text": f"{template}，样本 {index}"})
            tasks.append(
                {
                    "task_id": f"t-{review_number}",
                    "review_id": review_id,
                    "review_status": status,
                    "reviewer_sentiment": sentiment,
                    "reviewer_aspects": ["cleaning_effectiveness"],
                }
            )
    with reviews_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["review_id", "review_text"])
        writer.writeheader()
        writer.writerows(rows)
    tasks_path.write_text(
        "".join(json.dumps(task, ensure_ascii=False) + "\n" for task in tasks),
        encoding="utf-8",
    )
    return reviews_path, tasks_path


class BaselineSentimentTests(unittest.TestCase):
    def test_only_approved_or_verified_reviewed_tasks_become_training_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            reviews_path, tasks_path = _write_review_data(Path(temp_dir), status="pending")
            records = load_reviewed_records(reviews_path, tasks_path)

        self.assertEqual(records, [])

    @unittest.skipUnless(SKLEARN_AVAILABLE, "scikit-learn is not installed in this environment")
    def test_train_persists_auditable_model_and_predicts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            reviews_path, tasks_path = _write_review_data(base_dir)
            records = load_reviewed_records(reviews_path, tasks_path)
            result = train_baseline(
                records,
                base_dir / "baseline-v1",
                dataset_version="ds-reviewed-demo-v1",
                random_seed=9,
            )
            predictions = predict_baseline(result.model_path, ["导航总是碰撞，任务失败", "清扫效果很满意"])
            metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
            self.assertTrue(result.model_path.is_file())

        self.assertEqual(metadata["dataset_version"], "ds-reviewed-demo-v1")
        self.assertEqual(metadata["source_kind"], "human_reviewed")
        self.assertIn("macro_f1", metadata["metrics"])
        self.assertEqual(len(predictions), 2)
        self.assertTrue(all(item["sentiment"] in {"positive", "neutral", "negative"} for item in predictions))

    def test_synthetic_source_kind_is_rejected(self):
        with self.assertRaisesRegex(BaselineTrainingError, "human_reviewed"):
            train_baseline(
                [],
                Path("unused"),
                dataset_version="ds-any",
                source_kind="synthetic_reference",
            )


if __name__ == "__main__":
    unittest.main()
