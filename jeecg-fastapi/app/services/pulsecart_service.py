"""Persistence and orchestration helpers for the PulseCart P1 domain."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.pulsecart import (
    PcAnalysisRun,
    PcDatasetImport,
    PcIssue,
    PcReview,
    PcReviewTask,
)
from app.utils.common import new_id


_IMPORTER_MODULE = None
_ISSUE_TRANSITIONS = {
    "open": {"in_progress"},
    "in_progress": {"pending_validation", "open"},
    "pending_validation": {"closed", "in_progress"},
    "closed": set(),
}


def sentiment_ai_root() -> Path:
    """Resolve the sibling service locally and the copied directory in Docker."""
    candidates = (
        settings.base_dir.parent / "sentiment-ai",
        settings.base_dir / "sentiment-ai",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_load(value: str | None, default: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default
    return parsed


def _importer_module():
    """Load the standard-library importer without colliding with this app's ``app`` package."""
    global _IMPORTER_MODULE
    if _IMPORTER_MODULE is not None:
        return _IMPORTER_MODULE
    source = sentiment_ai_root() / "app" / "services" / "dataset_import.py"
    if not source.is_file():
        raise RuntimeError(f"PulseCart 数据导入模块不存在: {source}")
    spec = importlib.util.spec_from_file_location("pulsecart_dataset_import", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 PulseCart 数据导入模块")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _IMPORTER_MODULE = module
    return module


def _dataset_storage_dir() -> Path:
    path = settings.base_dir / "runtime" / "pulsecart" / "imports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _raw_storage_dir() -> Path:
    path = settings.base_dir / "runtime" / "pulsecart" / "raw"
    path.mkdir(parents=True, exist_ok=True)
    return path


def import_dataset(
    db: Session,
    content: bytes,
    *,
    source_filename: str,
    created_by: str | None,
    field_mapping: Mapping[str, str] | None = None,
) -> tuple[PcDatasetImport, Any, bool]:
    """Validate bytes once and persist the immutable dataset snapshot."""
    module = _importer_module()
    importer = module.DatasetImporter(_dataset_storage_dir())
    result = importer.import_bytes(
        content,
        source_filename=source_filename,
        field_mapping=field_mapping,
    )
    existing = (
        db.query(PcDatasetImport)
        .filter(PcDatasetImport.dataset_version == result.report.dataset_version)
        .first()
    )
    if existing:
        return existing, result, True

    file_hash = hashlib.sha256(content).hexdigest()
    raw_path = _raw_storage_dir() / f"{file_hash}.csv"
    if not raw_path.exists():
        raw_path.write_bytes(content)
    report = result.report
    dataset = PcDatasetImport(
        id=new_id(),
        dataset_version=report.dataset_version,
        source_filename=report.source_filename,
        file_sha256=report.file_sha256,
        storage_path=str(raw_path.relative_to(settings.base_dir)),
        status="validated",
        mapping_json=_json(report.mapping),
        quality_rules_json=_json(report.quality_rules),
        rejection_reasons_json=_json(report.rejection_reasons),
        received_rows=report.received_rows,
        valid_rows=report.valid_rows,
        rejected_rows=report.rejected_rows,
        created_by=created_by,
    )
    db.add(dataset)
    for record in result.records:
        reviewed_at = datetime.fromisoformat(record["reviewed_at"])
        db.add(
            PcReview(
                id=new_id(),
                dataset_version=report.dataset_version,
                review_id=record["review_id"],
                product_id=record["product_id"],
                category_id=record.get("category_id"),
                review_text=record["review_text"],
                reviewed_at=reviewed_at,
                channel=record.get("channel"),
                rating=record.get("rating"),
                product_version=record.get("product_version"),
                language=record.get("language", "unknown"),
            )
        )
    db.commit()
    db.refresh(dataset)
    return dataset, result, False


def seed_review_tasks(
    db: Session,
    dataset_version: str,
    tasks: list[dict[str, Any]],
) -> int:
    """Insert generated pending tasks idempotently for a dataset snapshot."""
    inserted = 0
    for task in tasks:
        task_id = str(task.get("task_id") or "").strip()
        review_id = str(task.get("review_id") or "").strip()
        if not task_id or not review_id:
            continue
        existing = db.query(PcReviewTask).filter(PcReviewTask.task_id == task_id).first()
        if existing:
            continue
        db.add(
            PcReviewTask(
                id=new_id(),
                task_id=task_id,
                dataset_version=dataset_version,
                review_id=review_id,
                sampling_group=str(task.get("sampling_group") or ""),
                sampling_reason=str(task.get("sampling_reason") or ""),
                assigned_role=str(task.get("assigned_role") or "product_operator"),
                review_status=str(task.get("review_status") or "pending"),
                model_version=task.get("model_version"),
                system_sentiment=task.get("system_sentiment"),
                system_aspects_json=_json(task.get("system_aspects") or []),
                system_confidence=task.get("system_confidence"),
                reviewer_sentiment=task.get("reviewer_sentiment"),
                reviewer_aspects_json=_json(task.get("reviewer_aspects") or []),
                reviewer_note=str(task.get("reviewer_note") or ""),
            )
        )
        inserted += 1
    db.commit()
    return inserted


def task_to_dict(task: PcReviewTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "dataset_version": task.dataset_version,
        "review_id": task.review_id,
        "sampling_group": task.sampling_group,
        "sampling_reason": task.sampling_reason,
        "assigned_role": task.assigned_role,
        "review_status": task.review_status,
        "model_version": task.model_version,
        "system_sentiment": task.system_sentiment,
        "system_aspects": _json_load(task.system_aspects_json, []),
        "system_confidence": task.system_confidence,
        "reviewer_sentiment": task.reviewer_sentiment,
        "reviewer_aspects": _json_load(task.reviewer_aspects_json, []),
        "reviewer_note": task.reviewer_note,
        "reviewer_id": task.reviewer_id,
        "reviewed_at": task.reviewed_at.isoformat() if task.reviewed_at else None,
    }


def review_to_dict(review: PcReview) -> dict[str, Any]:
    """Return the evidence fields exposed with an audit task or issue."""
    return {
        "product_id": review.product_id,
        "category_id": review.category_id,
        "review_text": review.review_text,
        "reviewed_at": review.reviewed_at.isoformat(),
        "channel": review.channel,
        "rating": review.rating,
        "product_version": review.product_version,
    }


def attach_reviews_to_tasks(
    tasks: list[PcReviewTask],
    reviews: list[PcReview],
) -> list[dict[str, Any]]:
    """Attach review evidence using the dataset/version composite identity.

    A source system can reuse a review identifier in a later import.  Looking
    up by ``review_id`` alone would expose evidence from the wrong snapshot.
    """
    review_by_key = {
        (review.dataset_version, review.review_id): review
        for review in reviews
    }
    records = []
    for task in tasks:
        value = task_to_dict(task)
        review = review_by_key.get((task.dataset_version, task.review_id))
        if review:
            value["review"] = review_to_dict(review)
        records.append(value)
    return records


def build_training_records(
    tasks: list[PcReviewTask],
    reviews: list[PcReview],
) -> list[dict[str, Any]]:
    """Build an auditable NLP request from approved human review decisions only."""
    review_by_key = {
        (review.dataset_version, review.review_id): review
        for review in reviews
    }
    records: list[dict[str, Any]] = []
    seen_review_ids: set[str] = set()
    for task in tasks:
        if task.review_status not in {"approved", "verified"}:
            continue
        sentiment = str(task.reviewer_sentiment or "").strip().lower()
        if sentiment not in {"positive", "neutral", "negative"}:
            raise ValueError(f"审核任务 {task.task_id} 缺少有效的人工情感标签")
        review = review_by_key.get((task.dataset_version, task.review_id))
        if review is None or not review.review_text.strip():
            raise ValueError(f"审核任务 {task.task_id} 找不到对应的评论原文")
        if review.review_id in seen_review_ids:
            raise ValueError(f"训练集存在重复评论: {review.review_id}")
        aspects = _json_load(task.reviewer_aspects_json, [])
        if not isinstance(aspects, list) or not all(isinstance(item, str) and item.strip() for item in aspects):
            raise ValueError(f"审核任务 {task.task_id} 的人工属性标签格式无效")
        seen_review_ids.add(review.review_id)
        records.append(
            {
                "review_id": review.review_id,
                "review_text": review.review_text,
                "sentiment": sentiment,
                "aspects": aspects,
                "review_status": task.review_status,
            }
        )
    return sorted(records, key=lambda item: item["review_id"])


def update_review_task(
    db: Session,
    task_id: str,
    *,
    status: str,
    reviewer_sentiment: str | None,
    reviewer_aspects: list[str],
    reviewer_note: str,
    reviewer_id: str | None,
) -> PcReviewTask:
    task = db.query(PcReviewTask).filter(PcReviewTask.task_id == task_id).first()
    if not task:
        raise LookupError(f"审核任务不存在: {task_id}")
    if status in {"approved", "verified"} and not reviewer_sentiment:
        raise ValueError("审核通过或复核时必须填写 reviewer_sentiment")
    if status == "rejected" and not reviewer_note.strip():
        raise ValueError("标记无效文本时必须填写 reviewer_note")
    task.review_status = status
    task.reviewer_sentiment = reviewer_sentiment
    task.reviewer_aspects_json = _json(reviewer_aspects)
    task.reviewer_note = reviewer_note.strip()
    task.reviewer_id = reviewer_id
    task.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


def analysis_run_to_dict(run: PcAnalysisRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "dataset_version": run.dataset_version,
        "model_version": run.model_version,
        "status": run.status,
        "source_kind": run.source_kind,
        "metrics": _json_load(run.metrics_json, {}),
        "error_message": run.error_message,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def issue_to_dict(issue: PcIssue) -> dict[str, Any]:
    return {
        "id": issue.id,
        "dataset_version": issue.dataset_version,
        "title": issue.title,
        "aspect": issue.aspect,
        "severity": issue.severity,
        "status": issue.status,
        "description": issue.description,
        "source_review_ids": _json_load(issue.source_review_ids_json, []),
        "owner_user_id": issue.owner_user_id,
        "resolution_note": issue.resolution_note,
        "created_by": issue.created_by,
        "created_at": issue.created_at.isoformat() if issue.created_at else None,
        "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
    }


def update_issue(
    db: Session,
    issue_id: str,
    *,
    status: str,
    resolution_note: str,
    owner_user_id: str | None,
) -> PcIssue:
    issue = db.query(PcIssue).filter(PcIssue.id == issue_id).first()
    if not issue:
        raise LookupError(f"问题卡片不存在: {issue_id}")
    if status != issue.status and status not in _ISSUE_TRANSITIONS.get(issue.status, set()):
        raise ValueError(f"问题卡片不允许从 {issue.status} 流转到 {status}")
    if status == "closed" and not resolution_note.strip():
        raise ValueError("关闭问题卡片前必须填写 resolution_note")
    issue.status = status
    issue.resolution_note = resolution_note.strip() or issue.resolution_note
    if owner_user_id is not None:
        issue.owner_user_id = owner_user_id
    db.commit()
    db.refresh(issue)
    return issue


__all__ = [
    "analysis_run_to_dict",
    "attach_reviews_to_tasks",
    "build_training_records",
    "import_dataset",
    "issue_to_dict",
    "review_to_dict",
    "seed_review_tasks",
    "sentiment_ai_root",
    "task_to_dict",
    "update_issue",
    "update_review_task",
]
