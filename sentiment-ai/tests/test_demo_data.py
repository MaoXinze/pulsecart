"""PulseCart synthetic demo-data contract tests."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

from app.services.demo_data import ASPECTS, generate_demo_dataset


class DemoDataTests(unittest.TestCase):
    def test_generator_creates_a_traceable_review_and_review_task_dataset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = generate_demo_dataset(temp_dir, total_reviews=120, review_task_count=30, seed=9)
            with result.reviews_path.open(encoding="utf-8", newline="") as handle:
                reviews = list(csv.DictReader(handle))
            tasks = [
                json.loads(line)
                for line in result.review_tasks_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            references = [
                json.loads(line)
                for line in result.reference_labels_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(len(reviews), 120)
        self.assertEqual(len({review["review_id"] for review in reviews}), 120)
        self.assertEqual(len({review["review_text"] for review in reviews}), 120)
        self.assertEqual({review["language"] for review in reviews}, {"zh"})
        self.assertEqual(len(tasks), 30)
        self.assertEqual(len({task["review_id"] for task in tasks}), 30)
        self.assertEqual({task["review_status"] for task in tasks}, {"pending"})
        self.assertEqual(
            {task["sampling_group"] for task in tasks},
            {"risk_or_uncertainty", "stratified_random"},
        )
        self.assertEqual(sum(task["sampling_group"] == "risk_or_uncertainty" for task in tasks), 15)
        self.assertEqual(len(references), 120)
        self.assertTrue(manifest["is_synthetic"])
        self.assertEqual(manifest["review_count"], 120)
        self.assertEqual(sum(manifest["sentiment_counts"].values()), 120)
        self.assertTrue(set(manifest["aspect_counts"]).issubset(set(ASPECTS)))

    def test_same_seed_produces_same_content(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = generate_demo_dataset(first_dir, total_reviews=120, review_task_count=30, seed=88)
            second = generate_demo_dataset(second_dir, total_reviews=120, review_task_count=30, seed=88)
            first_reviews = first.reviews_path.read_bytes()
            second_reviews = second.reviews_path.read_bytes()
            first_tasks = first.review_tasks_path.read_bytes()
            second_tasks = second.review_tasks_path.read_bytes()

        self.assertEqual(first_reviews, second_reviews)
        self.assertEqual(first_tasks, second_tasks)

    def test_invalid_task_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "review_task_count"):
                generate_demo_dataset(temp_dir, total_reviews=30, review_task_count=31)


if __name__ == "__main__":
    unittest.main()
