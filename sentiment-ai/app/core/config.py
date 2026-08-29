"""Local paths for the standalone PulseCart NLP service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[2]
BERT_MODEL_DIR = AI_ROOT / "artifacts" / "bert" / "best"


@dataclass(frozen=True)
class ModelServiceSettings:
    model_root: Path
    training_job_root: Path


def _path_from_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser().resolve() if value else default


settings = ModelServiceSettings(
    model_root=_path_from_env("PULSECART_MODEL_ROOT", AI_ROOT / "artifacts" / "models"),
    training_job_root=_path_from_env("PULSECART_TRAINING_JOB_ROOT", AI_ROOT / "runtime" / "training-jobs"),
)


__all__ = ["AI_ROOT", "BERT_MODEL_DIR", "ModelServiceSettings", "settings"]
