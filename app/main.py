"""本地实验入口 —— 仅本地使用，禁止上传到远程实例。

远程实例已有自己的应用入口；部署时只上传 app/games/avatar_lobby/ 游戏包。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.games import register_routers

app = FastAPI(title="虚拟形象大厅（本地实验）")

# 先注册更具体的游戏静态路径，避免被通用 /static 挂载提前截获。
register_routers(app)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
    name="static",
)


@app.get("/")
async def index():
    """本地只有一个游戏，根路径直接跳过去。"""
    return RedirectResponse(url="/avatar-lobby")
