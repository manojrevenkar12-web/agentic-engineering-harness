Bug in production health monitoring (`mrp.health.Health`): after a model has been taken out of
rotation for a task and an operator puts it back with `restore()` (after re-evaluating it), the very
next checked answer for that model takes it out of rotation again, even when that answer passed.

After `restore()`, the model must be judged only on answers observed after the restore: it needs
the usual minimum number of new samples before it can be excluded again. If it really is still bad,
it must be excluded again once those samples show it.
