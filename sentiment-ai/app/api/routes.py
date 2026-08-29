"""HTTP routes for both the legacy demo and the PulseCart P1 model API."""

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.model_service import BatchPredictionRequest, TrainingRunCreate
from app.schemas.predict import PredictRequest, PredictResponse
from app.services.model_registry import ModelNotReadyError, ModelRegistry
from app.services.training_jobs import TrainingJobError, TrainingJobStore

router = APIRouter()


def _model_registry() -> ModelRegistry:
    return ModelRegistry(settings.model_root)


def _training_job_store() -> TrainingJobStore:
    return TrainingJobStore(settings.training_job_root, settings.model_root)


@router.get("/health")
def health():
    """Compatibility health endpoint retained for the inherited binary demo."""
    return healthz()


@router.get("/healthz")
def healthz():
    models = _model_registry().list_models()
    ready_count = sum(model.status == "ready" for model in models)
    return {
        "service": "pulsecart-nlp",
        "status": "ready" if ready_count else "not_ready",
        "model_count": len(models),
        "ready_model_count": ready_count,
        "legacy_binary_bert": "not_registered_for_p1",
    }


@router.post("/api/sentiment/predict", response_model=PredictResponse)
def sentiment_predict(body: PredictRequest):
    """Legacy binary BERT endpoint, excluded from the PulseCart P1 contract."""
    from app.services.bert_sentiment import predict_sentiment

    results = predict_sentiment(body.texts)
    return PredictResponse(results=results)


@router.get("/api/v1/models")
def list_models():
    """List every artifact and make invalid model state visible to operators."""
    return {"models": [model.to_dict() for model in _model_registry().list_models()]}


@router.post("/api/v1/predictions:batch")
def batch_predict(body: BatchPredictionRequest):
    """Run P1 three-class inference with an explicit or current model version."""
    try:
        model, predictions = _model_registry().predict(body.texts, body.model_version)
    except ModelNotReadyError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "model_not_ready", "message": str(exc)},
        ) from exc
    return {
        "model_version": model.model_version,
        "model_type": model.model_type,
        "dataset_version": model.dataset_version,
        "predictions": predictions,
        "aspect_extraction": {"status": "not_available", "message": "P1 基线仅提供情感三分类，不伪造属性抽取结果"},
    }


@router.post("/api/v1/training-runs", status_code=202)
def create_training_run(body: TrainingRunCreate):
    """Persist a reproducible baseline-training job for the local worker."""
    try:
        job = _training_job_store().enqueue(
            dataset_version=body.dataset_version,
            model_version=body.model_version,
            random_seed=body.random_seed,
            records=[record.model_dump() for record in body.records],
        )
    except TrainingJobError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_training_run", "message": str(exc)}) from exc
    return _public_job(job)


@router.get("/api/v1/training-runs")
def list_training_runs():
    return {"training_runs": [_public_job(job) for job in _training_job_store().list()]}


@router.get("/api/v1/training-runs/{job_id}")
def get_training_run(job_id: str):
    try:
        return _public_job(_training_job_store().get(job_id))
    except TrainingJobError as exc:
        raise HTTPException(status_code=404, detail={"code": "training_run_not_found", "message": str(exc)}) from exc


def _public_job(job: dict) -> dict:
    """Expose run state and audit details without returning review text payloads."""
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "dataset_version": job["dataset_version"],
        "model_version": job["model_version"],
        "random_seed": job["random_seed"],
        "record_count": len(job["records"]),
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
        "result": job["result"],
        "error_message": job["error_message"],
    }
