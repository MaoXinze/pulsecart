"""角色默认首页配置（精简版）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user
from app.models.entities import SysUser
from app.schemas.response import Result

router = APIRouter(prefix="/sysRoleIndex", tags=["角色首页"])

_DEFAULT_INDEX = {
    "url": "/pulsecart/operations",
    "component": "sentiment/operations/index",
}


@router.get("/queryDefIndex")
def query_def_index(user: SysUser = Depends(get_current_user)):
    return Result.ok(_DEFAULT_INDEX)


@router.put("/updateDefIndex")
def update_def_index(
    url: str = Query(...),
    component: str = Query(...),
    isRoute: bool = Query(True),
    user: SysUser = Depends(get_current_user),
):
    _DEFAULT_INDEX["url"] = url
    _DEFAULT_INDEX["component"] = component
    return Result.ok(None, "设置成功")
