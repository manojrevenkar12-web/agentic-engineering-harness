"""Settings live in config/*.yaml. Environment variables override paths and service URLs only."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"

_ENV = {
    ("harness", "workdir"): "AEH_WORKDIR",
    ("harness", "services", "database_admin_url"): "AEH_DATABASE_ADMIN_URL",
    ("harness", "services", "redis_url"): "AEH_REDIS_URL",
    ("harness", "services", "record_url"): "AEH_RECORD_URL",
    ("agent", "binary"): "AEH_AGENT_BIN",
}


@cache
def _raw(name: str) -> dict[str, Any]:
    return yaml.safe_load((CONFIG / f"{name}.yaml").read_text())


def load(name: str) -> dict[str, Any]:
    """A fresh copy of config/<name>.yaml with environment overrides applied."""
    data = yaml.safe_load(yaml.safe_dump(_raw(name)))
    for path, var in _ENV.items():
        if path[0] == name and os.environ.get(var):
            node = data
            for k in path[1:-1]:
                node = node[k]
            node[path[-1]] = os.environ[var]
    return data


def prompt(name: str) -> str:
    return (CONFIG / "prompts" / f"{name}.md").read_text()


def workdir() -> Path:
    p = Path(load("harness")["workdir"])
    p.mkdir(parents=True, exist_ok=True)
    return p


def reports_dir() -> Path:
    """Generated results: reports/ in the repository (AEH_REPORTS_DIR overrides, e.g. in tests)."""
    return Path(os.environ.get("AEH_REPORTS_DIR") or ROOT / "reports")
