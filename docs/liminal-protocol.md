# 阈限月台 WebSocket 协议

与 [`networking-plan.md`](networking-plan.md)（**Avatar 大厅**，`protocolVersion: 6`）**不是同一套**。

本文件描述 **Liminal Platform（阈限月台）** 联机消息。实现真相：

| 层 | 路径 |
|--|--|
| TypeScript | `client/src/protocol/messages.ts` |
| Python | `app/games/liminal_platform/protocol.py` |
| 服务端处理 | `multiplayer.py` / `routes.py` |
| 客户端会话 | `client/src/net/network.ts` → 构建为 `static/js/lp-network.js` |

**改字段顺序：** 先改本协议（TS + Python + 本文）→ 再改服务端权威 → 最后改画面/操作。

## 常量

| 名 | 值 |
|--|--|
| `PROTOCOL_VERSION` | `1` |
| `PUBLIC_ROOM_ID` | `"public"` |
| 姿态上报 | ~20Hz（客户端）；服务端限流约 30Hz |
| 世界快照 | ~15Hz |

端点：`ws(s)://host/liminal-platform/ws`

## 客户端 → 服务端

| `type` | 说明 |
|--|--|
| `join` / `create` | 进房 / 建房（带 `protocolVersion`） |
| `pose` | 姿态（含可选 `aimX`/`aimY`、`heldId`） |
| `train` | 油门/刹车 |
| `fuel_add` | 加燃料意图 |
| `fire` | 开火 |
| `inv` | 库存意图（`op` 等扩展字段） |
| `appearance` | 皮套 |
| `chat` | 聊天（≤40 字） |
| `ping` | 心跳（`t`） |

版本不匹配的输入由服务端忽略或拒绝。

## 服务端 → 客户端

| `type` | 说明 |
|--|--|
| `room_joined` / `room_error` / `room_removed` | 房间生命周期 |
| `world_snapshot` | 玩家姿态 + `world.train` / `world.fuel` |
| `player_join` / `player_leave` | `temporary` 表示断线宽限 |
| `appearance` / `chat` | 外观与聊天广播 |
| `fuel_changed` / `weapon_fired` | 燃料与远端弹道提示 |
| `inv_snapshot` / `inv_room` | 库存权威快照 |
| `pong` | 心跳应答 |

## 关闭码（常用）

| 码 | 含义 |
|--|--|
| 4002 | 同 UID 被顶替（客户端停止自动重连） |
| 4004 / 4005 / 4006 | 坏房码 / 满房 / 协议类错误（客户端回公共月台） |
| 4401 | 未登录 |

## 前端构建

```bash
cd potatoblock-avatar-lobby   # 或本仓根
npm install
npm run build                 # 写入 app/games/liminal_platform/static/js/lp-*.js
# 或一键发布前检查（协议对齐 + build + 镜像）
python3 scripts/prepare_liminal_release.py
```

`push-liminal-platform.py` / `push-github.py --package …/avatar-lobby` **会自动跑** `prepare_liminal_release.py`，防止忘构建或主站缺 `protocol.py`。

产物进 git（生产 CD 无 Node）。后续模块（inventory-net / combat / UI）同法迁入 `client/src/`。
