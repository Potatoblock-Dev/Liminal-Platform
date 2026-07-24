# 阈限月台（Liminal Platform）

2D 横版 **联机** 小游戏：在一列可重组的列车上探索、协作、战斗与自动化。角色使用 Potatoblock **共用皮套**，挂在 [主站](https://game.potatoblock.com/) 网页体系里（登录、大厅入口、CD 上线）。

| | |
|--|--|
| 游玩（生产） | [game.potatoblock.com](https://game.potatoblock.com/) → 阈限月台 |
| 本仓 | 玩法 / 协议 / 资源的 **source of truth** |
| 门户对接 | [Potatoblock-Game](https://github.com/Potatoblock-Dev/Potatoblock-Game)（只 vendor 挂载，**不要**在那里日常改玩法） |

本地目录名可能仍是 `potatoblock-avatar-lobby/`，内容与本仓对应。

---

## 玩法

你在 **月台 / 列车** 世界里以皮套角色移动：走过道、跨车厢、捡放物资、与他人同房联机。

### 车厢（可拼接）

| 车厢 | 作用概要 |
|------|----------|
| **动力车厢** | 锅炉与燃料；影响列车驱动 |
| **仓储车厢** | 物资存放与搬运 |
| **卫兵防御车厢** | 双联炮塔、弹药箱；可入座射击 |
| **绘轨车厢** | 探测 / 视野类能力（与自动化传感器配合） |
| **枢机车厢** | 全屏控制台：为各节车厢编写自动化规则 |

列车可挂多节同类或不同类车厢；小地图 / 列车图用于定位。

### 核心循环

- **移动与交互**：行走、攀爬/过道、靠近设备按交互键（锅炉、炮塔座位、仓储、枢机控制台等）。
- **库存与双手**：地面掉落、背包、双手持物；弹药、煤炭、废料、炮塔弹等可搬运与装填。
- **战斗**：手持武器射击；卫兵车厢可入座操作炮塔（人数少时可一人控双塔）。
- **列车驾驶**：油门 / 刹车、燃料消耗；汽笛等反馈。
- **自动化（枢机）**：在控制台为指定车厢写「条件 → 行为」规则（持续判定有优先级；瞬时触发为边沿）。详见 [`docs/liminal-auto-program.md`](docs/liminal-auto-program.md)。

### 联机

公共月台或房间码进房；姿态、外观、聊天、开火、库存与世界快照由服务端权威同步。协议说明见 [`docs/liminal-protocol.md`](docs/liminal-protocol.md)（**与**皮套大厅的 avatar 协议**不是同一套**）。

---

## 技术

不换引擎、不另起一套生产服：仍挂在 Potatoblock **同一实例** 上。

| 层 | 选择 |
|--|--|
| 渲染 / 客户端 | **Canvas 2D**；现有 JS **逐步**迁 TypeScript（Vite：`client/src/` → `static/js/lp-*.js`） |
| 服务端 | **Python + FastAPI**；WebSocket 房间；库存 / 世界等权威逻辑可测、从 WS 处理拆出 |
| 改动顺序 | **协议（TS + Python + 文档）→ 服务端权威 → 画面 / 操作** |
| 不做 | 换 Godot 等引擎；为月台单独换 Node/Go/Rust 公网服；用 submodule 当 CD 主路径 |

前端 Phase 1 已迁网络会话：`client/src/` → `npm run build` → `lp-network.js` / `lp-session.js`。发布前脚本会校验协议版本并对齐镜像：

```bash
python3 scripts/prepare_liminal_release.py
```

`push-liminal-platform.py` / 主站 `push-github.py --package …/avatar-lobby` 会自动跑上述准备，避免忘构建。

---

## 仓库分工

```
改玩法 / 协议 / 资源     →  本仓 Liminal-Platform
登录、大厅入口、MCS CD   →  Potatoblock-Game（push 时 vendor 本仓 games 包）
```

| Token（本地 `potatogame/.env`） | 用途 |
|--|--|
| `LIMINAL_PLATFORM_GH_TOKEN` | 推送 **本仓** |
| `GH_TOKEN` | 推送 Potatoblock-Game（上线） |

```bash
# 只更新本仓
python3 ~/.cursor/skills/potatoblock-deploy/scripts/push-liminal-platform.py \
  --message "feat: …"

# 上主站（经 Game CD → MCS）
python3 ~/.cursor/skills/potatoblock-deploy/scripts/push-github.py \
  --worktree …/potatogame/.deploy-worktree \
  --package …/potatogame/potatoblock-avatar-lobby \
  --message "deploy: vendor liminal"
```

约定：Cursor skill **`liminal-platform-dev`**、**`potatoblock-deploy`**；挂载包内见 `SOURCE.md`。

---

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_local.py
```

- 大厅：[http://127.0.0.1:8100/](http://127.0.0.1:8100/)
- 月台：[http://127.0.0.1:8100/liminal-platform](http://127.0.0.1:8100/liminal-platform)

本地鉴权为 stub（固定测试身份）。生产鉴权只在主站实例。

改 TS 客户端时：`npm install && npm run build`（或依赖推送脚本里的 prepare）。

---

## 目录结构

```
Liminal-Platform/
├── run_local.py              # 仅本地启动
├── requirements.txt
├── package.json / client/    # TS 源 → Vite 构建进 static/js
├── docs/
│   ├── liminal-protocol.md   # 月台 WS 协议
│   ├── liminal-auto-program.md
│   ├── networking-plan.md    # 皮套大厅联网（旁路，非月台协议）
│   ├── skin-format.md
│   └── motion-references.md
├── scripts/prepare_liminal_release.py
├── game/Liminal_Platform/    # 开发镜像（与挂载包同步）
└── app/
    ├── main.py / routers/    # 仅本地 stub（不上 Game 仓）
    └── games/
        ├── liminal_platform/ # 月台挂载包（主站 vendor 目标）
        ├── avatar_lobby/     # 皮套大厅（同包 vendor）
        └── common/
```

`game/Liminal_Platform/` 与 `app/games/liminal_platform/` 应一致。一侧改完后用 `rsync` 或 prepare 脚本对齐。

**仅本地、不进主站包：** `run_local.py`、`app/main.py`、`app/routers/`、`app/static/`、`var/`、音频 `static/audio/.work/` 等中间产物。

---

## 文档

- [月台 WebSocket 协议](docs/liminal-protocol.md)
- [枢机自动化编程](docs/liminal-auto-program.md)
- [皮套大厅联网权威](docs/networking-plan.md)（大厅，非月台协议）
- [皮套格式](docs/skin-format.md)
- [动作参考](docs/motion-references.md)

---

## License / 素材

代码归属 Potatoblock-Dev。第三方素材（Kenney Mobile Controls、Kenney Game Icons、Kenney Input Prompts Pixel 等）遵循其各自许可证（多为 CC0）；使用时保留原作者说明即可。图标目录见 `app/games/liminal_platform/static/img/ui/`。
