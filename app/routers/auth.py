"""本地开发用鉴权 stub —— 仅本地实验，禁止上传到远程实例。

远程实例已有真正的 app/routers/auth.py（登录、JWT 等）。
本模块只模拟其接口签名，让游戏包在本地跑起来时不需要登录。

本地多人测试可通过查询参数 ?dev_user=xxx 切换身份（仅 stub）。
"""

from fastapi import Request, WebSocket

DEV_USER_ID = "dev-local"
DEV_NICKNAME = "本地测试员"


def _identity_from_query(query) -> tuple[str, str]:
    """从 query 读取可选的本地测试身份。"""
    user_id = query.get("dev_user") or DEV_USER_ID
    nickname = query.get("dev_name") or (
        DEV_NICKNAME if user_id == DEV_USER_ID else f"测试员-{user_id}"
    )
    return str(user_id), str(nickname)


async def get_optional_identity(request: Request):
    """本地返回开发者身份；可用 ?dev_user= 模拟多用户。"""
    return _identity_from_query(request.query_params)


async def get_current_identity_ws(websocket: WebSocket):
    """本地 WebSocket 鉴权 stub；支持 ?dev_user= 多标签测试。"""
    return _identity_from_query(websocket.query_params)


async def get_passport_nickname(user_id) -> str:
    """本地 stub：模拟远程通行证昵称查询，直接返回开发昵称。"""
    if str(user_id) == DEV_USER_ID:
        return DEV_NICKNAME
    return f"测试员-{user_id}"
