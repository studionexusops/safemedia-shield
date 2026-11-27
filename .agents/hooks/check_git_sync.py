#!/usr/bin/env python3
"""Antigravity Stop hook: enforce Git commit & push before completing a turn."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run_git(repo_dir: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command in repo_dir and return the completed process."""
    return subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )


def _resolve_repo_dir(payload: dict[str, Any]) -> Path:
    """Resolve the target Git repository root from hook payload or script location."""
    candidates: list[str] = []
    workspace_paths = payload.get("workspacePaths")
    if isinstance(workspace_paths, list):
        candidates.extend(str(p) for p in workspace_paths if isinstance(p, str))
    cwd = payload.get("cwd")
    if isinstance(cwd, str):
        candidates.append(cwd)

    for candidate in candidates:
        path = Path(candidate)
        if (path / ".git").exists():
            return path

    return Path(__file__).resolve().parents[2]


def _count_unpushed_commits(repo_dir: Path) -> int:
    """Count local commits that have not been pushed to any remote."""
    upstream = _run_git(repo_dir, ["rev-parse", "--abbrev-ref", "@{u}"])
    if upstream.returncode == 0 and upstream.stdout.strip():
        rev_list = _run_git(repo_dir, ["rev-list", "--count", "@{u}..HEAD"])
    else:
        rev_list = _run_git(repo_dir, ["rev-list", "--count", "HEAD", "--not", "--remotes"])

    if rev_list.returncode != 0:
        return 0
    try:
        return int(rev_list.stdout.strip() or "0")
    except ValueError:
        return 0


def evaluate_stop_hook(payload: dict[str, Any]) -> dict[str, str]:
    """Return a Stop hook decision JSON object based on payload and Git state."""
    if payload.get("terminationReason") != "NO_TOOL_CALL":
        return {}
    if payload.get("fullyIdle") is False:
        return {}
    # Avoid infinite continuation loops if the agent already tried to address it once this turn.
    if payload.get("continuationActive") is True:
        return {}

    repo_dir = _resolve_repo_dir(payload)
    status = _run_git(repo_dir, ["status", "--porcelain"])
    if status.returncode != 0:
        return {}

    dirty_lines = [line for line in status.stdout.splitlines() if line.strip()]
    unpushed_count = _count_unpushed_commits(repo_dir)

    if not dirty_lines and unpushed_count == 0:
        return {}

    branch_res = _run_git(repo_dir, ["rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "current"

    return {
        "decision": "continue",
        "reason": (
            f"Git未反映の変更が残っています（ブランチ: {branch}, "
            f"未コミット変更: {len(dirty_lines)}件, 未プッシュコミット: {unpushed_count}件）。"
            "GEMINI.md セクション8 に従い、テスト確認後にコミットし origin へプッシュしてください。"
        ),
    }


def main() -> int:
    """Read hook payload from stdin and emit JSON decision to stdout."""
    try:
        raw = sys.stdin.read().strip()
        payload: dict[str, Any] = json.loads(raw) if raw else {}
    except Exception:
        print("{}")
        return 0

    try:
        result = evaluate_stop_hook(payload)
    except Exception:
        result = {}

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
