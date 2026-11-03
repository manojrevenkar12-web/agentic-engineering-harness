"""From graded attempts to a decision, with the uncertainty that a dozen tasks really carry.

Tasks are the unit of resampling: a setup that is better on the same tasks is better; a setup that
got luckier tasks is not. Comparisons are paired by task, intervals come from the bootstrap over
tasks, and an A/A comparison of the same setup with itself shows how large a difference noise
alone produces.
"""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import median

import numpy as np

from .config import load


def _cells(attempts: list[dict], key: str = "accepted") -> dict[str, dict[str, list[float]]]:
    out: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for a in attempts:
        if a["state"] != "done":
            if a["state"] == "failed":  # a crashed attempt delivered nothing
                out[a["setup"]][a["task_id"]].append(0.0)
            continue
        g = a["grade"] or {}
        if key == "accepted":
            v = bool(g.get("accepted"))
        elif key == "accepted_if_formatted":
            # Exact, not estimated: these attempts passed every other check and the judge called them
            # mergeable; `ruff format` changes layout only. What a formatter hook would have turned around.
            v = bool(g.get("accepted")) or g.get("reasons") == ["static: format"]
        elif key == "resolved":
            v = bool(g.get("resolved")) and not (g.get("regression") or {}).get("failed")
        else:
            raise ValueError(key)
        out[a["setup"]][a["task_id"]].append(float(v))
    return out


def _cost(a: dict) -> float:
    return float(a.get("cost_usd") or 0) + float(a.get("judge_cost_usd") or 0)


def bootstrap_diff(a: dict[str, list[float]], b: dict[str, list[float]], n: int, conf: float, seed: int = 11) -> dict:
    tasks = sorted(set(a) & set(b))
    if not tasks:
        return {"tasks": 0}
    d = np.array([np.mean(a[t]) - np.mean(b[t]) for t in tasks])
    rng = np.random.default_rng(seed)
    boots = d[rng.integers(0, len(d), size=(n, len(d)))].mean(axis=1)
    lo, hi = np.quantile(boots, [(1 - conf) / 2, 1 - (1 - conf) / 2])
    return {"tasks": len(tasks), "diff": float(d.mean()), "lo": float(lo), "hi": float(hi)}


def bootstrap_rate(cells: dict[str, list[float]], n: int, conf: float, seed: int = 13) -> tuple[float, float, float]:
    tasks = sorted(cells)
    if not tasks:
        return (math.nan, math.nan, math.nan)
    p = np.array([np.mean(cells[t]) for t in tasks])
    rng = np.random.default_rng(seed)
    boots = p[rng.integers(0, len(p), size=(n, len(p)))].mean(axis=1)
    lo, hi = np.quantile(boots, [(1 - conf) / 2, 1 - (1 - conf) / 2])
    return float(p.mean()), float(lo), float(hi)


def cost_per_accepted(attempts: list[dict], setup: str, n: int, conf: float, seed: int = 17) -> dict:
    by_task: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for a in attempts:
        if a["setup"] == setup and a["state"] in ("done", "failed"):
            by_task[a["task_id"]].append((_cost(a), float(bool((a.get("grade") or {}).get("accepted")))))
    tasks = sorted(by_task)
    if not tasks:
        return {}
    cost = np.array([sum(c for c, _ in by_task[t]) for t in tasks])
    acc = np.array([sum(x for _, x in by_task[t]) for t in tasks])
    point = float(cost.sum() / acc.sum()) if acc.sum() else math.inf
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(tasks), size=(n, len(tasks)))
    c, k = cost[idx].sum(axis=1), acc[idx].sum(axis=1)
    ratio = np.sort(np.where(k > 0, c / np.maximum(k, 1e-9), np.inf))  # order statistics: inf stays inf
    lo, hi = ratio[int((1 - conf) / 2 * (n - 1))], ratio[int((1 - (1 - conf) / 2) * (n - 1))]
    return {"point": point, "lo": float(lo), "hi": float(hi)}


