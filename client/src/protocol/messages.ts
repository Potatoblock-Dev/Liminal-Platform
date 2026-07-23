/**
 * 阈限月台 WebSocket 协议（与大厅 avatar PROTOCOL_VERSION=6 不是同一套）。
 * 改字段时同步：本文件、app/games/liminal_platform/protocol.py、docs/liminal-protocol.md
 */

export const PROTOCOL_VERSION = 1 as const;
export const PUBLIC_ROOM_ID = 'public' as const;
export const POSE_RATE_HZ = 20 as const;

export type Gait = 'walk' | 'run';

/** 客户端 → 服务端 */
export type ClientMessage =
  | {
      type: 'join';
      protocolVersion: typeof PROTOCOL_VERSION;
      roomId: string;
    }
  | {
      type: 'create';
      protocolVersion: typeof PROTOCOL_VERSION;
    }
  | {
      type: 'pose';
      protocolVersion: typeof PROTOCOL_VERSION;
      sequence: number;
      x: number;
      y: number;
      vx: number;
      vy: number;
      facing: number;
      onGround: boolean;
      gait: Gait;
      headLook: number;
      heldId: string | null;
      aimX?: number;
      aimY?: number;
    }
  | {
      type: 'train';
      protocolVersion: typeof PROTOCOL_VERSION;
      throttle?: number;
      brake?: number;
    }
  | {
      type: 'fuel_add';
      protocolVersion: typeof PROTOCOL_VERSION;
      amount?: number;
      itemId: string;
    }
  | {
      type: 'fire';
      protocolVersion: typeof PROTOCOL_VERSION;
      x: number;
      y: number;
      dirX: number;
      dirY: number;
      facing?: number;
      source?: string;
      handIndex?: number;
      weaponId?: string;
    }
  | ({
      type: 'inv';
      protocolVersion: typeof PROTOCOL_VERSION;
      op?: string;
      [key: string]: unknown;
    })
  | {
      type: 'appearance';
      protocolVersion: typeof PROTOCOL_VERSION;
      skinId: string | null;
    }
  | {
      type: 'chat';
      protocolVersion: typeof PROTOCOL_VERSION;
      text: string;
    }
  | {
      type: 'ping';
      t: number;
    };

export type AppearancePayload = {
  skinId?: string | null;
  kind?: string;
  heightScale?: number;
  contentHash?: string;
  [key: string]: unknown;
};

export type SnapshotPlayer = {
  id: string;
  nickname: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  facing: number;
  onGround: boolean;
  gait: Gait;
  headLook: number;
  appearance?: AppearancePayload;
  connected: boolean;
  heldId?: string | null;
  aimX?: number;
  aimY?: number;
};

export type WorldTrain = {
  throttle: number;
  brake: number;
  speed: number;
  emergencyActive?: boolean;
};

export type WorldFuel = {
  level: number;
};

/** 服务端 → 客户端 */
export type ServerMessage =
  | {
      type: 'pong';
      t?: number;
    }
  | {
      type: 'room_joined';
      protocolVersion: number;
      roomId: string;
      isPublic: boolean;
      playerCount: number;
      maxPlayers: number;
      you?: string;
      [key: string]: unknown;
    }
  | {
      type: 'room_error';
      protocolVersion?: number;
      message?: string;
      [key: string]: unknown;
    }
  | {
      type: 'room_removed';
      reason?: string;
    }
  | {
      type: 'world_snapshot';
      protocolVersion: number;
      serverTick: number;
      serverTimeMs: number;
      roomId: string;
      isPublic: boolean;
      playerCount: number;
      maxPlayers: number;
      players: SnapshotPlayer[];
      world?: {
        train?: WorldTrain;
        fuel?: WorldFuel;
      };
    }
  | {
      type: 'player_join';
      protocolVersion: number;
      roomId?: string;
      playerId: string;
      playerCount?: number;
    }
  | {
      type: 'player_leave';
      protocolVersion: number;
      roomId?: string;
      playerId: string;
      temporary?: boolean;
      playerCount?: number;
    }
  | {
      type: 'appearance';
      protocolVersion: number;
      playerId: string;
      appearance?: AppearancePayload;
      roomId?: string;
    }
  | {
      type: 'fuel_changed';
      protocolVersion: number;
      level: number;
      [key: string]: unknown;
    }
  | {
      type: 'weapon_fired';
      protocolVersion: number;
      playerId: string;
      x: number;
      y: number;
      dirX: number;
      dirY: number;
      facing?: number;
      weaponId?: string;
      style?: string;
      [key: string]: unknown;
    }
  | {
      type: 'inv_snapshot';
      protocolVersion: number;
      roomId: string;
      personal: unknown;
      room: unknown;
    }
  | {
      type: 'inv_room';
      protocolVersion: number;
      roomId?: string;
      room: unknown;
    }
  | {
      type: 'chat';
      protocolVersion: number;
      text: string;
      playerId?: string;
      nickname?: string;
      [key: string]: unknown;
    };
