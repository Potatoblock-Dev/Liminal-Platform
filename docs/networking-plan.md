# Avatar 多人同屏协议

服务端权威、单 Uvicorn worker、进程内房间状态。客户端只发送输入与外观变更；服务端推进物理并广播世界快照。

## 权威模型（防卡顿 / 防闪现）

**服务端是位置真相**（他人看到的、房间状态、聊天/外观广播）。**本地画面用预测**，禁止每帧把本地坐标硬拽到快照——那是过去卡顿与人物闪现的主因。

| 对象 | 规则 |
|------|------|
| 远端玩家 | 只跟 `world_snapshot`；按 `serverTick` **自适应延迟**插值（约 2×快照间隔 + 0.35×RTT，钳制 100–280ms）；Hermite + 有限外推 |
| 本地玩家 | 本地积分移动；输入仍 20Hz 上报；**不**每帧硬校正 |
| 进房 / 换房 | 第一次见到自己的快照时硬对齐一次出生点 |
| 切后台 / 回前台 | 只清零输入，**不**硬拉本地坐标 |
| 大误差软校正 | 误差大时 blend；未确认输入堆积（领先服务端）时跳过软拉；极端误差才硬对齐；依据快照 `lastProcessedInput` |
| 时钟 | ping/pong 测 RTT；快照偏移用半 RTT 估计，低通平滑 |
| Avatar 内子项目 | 共享状态服务端权威；角色移动对齐本表，勿对本地每帧 snap |

```
本地输入 → 本地自绘（预测）→ WebSocketSession（20Hz input）
                              ↓
                     AvatarLobbyManager / AvatarRoom
                              ↓
                     30Hz 物理 · 15Hz world_snapshot（含 lastProcessedInput）
                              ↓
    自身：进房硬对齐 · ack 条件软校正 · 远端：RTT 自适应延迟 + Hermite
```

## 连接

- 端点：`ws(s)://host/avatar-lobby/ws`
- 鉴权：与站点一致的 WebSocket 身份（`get_current_identity_ws`），未登录关闭码 `4401`
- 协议版本：`6`（`protocolVersion` 字段，不匹配的输入忽略；严重错误可用关闭码 `4006`）

## 房间

| 类型 | roomId | 说明 |
|------|--------|------|
| 公共大厅 | `public` | 默认加入；始终存在 |
| 临时房间 | 6 位大写字母数字 | `create` 生成；空房自动销毁 |

- 每房最多 **10** 人；满员拒绝加入（消息 `room_error`，必要时关闭码 `4005`）
- 同 UID 新连接替换旧连接（关闭码 `4002`）
- 断线保留 **30 秒**（`temporary` leave）；超时后永久移除并广播 `player_leave`
- 邀请链接：`/avatar-lobby?room=ROOMID`

## 客户端 → 服务端

### `join` / `create`

```json
{ "type": "join", "protocolVersion": 6, "roomId": "public" }
{ "type": "create", "protocolVersion": 6 }
```

### `input`（20Hz）

```json
{
  "protocolVersion": 6,
  "type": "input",
  "sequence": 42,
  "direction": -1,
  "jump": false,
  "kneel": true
}
```

- `direction`：仅 `-1` / `0` / `1`；跪地时服务端禁止位移与起跳
- 不接受客户端坐标；消息体上限 4KB；输入约 30Hz 限流
- `sequence` 仅服务端用于丢弃乱序旧包，不下发 ack
- 超过 0.6s 未收到输入帧（切后台、半开连接）时服务端清零持续输入，防止角色沿旧方向跑飞

### `appearance`

```json
{ "type": "appearance", "protocolVersion": 6, "skinId": "abc123" }
```

仅系统皮套或本人皮套可广播；`skinId` 为空表示彩色占位。

### `ping`

```json
{ "type": "ping", "t": 12345.67 }
```

## 服务端 → 客户端

### `room_joined`

```json
{
  "type": "room_joined",
  "protocolVersion": 6,
  "roomId": "public",
  "isPublic": true,
  "playerCount": 2,
  "maxPlayers": 10,
  "you": "user-id"
}
```

### `world_snapshot`（约 15Hz，全房共享同一份；客户端用 `serverTick / 30` 秒作为插值时间轴）

```json
{
  "type": "world_snapshot",
  "protocolVersion": 6,
  "serverTick": 1200,
  "roomId": "public",
  "isPublic": true,
  "playerCount": 2,
  "maxPlayers": 10,
  "players": [
    {
      "id": "user-id",
      "nickname": "土豆",
      "nx": 0.5,
      "y": 0,
      "vx": 0,
      "vy": 0,
      "facing": 1,
      "onGround": true,
      "kneel": 0,
      "lastProcessedInput": 42,
      "appearance": {
        "skinId": "abc",
        "kind": "uv",
        "heightScale": 1.16,
        "contentHash": "…"
      },
      "connected": true
    }
  ]
}
```

- `nx`：归一化横坐标 `0..1`（已扣角色边距）；客户端映射到本地世界宽
- `y`：相对地面的逻辑像素，地面为 `0`，腾空为负；客户端 `groundY + y`
- `lastProcessedInput`：该玩家服务端已处理的最新 `input.sequence`；本地软校正用
- 本地玩家：见上文「权威模型」；禁止每帧硬校正；进房硬对齐 + ack 条件软校正
- `connected: false` 表示断线 grace 中；客户端应保留该远端，勿当永久离场删除

### `player_join` / `player_leave`

```json
{ "type": "player_join", "protocolVersion": 6, "roomId": "public", "playerId": "…", "playerCount": 3 }
{ "type": "player_leave", "protocolVersion": 6, "roomId": "public", "playerId": "…", "temporary": true, "playerCount": 2 }
```

### `appearance`

```json
{ "type": "appearance", "protocolVersion": 6, "roomId": "public", "playerId": "…", "appearance": { … } }
```

### 关闭码

| 码 | 含义 |
|----|------|
| 4002 | 同 UID 被新连接顶替；客户端应停止自动重连 |
| 4005 | 房间已满 |
| 4006 | 协议错误 |
| 4401 | 未登录（HTTP 路由用；WS 鉴权失败也可能用 4001） |

客户端收到 `4002` 后应展示「已在其他窗口打开」且不再自动重连；用户主动创建/加入房间时可重新开连。

## 参考（成熟联机模式）

实现对照下列公开资料，而非整包换中间件：

- [Gabriel Gambetta — Fast-Paced Multiplayer](https://www.gabrielgambetta.com/client-server-game-architecture.html)（预测 / 和解 / 插值）
- [Gaffer on Games — Networking](https://gafferongames.com/)（固定 tick、插值与外推）
- [Valve — Source Multiplayer Networking](https://developer.valvesoftware.com/wiki/Source_Multiplayer_Networking)（实体插值延迟、客户端预测）
