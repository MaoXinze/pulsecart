"""PulseCart domain tables.

The ``pc_`` prefix keeps the product domain isolated from the inherited
JeecgBoot system tables during the migration period.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PcDatasetImport(Base):
    __tablename__ = "pc_dataset_import"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dataset_version: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    source_filename: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), default="validated")
    mapping_json: Mapped[str] = mapped_column(Text)
    quality_rules_json: Mapped[str] = mapped_column(Text)
    rejection_reasons_json: Mapped[str] = mapped_column(Text)
    received_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PcReview(Base):
    __tablename__ = "pc_review"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dataset_version: Mapped[str] = mapped_column(String(40), index=True)
    review_id: Mapped[str] = mapped_column(String(128), index=True)
    product_id: Mapped[str] = mapped_column(String(128), index=True)
    category_id: Mapped[Optional[str]] = mapped_column(String(128))
    review_text: Mapped[str] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    channel: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer)
    product_version: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    language: Mapped[str] = mapped_column(String(16), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_pc_review_dataset_review", "dataset_version", "review_id", unique=True),
    )


class PcReviewTask(Base):
    __tablename__ = "pc_review_task"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    dataset_version: Mapped[str] = mapped_column(String(40), index=True)
    review_id: Mapped[str] = mapped_column(String(128), index=True)
    sampling_group: Mapped[str] = mapped_column(String(40))
    sampling_reason: Mapped[str] = mapped_column(String(80))
    assigned_role: Mapped[str] = mapped_column(String(64), default="product_operator")
    review_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(80))
    system_sentiment: Mapped[Optional[str]] = mapped_column(String(16))
    system_aspects_json: Mapped[str] = mapped_column(Text, default="[]")
    system_confidence: Mapped[Optional[float]] = mapped_column(Float)
    reviewer_sentiment: Mapped[Optional[str]] = mapped_column(String(16))
    reviewer_aspects_json: Mapped[str] = mapped_column(Text, default="[]")
    reviewer_note: Mapped[str] = mapped_column(Text, default="")
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(32))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PcAnalysisRun(Base):
    __tablename__ = "pc_analysis_run"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dataset_version: Mapped[str] = mapped_column(String(40), index=True)
    model_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    source_kind: Mapped[str] = mapped_column(String(32), default="human_reviewed")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class PcIssue(Base):
    __tablename__ = "pc_issue"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dataset_version: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(255))
    aspect: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    source_review_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    owner_user_id: Mapped[Optional[str]] = mapped_column(String(32))
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


__all__ = [
    "PcAnalysisRun",
    "PcDatasetImport",
    "PcIssue",
    "PcReview",
    "PcReviewTask",
]
