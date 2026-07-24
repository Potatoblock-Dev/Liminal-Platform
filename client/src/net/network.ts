/**
 * 阈限月台联机会话：姿态转发 + 共享列车/燃料/库存。
 * 构建为 IIFE → window.LiminalNetwork
 */

import {
  PROTOCOL_VERSION,
  POSE_RATE_HZ,
  PUBLIC_ROOM_ID,
  type ClientMessage,
  type ServerMessage,
} from '../protocol/messages';
import type { PlayerIdentity, LiminalNetworkApi } from '../globals';

const PING_MS = 5000;
const PONG_TIMEOUT_MS = 12000;
const MAX_BACKOFF_MS = 8000;

function wsUrl(): string {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const params = new URLSearchParams(location.search);
  const query = params.toString();
  return `${protocol}//${location.host}/liminal-platform/ws${query ? `?${query}` : ''}`;
}

function roomFromUrl(): string {
  const room = new URLSearchParams(location.search).get('room');
  return room && room.trim() ? room.trim().toUpperCase() : PUBLIC_ROOM_ID;
}

type PoseFrame = {
  sequence: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  facing: number;
  onGround: boolean;
  gait?: string;
  headLook?: number;
  heldId?: string | null;
  aimX?: number | null;
  aimY?: number | null;
  turretId?: 'left' | 'right' | null;
};

type FireDetail = {
  originX?: number;
  originY?: number;
  x?: number;
  y?: number;
  dirX: number;
  dirY: number;
  facing?: number;
  source?: string;
  turret?: boolean;
  turretId?: 'left' | 'right';
  handIndex?: number;
  weaponId?: string;
  shots?: Array<{ x: number; y: number; dirX: number; dirY: number }>;
  /** 武装车厢弹种 ap | t。 */
  ammoType?: string;
};

export class WebSocketSession extends EventTarget {
  mode = 'online';
  identity: PlayerIdentity | null = null;
  ws: WebSocket | null = null;
  roomId: string = PUBLIC_ROOM_ID;
  desiredRoomId: string | null = PUBLIC_ROOM_ID;
  createNext = false;
  connected = false;
  manualClose = false;
  reconnectAttempt = 0;
  reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  pingTimer: ReturnType<typeof setInterval> | null = null;
  lastPongAt = 0;
  playerCount = 0;
  maxPlayers = 10;
  isPublic = true;

  connect(identity: PlayerIdentity): void {
    this.identity = { ...identity };
    this.manualClose = false;
    this.desiredRoomId = roomFromUrl();
    this._open();
  }

  disconnect(): void {
    this.manualClose = true;
    this._clearTimers();
    if (this.ws) {
      try {
        this.ws.close(1000);
      } catch {
        /* ignore */
      }
      this.ws = null;
    }
    this.connected = false;
    this._emit('connectionchange', { status: 'offline' });
  }

  sendPose(frame: PoseFrame): void {
    const payload: ClientMessage = {
      type: 'pose',
      protocolVersion: PROTOCOL_VERSION,
      sequence: frame.sequence,
      x: frame.x,
      y: frame.y,
      vx: frame.vx,
      vy: frame.vy,
      facing: frame.facing,
      onGround: Boolean(frame.onGround),
      gait: frame.gait === 'run' ? 'run' : 'walk',
      headLook: Number(frame.headLook) || 0,
      heldId: frame.heldId || null,
    };
    if (frame.aimX != null && frame.aimY != null) {
      payload.aimX = frame.aimX;
      payload.aimY = frame.aimY;
    }
    if (frame.turretId === 'left' || frame.turretId === 'right') {
      payload.turretId = frame.turretId;
    }
    this._send(payload);
  }

  sendTrain(state: { throttle?: number; brake?: number }): void {
    const payload: ClientMessage = {
      type: 'train',
      protocolVersion: PROTOCOL_VERSION,
    };
    if (state.throttle != null) payload.throttle = state.throttle;
    if (state.brake != null) payload.brake = state.brake;
    this._send(payload);
  }

  sendFuelAdd(amount?: number, itemId?: string): void {
    this._send({
      type: 'fuel_add',
      protocolVersion: PROTOCOL_VERSION,
      amount: amount ?? undefined,
      itemId: itemId || 'coal',
    });
  }

