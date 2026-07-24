#!/usr/bin/env python3
"""Load potatoblock-vendor.json and apply SoT → Game path mappings.

Used by:
  - scripts/vendor_to_game.py (CI / manual vendor into Potatoblock-Game)
  - local push-github.py / push-liminal-platform.py (prepare + collect)

Config is the only package-specific surface — no liminal_* branches in callers.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


CONFIG_NAME = "potatoblock-vendor.json"


def find_config(package_root: Path) -> Path | None:
    """Return potatoblock-vendor.json under package_root if present."""
    path = package_root / CONFIG_NAME
    return path if path.is_file() else None


def load_config(package_root: Path) -> dict[str, Any] | None:
    """Parse vendor config; None if this package is not a SoT vendor source."""
    path = find_config(package_root)
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: root must be an object")
    if "mappings" not in data or not isinstance(data["mappings"], list):
        raise SystemExit(f"{path}: missing mappings[]")
    return data


def _should_skip(path: Path, root: Path, cfg: dict[str, Any]) -> bool:
    """Whether path should be omitted when collecting/copying."""
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    skip_dirs = set(cfg.get("exclude_dir_names") or [])
    if any(part in skip_dirs for part in parts):
        return True
    skip_names = set(cfg.get("exclude_file_names") or [])
    if path.name in skip_names:
        return True
    for suffix in cfg.get("exclude_name_suffixes") or []:
        if path.name.endswith(suffix):
            return True
    return False


def run_prepare(package_root: Path, cfg: dict[str, Any], *, skip_build: bool = False) -> None:
    """Run prepare scripts listed in config (relative to package_root)."""
    for rel in cfg.get("prepare") or []:
        script = package_root / rel
        if not script.is_file():
            raise SystemExit(f"prepare script missing: {script}")
        cmd = [sys.executable, str(script)]
        if skip_build:
            cmd.append("--skip-build")
        print("+", " ".join(cmd), flush=True)
        subprocess.run(cmd, cwd=package_root, check=True)


def collect_mapped_files(package_root: Path, cfg: dict[str, Any]) -> dict[str, Path]:
    """Build Game-repo relative path → local file from config mappings."""
    mapping: dict[str, Path] = {}
    for entry in cfg["mappings"]:
        src_rel = entry["from"]
        dest_rel = entry["to"]
        optional = bool(entry.get("optional"))
        src = package_root / src_rel
        if not src.exists():
            if optional:
                continue
            raise SystemExit(f"mapping source missing: {src}")
        if src.is_file():
            if not _should_skip(src, package_root, cfg):
                mapping[dest_rel] = src
            continue
        if not src.is_dir():
            if optional:
                continue
            raise SystemExit(f"mapping source not a file/dir: {src}")
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            if _should_skip(path, package_root, cfg):
                continue
            rel_inside = path.relative_to(src).as_posix()
            mapping[f"{dest_rel.rstrip('/')}/{rel_inside}"] = path
    return mapping


def prune_targets(worktree: Path, cfg: dict[str, Any], kept: set[str]) -> None:
    """Delete stale files under mappings with prune=true."""
    for entry in cfg["mappings"]:
        if not entry.get("prune"):
            continue
        root = worktree / entry["to"]
        if not root.is_dir():
            continue
        prefix = entry["to"].rstrip("/")
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(worktree).as_posix()
            if rel not in kept and (rel == prefix or rel.startswith(prefix + "/")):
                path.unlink()
                print(f"  remove stale {rel}")


def apply_mappings(package_root: Path, worktree: Path, cfg: dict[str, Any]) -> int:
    """Copy mapped files into Game worktree; prune configured targets. Returns file count."""
    files = collect_mapped_files(package_root, cfg)
    for rel, src in sorted(files.items()):
        dest = worktree / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"  stage {rel} ({src.stat().st_size} bytes)")
    prune_targets(worktree, cfg, set(files))
    # Drop a machine-readable stamp for operators (not control-flow).
    stamp = {
        "source": cfg.get("name"),
        "repository_config": CONFIG_NAME,
        "files": len(files),
        "runtime": cfg.get("runtime"),
    }
    stamp_path = worktree / "vendor-stamp.json"
    stamp_path.write_text(json.dumps(stamp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  stage vendor-stamp.json")
    return len(files)
