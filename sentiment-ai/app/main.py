"""Standalone model service for the PulseCart product-experience platform."""

from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(
    title="PulseCart NLP Service",
    version="2.0.0",
    description="人工审核数据驱动的三分类模型注册、训练任务与批量推理服务。",
)
app.include_router(router)


@app.get("/")
def root():
    return {
        "service": "pulsecart-nlp",
        "version": "2.0.0",
        "mode": "reviewed_three_class_sentiment",
        "docs": "/docs",
        "health": "/healthz",
        "models": "/api/v1/models",
        "legacy_binary_bert": "/api/sentiment/predict",
    }
