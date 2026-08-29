"""HTTP contracts for the PulseCart standalone NLP service."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class BatchPredictionRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=200)
    model_version: str | None = Field(default=None, max_length=80)

    @field_validator("texts")
    @classmethod
    def validate_texts(cls, texts: list[str]) -> list[str]:
        clean = [text.strip() for text in texts]
        if any(not text for text in clean):
            raise ValueError("texts 不能包含空字符串")
        if any(len(text) > 4000 for text in clean):
            raise ValueError("单条评论不能超过 4000 个字符")
        return clean


class TrainingRecordInput(BaseModel):
    review_id: str = Field(min_length=1, max_length=128)
    review_text: str = Field(min_length=1, max_length=4000)
    sentiment: str = Field(pattern="^(positive|neutral|negative)$")
    aspects: list[str] = Field(default_factory=list, max_length=11)
    review_status: str = Field(default="approved", pattern="^(approved|verified)$")


class TrainingRunCreate(BaseModel):
    dataset_version: str = Field(min_length=1, max_length=40)
    model_version: str = Field(min_length=3, max_length=80)
    random_seed: int = Field(default=68, ge=0, le=2_147_483_647)
    records: list[TrainingRecordInput] = Field(min_length=15)


__all__ = ["BatchPredictionRequest", "TrainingRecordInput", "TrainingRunCreate"]
