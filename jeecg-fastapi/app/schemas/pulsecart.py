"""PulseCart API contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SentimentLabel = Literal["positive", "neutral", "negative"]
ReviewTaskStatus = Literal["pending", "approved", "verified", "rejected"]
IssueStatus = Literal["open", "in_progress", "pending_validation", "closed"]


class ReviewTaskUpdate(BaseModel):
    review_status: ReviewTaskStatus
    reviewer_sentiment: SentimentLabel | None = None
    reviewer_aspects: list[str] = Field(default_factory=list, max_length=11)
    reviewer_note: str = Field(default="", max_length=2000)


class AnalysisRunCreate(BaseModel):
    dataset_version: str = Field(..., min_length=3, max_length=40)
    model_version: str = Field(..., min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    source_kind: Literal["human_reviewed"] = "human_reviewed"


class IssueCreate(BaseModel):
    dataset_version: str = Field(..., min_length=3, max_length=40)
    title: str = Field(..., min_length=1, max_length=255)
    aspect: str = Field(..., min_length=1, max_length=80)
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    description: str = Field(default="", max_length=5000)
    source_review_ids: list[str] = Field(default_factory=list, max_length=100)


class IssueUpdate(BaseModel):
    status: IssueStatus
    resolution_note: str = Field(default="", max_length=5000)
    owner_user_id: str | None = Field(default=None, max_length=32)
