"""PulseCart 数据集导入契约测试，仅依赖 Python 标准库。"""

from __future__ import annotations

import csv
import io
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

from app.services.dataset_import import DatasetImportError, DatasetImporter, ImportOptions


def _csv_bytes(rows: list[dict[str, str]], fieldnames: list[str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


class DatasetImportTests(unittest.TestCase):
    def test_import_normalizes_records_and_reports_quality(self):
        content = _csv_bytes(
            [
                {
                    "id": "r-1",
                    "sku": "sku-1",
                    "content": "物流很快，包装完好",
                    "date": "2026-08-01",
                    "score": "5",
                },
                {
                    "id": "r-2",
                    "sku": "sku-1",
                    "content": "物流很快，包装完好",
                    "date": "2026-08-02T12:30:00Z",
                    "score": "4",
                },
                {
                    "id": "r-3",
                    "sku": "sku-1",
                    "content": "",
                    "date": "not-a-date",
                    "score": "6",
                },
            ],
            ["id", "sku", "content", "date", "score"],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = DatasetImporter(temp_dir).import_bytes(content, source_filename="demo.csv")

        self.assertEqual(result.report.received_rows, 3)
        self.assertEqual(result.report.valid_rows, 2)
        self.assertEqual(result.report.rejected_rows, 1)
        self.assertEqual(result.report.duplicate_text_rows, 1)
        self.assertEqual(
            result.report.rejection_reasons,
            {
                "missing_review_text": 1,
                "invalid_reviewed_at": 1,
                "invalid_rating": 1,
            },
        )
        self.assertEqual(result.records[0]["reviewed_at"], "2026-08-01T00:00:00")
        self.assertEqual(result.records[0]["language"], "zh")
        self.assertEqual(result.rejected[0].row_number, 4)
        self.assertEqual(result.rejected[0].reason, "missing_review_text")
        self.assertEqual(
            result.rejected[0].reasons,
            ("missing_review_text", "invalid_reviewed_at", "invalid_rating"),
        )

    def test_import_is_idempotent_for_same_bytes_and_mapping(self):
        content = _csv_bytes(
            [
                {
                    "review_id": "r-1",
                    "product_id": "sku-1",
                    "review_text": "Good quality",
                    "reviewed_at": "2026-08-01",
                }
            ],
            ["review_id", "product_id", "review_text", "reviewed_at"],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            importer = DatasetImporter(temp_dir)
            first = importer.import_bytes(content)
            second = DatasetImporter(temp_dir).import_bytes(content)

        self.assertFalse(first.reused)
        self.assertTrue(second.reused)
        self.assertEqual(first.report.dataset_version, second.report.dataset_version)
        self.assertEqual(first.report.file_sha256, second.report.file_sha256)
        self.assertEqual(first.records, second.records)

    def test_persisted_rejections_restore_tuple_reasons(self):
        content = _csv_bytes(
            [
                {
                    "review_id": "r-1",
                    "product_id": "sku-1",
                    "review_text": "",
                    "reviewed_at": "not-a-date",
                }
            ],
            ["review_id", "product_id", "review_text", "reviewed_at"],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            first = DatasetImporter(temp_dir).import_bytes(content)
            second = DatasetImporter(temp_dir).import_bytes(content)

        self.assertFalse(first.reused)
        self.assertTrue(second.reused)
        self.assertEqual(second.rejected, first.rejected)
        self.assertIsInstance(second.rejected[0].reasons, tuple)
        self.assertEqual(
            second.rejected[0].reasons,
            ("missing_review_text", "invalid_reviewed_at"),
        )

    def test_duplicate_ids_and_invalid_values_are_rejected_deterministically(self):
        content = _csv_bytes(
            [
                {
                    "review_id": "same",
                    "product_id": "sku-1",
                    "review_text": "可以",
                    "reviewed_at": "2026-08-01",
                    "rating": "5.5",
                    "language": "zh",
                },
                {
                    "review_id": "same",
                    "product_id": "sku-1",
                    "review_text": "可以",
                    "reviewed_at": "2026-08-01",
                    "rating": "5",
                    "language": "fr",
                },
            ],
            ["review_id", "product_id", "review_text", "reviewed_at", "rating", "language"],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            result = DatasetImporter(temp_dir).import_bytes(content)

        self.assertEqual(result.report.valid_rows, 0)
        self.assertEqual(result.report.rejected_rows, 2)
        self.assertEqual(
            result.report.rejection_reasons,
            {
                "invalid_rating": 1,
                "duplicate_review_id": 1,
                "invalid_language": 1,
            },
        )

    def test_missing_required_column_fails_before_row_processing(self):
        content = _csv_bytes(
            [{"review_id": "r-1", "product_id": "sku-1", "review_text": "缺时间"}],
            ["review_id", "product_id", "review_text"],
        )
        with self.assertRaisesRegex(DatasetImportError, "reviewed_at"):
            DatasetImporter().import_bytes(content)

    def test_duplicate_text_can_be_rejected_by_explicit_policy(self):
        content = _csv_bytes(
            [
                {
                    "review_id": "r-1",
                    "product_id": "sku-1",
                    "review_text": "同一条评论",
                    "reviewed_at": "2026-08-01",
                },
                {
                    "review_id": "r-2",
                    "product_id": "sku-1",
                    "review_text": "同一条评论",
                    "reviewed_at": "2026-08-02",
                },
            ],
            ["review_id", "product_id", "review_text", "reviewed_at"],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            result = DatasetImporter(
                temp_dir, options=ImportOptions(reject_duplicate_text=True)
            ).import_bytes(content)

        self.assertEqual(result.report.valid_rows, 1)
        self.assertEqual(result.report.rejection_reasons, {"duplicate_review_text": 1})

    def test_quality_rule_change_creates_a_new_dataset_version(self):
        content = _csv_bytes(
            [
                {
                    "review_id": "r-1",
                    "product_id": "sku-1",
                    "review_text": "同一条评论",
                    "reviewed_at": "2026-08-01",
                },
                {
                    "review_id": "r-2",
                    "product_id": "sku-1",
                    "review_text": "同一条评论",
                    "reviewed_at": "2026-08-02",
                },
            ],
            ["review_id", "product_id", "review_text", "reviewed_at"],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            permissive = DatasetImporter(temp_dir).import_bytes(content)
            strict = DatasetImporter(
                temp_dir, options=ImportOptions(reject_duplicate_text=True)
            ).import_bytes(content)

        self.assertNotEqual(
            permissive.report.dataset_version, strict.report.dataset_version
        )
        self.assertEqual(permissive.report.valid_rows, 2)
        self.assertEqual(strict.report.valid_rows, 1)
        self.assertTrue(strict.report.quality_rules["reject_duplicate_text"])


if __name__ == "__main__":
    unittest.main()
