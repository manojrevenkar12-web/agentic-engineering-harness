import json
import os
from pathlib import Path

import pytest

HERE = Path(__file__).parent
DB = os.environ.get("AEH_TEST_DATABASE_URL")  # e.g. postgresql://postgres@localhost:5444/aeh_test


@pytest.fixture
def toy(tmp_path, monkeypatch):
    """A toy target and task set, the fake agent, and (when a database is given) a private record."""
    from tests.toy.build import build

    paths = build(tmp_path)
    script = tmp_path / "script.json"
    script.write_text(
        json.dumps({"patches": {"discount": str(paths["reference"])}, "judge_block": ['print("discount"']})
    )
    monkeypatch.setenv("AEH_TASKS_DIR", str(paths["tasks"]))
    monkeypatch.setenv("AEH_TARGETS_DIR", str(paths["targets"]))
    monkeypatch.setenv("AEH_TARGET_TOY", str(paths["repo"]))
    monkeypatch.setenv("AEH_WORKDIR", str(tmp_path / "work"))
    monkeypatch.setenv("AEH_AGENT_BIN", str(HERE / "fake_agent.py"))
    monkeypatch.setenv("AEH_FAKE_SCRIPT", str(script))
    monkeypatch.setenv("AEH_SLOT_PREFIX", "aeh_test_slot")
    monkeypatch.setenv("AEH_REPORTS_DIR", str(tmp_path / "reports"))
    if DB:
        base = DB.rsplit("/", 1)[0]
        monkeypatch.setenv("AEH_DATABASE_ADMIN_URL", base + "/postgres")
        monkeypatch.setenv("AEH_RECORD_URL", DB)
        import psycopg

        with psycopg.connect(DB, autocommit=True) as c:  # every test starts from an empty record
            c.execute("DROP SCHEMA IF EXISTS aeh CASCADE")
    paths["script"] = script
    return paths


def needs_db():
    return pytest.mark.skipif(not DB, reason="needs AEH_TEST_DATABASE_URL")
