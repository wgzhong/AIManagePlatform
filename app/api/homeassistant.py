"""
Home Assistant 代理 API — 解决浏览器 CORS 跨域问题
通过后端转发请求到 Home Assistant 实例。
"""

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/ha", tags=["homeassistant"])


class HAConfigSave(BaseModel):
    """保存 HA 配置"""
    url: str
    token: str


class HAServiceCall(BaseModel):
    """调用 HA 服务"""
    entity_id: str
    # 额外参数，如 brightness 等
    extra: dict | None = None


# ── 内存存储（生产环境应改为数据库）── #
_ha_config = {
    "url": "",
    "token": ""
}


@router.get("/config")
async def get_ha_config(request: Request):
    """获取已保存的 HA 配置（脱敏）"""
    return {
        "url": _ha_config["url"],
        "has_token": bool(_ha_config["token"]),
        "token_masked": (_ha_config["token"][:8] + "..." + _ha_config["token"][-4:]) if len(_ha_config["token"]) > 12 else ("****" if _ha_config["token"] else "")
    }


@router.post("/config")
async def save_ha_config(body: HAConfigSave):
    """保存 HA 连接配置（懒验证：加载设备时才校验 token 有效性）"""
    global _ha_config
    url = body.url.rstrip("/")
    token = body.token

    # 仅做基本的可达性检查（不验证 token，token 在 loadDevices 时校验）
    if not url:
        raise HTTPException(status_code=400, detail="请输入 Home Assistant 地址")
    if not token:
        raise HTTPException(status_code=400, detail="请输入访问令牌")

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                f"{url}/",
                headers={"Authorization": f"Bearer {token}"},
                follow_redirects=True,
            )
            # 只要能连上就放行，不严格判断 HTTP 状态码
            # token 有效性在 GET /states 时再校验
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="连接超时，请检查地址是否正确")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="无法连接，请检查地址和端口")

    _ha_config["url"] = url
    _ha_config["token"] = token
    return {"success": True, "message": "连接配置已保存"}


@router.get("/states")
async def ha_get_states():
    """获取所有 HA 实体状态（代理）"""
    if not _ha_config["url"] or not _ha_config["token"]:
        raise HTTPException(status_code=400, detail="未配置 Home Assistant 连接")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{_ha_config['url']}/api/states",
                headers={"Authorization": f"Bearer {_ha_config['token']}", "Content-Type": "application/json"},
            )
            if r.status_code == 401:
                raise HTTPException(status_code=401, detail="HA Token 无效或已过期")
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=f"HA API 错误: {r.status_code}")
            return r.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="请求超时")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="无法连接到 Home Assistant")


@router.get("/states/{entity_id:path}")
async def ha_get_state(entity_id: str):
    """获取单个实体状态"""
    if not _ha_config["url"] or not _ha_config["token"]:
        raise HTTPException(status_code=400, detail="未配置 Home Assistant 连接")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{_ha_config['url']}/api/states/{entity_id}",
                headers={"Authorization": f"Bearer {_ha_config['token']}", "Content-Type": "application/json"},
            )
            if r.status_code == 401:
                raise HTTPException(status_code=401, detail="HA Token 无效或已过期")
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=f"HA API 错误: {r.status_code}")
            return r.json()
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/service/{domain}/{service}")
async def ha_call_service(domain: str, service: str, body: HAServiceCall):
    """调用 HA 服务（开关灯、调节亮度等）"""
    if not _ha_config["url"] or not _ha_config["token"]:
        raise HTTPException(status_code=400, detail="未配置 Home Assistant 连接")

    payload = {"entity_id": body.entity_id}
    if body.extra:
        payload.update(body.extra)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{_ha_config['url']}/api/services/{domain}/{service}",
                headers={"Authorization": f"Bearer {_ha_config['token']}", "Content-Type": "application/json"},
                json=payload,
            )
            if r.status_code == 401:
                raise HTTPException(status_code=401, detail="HA Token 无效或已过期")
            if r.status_code not in (200, 201, 202):
                raise HTTPException(status_code=r.status_code, detail=f"服务调用失败: {r.text}")
            return {"success": True, "message": "命令已发送"}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="请求超时")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="无法连接到 Home Assistant")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def ha_health_check():
    """检查 HA 连接状态"""
    if not _ha_config["url"] or not _ha_config["token"]:
        return {"connected": False, "message": "未配置"}

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{_ha_config['url']}/api/states",
                headers={"Authorization": f"Bearer {_ha_config['token']}"},
            )
            if r.status_code == 200:
                return {"connected": True, "message": "已连接"}
            elif r.status_code in (401, 403):
                return {"connected": False, "message": "Token 无效或已过期"}
            return {"connected": False, "message": f"HA 返回 {r.status_code}"}
    except Exception as e:
        return {"connected": False, "message": f"连接失败: {str(e)[:50]}"}
