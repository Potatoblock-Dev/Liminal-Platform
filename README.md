# Liminal Platform（阈限月台）

2D 横版联机小游戏：列车车厢探索、皮套角色、持枪/库存、锅炉与卫兵炮塔等。挂在 [Potatoblock](https://game.potatoblock.com/) 网页体系里（登录、大厅入口、共用皮套），**不换引擎**（Canvas 2D + FastAPI）。

| | |
|--|--|
| 本仓（游戏源码真相） | [Potatoblock-Dev/Liminal-Platform](https://github.com/Potatoblock-Dev/Liminal-Platform) |
| 门户 / CD 对接仓 | [Potatoblock-Dev/Potatoblock-Game](https://github.com/Potatoblock-Dev/Potatoblock-Game)（只负责挂载与上线，**不要**在那里日常改玩法） |
| 本地入口 | [http://127.0.0.1:8100/](http://127.0.0.1:8100/) · 月台 [http://127.0.0.1:8100/liminal-platform](http://127.0.0.1:8100/liminal-platform) |

本地工作副本目录名可能仍是 `potatoblock-avatar-lobby/`，与本仓内容对应。

---

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_local.py
```

打开 [http://127.0.0.1:8100/](http://127.0.0.1:8100/)（大厅）或 [http://127.0.0.1:8100/liminal-platform](http://127.0.0.1:8100/liminal-platform)。

本地鉴权是 stub（`app/routers/auth.py`），固定测试身份，无需真实登录。生产鉴权只在主站 MCS 实例上。

---

## 仓库分工

```
改玩法 / 协议 / 资源  →  本仓 Liminal-Platform
挂登录、进大厅、CD 上线  →  Potatoblock-Game（vendor 本仓的 games 包）
```

| Token（本地 `potatogame/.env`） | 用途 |
|--|--|
| `LIMINAL_PLATFORM_GH_TOKEN` | 推送**本仓** |
| `GH_TOKEN` | 推送 Potatoblock-Game（上线用） |

推送到本仓：

```bash
python3 ~/.cursor/skills/potatoblock-deploy/scripts/push-liminal-platform.py \
  --message "feat: …"
```

挂到主站（经 Game CD → MCS，**不**直接打面板）：

```bash
python3 ~/.cursor/skills/potatoblock-deploy/scripts/push-github.py \
  --worktree …/potatogame/.deploy-worktree \
  --package …/potatogame/potatoblock-avatar-lobby \
  --message "deploy: vendor liminal"
```

Agent / 协作者约定见 Cursor skill **`liminal-platform-dev`**、**`potatoblock-deploy`**。

---

## 技术方向（摘要）

| 层 | 选择 |
|--|--|
| 客户端 | 现有 JS **逐步**迁 TypeScript（Vite 分模块：net / 世界 / 战斗 / 物品栏 / UI） |
| 服务端 | **继续** Python + FastAPI；房间 / 库存等权威逻辑可测、从 WS 处理里拆干净 |
| 渲染 | 先保持 Canvas 2D；逻辑稳了再谈表现层大改 |
| 不做 | 换 Godot/其它引擎；为月台另起一套生产后端语言或独立公网服 |

**改功能顺序：** 协议与消息类型 → 服务端权威 → 画面 / 操作。

细节见 [`docs/liminal-protocol.md`](docs/liminal-protocol.md)（月台 WS）；大厅皮套联机见 [`docs/networking-plan.md`](docs/networking-plan.md)。

**前端 TS（Phase 1）：** `client/src/` → `npm run build` → `app/games/liminal_platform/static/js/lp-network.js` / `lp-session.js`。

---

## 目录结构

```
Liminal-Platform/
├── run_local.py                 # 仅本地启动
├── requirements.txt
├── docs/
│   ├── liminal-protocol.md      # 月台 WS 协议（与大厅 avatar 协议分开）
│   ├── networking-plan.md       # 大厅联网权威
│   ├── skin-format.md           # 皮套格式
│   └── motion-references.md     # 动作参考
├── client/                      # TypeScript 源（Vite 构建进 static/js）
├── package.json                 # npm run build
├── game/Liminal_Platform/       # 开发镜像（与挂载包同步）
├── var/uploads/skins/           # 运行时上传（gitignore）
└── app/
    ├── main.py / routers/       # 仅本地 stub（不上 Potatoblock-Game）
    └── games/
        ├── avatar_lobby/        # 皮套大厅（vendor 进主站）
        ├── liminal_platform/    # 阈限月台挂载包（vendor 进主站）
        └── common/
```

`game/Liminal_Platform/` 与 `app/games/liminal_platform/` 应保持一致。改完一侧后：

```bash
rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' \
  game/Liminal_Platform/ app/games/liminal_platform/
# 或反向：app → game，视你以哪一侧为编辑源
```

**仅本地、不进主站包：** `run_local.py`、`app/main.py`、`app/routers/`、`app/static/`、`var/`。

---

## 文档

- [联网与权威模型](docs/networking-plan.md)
- [皮套格式](docs/skin-format.md)
- [动作参考](docs/motion-references.md)

---

## License / 素材

代码归属 Potatoblock-Dev。第三方素材（如 Kenney Mobile Controls）遵循其各自许可证（多为 CC0）；使用时保留原作者说明即可。