  sendFire(detail: FireDetail): void {
    const payload: ClientMessage = {
      type: 'fire',
      protocolVersion: PROTOCOL_VERSION,
      x: detail.originX ?? detail.x ?? 0,
      y: detail.originY ?? detail.y ?? 0,
      dirX: detail.dirX,
      dirY: detail.dirY,
      facing: detail.facing,
      source: detail.source || (detail.turret ? 'turret' : undefined),
      handIndex: detail.handIndex,
      weaponId: detail.weaponId,
    };
    if (detail.turretId === 'left' || detail.turretId === 'right') {
      payload.turretId = detail.turretId;
    }
    if (Array.isArray(detail.shots) && detail.shots.length > 0) {
      payload.shots = detail.shots.map((shot) => ({
        x: shot.x,
        y: shot.y,
        dirX: shot.dirX,
        dirY: shot.dirY,
      }));
    }
    const ammo = String(detail.ammoType || '').trim().toLowerCase();
    if (ammo === 'ap' || ammo === 't') {
      payload.ammoType = ammo;
    }
    this._send(payload);
  }

  /** 发送库存意图（transfer / reload / crate 等）。 */
  sendInv(detail?: Record<string, unknown>): void {
    this._send({
      type: 'inv',
      protocolVersion: PROTOCOL_VERSION,
      ...(detail || {}),
    } as ClientMessage);
  }

  setAppearance(appearance?: { skinId?: string | null }): void {
    this._send({
      type: 'appearance',
      protocolVersion: PROTOCOL_VERSION,
      skinId: appearance?.skinId || null,
    });
  }

