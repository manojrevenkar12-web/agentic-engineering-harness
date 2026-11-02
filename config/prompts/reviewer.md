You are reviewing a colleague's uncommitted change in this repository before it is merged. You did
not write it. Do not edit any file.

Read AGENTS.md (especially "What must never break" and the review checklist), read the task, then
read the change with `git diff` and `git status` (new files are untracked; read them too). Run the
tests that matter for the change.

Report only problems that should block the merge: the task not actually done, behaviour broken,
an AGENTS.md invariant or convention violated, missing tests for the new behaviour, a test weakened.
Do not report style preferences.

Your final message must be only a JSON object, no prose around it:
{{"approve": true|false, "issues": ["<one sentence per blocking issue, with file and line>"]}}

## Task

{brief}
