#!/usr/bin/env python3
"""Vendor this SoT package into Potatoblock-Game using potatoblock-vendor.json.

Env:
  POTATOBLOCK_GAME_TOKEN  — GitHub PAT with contents:write on target.repository
  (optional) GITHUB_SHA / CI_COMMIT_SHA — appended to commit message

Usage:
  python scripts/vendor_to_game.py
  python scripts/vendor_to_game.py --skip-build --dry-run
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from potatoblock_vendor import apply_mappings, load_config, run_prepare  # noqa: E402


def _run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    """Run a command (no secrets in argv)."""
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, env=env)


def _git_output(cmd: list[str], cwd: Path) -> str:
    """Return stripped stdout from git."""
    return subprocess.check_output(cmd, cwd=cwd, text=True).strip()


def _git_env(token: str, work: Path) -> dict[str, str]:
    """Build git env that authenticates without putting the PAT on argv.

    GitHub Actions masks secrets in command lines and can corrupt
    `git -c http...AUTHORIZATION: basic <pat>` into a broken command.
    ASKPASS keeps the token in a 0600 file instead.
    """
    token_file = work / ".pat"
    token_file.write_text(token, encoding="utf-8")
    token_file.chmod(0o600)

    askpass = work / "askpass.sh"
    # Paths are under mkdtemp; no secret in this script body.
    askpass.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        "  Username*) echo x-access-token ;;\n"
        f'  *) cat "{token_file}" ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    askpass.chmod(0o700)

    env = os.environ.copy()
    env["GIT_ASKPASS"] = str(askpass)
    env["GIT_TERMINAL_PROMPT"] = "0"
    # Prefer our PAT; drop job / other tokens that confuse HTTPS to github.com.
    for k in (
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "LIMINAL_PLATFORM_GH_TOKEN",
        "POTATOBLOCK_GAME_TOKEN",
    ):
        env.pop(k, None)
    return env


def main() -> None:
    """Clone Game repo, apply vendor mappings, commit and push if dirty."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="SoT package root (contains potatoblock-vendor.json)",
    )
    parser.add_argument("--skip-build", action="store_true", help="Pass --skip-build to prepare")
    parser.add_argument("--dry-run", action="store_true", help="Apply locally then discard; no push")
    parser.add_argument("--message", default="", help="Commit message override")
    args = parser.parse_args()

    package_root = args.package_root.resolve()
    cfg = load_config(package_root)
    if cfg is None:
        raise SystemExit(f"no potatoblock-vendor.json under {package_root}")

    target = cfg.get("target") or {}
    repo = target.get("repository")
    branch = target.get("branch") or "main"
    if not repo:
        raise SystemExit("target.repository missing in potatoblock-vendor.json")

    token = (os.environ.get("POTATOBLOCK_GAME_TOKEN") or "").strip()
    if not token and not args.dry_run:
        raise SystemExit("set POTATOBLOCK_GAME_TOKEN (contents:write on Potatoblock-Game)")

    run_prepare(package_root, cfg, skip_build=args.skip_build)

    prefix = (cfg.get("commit_message_prefix") or "deploy: vendor").rstrip()
    sha = (os.environ.get("GITHUB_SHA") or os.environ.get("CI_COMMIT_SHA") or "")[:12]
    message = args.message.strip() or (f"{prefix} {sha}".strip() if sha else prefix)

    work = Path(tempfile.mkdtemp(prefix="potatoblock-vendor-"))
    try:
        if args.dry_run:
            worktree = work / "game"
            worktree.mkdir()
            apply_mappings(package_root, worktree, cfg)
            print(f"dry-run ok → {worktree} (not pushed)")
            return

        remote_url = f"https://github.com/{repo}.git"
        worktree = work / "game"
        env = _git_env(token, work)
        # Clear Actions-injected GITHUB_TOKEN header so ASKPASS is used.
        auth_clear = [
            "-c",
            "credential.helper=",
            "-c",
            "http.https://github.com/.extraheader=",
        ]
        _run(
            [
                "git",
                *auth_clear,
                "clone",
                "--depth",
                "1",
                "--branch",
                branch,
                remote_url,
                str(worktree),
            ],
            env=env,
        )
        apply_mappings(package_root, worktree, cfg)

        status = _git_output(["git", "status", "--porcelain"], worktree)
        if not status:
            print("no file changes after vendor; skip push")
            return

        _run(["git", "config", "user.name", "potatoblock-vendor"], cwd=worktree)
        _run(["git", "config", "user.email", "vendor@users.noreply.github.com"], cwd=worktree)
        _run(["git", "add", "-A"], cwd=worktree)
        _run(["git", "commit", "-m", message], cwd=worktree)
        _run(
            ["git", *auth_clear, "push", "origin", f"HEAD:{branch}"],
            cwd=worktree,
            env=env,
        )
        print(f"vendored → {repo}@{branch}")
        print("Game repo Actions deploy.yml will sync MCS /app")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
