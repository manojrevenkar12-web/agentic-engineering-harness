"""A task's grader directory: hidden tests, the reference change, wrong and unmergeable changes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from ..tasks import Task


@dataclass(frozen=True)
class Variant:
    name: str
    patch: str
    why: str


@dataclass(frozen=True)
class GraderFiles:
    hidden_tests: list[Path]
    reference: str
    mutants: list[Variant]
    unmergeable: list[Variant]


def _variants(d: Path) -> list[Variant]:
    if not d.exists():
        return []
    notes = yaml.safe_load((d / "why.yaml").read_text()) if (d / "why.yaml").exists() else {}
    return [Variant(p.stem, p.read_text(), str((notes or {}).get(p.stem, ""))) for p in sorted(d.glob("*.patch"))]


def grader_files(task: Task) -> GraderFiles:
    g = task.dir / "grader"
    return GraderFiles(
        sorted((g / "hidden_tests").glob("test_*.py")),
        (g / "reference.patch").read_text(),
        _variants(g / "mutants"),
        _variants(g / "unmergeable"),
    )
