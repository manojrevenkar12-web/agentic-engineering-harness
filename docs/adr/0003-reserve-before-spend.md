# 3. Reserve the worst case before an attempt starts; PostgreSQL is the record

Status: accepted

## Decision

Before an attempt starts, its worst case (the sum of its sessions' caps plus the judge's cap) is
reserved in PostgreSQL in the same transaction that leases it, and only if settled spend plus open
reservations plus the reservation stays within the run's budget. When the attempt ends, the actual
cost is settled and the reservation released. The spend log is append-only.

A worker that dies leaves its lease to expire and its reservation open. Whoever takes the attempt
over counts that reservation as spent ("abandoned"), because the money may have been spent and the
harness cannot know. Results are written only by the worker that holds the lease.

## Consequences

- `committed <= budget` holds at every moment, not only at the end (tested with crashes and with
  attempts that spend their full cap).
- A budget that is nearly spent runs fewer attempts at a time; attempts that cannot fit are marked
  `skipped`, never silently dropped.
- Launch order interleaves setups and tasks (sample 1 of everything first), so a run cut short by
  its budget still compares setups on the same tasks.
