#!/usr/bin/env python3
"""发布前检查：协议版本对齐、构建 TS 客户端、同步 game/ 镜像。

供 push-liminal-platform / push-github（avatar-lobby 包）调用，避免：
- 改了 client/src 忘了 npm run build
- TS 与 protocol.py 的 PROTOCOL_VERSION 不一致
- app/games/liminal_platform 与 game/Liminal_Platform 漂移

Usage:
  python3 scripts/prepare_liminal_release.py
  python3 scripts/prepare_liminal_release.py --skip-build   # 仅检查（CI 已构建时）
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TS_PROTOCOL = ROOT / "client" / "src" / "protocol" / "messages.ts"
PY_PROTOCOL = ROOT / "app" / "games" / "liminal_platform" / "protocol.py"
APP_LIMINAL = ROOT / "app" / "games" / "liminal_platform"
GAME_LIMINAL = ROOT / "game" / "Liminal_Platform"
BUILT_NETWORK = APP_LIMINAL / "static" / "js" / "lp-network.js"
BUILT_SESSION = APP_LIMINAL / "static" / "js" / "lp-session.js"


def _extract_int_const(text: str, name: str) -> int:
    """从源码中解析 `NAME = 123`（TS/Python）。"""
    patterns = [
        rf"(?:export\s+)?const\s+{name}\s*=\s*(\d+)",
        rf"^{name}\s*=\s*(\d+)\s*$",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.MULTILINE)
        if m:
            return int(m.group(1))
    raise SystemExit(f"cannot find {name} in protocol sources")


def check_protocol_versions() -> int:
    """TS 与 Python PROTOCOL_VERSION 必须相同。"""
    if not TS_PROTOCOL.is_file() or not PY_PROTOCOL.is_file():
        raise SystemExit(f"missing protocol files:\n  {TS_PROTOCOL}\n  {PY_PROTOCOL}")
    ts_v = _extract_int_const(TS_PROTOCOL.read_text(encoding="utf-8"), "PROTOCOL_VERSION")
    py_v = _extract_int_const(PY_PROTOCOL.read_text(encoding="utf-8"), "PROTOCOL_VERSION")
    if ts_v != py_v:
        raise SystemExit(
            f"PROTOCOL_VERSION mismatch: TS={ts_v} ({TS_PROTOCOL}) "
            f"vs Python={py_v} ({PY_PROTOCOL})"
        )
    print(f"protocol OK: PROTOCOL_VERSION={ts_v}")
    return ts_v


def run_npm_build() -> None:
    """在包根执行 npm run build（生成 lp-network / lp-session）。"""
    pkg = ROOT / "package.json"
    if not pkg.is_file():
        raise SystemExit(f"missing {pkg}")
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm not found — install Node.js to build liminal client")
    node_modules = ROOT / "node_modules"
    if not node_modules.is_dir():
        print("npm install…")
        subprocess.run([npm, "install"], cwd=ROOT, check=True)
    print("npm run build…")
    subprocess.run([npm, "run", "build"], cwd=ROOT, check=True)
    subprocess.run([npm, "run", "typecheck"], cwd=ROOT, check=True)


def verify_built_artifacts() -> None:
    """构建产物必须存在且挂上全局 API。"""
    for path, marker in (
        (BUILT_NETWORK, "LiminalNetwork"),
        (BUILT_SESSION, "LiminalSession"),
    ):
        if not path.is_file():
            raise SystemExit(f"missing built file: {path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        if marker not in text:
            raise SystemExit(f"{path} missing marker {marker} — build broken?")
        # 源比产物新则视为未构建（允许 2s 时钟）
    src_newest = max(
        (p.stat().st_mtime for p in (ROOT / "client" / "src").rglob("*.ts")),
        default=0,
    )
    built_oldest = min(BUILT_NETWORK.stat().st_mtime, BUILT_SESSION.stat().st_mtime)
    if src_newest > built_oldest + 2:
        raise SystemExit(
            "client/src is newer than built lp-network/lp-session — run npm run build"
        )
    print(f"build OK: {BUILT_NETWORK.name}, {BUILT_SESSION.name}")


def rsync_game_mirror() -> None:
    """app/games/liminal_platform → game/Liminal_Platform，避免双份漂移。"""
    if not APP_LIMINAL.is_dir():
        raise SystemExit(f"missing {APP_LIMINAL}")
    GAME_LIMINAL.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "rsync",
        "-a",
        "--delete",
        "--exclude",
        "__pycache__",
        "--exclude",
        "*.pyc",
        f"{APP_LIMINAL}/",
        f"{GAME_LIMINAL}/",
    ]
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)
    if not (GAME_LIMINAL / "protocol.py").is_file():
        raise SystemExit("rsync failed: game/Liminal_Platform/protocol.py missing")
    print(f"mirror OK: {GAME_LIMINAL}")


def main() -> int:
    """执行协议检查 → 构建 → 校验产物 → 镜像同步。"""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--skip-build",
        action="store_true",
        help="跳过 npm build（仍检查版本与产物新鲜度）",
    )
    args = ap.parse_args()

    check_protocol_versions()
    if not args.skip_build:
        run_npm_build()
    verify_built_artifacts()
    rsync_game_mirror()
    print("prepare_liminal_release: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
