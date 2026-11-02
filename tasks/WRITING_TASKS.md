# Writing tasks

A task is a piece of work an engineer on the team could be handed: a bug report or a small feature
request against the target repository (`targets/<name>.yaml`, pinned to one commit). Agents get the
brief and a copy of the repository; a grader decides whether what they hand back would be merged.

You can write tasks without reading the harness code. Do not read `src/aeh`, `config/prompts` or
other task sets; you need only this file, the target repository and the commands below.

## What a task contains

```
tasks/<set>/<id>/
  task.yaml        id: <id>, title: "<one line>", kind: bug | feature, target: <target name>
  brief.md         what the agent is told, written like a ticket
  setup.patch      optional: turns the pinned commit into the task state (for example, adds the bug)
  grader/
    hidden_tests/test_hidden_<id>.py   tests the agent never sees
    reference.patch                     a change a maintainer would merge, against the task state
    mutants/<name>.patch                plausible wrong changes; the hidden tests must catch each
    mutants/why.yaml                    <name>: one line on what is wrong with it
    unmergeable/<name>.patch            optional: changes that pass the tests but should not be merged
    unmergeable/why.yaml                <name>: one line on why a maintainer would block it
```

## Rules

1. **The brief is the contract.** Hidden tests check only behaviour the brief states. If a test
   needs a status code, an error type, a name or a format, the brief says it.
2. **Realistic work.** Bugs a user could report, features a customer could ask for. Prefer work
   that touches more than one function, and areas where repository rules matter (AGENTS.md).
3. **Small enough.** A competent engineer finishes it in under an hour; the reference change is
   usually under 60 lines.
4. **Mutants are the mistakes people make**: the boundary case, the second code path, the wrong
   error shape, the fix in the wrong layer. At least two per task, each caught by the hidden tests.
5. **Unmergeable changes** pass every test and break a repository rule or do more than asked
   (hard-coded values, a bypassed safety rule, money as float, an unrelated change, a deleted test).
6. **No leaks.** Nothing in the brief or the task state may contain the answer. The task state is
   exported without history.
7. **Existing tests keep passing** in the task state, and with the reference change.

## Commands

```bash
python scripts/task_dev.py tasks/<set>/<id> base       # scratch copy of the pinned commit; edit it to add a bug
python scripts/task_dev.py tasks/<set>/<id> setup      # saves your edits as setup.patch
python scripts/task_dev.py tasks/<set>/<id> state      # scratch copy of the task state; edit it, then:
python scripts/task_dev.py tasks/<set>/<id> capture grader/reference.patch     # (or mutants/<name>.patch ...)
aeh prove --set <set> --no-judge                       # checks every rule above that a script can check
```

`aeh prove` must report the task as proven: the task state fails the hidden tests and passes its
own suite, the reference is accepted, every mutant is caught.
