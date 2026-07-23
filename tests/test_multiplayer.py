"""Avatar 多人房间服务端单元测试。"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import pytest

from app.games.avatar_lobby.multiplayer import (
    MAX_PLAYERS_PER_ROOM,
    PROTOCOL_VERSION,
    PUBLIC_ROOM_ID,
    AvatarLobbyManager,
    PlayerConnection,
)
from app.games.avatar_lobby import skins


class FakeWebSocket:
    """最小 WebSocket 替身：记录发送与关闭。"""

    def __init__(self) -> None:
        self.sent: List[Dict[str, Any]] = []
        self.closed_with: Optional[int] = None
        self.client_state = type("S", (), {"name": "CONNECTED"})()
        # Starlette 用枚举比较；这里用简单属性模拟 CONNECTED。
        from starlette.websockets import WebSocketState

        self.client_state = WebSocketState.CONNECTED

    async def send_json(self, message: Dict[str, Any]) -> None:
        self.sent.append(message)

    async def close(self, code: int = 1000) -> None:
        from starlette.websockets import WebSocketState

        self.closed_with = code
        self.client_state = WebSocketState.DISCONNECTED


async def _drain(connection: PlayerConnection, timeout: float = 0.2) -> List[Dict[str, Any]]:
    await asyncio.sleep(0.05)
    ws = connection.websocket
    assert isinstance(ws, FakeWebSocket)
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.01)
    return list(ws.sent)


@pytest.fixture
def manager() -> AvatarLobbyManager:
    return AvatarLobbyManager()


@pytest.mark.asyncio
async def test_join_public_room(manager: AvatarLobbyManager) -> None:
    ws = FakeWebSocket()
    conn = PlayerConnection(ws, "u1", "Alice")
    room = await manager.join(conn, room_id=PUBLIC_ROOM_ID)
    assert room.room_id == PUBLIC_ROOM_ID
    assert room.is_public
    assert "u1" in room.players
    messages = await _drain(conn)
    assert any(m.get("type") == "room_joined" for m in messages)
    assert any(m.get("type") == "world_snapshot" for m in messages)
    await conn.close()


@pytest.mark.asyncio
async def test_create_and_join_private_room(manager: AvatarLobbyManager) -> None:
    host_ws = FakeWebSocket()
    host = PlayerConnection(host_ws, "host", "Host")
    room = await manager.join(host, create=True)
    assert room.room_id != PUBLIC_ROOM_ID
    assert not room.is_public

    guest_ws = FakeWebSocket()
    guest = PlayerConnection(guest_ws, "guest", "Guest")
    joined = await manager.join(guest, room_id=room.room_id)
    assert joined.room_id == room.room_id
    assert room.connected_count() == 2

    await host.close()
    await guest.close()


@pytest.mark.asyncio
async def test_room_capacity(manager: AvatarLobbyManager) -> None:
    room = await manager.create_private_room()
    connections = []
    for i in range(MAX_PLAYERS_PER_ROOM):
        ws = FakeWebSocket()
        conn = PlayerConnection(ws, f"u{i}", f"P{i}")
        await manager.join(conn, room_id=room.room_id)
        connections.append(conn)

    overflow_ws = FakeWebSocket()
    overflow = PlayerConnection(overflow_ws, "overflow", "X")
    with pytest.raises(ValueError, match="满"):
        await manager.join(overflow, room_id=room.room_id)

    for conn in connections:
        await conn.close()


@pytest.mark.asyncio
async def test_input_validation_and_ack(manager: AvatarLobbyManager) -> None:
    ws = FakeWebSocket()
    conn = PlayerConnection(ws, "u1", "Alice")
    room = await manager.join(conn, room_id=PUBLIC_ROOM_ID)
    player = room.players["u1"]

    await manager.handle_input(
        "u1",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "sequence": 3,
            "direction": 1,
            "jump": False,
            "kneel": False,
        },
    )
    assert player.ack_sequence == 3
    assert player.direction == 1

    await manager.handle_input(
        "u1",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "sequence": 2,
            "direction": -1,
        },
    )
    assert player.ack_sequence == 3
    assert player.direction == 1

    await manager.handle_input(
        "u1",
        {
            "protocolVersion": 1,
            "sequence": 10,
            "direction": -1,
        },
    )
    assert player.ack_sequence == 3

    await manager.handle_input(
        "u1",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "sequence": 4,
            "direction": 99,
        },
    )
    assert player.direction == 0
    await conn.close()


@pytest.mark.asyncio
async def test_input_idle_zeroed(manager: AvatarLobbyManager) -> None:
    ws = FakeWebSocket()
    conn = PlayerConnection(ws, "idle1", "Idle")
    room = await manager.join(conn, room_id=PUBLIC_ROOM_ID)
    player = room.players["idle1"]
    await manager.handle_input(
        "idle1",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "sequence": 1,
            "direction": 1,
            "jump": True,
            "kneel": False,
        },
    )
    assert player.direction == 1
    # 模拟长时间收不到输入帧（切后台/半开连接）。
    player.connection.last_input_at = 0.0
    player.vx = 100.0
    room.step_physics(1 / 30)
    assert player.direction == 0
    assert player.jump_held is False
    assert player.vx < 100.0
    await conn.close()


@pytest.mark.asyncio
async def test_uid_replace_connection(manager: AvatarLobbyManager) -> None:
    first_ws = FakeWebSocket()
    first = PlayerConnection(first_ws, "u1", "Alice")
    await manager.join(first, room_id=PUBLIC_ROOM_ID)

    second_ws = FakeWebSocket()
    second = PlayerConnection(second_ws, "u1", "Alice2")
    room = await manager.join(second, room_id=PUBLIC_ROOM_ID)
    assert room.players["u1"].connection is second
    assert first_ws.closed_with is not None
    await second.close()


@pytest.mark.asyncio
async def test_disconnect_grace_then_remove(manager: AvatarLobbyManager, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.games.avatar_lobby.multiplayer.DISCONNECT_GRACE_SECONDS",
        0.05,
    )
    ws = FakeWebSocket()
    conn = PlayerConnection(ws, "temp", "Temp")
    room = await manager.join(conn, create=True)
    room_id = room.room_id
    await manager.handle_disconnect(conn)
    assert "temp" in room.players
    assert room.players["temp"].connected is False
    await asyncio.sleep(0.15)
    assert room_id not in manager.rooms


@pytest.mark.asyncio
async def test_empty_private_room_destroyed(manager: AvatarLobbyManager) -> None:
    ws = FakeWebSocket()
    conn = PlayerConnection(ws, "solo", "Solo")
    room = await manager.join(conn, create=True)
    room_id = room.room_id
    await manager._remove_player(room, "solo", announce=False)
    assert room_id not in manager.rooms


@pytest.mark.asyncio
async def test_appearance_permission(tmp_path, monkeypatch, manager: AvatarLobbyManager) -> None:
    monkeypatch.setattr(skins, "SKINS_ROOT", tmp_path / "skins")
    monkeypatch.setattr(skins, "WORN_ROOT", tmp_path / "worn")
    (tmp_path / "skins").mkdir()
    (tmp_path / "worn").mkdir()

    png_a = b"\x89PNG\r\n\x1a\n" + b"AAAA"
    png_b = b"\x89PNG\r\n\x1a\n" + b"BBBB"
    own = skins.save_skin(
        data=png_a,
        skin_name="mine",
        uploader_id="owner",
        kind="plain",
        height_scale=1.1,
    )
    other = skins.save_skin(
        data=png_b,
        skin_name="theirs",
        uploader_id="other",
        kind="plain",
        height_scale=1.0,
    )

    assert skins.get_appearance_for_broadcast("owner", own["id"]) is not None
    assert skins.get_appearance_for_broadcast("owner", other["id"]) is None
    cleared = skins.get_appearance_for_broadcast("owner", None)
    assert cleared is not None
    assert cleared["skinId"] is None

    ws = FakeWebSocket()
    conn = PlayerConnection(ws, "owner", "Owner")
    room = await manager.join(conn, room_id=PUBLIC_ROOM_ID)
    await manager.handle_appearance("owner", {"skinId": own["id"]})
    assert room.players["owner"].appearance["skinId"] == own["id"]
    await conn.close()


@pytest.mark.asyncio
async def test_shared_snapshot_has_no_personal_fields(manager: AvatarLobbyManager) -> None:
    """快照应全房共享：无 ackSequence / you，player 条目也不带 ack。"""
    ws_a = FakeWebSocket()
    ws_b = FakeWebSocket()
    a = PlayerConnection(ws_a, "a", "A")
    b = PlayerConnection(ws_b, "b", "B")
    await manager.join(a, room_id=PUBLIC_ROOM_ID)
    await manager.join(b, room_id=PUBLIC_ROOM_ID)
    room = manager.rooms[PUBLIC_ROOM_ID]
    snap = room.world_snapshot()
    assert "ackSequence" not in snap
    assert "you" not in snap
    for player in snap["players"]:
        assert "ackSequence" not in player
    await room.broadcast_snapshot()
    await asyncio.sleep(0.05)
    snaps_a = [m for m in ws_a.sent if m.get("type") == "world_snapshot"]
    snaps_b = [m for m in ws_b.sent if m.get("type") == "world_snapshot"]
    assert snaps_a and snaps_b
    assert snaps_a[-1]["serverTick"] == snaps_b[-1]["serverTick"]
    await a.close()
    await b.close()
