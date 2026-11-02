"""Authoring helper for tasks (people only; agents never run this).

python scripts/task_dev.py tasks/dev/D01-x base     -> a scratch copy of the pinned commit
python scripts/task_dev.py tasks/dev/D01-x setup    -> writes setup.patch from the scratch copy's changes
python scripts/task_dev.py tasks/dev/D01-x state    -> a scratch copy of the task state
python scripts/task_dev.py tasks/dev/D01-x capture grader/reference.patch
                                                      -> writes the scratch copy's changes to that file
"""

from __future__ import annotations

import sys
from pathlib import Path

from aeh.config import workdir
from aeh.target import base_tree
from aeh.tasks import checkout, diff, git, load_task

task = load_task(Path(sys.argv[1]).resolve())
what = sys.argv[2]
scratch = workdir() / "authoring" / task.id
if what == "base":
    import shutil

    if scratch.exists():
        shutil.rmtree(scratch)
    shutil.copytree(base_tree(task.target), scratch, ignore=shutil.ignore_patterns(".complete"))
    git(scratch, "init", "-q", "-b", "main")
    git(scratch, "add", "-A")
    git(scratch, "commit", "-q", "-m", "base")
    print(scratch)
elif what == "setup":
    (task.dir / "setup.patch").write_text(diff(scratch))
    print("wrote", task.dir / "setup.patch")
elif what == "state":
    print(checkout(task, scratch))
elif what == "capture":
    out = task.dir / sys.argv[3]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(diff(scratch))
    git(scratch, "checkout", "-q", "--", ".")
    git(scratch, "clean", "-qfd")
    print("wrote", out)
