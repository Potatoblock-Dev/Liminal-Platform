# 虚拟形象大厅（potatoblock-avatar-lobby）

类似虚拟形象大厅的玩法：用户上传符合格式的「皮套」贴图，皮套人可以在 2D 横版场景里做简单移动（左右走、跳跃、单膝跪地）。

**当前只在本地实验，暂不上传 MCS / game.potatoblock.com。** 源码可推到独立仓 [Liminal-Platform](https://github.com/Potatoblock-Dev/Liminal-Platform)（`LIMINAL_PLATFORM_GH_TOKEN` + `push-liminal-platform.py`）。目录结构沿用 potatoblock 系列（`app/games/<游戏包>/`）；若以后要挂到主站，只上传 `app/games/avatar_lobby/` / `liminal_platform/`。

## 本地运行

```bash
pip install -r requirements.txt
python run_local.py
# 打开 http://127.0.0.1:8100/
```

本地不需要登录：`app/routers/auth.py` 是开发用 stub，固定返回一个测试身份。

## 目录结构

```
potatoblock-avatar-lobby/
├── run_local.py                  # 本地启动入口（仅本地）
├── requirements.txt
├── docs/
│   ├── skin-format.md            # 皮套格式草案，格式定稿前以此为准
│   ├── motion-references.md       # 程序化动作算法与开源参考
│   └── networking-plan.md        # 联网权威模型、消息契约与扩展顺序
├── var/uploads/skins/            # 用户上传的皮套（gitignore，不进版本库）
├── game/                         # 独立小游戏项目目录（与 app/games 挂载包对应）
│   └── Liminal_Platform/         # 阈限月台 — 从大厅入口 /liminal-platform 进入
└── app/
    ├── main.py                   # 本地 FastAPI 入口（仅本地）
    ├── routers/auth.py           # 本地鉴权 stub（仅本地，模拟远程接口）
    ├── static/css/site.css       # 本地最小站点样式
    └── games/
        ├── __init__.py           # 游戏包注册器（与远程实例一致）
        ├── avatar_lobby/         # ★ Avatar 虚拟形象大厅
        │   ├── routes.py         # 页面 + 皮套上传/列出/取贴图接口
        │   ├── skins.py          # 皮套文件管理（校验、落盘、读取）
        │   ├── templates/index.html
        │   └── static/
        │       ├── css/avatar-lobby.css
        │       └── js/
        │           ├── avatar-lobby.js   # 2D 横版移动 + 皮套选择/渲染
        │           ├── world-objects.js  # 大厅可交互入口（阈限月台等）
        │           └── …
        └── liminal_platform/     # 阈限月台挂载包（资源在 game/Liminal_Platform/）
            ├── routes.py         # 加载 game/Liminal_Platform/routes.py
            └── __init__.py
```

## 仅本地的文件（部署时不上传）

- `run_local.py`、`app/main.py`、`app/routers/auth.py`、`app/static/`
- `var/`（本地上传数据）

## 后续计划

- 皮套格式定稿（多贴图 / 动画帧，见 docs/skin-format.md 的扩展方向）
- 房间 + WebSocket 多人同步（可复用 draw_guess 的 lobby 模式）
- 更接近潜幽症的行动方式（蹲、冲刺等）
