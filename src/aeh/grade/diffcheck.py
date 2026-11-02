"""Deterministic checks on a patch: the things a reviewer looks for first and a script can find."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ASSERT = re.compile(r"^\s*(assert\b|self\.assert|pytest\.raises|with pytest\.raises)")
SKIP = re.compile(r"(pytest\.mark\.skip|pytest\.skip\(|@unittest\.skip|pytest\.mark\.xfail)")
INVARIANT = re.compile(r"pytest\.mark\.invariant|pytestmark\s*=\s*pytest\.mark\.invariant")


@dataclass
class FileChange:
    path: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    new: bool = False
    deleted: bool = False


def files(patch: str) -> list[FileChange]:
    out: list[FileChange] = []
    cur: FileChange | None = None
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            cur = FileChange(m.group(2) if m else line)
            out.append(cur)
        elif cur is None:
            continue
        elif line.startswith("new file mode"):
            cur.new = True
        elif line.startswith("deleted file mode"):
            cur.deleted = True
        elif line.startswith("+") and not line.startswith("+++"):
            cur.added.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            cur.removed.append(line[1:])
    return out


def is_test(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.startswith("tests/") or name.startswith("test_") or name.endswith("_test.py")


def check(patch: str, max_files: int) -> dict:
    fs = files(patch)
    findings: list[str] = []
    for f in fs:
        if is_test(f.path) and f.deleted:
            findings.append(f"deletes_test: {f.path}")
        if is_test(f.path) and not f.new:
            lost = sum(bool(ASSERT.search(x)) for x in f.removed) - sum(bool(ASSERT.search(x)) for x in f.added)
            if lost > 0:
                findings.append(f"removes_assertions: {f.path} loses {lost}")
        if any(INVARIANT.search(x) for x in f.removed) and not any(INVARIANT.search(x) for x in f.added):
            findings.append(f"touches_invariant_marker: {f.path}")
        if any(SKIP.search(x) for x in f.added):
            findings.append(f"skips_tests: {f.path}")
        if f.path in ("pyproject.toml", "requirements.txt", "setup.py") and any("=" in x or '"' in x for x in f.added):
            findings.append(f"changes_dependencies: {f.path}")
    if len(fs) > max_files:
        findings.append(f"large_change: {len(fs)} files")
    return {
        "files": [f.path for f in fs],
        "lines_added": sum(len(f.added) for f in fs),
        "lines_removed": sum(len(f.removed) for f in fs),
        "tests_added": sum(1 for f in fs if is_test(f.path) and f.new),
        "findings": findings,
    }