def summarize(attempts: list[dict]) -> dict:
    cfg = load("decision")
    n, conf = int(cfg["bootstrap_samples"]), float(cfg["confidence"])
    acc, res = _cells(attempts, "accepted"), _cells(attempts, "resolved")
    fmt = _cells(attempts, "accepted_if_formatted")
    setups = sorted({a["setup"] for a in attempts})
    out: dict = {"setups": {}, "confidence": conf}
    for s in setups:
        mine = [a for a in attempts if a["setup"] == s and a["state"] in ("done", "failed")]
        if not mine:
            continue
        rate, lo, hi = bootstrap_rate(acc[s], n, conf)
        rrate, rlo, rhi = bootstrap_rate(res[s], n, conf)
        frate, flo, fhi = bootstrap_rate(fmt[s], n, conf)
        graded = [a for a in mine if a["state"] == "done"]
        passing = [
            a
            for a in graded
            if (a["grade"] or {}).get("resolved") and not ((a["grade"] or {}).get("regression") or {}).get("failed")
        ]
        rejected = [a for a in passing if not (a["grade"] or {}).get("accepted")]
        durations = [sum(x.get("duration_s", 0) for x in (a["outcome"] or {}).get("sessions", [])) for a in graded]
        out["setups"][s] = {
            "attempts": len(mine),
            "failed": sum(a["state"] == "failed" for a in mine),
            "tasks": len(acc[s]),
            "accepted": {"rate": rate, "lo": lo, "hi": hi},
            "tests_pass": {"rate": rrate, "lo": rlo, "hi": rhi},
            "rejected_after_tests_pass": len(rejected),
            "tests_pass_count": len(passing),
            "rejection_layers": _layers(rejected),
            # Not a re-grade: the attempts whose only finding was `ruff format`. A formatter hook would have
            # turned them into accepted changes, so this separates a discipline gap from a quality gap.
            "format_only": sum((a["grade"] or {}).get("reasons") == ["static: format"] for a in rejected),
            "accepted_if_formatted": {"rate": frate, "lo": flo, "hi": fhi},
            "cost_usd_total": round(sum(_cost(a) for a in mine), 4),
            "cost_usd_per_attempt": round(sum(_cost(a) for a in mine) / len(mine), 4),
            "cost_per_accepted": cost_per_accepted(attempts, s, n, conf),
            "median_minutes": round(median(durations) / 60, 2) if durations else None,
            "denied_actions": sum(
                len(x.get("denials", [])) for a in graded for x in (a["outcome"] or {}).get("sessions", [])
            ),
        }
    base = cfg["baseline"]
    out["vs_baseline"] = {
        s: bootstrap_diff(acc[s], acc[base], n, conf) for s in out["setups"] if s != base and base in acc
    }
    out["vs_baseline_if_formatted"] = {
        s: bootstrap_diff(fmt[s], fmt[base], n, conf) for s in out["setups"] if s != base and base in fmt
    }
    out["aa"] = _aa(attempts, n, conf)
    out["decision"] = decide(out, base, float(cfg["max_quality_loss"]))
    out["per_task"] = {
        s: {t: {"accepted": sum(v), "of": len(v)} for t, v in sorted(acc[s].items())} for s in out["setups"]
    }
    return out


def _layers(rejected: list[dict]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for a in rejected:
        g = a["grade"] or {}
        if not all(v.get("ok") for v in (g.get("static") or {}).values()):
            out["static checks"] += 1
        elif any(
            r.split(":")[0] in ("deletes_test", "removes_assertions", "touches_invariant_marker", "skips_tests")
            for r in g.get("reasons", [])
        ):
            out["diff checks"] += 1
        else:
            out["review judge"] += 1
    return dict(out)


def _aa(attempts: list[dict], n: int, conf: float) -> dict:
    """Sample 1 against sample 2 of the same setup, paired by task: the size of pure noise."""
    out = {}
    for s in sorted({a["setup"] for a in attempts}):
        one: dict[str, list[float]] = defaultdict(list)
        two: dict[str, list[float]] = defaultdict(list)
        for a in attempts:
            if a["setup"] != s or a["state"] not in ("done", "failed") or a["sample"] > 2:
                continue
            v = float(bool((a.get("grade") or {}).get("accepted")))
            (one if a["sample"] == 1 else two)[a["task_id"]].append(v)
        if set(one) & set(two):
            out[s] = bootstrap_diff(two, one, n, conf)
    return out


def decide(summary: dict, base: str, max_loss: float) -> dict:
    """Apply config/decision.yaml: better, or as good and cheaper; otherwise keep the baseline."""
    if base not in summary["setups"]:
        return {"choice": None, "why": f"baseline {base} has no results"}
    b = summary["setups"][base]
    best, why = base, "no candidate beat the baseline by the decision rule"
    best_cost = b["cost_per_accepted"].get("point", math.inf)
    for s, d in summary.get("vs_baseline", {}).items():
        if not d.get("tasks"):
            continue
        c = summary["setups"][s]["cost_per_accepted"].get("point", math.inf)
        if d["lo"] > 0 and (best == base or c < best_cost):
            best, best_cost, why = (
                s,
                c,
                f"accepted rate {d['diff']:+.0%} over {base} (interval {d['lo']:+.0%} to {d['hi']:+.0%})",
            )
        elif d["lo"] > -max_loss and d["lo"] <= 0 <= d["hi"] and c < best_cost and best == base:
            best, best_cost, why = (
                s,
                c,
                f"no measurable quality difference, ${c:.2f} per accepted change vs ${b['cost_per_accepted'].get('point', math.inf):.2f}",
            )
    return {"choice": best, "why": why}
