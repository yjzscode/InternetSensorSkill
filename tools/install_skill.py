#!/usr/bin/env python3
"""Install this AgentSkills package into a supported host directory."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


SKILL_NAME = "trend-aware-content-improver"

DEFAULT_IGNORES = {
    ".git",
    ".claude",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".DS_Store",
    ".env",
    "config.json",
    "cdp-proxy.log",
}


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_destination(host: str) -> Path | None:
    home = Path.home()
    if host == "claude":
        return home / ".claude" / "skills" / SKILL_NAME
    if host == "openclaw":
        return home / ".openclaw" / "workspace" / "skills" / SKILL_NAME
    if host == "codex":
        base = Path(os.environ.get("CODEX_HOME", home / ".codex"))
        return base / "skills" / SKILL_NAME
    if host == "hermes":
        configured = os.environ.get("HERMES_SKILLS_DIR")
        if configured:
            return Path(configured).expanduser() / SKILL_NAME
        candidate = home / ".hermes" / "skills"
        if candidate.exists():
            return candidate / SKILL_NAME
        return None
    raise ValueError(f"Unsupported host: {host}")


def ignored(directory: str, names: list[str]) -> set[str]:
    root = source_root()
    current = Path(directory).resolve()
    rel = current.relative_to(root) if current != root else Path()
    blocked: set[str] = set()
    for name in names:
        path = rel / name
        parts = path.parts
        suffix = Path(name).suffix
        if name in DEFAULT_IGNORES or suffix in {".pyc", ".pyo"}:
            blocked.add(name)
            continue
        if parts and parts[0] == "outputs" and name != ".gitkeep":
            blocked.add(name)
            continue
        if len(parts) >= 2 and parts[0] == "skills" and parts[1] == "web-access":
            if name == ".git":
                blocked.add(name)
    return blocked


def install(dest: Path, *, force: bool, dry_run: bool) -> None:
    src = source_root()
    dest = dest.expanduser().resolve()
    if dest.name != SKILL_NAME:
        raise SystemExit(
            f"Destination must end with {SKILL_NAME!r} so the folder matches SKILL.md name: {dest}"
        )
    if dry_run:
        print(f"source: {src}")
        print(f"destination: {dest}")
        print("mode: dry-run")
        return
    if dest.exists():
        if not force:
            raise SystemExit(f"Destination exists: {dest}\nRe-run with --force to replace it.")
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, ignore=ignored)
    print(f"Installed {SKILL_NAME} to {dest}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", choices=["claude", "openclaw", "codex", "hermes"])
    parser.add_argument(
        "--dest",
        type=Path,
        help=f"Full destination skill directory. Must end with {SKILL_NAME}.",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing installed copy.")
    parser.add_argument("--dry-run", action="store_true", help="Show the resolved destination only.")
    args = parser.parse_args(argv)

    dest = args.dest or default_destination(args.host)
    if dest is None:
        raise SystemExit(
            "Could not infer Hermes skills directory. Set HERMES_SKILLS_DIR to the Hermes skills root "
            f"or pass --dest /path/to/{SKILL_NAME}."
        )
    install(dest, force=args.force, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
