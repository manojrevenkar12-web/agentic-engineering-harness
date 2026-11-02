#!/usr/bin/env python3
"""A stand-in for `claude -p` in tests: same flags, same stream-json events, no model and no cost.

The executor applies the patch named in AEH_FAKE_SCRIPT (a JSON file mapping a substring of the
brief to a patch file); reviewers approve; selectors pick 1; judges answer per the script's
"judge" entry. AEH_FAKE_COST is the cost every session reports.
"""

import json
import os
import subprocess
import sys

args = sys.argv[1:]
prompt = sys.stdin.read()
tools = args[args.index("--tools") + 1] if "--tools" in args else ""
script = json.load(open(os.environ["AEH_FAKE_SCRIPT"])) if os.environ.get("AEH_FAKE_SCRIPT") else {}
cost = float(os.environ.get("AEH_FAKE_COST", "0.01"))


def emit(ev):
    print(json.dumps(ev), flush=True)


emit({"type": "system", "subtype": "init", "cwd": os.getcwd()})
if "Do not edit any file" in prompt and "choice" in prompt:
    result = '{"choice": 1, "reason": "fake"}'
elif "Do not edit any file" in prompt:
    result = '{"approve": true, "issues": []}'
elif "merges changes into this repository" in prompt:  # the judge
    blocked = [b for b in script.get("judge_block", []) if b in prompt]
    result = json.dumps({"mergeable": not blocked, "blocking": [f"contains {b}" for b in blocked]})
else:
    result = "no matching patch"
    for key, patch in script.get("patches", {}).items():
        if key in prompt:
            emit({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Edit", "input": {}}]}})
            if os.environ.get("AEH_FAKE_SLEEP"):
                import time

                time.sleep(float(os.environ["AEH_FAKE_SLEEP"]))
            subprocess.run(["git", "apply", patch], check=True)
            result = "applied"
            break
emit(
    {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": result,
        "num_turns": 2,
        "total_cost_usd": cost,
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        "permission_denials": [],
    }
)
