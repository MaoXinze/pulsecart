from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "mysql+pymysql://root:root@127.0.0.1:3306/jeecg-boot?charset=utf8mb4"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_connect_timeout: int = 10
    db_read_timeout: int = 30
    db_write_timeout: int = 30
    db_migration_read_timeout: int = 300
    db_migration_write_timeout: int = 300
    db_migration_retries: int = 3
    db_connect_retries: int = 3
    db_connect_retry_delay: float = 1.0
    db_session_ping: bool = False
    db_warmup_enabled: bool = False
    db_warmup_connections: int = 1
    db_background_connect: bool = True
    auth_cache_ttl_seconds: int = 300
    dict_cache_ttl_seconds: int = 600
    permission_cache_ttl_seconds: int = 600
    user_roles_cache_ttl_seconds: int = 600
    jwt_expire_hours: int = 84
    enable_login_captcha: bool = False
    signature_secret: str = "dd05f1c54d63749eda95f9fa6d49v442a"
    context_path: str = "/jeecg-boot"
    cors_origins: str = "http://localhost:3100,http://127.0.0.1:3100"
    base_dir: Path = BASE_DIR
    upload_dir: str = "uploads"
    upload_max_mb: int = 10

    # 第三方登录（网站应用 OAuth，需在对应开放平台配置回调地址）
    third_login_base_url: str = "http://localhost:8006/jeecg-boot"
    frontend_url: str = "http://localhost:3100"

    wechat_open_client_id: str = ""
    wechat_open_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    dingtalk_client_id: str = ""
    dingtalk_client_secret: str = ""

    wechat_enterprise_corp_id: str = ""
    wechat_enterprise_agent_id: str = ""
    wechat_enterprise_secret: str = ""

    # Spug 短信推送 https://push.spug.cc
    spug_sms_api_url: str = ""
    spug_sms_name: str = "推送助手"

    # sentiment-ai 推理服务（默认 Mock，可切真实转发）
    sentiment_ai_base_url: str = "http://127.0.0.1:8100"
    sentiment_ai_mock: bool = True
    sentiment_ai_timeout: float = 1.5
    sentiment_ai_training_timeout: float = 8.0


settings = Settings()
