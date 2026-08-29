"""Model discovery and inference for the standalone PulseCart NLP service.

Only persisted model artifacts with auditable metadata are eligible for
inference.  This intentionally does not auto-discover the inherited binary
BERT directory: that model has a different label contract from PulseCart P1.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.baseline_sentiment import BaselineTrainingError, predict_baseline


MIN_PUBLISHABLE_MACRO_F1 = 0.65
MIN_PUBLISHABLE_TEST_RECORDS = 30


class ModelNotReadyError(RuntimeError):
    """Raised when a requested model is absent, invalid, or not publishable."""


@dataclass(frozen=True)
class RegisteredModel:
    model_version: str
    model_type: str
    dataset_version: str
    created_at: str
    model_path: Path
    metadata: dict[str, Any]
    status: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "model_type": self.model_type,
            "dataset_version": self.dataset_version,
            "created_at": self.created_at,
            "status": self.status,
            "reason": self.reason,
            "metrics": self.metadata.get("metrics", {}),
            "artifact_sha256": self.metadata.get("artifact_sha256"),
        }


class ModelRegistry:
    """Read-only registry backed by versioned artifacts on local storage."""

    def __init__(self, model_root: str | Path):
        self.model_root = Path(model_root)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _read_artifact(self, metadata_path: Path) -> RegisteredModel:
        model_path = metadata_path.with_name("model.joblib")
        fallback_version = metadata_path.parent.name
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return RegisteredModel(
                model_version=fallback_version,
                model_type="unknown",
                dataset_version="unknown",
                created_at="",
                model_path=model_path,
                metadata={},
                status="invalid",
                reason=f"模型元数据无法读取: {exc}",
            )
        required = ("model_version", "model_type", "dataset_version", "artifact_sha256")
        missing = [key for key in required if not isinstance(metadata.get(key), str) or not metadata[key].strip()]
        if missing:
            return RegisteredModel(
                model_version=str(metadata.get("model_version") or fallback_version),
                model_type=str(metadata.get("model_type") or "unknown"),
                dataset_version=str(metadata.get("dataset_version") or "unknown"),
                created_at=str(metadata.get("created_at") or ""),
                model_path=model_path,
                metadata=metadata,
                status="invalid",
                reason=f"模型元数据缺少字段: {', '.join(missing)}",
            )
        if metadata["model_type"] != "tfidf_logistic_regression":
            return RegisteredModel(
                model_version=metadata["model_version"],
                model_type=metadata["model_type"],
                dataset_version=metadata["dataset_version"],
                created_at=str(metadata.get("created_at") or ""),
                model_path=model_path,
                metadata=metadata,
                status="unsupported",
                reason="P1 模型服务仅支持 tfidf_logistic_regression 三分类产物",
            )
        if not model_path.is_file():
            return RegisteredModel(
                model_version=metadata["model_version"],
                model_type=metadata["model_type"],
                dataset_version=metadata["dataset_version"],
                created_at=str(metadata.get("created_at") or ""),
                model_path=model_path,
                metadata=metadata,
                status="invalid",
                reason="模型文件 model.joblib 不存在",
            )
        actual_hash = self._sha256(model_path)
        if actual_hash != metadata["artifact_sha256"]:
            return RegisteredModel(
                model_version=metadata["model_version"],
                model_type=metadata["model_type"],
                dataset_version=metadata["dataset_version"],
                created_at=str(metadata.get("created_at") or ""),
                model_path=model_path,
                metadata=metadata,
                status="invalid",
                reason="模型文件哈希与训练元数据不一致",
            )
        metrics = metadata.get("metrics")
        macro_f1 = metrics.get("macro_f1") if isinstance(metrics, dict) else None
        test_records = metadata.get("test_records")
        reasons = []
        if not isinstance(macro_f1, (int, float)) or macro_f1 < MIN_PUBLISHABLE_MACRO_F1:
            display_f1 = "缺失" if not isinstance(macro_f1, (int, float)) else f"{macro_f1:.3f}"
            reasons.append(f"Macro-F1 {display_f1} 未达到 {MIN_PUBLISHABLE_MACRO_F1:.2f}")
        if not isinstance(test_records, int) or test_records < MIN_PUBLISHABLE_TEST_RECORDS:
            display_count = "缺失" if not isinstance(test_records, int) else str(test_records)
            reasons.append(f"独立测试样本 {display_count} 少于 {MIN_PUBLISHABLE_TEST_RECORDS}")
        if reasons:
            return RegisteredModel(
                model_version=metadata["model_version"],
                model_type=metadata["model_type"],
                dataset_version=metadata["dataset_version"],
                created_at=str(metadata.get("created_at") or ""),
                model_path=model_path,
                metadata=metadata,
                status="evaluation_only",
                reason="；".join(reasons),
            )
        return RegisteredModel(
            model_version=metadata["model_version"],
            model_type=metadata["model_type"],
            dataset_version=metadata["dataset_version"],
            created_at=str(metadata.get("created_at") or ""),
            model_path=model_path,
            metadata=metadata,
            status="ready",
        )

    def list_models(self) -> list[RegisteredModel]:
        if not self.model_root.is_dir():
            return []
        models = [self._read_artifact(path) for path in self.model_root.glob("*/metadata.json")]
        return sorted(models, key=lambda model: (model.created_at, model.model_version), reverse=True)

    def resolve(self, model_version: str | None = None) -> RegisteredModel:
        models = self.list_models()
        if model_version:
            for model in models:
                if model.model_version == model_version:
                    if model.status != "ready":
                        raise ModelNotReadyError(f"模型 {model_version} 当前不可用: {model.reason or model.status}")
                    return model
            raise ModelNotReadyError(f"未注册模型版本: {model_version}")
        for model in models:
            if model.status == "ready":
                return model
        raise ModelNotReadyError("暂无可用模型。请先使用人工审核数据运行训练任务并发布产物。")

    def predict(self, texts: list[str], model_version: str | None = None) -> tuple[RegisteredModel, list[dict[str, Any]]]:
        model = self.resolve(model_version)
        try:
            predictions = predict_baseline(model.model_path, texts)
        except BaselineTrainingError as exc:
            raise ModelNotReadyError(str(exc)) from exc
        return model, predictions


__all__ = [
    "MIN_PUBLISHABLE_MACRO_F1",
    "MIN_PUBLISHABLE_TEST_RECORDS",
    "ModelNotReadyError",
    "ModelRegistry",
    "RegisteredModel",
]
