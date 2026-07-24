/** 尚未迁到 TS 的全局桥（由其它 script 标签挂到 window）。 */

export type PlayerIdentity = {
  userId: string;
  nickname?: string;
  [key: string]: unknown;
};

export type AvatarEntityApi = {
  createAvatarEntity: (opts: Record<string, unknown>) => Record<string, unknown>;
  loadAppearance: (entity: Record<string, unknown>, appearance: unknown) => void;
  pushSnapshot: (
    entity: Record<string, unknown>,
    pose: Record<string, unknown>,
    serverMs: number
  ) => void;
  sampleRemote: (
    entity: Record<string, unknown>,
    renderMs: number
  ) => Record<string, unknown> | null;
  updateEntityMotion: (entity: Record<string, unknown>, dt: number) => void;
  applyAimArmPose?: (entity: Record<string, unknown>, aim: { x: number; y: number }) => void;
  drawAvatar: (
    ctx: CanvasRenderingContext2D,
    entity: Record<string, unknown>,
    view: unknown,
    dpr: number,
    options?: {
      skipFrontArm?: boolean;
      skipBackArm?: boolean;
      skipNickname?: boolean;
    }
  ) => void;
  drawBackArm?: (ctx: CanvasRenderingContext2D, entity: Record<string, unknown>) => void;
  drawFrontArm?: (ctx: CanvasRenderingContext2D, entity: Record<string, unknown>) => void;
};

export type LiminalNetworkApi = {
  PROTOCOL_VERSION: number;
  POSE_RATE_HZ: number;
  PUBLIC_ROOM_ID: string;
  createSession: () => WebSocketSessionLike;
  /** 本机开发入口（localhost / 环回）时为 true。 */
  isLocalDevHost: () => boolean;
};

export type WebSocketSessionLike = EventTarget & {
  connected: boolean;
  connect: (identity: PlayerIdentity) => void;
  /** 本地默认断线：只存身份，不打开 WebSocket。 */
  prepareOffline: (identity: PlayerIdentity) => void;
  disconnect: () => void;
  createRoom?: () => void;
  joinRoom?: (roomId?: string) => void;
  returnPublic?: () => void;
  manualClose?: boolean;
  mode?: string;
  roomId?: string;
  isPublic?: boolean;
  playerCount?: number;
  maxPlayers?: number;
  sendPose: (frame: {
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
    pressure?: number | null;
    hp?: number | null;
  }) => void;
  sendTrain: (state: { throttle?: number; brake?: number }) => void;
  sendFuelAdd: (amount?: number, itemId?: string) => void;
  sendFire: (detail: Record<string, unknown> & { dirX?: number; dirY?: number }) => void;
  sendHeal: (detail: {
    targetId?: string | null;
    handIndex?: number;
    dt?: number;
    aimX?: number;
    aimY?: number;
  }) => void;
  sendRevive: (detail: { targetId: string; handIndex?: number }) => void;
  sendInv: (detail: Record<string, unknown>) => void;
  setAppearance: (appearance: { skinId?: string | null }) => void;
};

declare global {
  interface Window {
    LiminalNetwork?: LiminalNetworkApi;
    LiminalSession?: Record<string, unknown>;
    AvatarEntity?: AvatarEntityApi;
    LiminalMultiplayerUi?: {
      bindMultiplayerUi?: (session: WebSocketSessionLike) => void;
    };
    LpInventoryNet?: {
      bindSession?: (session: WebSocketSessionLike) => void;
      applySnapshot?: (detail: unknown) => void;
      applyRoomOnly?: (detail: unknown) => void;
    };
    LiminalInteract?: {
      setFuelLevel?: (level: number) => void;
    };
    LpCombat?: {
      spawnProjectile?: (detail: Record<string, unknown>) => void;
      getHeldWeaponItem?: () => { id: string } | null | undefined;
    };
    LpTrainDrive?: {
      applyAuthority?: (train: unknown) => void;
    };
    LpGuardTurret?: {
      isManned?: () => boolean;
      getMannedId?: () => 'left' | 'right' | null;
      syncRemoteOperators?: (operators: Array<{
        playerId: string;
        turretId: 'left' | 'right';
        aimX?: number | null;
        aimY?: number | null;
      }>) => void;
      noteRemoteFire?: (detail: Record<string, unknown>) => void;
    };
    LpGame?: {
      isUiOpen?: () => boolean;
      getLocalAvatar?: () => Record<string, unknown>;
      getLocalX?: () => number;
      getHp?: () => number;
      getMaxHp?: () => number;
      getLifeState?: () => string;
      isIncapacitated?: () => boolean;
    };
    LpPressure?: {
      getPressure?: () => number;
      getEffectiveMax?: () => number;
      setPressure?: (v: number, localX?: number) => void;
      noteAllyDeathNearby?: (localX?: number) => void;
      noteAllyRedeployNearby?: (localX?: number) => void;
    };
    LpPlayerDeath?: {
      isIncapacitated?: () => boolean;
      isDowned?: () => boolean;
      isDead?: () => boolean;
      getLifeState?: () => string;
      poseExtras?: () => {
        lifeState?: string;
        downedRemain?: number | null;
        deathCause?: string | null;
      };
      applyDownedPose?: (entity: Record<string, unknown>, dt?: number) => void;
      allyDeathRadius?: () => number;
    };
    LpItemCatalog?: {
      getItem?: (id: string) => unknown;
    };
    LpWeaponHold?: {
      drawHeldWeapon?: (
        ctx: CanvasRenderingContext2D,
        entity: Record<string, unknown>,
        aim: { x: number; y: number },
        item: unknown
      ) => void;
      applyAimArmPose?: (
        entity: Record<string, unknown>,
        aim: { x: number; y: number },
        item: unknown
      ) => void;
    };
  }
}

export {};
