"""HTTP client for the PulseCart local NLP training service."""

from __future__ import annotations

from typing import Any

import httpx


class TrainingServiceError(RuntimeError):
    """Raised when the local training service cannot accept or report a job."""


def _message(payload: Any) -> str:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("code") or detail)
        if detail:
            return str(detail)
    return "训练服务返回了无法识别的响应"


def _request_json(
    method: str,
    base_url: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout)) as client:
            response = client.request(method, url, json=payload)
    except httpx.HTTPError as exc:
        raise TrainingServiceError(f"无法连接 PulseCart NLP 训练服务: {exc}") from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise TrainingServiceError(f"训练服务响应不是 JSON，HTTP {response.status_code}") from exc
    if response.is_error:
        raise TrainingServiceError(f"训练服务拒绝请求，HTTP {response.status_code}: {_message(body)}")
    if not isinstance(body, dict):
        raise TrainingServiceError("训练服务响应必须是对象")
    return body


def submit_training_run(
    base_url: str,
    *,
    dataset_version: str,
    model_version: str,
    records: list[dict[str, Any]],
    random_seed: int,
    timeout: float,
) -> dict[str, Any]:
    body = _request_json(
        "POST",
        base_url,
        "/api/v1/training-runs",
        payload={
            "dataset_version": dataset_version,
            "model_version": model_version,
            "random_seed": random_seed,
            "records": records,
        },
        timeout=timeout,
    )
    if not isinstance(body.get("job_id"), str) or not body["job_id"].strip():
        raise TrainingServiceError("训练服务未返回 job_id")
    if body.get("status") != "queued":
        raise TrainingServiceError(f"训练服务返回了异常初始状态: {body.get('status')}")
    return body


def get_training_run(base_url: str, job_id: str, *, timeout: float) -> dict[str, Any]:
    body = _request_json(
        "GET",
        base_url,
        f"/api/v1/training-runs/{job_id}",
        timeout=timeout,
    )
    if body.get("job_id") != job_id:
        raise TrainingServiceError("训练服务返回的 job_id 不匹配")
    if body.get("status") not in {"queued", "running", "succeeded", "failed"}:
        raise TrainingServiceError(f"训练服务返回了未知状态: {body.get('status')}")
    return body


__all__ = ["TrainingServiceError", "get_training_run", "submit_training_run"]
