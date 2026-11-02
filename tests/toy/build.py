"""A tiny target repository, task set and target definition for tests (no services, runs in seconds)."""

from __future__ import annotations

import subprocess
from pathlib import Path

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]

PRICE = '''from decimal import Decimal


def total(prices: list[Decimal], discount: Decimal) -> Decimal:
    """Sum of prices minus a discount share, never below zero."""
    return max(Decimal(0), sum(prices, Decimal(0)) * (1 - discount))
'''

TEST = """from decimal import Decimal

from shop.price import total


def test_total():
    assert total([Decimal("2"), Decimal("3")], Decimal("0")) == Decimal("5")
"""

HIDDEN = """from decimal import Decimal

from shop.price import total


def test_discount_over_one_is_refused():
    import pytest

    with pytest.raises(ValueError):
        total([Decimal("1")], Decimal("1.5"))


def test_normal_discount():
    assert total([Decimal("10")], Decimal("0.25")) == Decimal("7.5")
"""

REFERENCE_CODE = PRICE.replace(
    "    return max(Decimal(0), sum(prices, Decimal(0)) * (1 - discount))\n",
    '    if not Decimal(0) <= discount <= Decimal(1):\n        raise ValueError("discount must be a share between 0 and 1")\n'
    "    return max(Decimal(0), sum(prices, Decimal(0)) * (1 - discount))\n",
)
MUTANT_CODE = PRICE.replace("    return max(", "    discount = min(discount, Decimal(1))\n    return max(")
UNMERGEABLE_CODE = REFERENCE_CODE.replace(
    "from decimal import Decimal\n", "from decimal import Decimal\n\nimport requests  # noqa: F401\n"
)


def _diff(repo: Path, path: str, text: str) -> str:
    p = repo / path
    old = p.read_text()
    p.write_text(text)
    d = subprocess.run([*GIT, "diff"], cwd=repo, capture_output=True, text=True, check=True).stdout
    p.write_text(old)
    return d


def build(root: Path) -> dict[str, Path]:
    repo = root / "toy-repo"
    (repo / "shop").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "shop" / "__init__.py").write_text("")
    (repo / "shop" / "price.py").write_text(PRICE)
    (repo / "tests" / "__init__.py").write_text("")
    (repo / "tests" / "test_price.py").write_text(TEST)
    (repo / "AGENTS.md").write_text("# Rules\n\nMoney is Decimal. No new dependencies.\n")
    subprocess.run([*GIT, "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run([*GIT, "add", "-A"], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "toy"], cwd=repo, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    targets = root / "targets"
    targets.mkdir()
    (targets / "toy.yaml").write_text(
        f'name: toy\nrepo: {repo}\ncommit: {commit}\nenv:\n  PYTHONPATH: "."\ndatabase_extensions: []\ncommands:\n'
        '  tests: [python3, -m, pytest, -q, -p, "no:cacheprovider"]\n  format: [python3, -c, "pass"]\n  lint: [python3, -c, "pass"]\n  types: [python3, -c, "pass"]\n'
    )
    t = root / "tasks" / "toyset" / "T01-discount"
    (t / "grader" / "hidden_tests").mkdir(parents=True)
    (t / "grader" / "mutants").mkdir()
    (t / "grader" / "unmergeable").mkdir()
    (t / "task.yaml").write_text("id: T01-discount\ntitle: Refuse discounts over 100%\nkind: bug\ntarget: toy\n")
    (t / "brief.md").write_text(
        "A discount share above 1 makes totals zero. Raise ValueError for a discount outside [0, 1].\n"
    )
    (t / "setup.patch").write_text("")
    (t / "grader" / "hidden_tests" / "test_hidden_t01.py").write_text(HIDDEN)
    ref = _diff(repo, "shop/price.py", REFERENCE_CODE)
    (t / "grader" / "reference.patch").write_text(ref)
    (t / "grader" / "mutants" / "clamps.patch").write_text(_diff(repo, "shop/price.py", MUTANT_CODE))
    (t / "grader" / "unmergeable" / "adds_dependency.patch").write_text(_diff(repo, "shop/price.py", UNMERGEABLE_CODE))
    return {
        "repo": repo,
        "targets": targets,
        "tasks": root / "tasks",
        "reference": t / "grader" / "reference.patch",
        "mutant": t / "grader" / "mutants" / "clamps.patch",
    }
