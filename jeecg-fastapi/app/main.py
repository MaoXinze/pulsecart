from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
import logging

from sqlalchemy.exc import OperationalError

from app.api.router import sys_router
from app.api.pulsecart import router as pulsecart_router
from app.api.websocket import router as websocket_router
from app.core.config import settings
from app.schemas.response import Result
from app.services.sms_service import is_spug_configured

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sentiment-Plus",
    description="Sentiment-Plus：系统配置 + 评论分析（情感/关键词/属性聚合）",
    version="0.1.0",
)

_cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https?://[\w.-]+(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sys_router, prefix=f"{settings.context_path}/sys")
app.include_router(pulsecart_router, prefix=settings.context_path)
app.include_router(websocket_router, prefix=settings.context_path)


@app.on_event("startup")
def log_startup_config():
    from app.db.startup import mark_db_ready, start_background_db_connect
    from app.db.session import ping_db, warmup_db_pool

    try:
        if settings.db_warmup_enabled:
            elapsed = warmup_db_pool()
            logger.info("数据库连接池已预热，首次连通耗时 %.2fs", elapsed)
        else:
            elapsed = ping_db()
            logger.info("数据库连通检查通过，耗时 %.2fs", elapsed)
        mark_db_ready()
        if elapsed > 1.0:
            logger.warning(
                "数据库响应较慢（>1s）。开发环境建议使用本地 MySQL，见 .env.example 中 DATABASE_URL 注释"
            )
    except Exception as exc:
        logger.warning("启动时连接数据库失败，将转入后台重试: %s", exc)
        start_background_db_connect()

    if is_spug_configured():
        logger.info("短信: Spug 已配置，将真实发送")
    else:
        logger.warning("短信: 未配置 SPUG_SMS_API_URL，使用开发模式（验证码仅在接口 message 中返回）")


@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    detail = str(getattr(exc, "orig", exc) or exc)
    logger.error("数据库操作失败 %s %s: %s", request.method, request.url.path, detail)
    hint = "请确认 MySQL 已启动，且 jeecg-fastapi/.env 中 DATABASE_URL 账号密码正确（密码含 @ 需写成 %40）。"
    return JSONResponse(
        status_code=200,
        content=Result.error(
            f"数据库连接异常，请稍后重试。{hint}",
            500,
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    code = 401 if exc.status_code == 401 else 500
    return JSONResponse(
        status_code=200,
        content=Result.error(exc.detail, code).model_dump(),
    )


@app.get(f"{settings.context_path}/health")
def health():
    from app.db.session import is_db_healthy

    db_ok, db_latency_ms = is_db_healthy()

    return Result.ok({
        "status": "ok" if db_ok else "degraded",
        "backend": "fastapi",
        "db": "ok" if db_ok else "error",
        "dbLatencyMs": db_latency_ms,
        "smsMode": "spug" if is_spug_configured() else "dev",
    })


@app.get("/")
def root():
    return Result.ok({"message": "JeecgBoot FastAPI", "api": f"{settings.context_path}/sys"})
