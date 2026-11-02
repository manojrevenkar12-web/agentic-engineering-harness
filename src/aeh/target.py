"""The repository the team works on, pinned to one commit, exported without its history."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import ROOT, workdir


@dataclass
class Target:
    name: str
    repo: str
    commit: str
    env: dict[str, str] = field(default_factory=dict)
    database_extensions: list[str] = field(default_factory=list)
    commands: dict[str, list[str]] = field(default_factory=dict)

    def env_for(self, database_url: str, redis_url: str) -> dict[str, str]:
        return {k: v.format(database_url=database_url, redis_url=redis_url) for k, v in self.env.items()}


def targets_dir() -> Path:
    return Path(os.environ.get("AEH_TARGETS_DIR") or ROOT / "targets")


def load_target(name: str) -> Target:
    raw = yaml.safe_load((targets_dir() / f"{name}.yaml").read_text())
    return Target(**raw)


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def source_repo(t: Target) -> Path:
    """A local clone holding the pinned commit: AEH_TARGET_<NAME> if set, else a cached clone."""
    env = os.environ.get("AEH_TARGET_" + t.name.upper().replace("-", "_"))
    if env:
        return Path(env)
    clone = workdir() / "targets" / t.name
    if not (clone / ".git").exists():
        clone.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", "--quiet", t.repo, str(clone)])
    try:
        _run(["git", "cat-file", "-e", t.commit + "^{commit}"], clone)
    except subprocess.CalledProcessError:
        _run(["git", "fetch", "--quiet", "origin", t.commit], clone)
    return clone


def base_tree(t: Target) -> Path:
    """The files of the pinned commit, exported once (no .git, so no history to read answers from)."""
    out = workdir() / "base" / f"{t.name}-{t.commit[:12]}"
    if (out / ".complete").exists():
        return out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    src = source_repo(t)
    archive = subprocess.run(
        ["git", "archive", "--format=tar", t.commit], cwd=src, check=True, capture_output=True
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(out)], input=archive, check=True)
    (out / ".complete").write_text(t.commit)
    return out
