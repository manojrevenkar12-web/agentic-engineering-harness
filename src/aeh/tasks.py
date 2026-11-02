"""Tasks: a brief an agent may read, and a task state of the target repository to work in.

Each task lives in tasks/<set>/<id>/:
    task.yaml     id, title, kind, target
    brief.md      what the agent is told (a ticket, written the way the team writes them)
    setup.patch   applied to the pinned commit to create the task state (agents never see it)
    grader/       hidden tests, a reference change, wrong changes and unmergeable changes;
                  only aeh.grade and aeh.prove read it (tests/test_isolation.py checks)

The task state is a fresh git repository with one commit, so `git log` and `git diff` show nothing
but the agent's own work.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import ROOT, workdir
from .target import Target, base_tree, load_target


def sets_dir() -> Path:
    return Path(os.environ.get("AEH_TASKS_DIR") or ROOT / "tasks")


GIT_ID = ["-c", "user.name=aeh", "-c", "user.email=aeh@localhost", "-c", "commit.gpgsign=false"]


@dataclass(frozen=True)
class Task:
    id: str
    set: str
    title: str
    kind: str
    target_name: str
    dir: Path

    @property
    def brief(self) -> str:
        return (self.dir / "brief.md").read_text().strip()

    @property
    def target(self) -> Target:
        return load_target(self.target_name)


def load_task(path: Path) -> Task:
    raw = yaml.safe_load((path / "task.yaml").read_text())
    return Task(raw["id"], path.parent.name, raw["title"], raw["kind"], raw["target"], path)


def load_set(name: str) -> list[Task]:
    d = sets_dir() / name
    return [load_task(p) for p in sorted(d.iterdir()) if (p / "task.yaml").exists()]


def git(cwd: Path, *args: str, check: bool = True, input: str | None = None) -> str:
    r = subprocess.run(["git", *GIT_ID, *args], cwd=cwd, capture_output=True, text=True, check=False, input=input)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {r.stderr.strip()}")
    return r.stdout


def state_template(task: Task) -> Path:
    """The task state, built once per task and copied for every attempt."""
    out = workdir() / "states" / task.set / task.id
    setup = task.dir / "setup.patch"
    stamp = f"{task.target.commit}:{setup.stat().st_mtime_ns if setup.exists() else 0}"
    if (out / ".git").exists() and (out / ".git" / "aeh-stamp").read_text() == stamp:
        return out
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(base_tree(task.target), out, ignore=shutil.ignore_patterns(".complete"))
    git(out, "init", "-q", "-b", "main")
    if setup.exists() and setup.read_text().strip():
        git(out, "apply", "--whitespace=nowarn", str(setup))
    git(out, "add", "-A")
    git(out, "commit", "-q", "-m", "task state")
    (out / ".git" / "aeh-stamp").write_text(stamp)
    return out


def checkout(task: Task, dest: Path) -> Path:
    """A private copy of the task state for one attempt (or one grading run)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(state_template(task), dest, symlinks=True)
    return dest


def diff(repo: Path) -> str:
    """Everything changed in the working tree against the task state, new files included."""
    git(repo, "add", "-A", "-N")
    return git(repo, "diff", "--binary", "HEAD")


def apply(repo: Path, patch: str) -> bool:
    if not patch.strip():
        return True
    r = subprocess.run(
        ["git", *GIT_ID, "apply", "--whitespace=nowarn", "-"], cwd=repo, input=patch, text=True, capture_output=True
    )
    return r.returncode == 0
