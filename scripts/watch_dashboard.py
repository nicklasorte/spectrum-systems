#!/usr/bin/env python3
"""Poll repository surfaces and refresh dashboard snapshot on relevant changes."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

WATCH_DIRECTORIES = [
    "docs",
    "contracts",
    "spectrum_systems/modules/runtime",
    "tests",
    "runs",
    "artifacts",
]

IGNORED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "node_modules",
    ".next",
}

IGNORED_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
}

IGNORED_SUFFIXES = {
    "~",
    ".swp",
    ".swo",
    ".tmp",
    ".temp",
}

SELF_GENERATED_RELATIVE_PATHS = {
    "artifacts/dashboard/repo_snapshot.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch repo surfaces and refresh dashboard snapshot on changes.")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds (default: 2.0).")
    parser.add_argument("--debounce", type=float, default=1.5, help="Debounce window in seconds (default: 1.5).")
    return parser.parse_args()


def should_ignore(path: Path, root: Path) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        rel_parts = path.parts

    for part in rel_parts:
        if part in IGNORED_DIR_NAMES:
            return True

    name = path.name
    if name in IGNORED_FILE_NAMES:
        return True

    if name.startswith(".") and name not in {".env", ".env.example"}:
        return True

    return any(name.endswith(suffix) for suffix in IGNORED_SUFFIXES)


def gather_file_state(repo_root: Path, watch_roots: list[Path]) -> dict[str, int]:
    state: dict[str, int] = {}

    for watch_root in watch_roots:
        if not watch_root.exists() or not watch_root.is_dir():
            continue

        for path in watch_root.rglob("*"):
            if should_ignore(path, repo_root):
                continue
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            relative = str(path.relative_to(repo_root))
            if relative in SELF_GENERATED_RELATIVE_PATHS:
                continue
            state[relative] = stat.st_mtime_ns

    return state


def run_refresh(repo_root: Path) -> bool:
    refresh_script = repo_root / "scripts/refresh_dashboard.sh"
    if not refresh_script.is_file():
        print(f"[watch] refresh failed: missing {refresh_script}", flush=True)
        return False

    print("[watch] refresh running", flush=True)
    result = subprocess.run([str(refresh_script)], cwd=repo_root, check=False)
    if result.returncode == 0:
        print("[watch] refresh succeeded", flush=True)
        return True

    print(f"[watch] refresh failed (exit={result.returncode})", flush=True)
    return False


def main() -> int:
    args = parse_args()

    if args.interval <= 0:
        print("ERROR: --interval must be positive", file=sys.stderr)
        return 1
    if args.debounce < 0:
        print("ERROR: --debounce must be >= 0", file=sys.stderr)
        return 1

    repo_root = Path(__file__).resolve().parents[1]
    watch_roots = [repo_root / relative for relative in WATCH_DIRECTORIES]
    active_roots = [path for path in watch_roots if path.exists() and path.is_dir()]

    if not active_roots:
        print("ERROR: no watchable directories found", file=sys.stderr)
        return 1

    print("[watch] watcher started", flush=True)
    print(f"[watch] interval={args.interval:.1f}s debounce={args.debounce:.1f}s", flush=True)
    print("[watch] roots=" + ", ".join(str(path.relative_to(repo_root)) for path in active_roots), flush=True)

    previous_state = gather_file_state(repo_root, active_roots)
    pending_change_at: float | None = None

    while True:
        time.sleep(args.interval)
        current_state = gather_file_state(repo_root, active_roots)

        if current_state != previous_state:
            print("[watch] change detected", flush=True)
            previous_state = current_state
            pending_change_at = time.monotonic()
            continue

        if pending_change_at is None:
            continue

        if time.monotonic() - pending_change_at < args.debounce:
            continue

        run_refresh(repo_root)
        pending_change_at = None


if __name__ == "__main__":
    raise SystemExit(main())