  sendChat(text: string): void {
    const cleaned = String(text || '')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 40);
    if (!cleaned) return;
    this._send({
      type: 'chat',
      protocolVersion: PROTOCOL_VERSION,
      text: cleaned,
    });
  }

  createRoom(): void {
    this.createNext = true;
    this.desiredRoomId = null;
    if (this.connected) {
      this._send({ type: 'create', protocolVersion: PROTOCOL_VERSION });
      this.createNext = false;
    } else {
      this._open();
    }
  }

  joinRoom(roomId?: string): void {
    this.createNext = false;
    this.desiredRoomId = (roomId || PUBLIC_ROOM_ID).toUpperCase();
    if (this.connected) {
      this._send({
        type: 'join',
        protocolVersion: PROTOCOL_VERSION,
        roomId: this.desiredRoomId,
      });
    } else {
      this._open();
    }
  }

  returnPublic(): void {
    this.joinRoom(PUBLIC_ROOM_ID);
  }

  /** 打开（或替换）WebSocket；替换时先摘掉旧 socket，避免 onclose 误排重连。 */
  _open(): void {
    this._clearTimers();
    this.manualClose = false;
    const prev = this.ws;
    this.ws = null;
    if (prev) {
      try {
        prev.close();
      } catch {
        /* ignore */
      }
    }
    // 自动重连统一用 reconnecting，避免 UI 在 connecting/offline 间闪烁。
    const status = this.reconnectAttempt > 0 ? 'reconnecting' : 'connecting';
    this._emit('connectionchange', { status });
    const socket = new WebSocket(wsUrl());
    this.ws = socket;

    socket.onopen = () => {
      if (this.ws !== socket) return;
      this.connected = true;
      this.reconnectAttempt = 0;
      this.lastPongAt = performance.now();
      this._emit('connectionchange', { status: 'online' });
      if (this.createNext) {
        this._send({ type: 'create', protocolVersion: PROTOCOL_VERSION });
        this.createNext = false;
      } else {
        this._send({
          type: 'join',
          protocolVersion: PROTOCOL_VERSION,
          roomId: this.desiredRoomId || PUBLIC_ROOM_ID,
        });
      }
      this.pingTimer = setInterval(() => this._ping(), PING_MS);
    };

    socket.onmessage = (event) => {
      if (this.ws !== socket) return;
      let payload: ServerMessage;
      try {
        payload = JSON.parse(String(event.data)) as ServerMessage;
      } catch {
        return;
      }
      this._handleMessage(payload);
    };

    socket.onclose = (event) => {
      if (this.ws !== socket) return;
      this.connected = false;
      this.ws = null;
      this._clearPing();
      if (event.code === 4002) {
        this.manualClose = true;
        this._emit('connectionchange', { status: 'replaced' });
        return;
      }
      if (event.code === 4004 || event.code === 4005 || event.code === 4006) {
        this.desiredRoomId = PUBLIC_ROOM_ID;
        this.createNext = false;
      }
      this._emit('connectionchange', { status: 'offline' });
      if (!this.manualClose) this._scheduleReconnect();
    };

    socket.onerror = () => {};
  }

  _handleMessage(payload: ServerMessage): void {
    const type = payload?.type;
    if (type === 'pong') {
      this.lastPongAt = performance.now();
      return;
    }
    if (type === 'room_joined') {
      this.roomId = payload.roomId;
      this.isPublic = Boolean(payload.isPublic);
      this.playerCount = payload.playerCount || 1;
      this.maxPlayers = payload.maxPlayers || 10;
      this.desiredRoomId = payload.roomId;
      this._syncUrlRoom(payload.roomId, payload.isPublic);
      this._emit('roomchange', payload);
      return;
    }
    if (type === 'room_error') {
      this.desiredRoomId = this.roomId || PUBLIC_ROOM_ID;
      this.createNext = false;
      this._emit('roomerror', payload);
      return;
    }
    if (type === 'room_removed') {
      this.desiredRoomId = PUBLIC_ROOM_ID;
      this.createNext = false;
      this._emit('roomerror', {
        message: payload.reason === 'joined_other_game' ? '已进入其他游戏' : '已离开房间',
      });
      return;
    }
    if (type === 'world_snapshot') {
      this.roomId = payload.roomId || this.roomId;
      this.isPublic = payload.isPublic ?? this.isPublic;
      this.playerCount = payload.playerCount || 0;
      this.maxPlayers = payload.maxPlayers || this.maxPlayers;
      this._emit('worldsnapshot', payload);
      return;
    }
    if (type === 'player_leave') {
      this.playerCount = payload.playerCount || this.playerCount;
      this._emit('playerleave', payload);
      return;
    }
    if (type === 'player_join') {
      this.playerCount = payload.playerCount || this.playerCount;
      this._emit('playerjoin', payload);
      return;
    }
    if (type === 'appearance') {
      this._emit('appearance', payload);
      return;
    }
    if (type === 'fuel_changed') {
      this._emit('fuelchanged', payload);
      return;
    }
    if (type === 'weapon_fired') {
      this._emit('weaponfired', payload);
      return;
    }
    if (type === 'inv_snapshot') {
      this._emit('invsnapshot', payload);
      return;
    }
    if (type === 'inv_room') {
      this._emit('invroom', payload);
      return;
    }
    if (type === 'chat') {
      this._emit('chat', payload);
    }
  }

  _ping(): void {
    if (!this.connected) return;
    if (performance.now() - this.lastPongAt > PONG_TIMEOUT_MS) {
      try {
        this.ws?.close();
      } catch {
        /* ignore */
      }
      return;
    }
    this._send({ type: 'ping', t: performance.now() });
  }

  _send(message: ClientMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify(message));
  }

  _scheduleReconnect(): void {
    this._clearReconnect();
    const delay = Math.min(MAX_BACKOFF_MS, 500 * 2 ** this.reconnectAttempt);
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => {
      if (!this.manualClose) this._open();
    }, delay);
  }

  _syncUrlRoom(roomId: string, isPublic: boolean): void {
    const url = new URL(location.href);
    if (isPublic || roomId === PUBLIC_ROOM_ID) {
      url.searchParams.delete('room');
    } else {
      url.searchParams.set('room', roomId);
    }
    history.replaceState(null, '', url);
  }

  _clearPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  _clearReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  _clearTimers(): void {
    this._clearPing();
    this._clearReconnect();
  }

  _emit(name: string, detail: unknown): void {
    this.dispatchEvent(new CustomEvent(name, { detail }));
  }
}

export function createSession(): WebSocketSession {
  return new WebSocketSession();
}

export function installLiminalNetwork(): void {
  window.LiminalNetwork = {
    PROTOCOL_VERSION,
    POSE_RATE_HZ,
    PUBLIC_ROOM_ID,
    createSession,
  } as LiminalNetworkApi;
}
