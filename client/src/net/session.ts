/**
 * 阈限月台联机绑定：远端玩家、姿态上报、共享列车/燃料/开火。
 * 构建为 IIFE → window.LiminalSession
 */

import type { PlayerIdentity, WebSocketSessionLike } from '../globals';
import type { SnapshotPlayer, ServerMessage } from '../protocol/messages';

type RemoteEntity = Record<string, unknown> & {
  _lpDisconnected?: boolean;
  _physicsY?: number;
  _heldId?: string | null;
  _aimX?: number | null;
  _aimY?: number | null;
  _turretId?: 'left' | 'right' | null;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  facing?: number;
  onGround?: boolean;
  gait?: string;
  headLook?: number;
  headLookVelocity?: number;
  moveDirection?: number;
  nickname?: string;
};

export function installLiminalSession(): void {
  const entityApi = window.AvatarEntity;
  const netApi = window.LiminalNetwork;
  if (!entityApi || !netApi) return;
  const Entity = entityApi;
  const Net = netApi;

  const POSE_INTERVAL = 1000 / (Net.POSE_RATE_HZ || 20);
  const INTERP_DELAY_MS = 120;

  const remotePlayers = new Map<string, RemoteEntity>();
  let session: WebSocketSessionLike | null = null;
  let localUserId = '';
  let poseSequence = 0;
  let lastPoseSentAt = 0;
  let lastTrainSentAt = 0;
  let clockOffsetMs: number | null = null;

  /** 把服务端 wall-clock 映到 performance.now 时间轴。 */
  function mapServerMs(serverTimeMs: number | null | undefined): number {
    const now = performance.now();
    if (serverTimeMs == null || !Number.isFinite(serverTimeMs)) return now;
    const offset = now - serverTimeMs;
    if (clockOffsetMs === null || Math.abs(offset - clockOffsetMs) > 1000) {
      clockOffsetMs = offset;
    } else {
      clockOffsetMs += (offset - clockOffsetMs) * 0.1;
    }
    return serverTimeMs + clockOffsetMs;
  }

  /** 创建并连接会话。 */
  function start(identity: PlayerIdentity): void {
    localUserId = String(identity.userId || '');
    session = Net.createSession();
    window.LiminalMultiplayerUi?.bindMultiplayerUi?.(session);
    session.connect(identity);
    window.LpInventoryNet?.bindSession?.(session);
    window.addEventListener('beforeunload', () => session?.disconnect());

    session.addEventListener('worldsnapshot', ((event: CustomEvent) => {
      applyWorldSnapshot(event.detail);
    }) as EventListener);
    session.addEventListener('invsnapshot', ((event: CustomEvent) => {
      window.LpInventoryNet?.applySnapshot?.(event.detail);
    }) as EventListener);
    session.addEventListener('invroom', ((event: CustomEvent) => {
      window.LpInventoryNet?.applyRoomOnly?.(event.detail);
    }) as EventListener);
    session.addEventListener('playerleave', ((event: CustomEvent) => {
      const id = String(event.detail?.playerId || '');
      if (!id) return;
      if (event.detail?.temporary) {
        const remote = remotePlayers.get(id);
        if (remote) {
          remote._lpDisconnected = true;
          remote._turretId = null;
        }
        syncGuardTurretOperators();
        return;
      }
      remotePlayers.delete(id);
      syncGuardTurretOperators();
    }) as EventListener);
    session.addEventListener('appearance', ((event: CustomEvent) => {
      const detail = event.detail || {};
      const remote = remotePlayers.get(String(detail.playerId));
      if (remote && detail.appearance) Entity.loadAppearance(remote, detail.appearance);
    }) as EventListener);
    session.addEventListener('roomchange', () => {
      remotePlayers.clear();
      clockOffsetMs = null;
      window.LpGuardTurret?.syncRemoteOperators?.([]);
    });
    session.addEventListener('fuelchanged', ((event: CustomEvent) => {
      const level = event.detail?.level;
      if (level != null) window.LiminalInteract?.setFuelLevel?.(level);
    }) as EventListener);
    session.addEventListener('weaponfired', ((event: CustomEvent) => {
      const detail = event.detail || {};
      if (String(detail.playerId) === localUserId) return;
      const shots = Array.isArray(detail.shots) && detail.shots.length > 0
        ? detail.shots
        : [
            {
              x: detail.x,
              y: detail.y,
              dirX: detail.dirX,
              dirY: detail.dirY,
            },
          ];
      for (const shot of shots) {
        window.LpCombat?.spawnProjectile?.({
          originX: shot.x,
          originY: shot.y,
          dirX: shot.dirX,
          dirY: shot.dirY,
          facing: detail.facing,
          weaponId: detail.weaponId,
          style: detail.style,
        });
      }
      if (detail.source === 'turret' || detail.weaponId === 'guard_turret') {
        window.LpGuardTurret?.noteRemoteFire?.(detail);
      }
    }) as EventListener);

    window.addEventListener('lp:weapon-fired', ((event: CustomEvent) => {
      if (!session?.connected) return;
      session.sendFire(event.detail || {});
    }) as EventListener);
  }

  /** 确保远端实体存在。 */
  function ensureRemote(playerId: string, snapshot: SnapshotPlayer): RemoteEntity {
    let remote = remotePlayers.get(playerId);
    if (!remote) {
      remote = Entity.createAvatarEntity({
        id: playerId,
        nickname: snapshot.nickname || '旅人',
        x: snapshot.x ?? 0,
        y: 0,
      }) as RemoteEntity;
      remote._physicsY = snapshot.y ?? 0;
      remotePlayers.set(playerId, remote);
    }
    remote._lpDisconnected = false;
    return remote;
  }

  /** 把快照中的持枪/瞄准/炮位写到远端实体。 */
  function applyRemoteHold(remote: RemoteEntity, player: SnapshotPlayer): void {
    remote._heldId = player.heldId || null;
    if (player.aimX != null && player.aimY != null) {
      remote._aimX = Number(player.aimX);
      remote._aimY = Number(player.aimY);
    } else {
      remote._aimX = null;
      remote._aimY = null;
    }
    remote._turretId =
      player.turretId === 'left' || player.turretId === 'right'
        ? player.turretId
        : null;
  }

  /** 把远端炮位占用与瞄准同步给卫兵炮塔模块。 */
  function syncGuardTurretOperators(): void {
    const operators: Array<{
      playerId: string;
      turretId: 'left' | 'right';
      aimX?: number | null;
      aimY?: number | null;
    }> = [];
    for (const [playerId, remote] of remotePlayers) {
      if (remote._lpDisconnected) continue;
      if (remote._turretId !== 'left' && remote._turretId !== 'right') continue;
      operators.push({
        playerId,
        turretId: remote._turretId,
        aimX: remote._aimX,
        aimY: remote._aimY,
      });
    }
    window.LpGuardTurret?.syncRemoteOperators?.(operators);
  }

  /** 应用世界快照：远端姿态 + 共享列车/燃料。 */
  function applyWorldSnapshot(payload: Extract<ServerMessage, { type: 'world_snapshot' }> | null): void {
    if (!payload) return;
    const serverMs = mapServerMs(payload.serverTimeMs);
    const seen = new Set<string>();
    for (const player of payload.players || []) {
      const id = String(player.id);
      if (!id || id === localUserId) continue;
      seen.add(id);
      if (player.connected === false) {
        const existing = remotePlayers.get(id);
        if (existing) existing._lpDisconnected = true;
        continue;
      }
      const remote = ensureRemote(id, player);
      Entity.pushSnapshot(
        remote,
        {
          x: player.x,
          y: player.y,
          vx: player.vx,
          vy: player.vy,
          facing: player.facing,
          onGround: player.onGround,
          gait: player.gait,
          headLook: player.headLook,
          nickname: player.nickname,
        },
        serverMs
      );
      applyRemoteHold(remote, player);
      if (player.appearance) Entity.loadAppearance(remote, player.appearance);
      remote.nickname = player.nickname || remote.nickname;
    }
    for (const id of [...remotePlayers.keys()]) {
      if (!seen.has(id)) remotePlayers.delete(id);
    }

    syncGuardTurretOperators();

    const world = payload.world;
    if (world?.train) window.LpTrainDrive?.applyAuthority?.(world.train);
    if (world?.fuel?.level != null) {
      window.LiminalInteract?.setFuelLevel?.(world.fuel.level);
    }
  }

  /** 上报本地姿态（限频）。 */
  function maybeSendPose(frame: {
    x: number;
    y: number;
    vx: number;
    vy: number;
    facing: number;
    onGround: boolean;
    gait?: string;
    headLook?: number;
    aimX?: number | null;
    aimY?: number | null;
  }): void {
    if (!session?.connected) return;
    const now = performance.now();
    if (now - lastPoseSentAt < POSE_INTERVAL) return;
    lastPoseSentAt = now;
    poseSequence += 1;
    const held = window.LpCombat?.getHeldWeaponItem?.();
    const turretManned = Boolean(window.LpGuardTurret?.isManned?.());
    const turretId = window.LpGuardTurret?.getMannedId?.();
    // 控制台打开时不上报 heldId，远端也不画枪（本机库存槽不变）。
    const suppressHeld =
      turretManned || Boolean(window.LpGame?.isUiOpen?.());
    session.sendPose({
      sequence: poseSequence,
      x: frame.x,
      y: frame.y,
      vx: frame.vx,
      vy: frame.vy,
      facing: frame.facing,
      onGround: frame.onGround,
      gait: frame.gait,
      headLook: frame.headLook,
      heldId: suppressHeld ? null : held?.id || null,
      aimX: frame.aimX,
      aimY: frame.aimY,
      turretId:
        turretManned && (turretId === 'left' || turretId === 'right')
          ? turretId
          : null,
    });
  }

  /** 上报列车操作（限频）。 */
  function notifyTrain(
    state: { throttle?: number; brake?: number } | null,
    options: { force?: boolean } = {}
  ): void {
    if (!session?.connected || !state) return;
    const now = performance.now();
    if (!options.force && now - lastTrainSentAt < 50) return;
    lastTrainSentAt = now;
    session.sendTrain({
      throttle: state.throttle,
      brake: state.brake,
    });
  }

  /** 上报加燃料。 */
  function notifyFuelAdd(amount?: number, itemId?: string): void {
    if (!session?.connected) return;
    session.sendFuelAdd(amount, itemId);
  }

  /** 上报库存意图。 */
  function sendInv(payload: Record<string, unknown>): void {
    if (!session?.connected) return;
    session.sendInv(payload);
  }

  /**
   * 插值远端姿态并推进程序化动作。
   */
  function tickRemotes(
    dt: number,
    stageYFromPhysics: (entity: RemoteEntity, physicsY: number) => number
  ): void {
    const renderMs = performance.now() - INTERP_DELAY_MS;
    for (const remote of remotePlayers.values()) {
      if (remote._lpDisconnected) continue;
      const sample = Entity.sampleRemote(remote, renderMs);
      if (!sample) continue;
      if (sample.x != null) remote.x = sample.x as number;
      remote._physicsY = (sample.y as number) ?? 0;
      remote.y = stageYFromPhysics(remote, remote._physicsY);
      remote.vx = (sample.vx as number) ?? 0;
      remote.vy = (sample.vy as number) ?? 0;
      remote.facing = (sample.facing as number) || remote.facing;
      remote.onGround = Boolean(sample.onGround);
      remote.gait = sample.gait === 'run' ? 'run' : 'walk';
      remote.headLook = (sample.headLook as number) ?? 0;
      remote.headLookVelocity = 0;
      remote.moveDirection = Math.sign(remote.vx || 0) || 0;
      remote.nickname = (sample.nickname as string) || remote.nickname;
      Entity.updateEntityMotion(remote, dt);
    }
  }

  /** 远端默认瞄准点。 */
  function remoteAimWorld(remote: RemoteEntity): { x: number; y: number } {
    if (remote._aimX != null && remote._aimY != null) {
      return { x: remote._aimX, y: remote._aimY };
    }
    const facing = (remote.facing ?? 1) >= 0 ? 1 : -1;
    return { x: (remote.x ?? 0) + facing * 140, y: (remote.y ?? 0) - 56 };
  }

  /** 绘制远端玩家（持枪层序与本机一致；入座炮塔时不画手持枪）。 */
  function drawRemotes(
    ctx: CanvasRenderingContext2D,
    view: unknown,
    dpr: number
  ): void {
    for (const remote of remotePlayers.values()) {
      if (remote._lpDisconnected) continue;
      const inTurret =
        remote._turretId === 'left' || remote._turretId === 'right';
      const heldId = inTurret ? null : remote._heldId;
      const item = heldId ? window.LpItemCatalog?.getItem?.(heldId) : null;
      if (item && window.LpWeaponHold?.drawHeldWeapon) {
        const aim = remoteAimWorld(remote);
        window.LpWeaponHold.applyAimArmPose?.(remote, aim, item);
        Entity.drawAvatar(ctx, remote, view, dpr, {
          skipBackArm: true,
        });
        window.LpWeaponHold.drawHeldWeapon(ctx, remote, aim, item);
        Entity.drawBackArm?.(ctx, remote);
      } else {
        Entity.drawAvatar(ctx, remote, view, dpr);
      }
    }
  }

  function setAppearance(appearance: { skinId?: string | null }): void {
    session?.setAppearance?.(appearance);
  }

  function isConnected(): boolean {
    return Boolean(session?.connected);
  }

  window.LiminalSession = {
    start,
    maybeSendPose,
    notifyTrain,
    notifyFuelAdd,
    sendInv,
    tickRemotes,
    drawRemotes,
    setAppearance,
    isConnected,
    getSession: () => session,
    remotes: () => remotePlayers,
  };
}
