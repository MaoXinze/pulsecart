"""Durable local training-job queue for PulseCart development and demo mode.

The records are saved with each job so a queued run is reproducible.  A Redis
worker may replace this store in deployment without changing the HTTP contract.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.services.baseline_sentiment import (
    BaselineTrainingError,
    SENTIMENT_LABELS,
    TRAINABLE_REVIEW_STATUSES,
    ReviewedRecord,
    train_baseline,
    validate_reviewed_records,
)


MODEL_VERSION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")
VALID_JOB_STATUSES = frozenset({"queued", "running", "succeeded", "failed"})


class TrainingJobError(ValueError):
    """Raised for invalid requests or unavailable training jobs."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TrainingJobStore:
    def __init__(self, root: str | Path, model_root: str | Path):
        self.root = Path(root)
        self.model_root = Path(model_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.model_root.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        return self.root / f"{job_id}.json"

    @staticmethod
    def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary_path.replace(path)

    def _read(self, job_id: str) -> dict[str, Any]:
        path = self._path(job_id)
        if not path.is_file():
            raise TrainingJobError(f"训练任务不存在: {job_id}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TrainingJobError(f"训练任务损坏: {job_id}") from exc

    @staticmethod
    def _normalise_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        reviewed_records = []
        seen_review_ids: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                raise TrainingJobError("records 中的每一项必须是对象")
            try:
                reviewed = ReviewedRecord(
                    review_id=str(record["review_id"]).strip(),
                    review_text=str(record["review_text"]).strip(),
                    sentiment=str(record["sentiment"]).strip(),
                    aspects=tuple(str(item).strip() for item in record.get("aspects", [])),
                    review_status=str(record.get("review_status") or "approved").strip(),
                )
            except KeyError as exc:
                raise TrainingJobError(f"训练记录缺少字段: {exc.args[0]}") from exc
            if not reviewed.review_id or not reviewed.review_text or not reviewed.sentiment:
                raise TrainingJobError("训练记录 review_id、review_text、sentiment 均不能为空")
            if reviewed.sentiment not in SENTIMENT_LABELS:
                raise TrainingJobError(f"训练记录包含不支持的情感标签: {reviewed.sentiment}")
            if reviewed.review_status not in TRAINABLE_REVIEW_STATUSES:
                raise TrainingJobError("训练记录必须来自 approved 或 verified 人工审核状态")
            if reviewed.review_id in seen_review_ids:
                raise TrainingJobError(f"训练记录包含重复 review_id: {reviewed.review_id}")
            seen_review_ids.add(reviewed.review_id)
            reviewed_records.append(reviewed)

        try:
            validated_records = validate_reviewed_records(reviewed_records)
        except BaselineTrainingError as exc:
            raise TrainingJobError(str(exc)) from exc

        return [
            {
                "review_id": reviewed.review_id,
                "review_text": reviewed.review_text,
                "sentiment": reviewed.sentiment,
                "aspects": list(reviewed.aspects),
                "review_status": reviewed.review_status,
            }
            for reviewed in validated_records
        ]

    def enqueue(
        self,
        *,
        dataset_version: str,
        model_version: str,
        random_seed: int,
        records: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        if not dataset_version.strip():
            raise TrainingJobError("dataset_version 不能为空")
        if not MODEL_VERSION_PATTERN.fullmatch(model_version):
            raise TrainingJobError("model_version 只能使用小写字母、数字和连字符，长度为 3-80")
        if (self.model_root / model_version).exists():
            raise TrainingJobError(f"模型版本已存在，不能覆盖历史产物: {model_version}")
        existing_job = next(
            (job for job in self.list() if job.get("model_version") == model_version),
            None,
        )
        if existing_job:
            raise TrainingJobError(
                f"模型版本已关联训练任务: {existing_job.get('job_id')}，请使用新的 model_version"
            )
        normalised = self._normalise_records(records)
        job_id = f"train-{uuid.uuid4().hex}"
        job = {
            "job_id": job_id,
            "status": "queued",
            "dataset_version": dataset_version,
            "model_version": model_version,
            "random_seed": random_seed,
            "records": normalised,
            "created_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error_message": None,
        }
        self._atomic_write(self._path(job_id), job)
        return job

    def get(self, job_id: str) -> dict[str, Any]:
        return self._read(job_id)

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        jobs = []
        for path in self.root.glob("train-*.json"):
            try:
                jobs.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(jobs, key=lambda job: str(job.get("created_at", "")), reverse=True)[:limit]

    def claim_next(self) -> dict[str, Any] | None:
        queued_jobs = [job for job in self.list() if job.get("status") == "queued"]
        if not queued_jobs:
            return None
        job = sorted(queued_jobs, key=lambda item: str(item["created_at"]))[0]
        job["status"] = "running"
        job["started_at"] = _utc_now()
        self._atomic_write(self._path(job["job_id"]), job)
        return job

    def execute_next(self) -> dict[str, Any] | None:
        job = self.claim_next()
        if job is None:
            return None
        try:
            records = [
                ReviewedRecord(
                    review_id=record["review_id"],
                    review_text=record["review_text"],
                    sentiment=record["sentiment"],
                    aspects=tuple(record.get("aspects", [])),
                    review_status=record["review_status"],
                )
                for record in job["records"]
            ]
            result = train_baseline(
                records,
                self.model_root / job["model_version"],
                dataset_version=job["dataset_version"],
                random_seed=int(job["random_seed"]),
            )
            job["status"] = "succeeded"
            job["result"] = {
                "model_version": job["model_version"],
                "model_path": str(result.model_path),
                "metadata_path": str(result.metadata_path),
                "training_records": result.training_records,
                "test_records": result.test_records,
                "metrics": result.metrics,
            }
        except Exception as exc:  # Persist failure; the worker process can then safely continue.
            job["status"] = "failed"
            job["error_message"] = str(exc)
        job["finished_at"] = _utc_now()
        self._atomic_write(self._path(job["job_id"]), job)
        return job


__all__ = ["MODEL_VERSION_PATTERN", "TrainingJobError", "TrainingJobStore", "VALID_JOB_STATUSES"]
