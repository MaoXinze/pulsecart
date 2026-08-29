"""第三方登录 API（兼容 JeecgBoot Vue3 前端）。"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.third_login_cache import pop_value, set_value
from app.core.config import settings
from app.db.session import get_db
from app.schemas.response import Result
from app.services.third_login_service import (
    bind_third_phone,
    build_oauth2_redirect_url,
    get_corp_id_client_id,
    get_login_user,
    handle_oauth_callback,
    issue_login_token,
    oauth2_complete_login,
)
from app.services.third_oauth_providers import (
    SUPPORTED_RENDER_SOURCES,
    build_authorize_url,
    build_oauth2_login_url,
    create_oauth_state,
)

router = APIRouter(tags=["第三方登录"])


def _enabled_third_sources() -> list[str]:
    """Expose only OAuth providers that have all credentials needed to finish login."""
    configured = (
        ("github", settings.github_client_id and settings.github_client_secret),
        ("wechat_open", settings.wechat_open_client_id and settings.wechat_open_client_secret),
        ("dingtalk", settings.dingtalk_client_id and settings.dingtalk_client_secret),
        (
            "wechat_enterprise",
            settings.wechat_enterprise_corp_id and settings.wechat_enterprise_secret,
        ),
    )
    return [source for source, is_configured in configured if is_configured]


@router.get("/thirdLogin/config")
def third_login_config():
    """Let the login page degrade quietly when no external identity provider is configured."""
    return Result.ok({"enabledSources": _enabled_third_sources()})


def _callback_html(payload: Any) -> HTMLResponse:
    data = json.dumps(payload, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>第三方登录</title></head>
<body><script>
(function() {{
  var payload = {data};
  if (window.opener) {{
    window.opener.postMessage(payload, "*");
    window.close();
  }} else {{
    document.body.innerText = typeof payload === "string" ? payload : JSON.stringify(payload);
  }}
}})();
</script></body></html>"""
    return HTMLResponse(content=html)


@router.get("/thirdLogin/render/{source}")
def render_third_login(source: str):
    if source not in SUPPORTED_RENDER_SOURCES:
        return Result.error(f"不支持的第三方登录: {source}")
    try:
        state = create_oauth_state()
        set_value(f"oauth_state:{state}", source)
        url = build_authorize_url(source, state)
        return RedirectResponse(url=url, status_code=302)
    except ValueError as exc:
        return Result.error(str(exc))


@router.get("/thirdLogin/{source}/callback", response_class=HTMLResponse)
async def third_login_callback(
    source: str,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    tenant_id: int = Query(0, alias="tenantId"),
    db: Session = Depends(get_db),
):
    if not code:
        return _callback_html("登录失败")
    if state and pop_value(f"oauth_state:{state}") is None and state not in ("", "null"):
        pass
    try:
        payload = await handle_oauth_callback(db, source, code, tenant_id=tenant_id)
        return _callback_html(payload)
    except Exception:
        return _callback_html("登录失败")


@router.get("/thirdLogin/getLoginUser/{token}/{third_type}/{tenant_id}")
def get_third_login_user(
    token: str,
    third_type: str,
    tenant_id: int,
    db: Session = Depends(get_db),
):
    try:
        data = get_login_user(db, token, third_type, tenant_id)
        return Result.ok(data, "登录成功")
    except ValueError as exc:
        return Result.error(str(exc), 401)


@router.post("/thirdLogin/bindingThirdPhone")
def binding_third_phone(
    body: dict,
    db: Session = Depends(get_db),
):
    mobile = body.get("mobile") or body.get("phone")
    captcha = body.get("captcha")
    third_user_uuid = body.get("thirdUserUuid") or body.get("third_user_uuid")
    tenant_id = int(body.get("tenantId") or 0)
    try:
        token = bind_third_phone(db, mobile, captcha, third_user_uuid, tenant_id)
        return Result.ok(token)
    except ValueError as exc:
        return Result.error(str(exc))


@router.get("/thirdLogin/oauth2/{source}/login")
def oauth2_login(
    source: str,
    state: str = Query(""),
    tenant_id: int = Query(0, alias="tenantId"),
):
    try:
        oauth_state = create_oauth_state()
        set_value(f"oauth2_state:{oauth_state}", {"source": source, "state": state, "tenant_id": tenant_id})
        base = settings.third_login_base_url.rstrip("/")
        url = build_oauth2_login_url(source, oauth_state, base, tenant_id)
        return RedirectResponse(url=url, status_code=302)
    except ValueError as exc:
        return Result.error(str(exc))


@router.get("/thirdLogin/oauth2/{source}/callback")
async def oauth2_callback(
    source: str,
    code: Optional[str] = Query(None),
    auth_code: Optional[str] = Query(None, alias="authCode"),
    state: str = Query(""),
    tenant_id: int = Query(0, alias="tenantId"),
    db: Session = Depends(get_db),
):
    oauth_code = code or auth_code
    if not oauth_code:
        return "登录失败"
    try:
        user = await oauth2_complete_login(db, source, oauth_code, tenant_id=tenant_id)
        token = issue_login_token(user)
        redirect_url = build_oauth2_redirect_url(state, token, str(tenant_id), source)
        return RedirectResponse(url=redirect_url, status_code=302)
    except Exception:
        return "登录失败"


@router.get("/thirdLogin/oauth2/dingding/login")
async def oauth2_dingding_login(
    auth_code: str = Query(..., alias="authCode"),
    state: str = Query(""),
    tenant_id: int = Query(0, alias="tenantId"),
    db: Session = Depends(get_db),
):
    try:
        user = await oauth2_complete_login(db, "dingtalk", auth_code, tenant_id=tenant_id)
        token = issue_login_token(user)
        redirect_url = build_oauth2_redirect_url(state, token, str(tenant_id), "dingtalk")
        return RedirectResponse(url=redirect_url, status_code=302)
    except Exception:
        return "登录失败"


@router.get("/thirdLogin/get/corpId/clientId")
def corp_id_client_id(tenant_id: int = Query(0, alias="tenantId"), db: Session = Depends(get_db)):
    data = get_corp_id_client_id(db, tenant_id)
    if not data:
        return Result.error("还未配置钉钉应用，请配置钉钉应用")
    return Result.ok(data)
