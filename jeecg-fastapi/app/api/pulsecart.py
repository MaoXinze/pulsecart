"""PulseCart domain API (P1 data and operations workflow)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import tuple_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.pulsecart import PcAnalysisRun, PcDatasetImport, PcIssue, PcReview, PcReviewTask
from app.models.entities import SysUser
from app.schemas.pulsecart import AnalysisRunCreate, IssueCreate, IssueUpdate, ReviewTaskUpdate
from app.schemas.response import Result
from app.services.pulsecart_service import (
    analysis_run_to_dict,
    attach_reviews_to_tasks,
    build_training_records,
    import_dataset,
    issue_to_dict,
    seed_review_tasks,
    sentiment_ai_root,
    task_to_dict,
    update_issue,
    update_review_task,
)
from app.services.pulsecart_training_client import (
    TrainingServiceError,
    get_training_run,
    submit_training_run,
)
from app.utils.common import new_id


router = APIRouter(prefix="/api/v1", tags=["PulseCart 商品体验"])


def _parse_mapping(value: str | None) -> dict[str, str] | None:
    if not value or not value.strip():
        return None
    try:
        mapping = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="field_mapping 必须是 JSON 对象") from exc
    if not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
        raise HTTPException(status_code=400, detail="field_mapping 必须是标准字段到原始列名的 JSON 对象")
    return mapping


def _naive_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _training_job_id(run: PcAnalysisRun) -> str | None:
    try:
        metrics = json.loads(run.metrics_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return None
    job_id = metrics.get("training_job_id") if isinstance(metrics, dict) else None
    return job_id.strip() if isinstance(job_id, str) and job_id.strip() else None


def _sync_analysis_run(run: PcAnalysisRun, training_job: dict) -> None:
    status = str(training_job["status"])
    run.status = status
    try:
        metrics = json.loads(run.metrics_json or "{}")
    except (TypeError, json.JSONDecodeError):
        metrics = {}
    result = training_job.get("result")
    metrics.update(
        {
            "training_job_id": training_job["job_id"],
            "reviewed_records": int(training_job["record_count"]),
            "training": {
                "status": status,
                "training_records": result.get("training_records") if isinstance(result, dict) else None,
                "test_records": result.get("test_records") if isinstance(result, dict) else None,
                "metrics": result.get("metrics") if isinstance(result, dict) else None,
            },
        }
    )
    run.metrics_json = json.dumps(metrics, ensure_ascii=False)
    run.error_message = str(training_job.get("error_message") or "") or None
    run.started_at = _naive_utc(training_job.get("started_at"))
    run.finished_at = _naive_utc(training_job.get("finished_at"))


def _user_id(user: SysUser) -> str:
    return str(user.id)


@router.post("/datasets/imports")
async def create_dataset_import(
    file: UploadFile = File(...),
    field_mapping: str | None = Form(None),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filename = (file.filename or "reviews.csv").strip()
    if not filename.casefold().endswith(".csv"):
        return Result.error("一期只支持 CSV 文件", code=400)
    content = await file.read()
    if not content:
        return Result.error("上传文件为空", code=400)
    if len(content) > settings.upload_max_mb * 1024 * 1024:
        return Result.error(f"文件不能超过 {settings.upload_max_mb}MB", code=400)
    try:
        dataset, report, reused = import_dataset(
            db,
            content,
            source_filename=Path(filename).name,
            created_by=_user_id(user),
            field_mapping=_parse_mapping(field_mapping),
        )
    except (RuntimeError, ValueError) as exc:
        return Result.error(str(exc), code=400)
    return Result.ok(
        {
            "dataset_version": dataset.dataset_version,
            "status": dataset.status,
            "reused": reused,
            "report": report.to_dict(),
        },
        "数据集导入校验完成",
    )


@router.get("/datasets")
def list_datasets(
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(PcDatasetImport).order_by(PcDatasetImport.created_at.desc()).limit(100).all()
    return Result.ok(
        [
            {
                "dataset_version": row.dataset_version,
                "source_filename": row.source_filename,
                "status": row.status,
                "file_sha256": row.file_sha256,
                "received_rows": row.received_rows,
                "valid_rows": row.valid_rows,
                "rejected_rows": row.rejected_rows,
                "rejection_reasons": json.loads(row.rejection_reasons_json or "{}"),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    )


@router.post("/demo/bootstrap")
def bootstrap_demo(
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import the checked-in synthetic dataset and seed its pending review queue."""
    demo_dir = sentiment_ai_root() / "data" / "demo" / "sweep_robot"
    reviews_path = demo_dir / "reviews.csv"
    tasks_path = demo_dir / "review_tasks.jsonl"
    if not reviews_path.is_file() or not tasks_path.is_file():
        return Result.error("PulseCart 演示数据不存在，请先生成 data/demo/sweep_robot", code=400)
    try:
        dataset, report, reused = import_dataset(
            db,
            reviews_path.read_bytes(),
            source_filename=reviews_path.name,
            created_by=_user_id(user),
        )
        tasks = [
            json.loads(line)
            for line in tasks_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        inserted = seed_review_tasks(db, dataset.dataset_version, tasks)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return Result.error(str(exc), code=400)
    return Result.ok(
        {
            "dataset_version": dataset.dataset_version,
            "report": report.to_dict(),
            "reused": reused,
            "review_tasks_inserted": inserted,
        },
        "PulseCart 演示数据已准备",
    )


@router.get("/review-tasks")
def list_review_tasks(
    status: str | None = Query(None),
    dataset_version: str | None = Query(None),
    limit: int = Query(50, ge=1, le=300),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(PcReviewTask)
    if status:
        query = query.filter(PcReviewTask.review_status == status)
    if dataset_version:
        query = query.filter(PcReviewTask.dataset_version == dataset_version)
    rows = query.order_by(PcReviewTask.created_at.asc()).limit(limit).all()
    if not rows:
        return Result.ok([])
    review_pairs = {(row.dataset_version, row.review_id) for row in rows}
    reviews = (
        db.query(PcReview)
        .filter(
            tuple_(PcReview.dataset_version, PcReview.review_id).in_(review_pairs),
        )
        .all()
    )
    return Result.ok(attach_reviews_to_tasks(rows, reviews))


@router.patch("/review-tasks/{task_id}")
def review_task_update(
    task_id: str,
    body: ReviewTaskUpdate,
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        task = update_review_task(
            db,
            task_id,
            status=body.review_status,
            reviewer_sentiment=body.reviewer_sentiment,
            reviewer_aspects=body.reviewer_aspects,
            reviewer_note=body.reviewer_note,
            reviewer_id=_user_id(user),
        )
    except LookupError as exc:
        return Result.error(str(exc), code=404)
    except ValueError as exc:
        return Result.error(str(exc), code=400)
    return Result.ok(task_to_dict(task), "审核任务已保存")


@router.post("/analysis-runs")
def create_analysis_run(
    body: AnalysisRunCreate,
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dataset = db.query(PcDatasetImport).filter(PcDatasetImport.dataset_version == body.dataset_version).first()
    if not dataset:
        return Result.error("dataset_version 不存在", code=404)
    existing_run = (
        db.query(PcAnalysisRun)
        .filter(PcAnalysisRun.model_version == body.model_version)
        .first()
    )
    if existing_run:
        return Result.error(
            f"model_version 已关联分析运行: {existing_run.id}，请使用新的模型版本",
            code=409,
        )
    tasks = (
        db.query(PcReviewTask)
        .filter(
            PcReviewTask.dataset_version == body.dataset_version,
            PcReviewTask.review_status.in_(["approved", "verified"]),
            PcReviewTask.reviewer_sentiment.isnot(None),
        )
        .order_by(PcReviewTask.task_id.asc())
        .all()
    )
    if len(tasks) < 15:
        return Result.error("人工审核样本不足 15 条，暂不能创建正式训练/评测运行", code=400)
    review_pairs = {(task.dataset_version, task.review_id) for task in tasks}
    reviews = (
        db.query(PcReview)
        .filter(tuple_(PcReview.dataset_version, PcReview.review_id).in_(review_pairs))
        .all()
    )
    try:
        records = build_training_records(tasks, reviews)
    except ValueError as exc:
        return Result.error(f"训练数据校验失败: {exc}", code=400)

    label_counts = Counter(record["sentiment"] for record in records)
    missing_labels = [label for label in ("positive", "neutral", "negative") if label not in label_counts]
    small_classes = [label for label, count in label_counts.items() if count < 3]
    if missing_labels or small_classes:
        problems = []
        if missing_labels:
            problems.append(f"缺少情感标签: {', '.join(missing_labels)}")
        if small_classes:
            problems.append(f"每类至少需要 3 条: {', '.join(sorted(small_classes))}")
        return Result.error(f"训练数据校验失败，{'；'.join(problems)}", code=400)

    try:
        training_job = submit_training_run(
            settings.sentiment_ai_base_url,
            dataset_version=body.dataset_version,
            model_version=body.model_version,
            records=records,
            random_seed=68,
            timeout=settings.sentiment_ai_training_timeout,
        )
    except TrainingServiceError as exc:
        return Result.error(f"无法提交正式训练任务: {exc}", code=502)
    run = PcAnalysisRun(
        id=new_id(),
        dataset_version=body.dataset_version,
        model_version=body.model_version,
        status="queued",
        source_kind=body.source_kind,
        metrics_json=json.dumps(
            {
                "reviewed_records": len(records),
                "training_job_id": training_job["job_id"],
                "training": {"status": "queued"},
            },
            ensure_ascii=False,
        ),
        created_by=_user_id(user),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return Result.ok(analysis_run_to_dict(run), "分析运行已进入队列")


@router.get("/analysis-runs")
def list_analysis_runs(
    dataset_version: str | None = Query(None),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(PcAnalysisRun)
    if dataset_version:
        query = query.filter(PcAnalysisRun.dataset_version == dataset_version)
    rows = query.order_by(PcAnalysisRun.created_at.desc()).limit(100).all()
    return Result.ok([analysis_run_to_dict(row) for row in rows])


@router.post("/analysis-runs/{run_id}/sync")
def sync_analysis_run(
    run_id: str,
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.query(PcAnalysisRun).filter(PcAnalysisRun.id == run_id).first()
    if not run:
        return Result.error("分析运行不存在", code=404)
    job_id = _training_job_id(run)
    if not job_id:
        return Result.error("分析运行未关联训练任务", code=409)
    try:
        training_job = get_training_run(
            settings.sentiment_ai_base_url,
            job_id,
            timeout=settings.sentiment_ai_training_timeout,
        )
    except TrainingServiceError as exc:
        return Result.error(f"无法同步训练任务: {exc}", code=502)
    _sync_analysis_run(run, training_job)
    db.commit()
    db.refresh(run)
    return Result.ok(analysis_run_to_dict(run), "分析运行状态已同步")


@router.post("/issues")
def create_issue(
    body: IssueCreate,
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dataset = db.query(PcDatasetImport).filter(PcDatasetImport.dataset_version == body.dataset_version).first()
    if not dataset:
        return Result.error("dataset_version 不存在", code=404)
    if body.source_review_ids:
        found = {
            row.review_id
            for row in db.query(PcReview.review_id)
            .filter(PcReview.dataset_version == body.dataset_version, PcReview.review_id.in_(body.source_review_ids))
            .all()
        }
        missing = sorted(set(body.source_review_ids) - found)
        if missing:
            return Result.error(f"来源评论不存在: {', '.join(missing[:5])}", code=400)
    issue = PcIssue(
        id=new_id(),
        dataset_version=body.dataset_version,
        title=body.title.strip(),
        aspect=body.aspect.strip(),
        severity=body.severity,
        status="open",
        description=body.description.strip(),
        source_review_ids_json=json.dumps(body.source_review_ids, ensure_ascii=False),
        created_by=_user_id(user),
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return Result.ok(issue_to_dict(issue), "问题卡片已创建")


@router.get("/issues")
def list_issues(
    dataset_version: str | None = Query(None),
    status: str | None = Query(None),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(PcIssue)
    if dataset_version:
        query = query.filter(PcIssue.dataset_version == dataset_version)
    if status:
        query = query.filter(PcIssue.status == status)
    rows = query.order_by(PcIssue.updated_at.desc()).limit(100).all()
    return Result.ok([issue_to_dict(row) for row in rows])


@router.patch("/issues/{issue_id}")
def issue_update(
    issue_id: str,
    body: IssueUpdate,
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        issue = update_issue(
            db,
            issue_id,
            status=body.status,
            resolution_note=body.resolution_note,
            owner_user_id=body.owner_user_id,
        )
    except LookupError as exc:
        return Result.error(str(exc), code=404)
    except ValueError as exc:
        return Result.error(str(exc), code=400)
    return Result.ok(issue_to_dict(issue), "问题卡片状态已更新")


__all__ = ["router"]
