-- The record of every benchmark run. PostgreSQL is the source of truth; files under the workdir
-- (worktrees, transcripts) are scratch that can be deleted at any time.
CREATE SCHEMA IF NOT EXISTS aeh;

CREATE TABLE IF NOT EXISTS aeh.runs (
  id          text PRIMARY KEY,
  task_set    text NOT NULL,
  budget_usd  numeric(12, 6) NOT NULL CHECK (budget_usd >= 0),
  config      jsonb NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS aeh.attempts (
  id              bigserial PRIMARY KEY,
  run_id          text NOT NULL REFERENCES aeh.runs (id),
  task_id         text NOT NULL,
  setup           text NOT NULL,
  sample          int NOT NULL,
  position        int NOT NULL,               -- launch order: every setup gets sample 1 of every task first
  state           text NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'running', 'done', 'failed', 'skipped')),
  worker          text,
  lease_until     timestamptz,
  tries           int NOT NULL DEFAULT 0,
  reserved_usd    numeric(12, 6) NOT NULL DEFAULT 0 CHECK (reserved_usd >= 0),   -- open reservation
  cost_usd        numeric(12, 6),                                                  -- settled agent spend
  judge_cost_usd  numeric(12, 6),
  abandoned_usd   numeric(12, 6) NOT NULL DEFAULT 0,   -- reservations of crashed tries, counted in full
  outcome         jsonb,
  grade           jsonb,
  patch           text,
  error           text,
  started_at      timestamptz,
  finished_at     timestamptz,
  UNIQUE (run_id, task_id, setup, sample)
);
CREATE INDEX IF NOT EXISTS attempts_queue ON aeh.attempts (run_id, state, position);

-- Append-only audit of money: every reservation, settlement and release.
CREATE TABLE IF NOT EXISTS aeh.spend (
  id          bigserial PRIMARY KEY,
  run_id      text NOT NULL REFERENCES aeh.runs (id),
  attempt_id  bigint NOT NULL REFERENCES aeh.attempts (id),
  kind        text NOT NULL CHECK (kind IN ('reserve', 'settle', 'release', 'abandon')),
  amount_usd  numeric(12, 6) NOT NULL,
  at          timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION aeh.no_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'aeh.spend is append-only'; END $$;
DROP TRIGGER IF EXISTS spend_append_only ON aeh.spend;
CREATE TRIGGER spend_append_only BEFORE UPDATE OR DELETE ON aeh.spend FOR EACH ROW EXECUTE FUNCTION aeh.no_update();
