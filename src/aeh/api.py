"""Read-only API over the record, for the dashboard and for people watching a run."""

from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException

from . import stats, store
from .config import reports_dir

app = FastAPI(title="agentic engineering harness")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/results")
def results() -> dict:
    p = reports_dir() / "results.json"
    if not p.exists():
        raise HTTPException(404, "no report yet; run aeh report")
    return json.loads(p.read_text())


@app.get("/runs/{run_id}")
def run(run_id: str) -> dict:
    conn = store.connect()
    rows = store.attempts(conn, run_id)
    if not rows:
        raise HTTPException(404, f"no run {run_id}")
    states: dict[str, int] = {}
    for r in rows:
        states[r["state"]] = states.get(r["state"], 0) + 1
    done = [r for r in rows if r["state"] in ("done", "failed")]
    return {
        "run": run_id,
        "states": states,
        "ledger": store.ledger_check(conn, run_id),
        "summary": stats.summarize(done) if done else None,
    }
