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
};

export type WebSocketSessionLike = EventTarget & {
  connected: boolean;
  connect: (identity: PlayerIdentity) => void;
  disconnect: () => void;
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
  }) => void;
  sendTrain: (state: { throttle?: number; brake?: number }) => void;
  sendFuelAdd: (amount?: number, itemId?: string) => void;
  sendFire: (detail: Record<string, unknown> & { dirX?: number; dirY?: number }) => void;
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
    };
  }
}

export {};
