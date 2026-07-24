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
    """Private HOME with url.insteadOf auth — PAT never appears on argv.

    Actions masks secrets in process argv and can break `git -c ...<token>...`.
    Writing insteadOf into $HOME/.gitconfig avoids that and bypasses the job
    GITHUB_TOKEN extraheader on the runner.
    """
    home = work / "git-home"
    home.mkdir(parents=True, exist_ok=True)
    # insteadOf rewrites https://github.com/… → authenticated URL.
    (home / ".gitconfig").write_text(
        "[url \"https://x-access-token:"
        + token
        + "@github.com/\"]\n"
        "\tinsteadOf = https://github.com/\n",
        encoding="utf-8",
    )
    (home / ".gitconfig").chmod(0o600)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["GIT_TERMINAL_PROMPT"] = "0"
    # Do not inherit runner system gitconfig (job token headers).
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    for k in (
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "LIMINAL_PLATFORM_GH_TOKEN",
        "POTATOBLOCK_GAME_TOKEN",
        "GIT_ASKPASS",
        "SSH_ASKPASS",
        "GIT_CONFIG_GLOBAL",
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

    if token and not args.dry_run:
        # Potatoblock-Game is public — clone succeeds without auth. Fail fast if
        # the Actions secret cannot push (common mis-paste of Liminal-only PAT).
        import json
        import subprocess

        probe = subprocess.run(
            [
                "curl",
                "-sS",
                "-H",
                "Accept: application/vnd.github+json",
                "-H",
                f"Authorization: Bearer {token}",
                "-H",
                "User-Agent: potatoblock-vendor",
                f"https://api.github.com/repos/{repo}",
            ],
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            raise SystemExit(f"token probe failed: {probe.stderr.strip() or probe.stdout[:200]}")
        try:
            meta = json.loads(probe.stdout)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"token probe: bad JSON from GitHub API") from exc
        if meta.get("message") and "permissions" not in meta:
            raise SystemExit(
                f"POTATOBLOCK_GAME_TOKEN rejected by GitHub API ({meta.get('message')}). "
                "Update Liminal Actions secret with .env GH_TOKEN / "
                "POTATOBLOCK_GAME_VENDOR_TOKEN (Game Contents: Write)."
            )
        perms = meta.get("permissions") or {}
        if not perms.get("push"):
            raise SystemExit(
                "POTATOBLOCK_GAME_TOKEN can read but not push Potatoblock-Game. "
                "Use potatoblock-deploy / GH_TOKEN (Contents: Write on Game), "
                "not the Liminal-only PAT."
            )
        print(f"token OK: push access on {repo}", flush=True)

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
        _run(
            ["git", "clone", "--depth", "1", "--branch", branch, remote_url, str(worktree)],
            env=env,
        )
        apply_mappings(package_root, worktree, cfg)

        status = _git_output(["git", "status", "--porcelain"], worktree)
        if not status:
            print("no file changes after vendor; skip push")
            return

        _run(["git", "config", "user.name", "potatoblock-vendor"], cwd=worktree, env=env)
        _run(
            ["git", "config", "user.email", "vendor@users.noreply.github.com"],
            cwd=worktree,
            env=env,
        )
        _run(["git", "add", "-A"], cwd=worktree, env=env)
        _run(["git", "commit", "-m", message], cwd=worktree, env=env)
        _run(["git", "push", "origin", f"HEAD:{branch}"], cwd=worktree, env=env)
        print(f"vendored → {repo}@{branch}")
        print("Game repo Actions deploy.yml will sync MCS /app")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
