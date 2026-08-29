"""Reproducible TF-IDF sentiment baseline for reviewed PulseCart records.

This module intentionally has no FastAPI dependency. A worker, CLI command or
future model service can all call it with the same reviewed records and produce
an auditable model run.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SENTIMENT_LABELS = ("positive", "neutral", "negative")
TRAINABLE_REVIEW_STATUSES = frozenset({"approved", "verified"})


class BaselineTrainingError(ValueError):
    """Raised when reviewed data cannot produce a valid baseline run."""


@dataclass(frozen=True)
class ReviewedRecord:
    review_id: str
    review_text: str
    sentiment: str
    aspects: tuple[str, ...]
    review_status: str


@dataclass(frozen=True)
class BaselineTrainingResult:
    model_path: Path
    metadata_path: Path
    training_records: int
    test_records: int
    metrics: dict[str, Any]


def _require_ml_dependencies() -> tuple[Any, ...]:
    try:
        from joblib import dump, load
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
    except ImportError as exc:
        raise BaselineTrainingError(
            "缺少传统机器学习依赖。请使用 Python 3.12 环境安装仓库根目录 requirements.txt。"
        ) from exc
    return (
        dump,
        load,
        TfidfVectorizer,
        LogisticRegression,
        accuracy_score,
        classification_report,
        confusion_matrix,
        train_test_split,
        Pipeline,
        f1_score,
    )


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineTrainingError(f"无法读取审核任务文件: {path}") from exc


def load_reviewed_records(
    reviews_path: str | Path,
    review_tasks_path: str | Path,
) -> list[ReviewedRecord]:
    """Load only reviewed labels, never synthetic reference labels.

    A review task must be marked ``approved`` or ``verified`` and have a valid
    reviewer sentiment to become training data. Pending tasks are intentionally
    invisible to this function.
    """
    reviews_file = Path(reviews_path)
    tasks_file = Path(review_tasks_path)
    try:
        with reviews_file.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "review_id" not in reader.fieldnames or "review_text" not in reader.fieldnames:
                raise BaselineTrainingError("评论 CSV 必须包含 review_id 和 review_text")
            reviews = {
                str(row["review_id"]).strip(): str(row["review_text"]).strip()
                for row in reader
                if str(row.get("review_id") or "").strip()
            }
    except OSError as exc:
        raise BaselineTrainingError(f"无法读取评论 CSV: {reviews_file}") from exc

    records: list[ReviewedRecord] = []
    seen_review_ids: set[str] = set()
    for task in _load_jsonl(tasks_file):
        review_id = str(task.get("review_id") or "").strip()
        review_status = str(task.get("review_status") or "").strip().lower()
        sentiment = str(task.get("reviewer_sentiment") or "").strip().lower()
        if not review_id or review_status not in TRAINABLE_REVIEW_STATUSES or not sentiment:
            continue
        if sentiment not in SENTIMENT_LABELS:
            raise BaselineTrainingError(f"审核任务 {task.get('task_id', review_id)} 包含不支持的情感标签: {sentiment}")
        if review_id in seen_review_ids:
            raise BaselineTrainingError(f"审核任务中存在重复 review_id: {review_id}")
        review_text = reviews.get(review_id)
        if not review_text:
            raise BaselineTrainingError(f"审核任务引用了不存在或空文本的评论: {review_id}")
        raw_aspects = task.get("reviewer_aspects") or []
        if not isinstance(raw_aspects, list) or not all(isinstance(item, str) and item.strip() for item in raw_aspects):
            raise BaselineTrainingError(f"审核任务 {task.get('task_id', review_id)} 的 reviewer_aspects 格式无效")
        seen_review_ids.add(review_id)
        records.append(
            ReviewedRecord(
                review_id=review_id,
                review_text=review_text,
                sentiment=sentiment,
                aspects=tuple(raw_aspects),
                review_status=review_status,
            )
        )
    return records


def validate_reviewed_records(records: Iterable[ReviewedRecord]) -> list[ReviewedRecord]:
    """Validate the minimum evidence required for a three-class baseline."""
    validated = list(records)
    if len(validated) < 15:
        raise BaselineTrainingError("至少需要 15 条已审核记录才能训练三分类基线")
    label_counts = Counter(record.sentiment for record in validated)
    missing_labels = [label for label in SENTIMENT_LABELS if label not in label_counts]
    if missing_labels:
        raise BaselineTrainingError(f"训练集缺少情感标签: {', '.join(missing_labels)}")
    small_classes = [label for label, count in label_counts.items() if count < 3]
    if small_classes:
        raise BaselineTrainingError(f"每个情感标签至少需要 3 条已审核记录: {', '.join(sorted(small_classes))}")
    return validated


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def train_baseline(
    records: Iterable[ReviewedRecord],
    output_dir: str | Path,
    *,
    dataset_version: str,
    random_seed: int = 68,
    test_ratio: float = 0.2,
    source_kind: str = "human_reviewed",
) -> BaselineTrainingResult:
    """Train and persist a character TF-IDF + Logistic Regression baseline."""
    if source_kind != "human_reviewed":
        raise BaselineTrainingError("正式基线仅接受 source_kind='human_reviewed'，不得使用合成参考标签训练")
    if not dataset_version.strip():
        raise BaselineTrainingError("dataset_version 不能为空")
    if not 0 < test_ratio < 0.5:
        raise BaselineTrainingError("test_ratio 必须在 0 和 0.5 之间")
    validated = validate_reviewed_records(records)
    (
        dump,
        _,
        TfidfVectorizer,
        LogisticRegression,
        accuracy_score,
        classification_report,
        confusion_matrix,
        train_test_split,
        Pipeline,
        f1_score,
    ) = _require_ml_dependencies()

    texts = [record.review_text for record in validated]
    labels = [record.sentiment for record in validated]
    class_count = len(SENTIMENT_LABELS)
    test_count = max(class_count, round(len(validated) * test_ratio))
    if len(validated) - test_count < class_count:
        raise BaselineTrainingError("训练样本不足以在训练集和测试集中同时覆盖三类情感")
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts,
        labels,
        test_size=test_count,
        random_state=random_seed,
        stratify=labels,
    )
    pipeline = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(analyzer="char", ngram_range=(2, 4), min_df=1, sublinear_tf=True)),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1200,
                    random_state=random_seed,
                    class_weight="balanced",
                ),
            ),
        ]
    )
    pipeline.fit(train_texts, train_labels)
    predictions = pipeline.predict(test_texts).tolist()
    metrics = {
        "accuracy": round(float(accuracy_score(test_labels, predictions)), 6),
        "macro_f1": round(float(f1_score(test_labels, predictions, labels=list(SENTIMENT_LABELS), average="macro", zero_division=0)), 6),
        "classification_report": classification_report(
            test_labels,
            predictions,
            labels=list(SENTIMENT_LABELS),
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": {
            "labels": list(SENTIMENT_LABELS),
            "values": confusion_matrix(test_labels, predictions, labels=list(SENTIMENT_LABELS)).tolist(),
        },
    }
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model_path = output_path / "model.joblib"
    temporary_model_path = output_path / "model.joblib.tmp"
    dump(pipeline, temporary_model_path)
    temporary_model_path.replace(model_path)

    record_digest = _sha256_json([asdict(record) for record in sorted(validated, key=lambda item: item.review_id)])
    metadata = {
        "model_type": "tfidf_logistic_regression",
        "model_version": output_path.name,
        "dataset_version": dataset_version,
        "source_kind": source_kind,
        "random_seed": random_seed,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "training_records": len(train_texts),
        "test_records": len(test_texts),
        "label_counts": dict(sorted(Counter(labels).items())),
        "training_record_sha256": record_digest,
        "feature_config": {"analyzer": "char", "ngram_range": [2, 4], "min_df": 1, "sublinear_tf": True},
        "classifier_config": {"class_weight": "balanced", "max_iter": 1200},
        "metrics": metrics,
        "artifact_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
    }
    metadata_path = output_path / "metadata.json"
    _atomic_json_write(metadata_path, metadata)
    return BaselineTrainingResult(
        model_path=model_path,
        metadata_path=metadata_path,
        training_records=len(train_texts),
        test_records=len(test_texts),
        metrics=metrics,
    )


def predict_baseline(model_path: str | Path, texts: list[str]) -> list[dict[str, Any]]:
    """Run inference using an explicitly selected persisted baseline model."""
    if not texts or not all(isinstance(text, str) and text.strip() for text in texts):
        raise BaselineTrainingError("texts 必须是非空字符串列表")
    _, load, *_ = _require_ml_dependencies()
    path = Path(model_path)
    if not path.is_file():
        raise BaselineTrainingError(f"未找到基线模型产物: {path}")
    model = load(path)
    probabilities = model.predict_proba(texts)
    labels = list(model.classes_)
    predictions = model.predict(texts)
    return [
        {
            "text": text,
            "sentiment": str(prediction),
            "confidence": round(float(max(probability)), 6),
            "probabilities": {label: round(float(value), 6) for label, value in zip(labels, probability)},
        }
        for text, prediction, probability in zip(texts, predictions, probabilities)
    ]


__all__ = [
    "BaselineTrainingError",
    "BaselineTrainingResult",
    "ReviewedRecord",
    "SENTIMENT_LABELS",
    "TRAINABLE_REVIEW_STATUSES",
    "load_reviewed_records",
    "predict_baseline",
    "train_baseline",
    "validate_reviewed_records",
]
