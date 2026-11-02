"""What an agent can reach: the agent-facing code never touches a task's grader files."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "aeh"
AGENT_SIDE = ["agent.py", "flows.py", "tasks.py", "services.py", "target.py", "solve.py"]


def test_agent_side_never_imports_grading_or_proofs():
    for name in AGENT_SIDE:
        tree = ast.parse((SRC / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")
                assert "prove" not in mod and not (mod[:1] == ["grade"] and name != "solve.py"), (
                    f"{name}: {node.module}"
                )
                if name == "solve.py":  # daily use may run the free diff checks, never the grader files
                    assert node.module != "grade.files", name


def test_agent_side_never_names_the_grader_directory():
    for name in AGENT_SIDE:
        text = (SRC / name).read_text()
        code = "\n".join(line for line in text.splitlines() if not line.strip().startswith(("#", '"""')))
        assert '"grader"' not in code and "'grader'" not in code, name


def test_the_task_state_has_no_history(toy):
    from aeh.tasks import git, load_set, state_template

    task = load_set("toyset")[0]
    repo = state_template(task)
    assert git(repo, "log", "--oneline").strip().count("\n") == 0
    assert not (repo / "grader").exists() and not list(repo.rglob("test_hidden_*"))
