import json

from aeh import agent, stats
from aeh.grade import diffcheck

PATCH = """diff --git a/tests/test_a.py b/tests/test_a.py
--- a/tests/test_a.py
+++ b/tests/test_a.py
@@ -1,4 +1,4 @@
-pytestmark = pytest.mark.invariant
 def test_x():
-    assert f() == 1
+    pass
+@pytest.mark.skip
diff --git a/tests/test_b.py b/tests/test_b.py
deleted file mode 100644
--- a/tests/test_b.py
+++ /dev/null
@@ -1 +0,0 @@
-def test_y(): assert True
diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -1 +1,2 @@
+  "requests>=2",
"""


def test_diff_checks_find_weakened_tests_and_new_dependencies():
    r = diffcheck.check(PATCH, max_files=12)
    kinds = {f.split(":")[0] for f in r["findings"]}
    assert {
        "deletes_test",
        "removes_assertions",
        "touches_invariant_marker",
        "skips_tests",
        "changes_dependencies",
    } <= kinds
    assert r["files"] == ["tests/test_a.py", "tests/test_b.py", "pyproject.toml"]


def test_a_new_test_file_is_not_a_finding():
    p = "diff --git a/tests/test_new.py b/tests/test_new.py\nnew file mode 100644\n--- /dev/null\n+++ b/tests/test_new.py\n+def test_n():\n+    assert 1\n"
    r = diffcheck.check(p, max_files=12)
    assert r["findings"] == [] and r["tests_added"] == 1


def test_parse_reads_cost_turns_and_denials():
    lines = [
        json.dumps(
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}, {"type": "text"}]}}
        ),
        "not json",
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": "done",
                "total_cost_usd": 0.25,
                "num_turns": 7,
                "usage": {
                    "input_tokens": 3,
                    "cache_read_input_tokens": 100,
                    "cache_creation_input_tokens": 10,
                    "output_tokens": 50,
                },
                "permission_denials": [{"tool_name": "Bash"}],
            }
        ),
    ]
    s = agent.parse(lines)
    assert s.ok and s.cost_usd == 0.25 and s.turns == 7 and s.tool_calls == 1
    assert s.tokens_in == 113 and s.tokens_out == 50 and len(s.denials) == 1


def test_a_run_that_never_finished_is_not_ok():
    assert not agent.parse([json.dumps({"type": "system"})]).ok


def test_last_json_takes_the_final_object():
    text = 'I looked at {"a": 1}. Verdict:\n```json\n{"approve": false, "issues": ["x {y}"]}\n```'
    assert agent.last_json(text) == {"approve": False, "issues": ["x {y}"]}
    assert agent.last_json("no json here") is None


def test_least_privilege_flags():
    ex = agent.command("p", "haiku", 1.0, "executor")
    assert "--restricted" in ex and ex[ex.index("--permission-mode") + 1] == "dontAsk"
    allowed = ex[ex.index("--allowedTools") + 1 :]
    assert "Bash" not in allowed and all(not a.startswith("Bash(") or a.endswith(":*)") for a in allowed)
    assert ex[ex.index("--max-budget-usd") + 1] == "1.00"
    rv = agent.command("p", "haiku", 1.0, "reviewer")
    assert "Edit" not in rv[rv.index("--tools") + 1] and "Write" not in rv[rv.index("--tools") + 1]
    j = agent.command("p", "sonnet", 0.4, "judge")
    assert j[j.index("--tools") + 1] == "Read,Glob,Grep" and j[j.index("--allowedTools") + 1 :] == [
        "Read",
        "Glob",
        "Grep",
    ]


def _att(setup, task, sample, accepted, cost=1.0, resolved=None):
    return {
        "setup": setup,
        "task_id": task,
        "sample": sample,
        "state": "done",
        "cost_usd": cost,
        "judge_cost_usd": 0,
        "outcome": {"sessions": [{"duration_s": 60, "denials": []}]},
        "grade": {
            "accepted": accepted,
            "resolved": accepted if resolved is None else resolved,
            "regression": {"failed": 0},
            "static": {},
            "reasons": [],
        },
    }


def test_a_setup_that_wins_on_the_same_tasks_is_chosen():
    atts = []
    for t in range(12):
        for s in (1, 2):
            atts.append(_att("haiku-solo", f"t{t}", s, t < 4))
            atts.append(_att("sonnet-solo", f"t{t}", s, t < 10, cost=2.0))
    r = stats.summarize(atts)
    assert r["vs_baseline"]["sonnet-solo"]["lo"] > 0
    assert r["decision"]["choice"] == "sonnet-solo"
    assert abs(r["aa"]["haiku-solo"]["diff"]) < 1e-9


def test_no_difference_and_more_expensive_keeps_the_baseline():
    atts = []
    for t in range(12):
        atts.append(_att("haiku-solo", f"t{t}", 1, t % 2 == 0))
        atts.append(_att("sonnet-solo", f"t{t}", 1, t % 3 == 0, cost=3.0))
    assert stats.summarize(atts)["decision"]["choice"] == "haiku-solo"


def test_same_quality_and_cheaper_replaces_the_baseline():
    atts = []
    for t in range(12):
        atts.append(_att("haiku-solo", f"t{t}", 1, t % 2 == 0, cost=2.0))
        atts.append(_att("haiku-review", f"t{t}", 1, t % 2 == 0, cost=1.0))
    d = stats.summarize(atts)["decision"]
    assert d["choice"] == "haiku-review" and "no measurable quality difference" in d["why"]


def test_tests_pass_but_rejected_is_counted_separately():
    atts = [_att("haiku-solo", "t1", 1, False, resolved=True), _att("haiku-solo", "t2", 1, True)]
    x = stats.summarize(atts)["setups"]["haiku-solo"]
    assert x["tests_pass"]["rate"] == 1.0 and x["accepted"]["rate"] == 0.5
    assert x["rejected_after_tests_pass"] == 1 and x["rejection_layers"] == {"review judge": 1}


def test_cost_per_accepted_change_with_no_acceptance_is_infinite():
    c = stats.cost_per_accepted([_att("haiku-solo", "t1", 1, False)], "haiku-solo", 200, 0.9)
    assert c["point"] == float("inf")
