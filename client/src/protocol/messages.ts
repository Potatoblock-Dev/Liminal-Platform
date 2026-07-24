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
      /** 入座炮位：left/right；未入座省略。服务端保证同侧唯一。 */
      turretId?: 'left' | 'right';
      /** 本机压力 0…200（HUD 透传，非权威玩法结算）。 */
      pressure?: number;
      /** 本机生命（HUD 透传；小怪伤害仍本地）。 */
      hp?: number;
      /** 生命态：alive | downed | dead（联机濒死/死亡同步）。 */
      lifeState?: 'alive' | 'downed' | 'dead';
      /** 濒死剩余秒数（仅 lifeState=downed）。 */
      downedRemain?: number | null;
      /** 最终死亡原因：timer | redeploy | solo（仅 lifeState=dead）。 */
      deathCause?: 'timer' | 'redeploy' | 'solo' | null;
      /** 伴飞无人机世界坐标（本地权威；缺省=无伴飞）。 */
      droneX?: number;
      droneY?: number;
      droneVx?: number;
      droneVy?: number;
      /** 炮管瞄准角（弧度）。 */
      droneAim?: number;
      /** 0=hover 1=grab 2=fiddle 3=release。 */
      dronePhase?: number;
      /**
       * 所在场景：train=车厢走道；platform=月台。
       * 缺省 train。发车锁：房内任一人为 platform 时服务端拒绝非零油门。
       */
      scene?: 'train' | 'platform';
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
      /** 炮塔座位；source=turret 时可选。 */
      turretId?: 'left' | 'right';
      /**
       * 联机双联时附加枪口（与 x/y/dir* 同耗一发弹药）。
       * 远端按数组逐发生成弹道；缺省仅用 x/y/dir*。
       */
      shots?: Array<{ x: number; y: number; dirX: number; dirY: number }>;
      /** 武装车厢弹种：ap | t（仅外观/后续玩法；服务端透传）。 */
      ammoType?: string;
    }
  | {
      type: 'heal';
      protocolVersion: typeof PROTOCOL_VERSION;
      handIndex?: number;
      dt: number;
      /** 队友 userId；缺省/空=自疗。 */
      targetId?: string | null;
      aimX?: number;
      aimY?: number;
    }
  | {
      /** 消耗整箱医箱复活濒死队友。 */
      type: 'revive';
      protocolVersion: typeof PROTOCOL_VERSION;
      targetId: string;
      handIndex?: number;
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
  /** 当前占用的卫兵炮位；未入座省略。 */
  turretId?: 'left' | 'right';
  /** 客户端上报的压力（HUD）。 */
  pressure?: number;
  /** 客户端上报的生命（HUD）。 */
  hp?: number;
  /** 生命态透传。 */
  lifeState?: 'alive' | 'downed' | 'dead';
  downedRemain?: number | null;
  deathCause?: 'timer' | 'redeploy' | 'solo' | null;
  /** 伴飞无人机位姿回显（有则远端绘制）。 */
  droneX?: number;
  droneY?: number;
  droneVx?: number;
  droneVy?: number;
  droneAim?: number;
  dronePhase?: number;
  /** 所在场景；缺省 train。 */
  scene?: 'train' | 'platform';
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
      source?: string;
      turretId?: 'left' | 'right';
      shots?: Array<{ x: number; y: number; dirX: number; dirY: number }>;
      /** 武装弹种 ap | t；远端弹道外观。 */
      ammoType?: string;
      [key: string]: unknown;
    }
  | {
      type: 'player_healed';
      protocolVersion: number;
      roomId?: string;
      by: string;
      targetId: string;
      amount: number;
      ally?: boolean;
    }
  | {
      type: 'player_revived';
      protocolVersion: number;
      roomId?: string;
      by: string;
      targetId: string;
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
