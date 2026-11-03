/** Shape of reports/results.json, written by `aeh report`. The dashboard only reads it. */

export interface Interval {
  rate: number | null;
  lo: number | null;
  hi: number | null;
}

export interface Diff {
  tasks: number;
  diff?: number;
  lo?: number;
  hi?: number;
}

export interface SetupResult {
  attempts: number;
  failed: number;
  tasks: number;
  accepted: Interval;
  tests_pass: Interval;
  rejected_after_tests_pass: number;
  tests_pass_count: number;
  rejection_layers: Record<string, number>;
  /** Rejected only by `ruff format`: a formatter hook would have accepted them. Older results lack it. */
  format_only?: number;
  cost_usd_total: number;
  cost_usd_per_attempt: number;
  cost_per_accepted: { point?: number | null; lo?: number | null; hi?: number | null };
  median_minutes: number | null;
  denied_actions: number;
}

export interface Ledger {
  run: string;
  committed_usd: number;
  budget_usd: number;
  within_budget: boolean;
  open_reservations_match: boolean;
  settled_match: boolean;
  abandoned_usd: number;
}

export interface Dev {
  confidence: number;
  setups: Record<string, SetupResult>;
  vs_baseline: Record<string, Diff>;
  aa: Record<string, Diff>;
  decision: { choice: string | null; why: string };
  per_task: Record<string, Record<string, { accepted: number; of: number }>>;
  ledgers: Ledger[];
}

export interface ProofTask {
  task: string;
  proven: boolean;
  state: { hidden_failed: number; suite_failed: number; suite_passed: number };
  reference: { accepted: boolean; judge: boolean | null };
  mutants: { name: string; caught: boolean; why: string }[];
  unmergeable: { name: string; tests_pass: boolean; rejected_by: string; why: string }[];
}

export interface Proof {
  set: string;
  tasks: number;
  proven: number;
  mutants: number;
  mutants_caught: number;
  unmergeable: number;
  unmergeable_rejected: number;
  unmergeable_rejected_by: Record<string, number>;
  judge_passes_references: string;
  judge_cost_usd: number;
  tasks_detail: ProofTask[];
}

export interface Heldout {
  recorded_at: string;
  run: string;
  tasks: string[];
  setups: Record<string, { attempts: number; accepted: number; tests_pass: number; cost_usd: number; per_task: Record<string, boolean> }>;
  ledger: Omit<Ledger, "run">;
  skipped_for_budget: number;
}

export interface SetupConfig {
  model: string;
  flow: "solo" | "review" | "best_of";
  n?: number;
}

export interface Results {
  generated_at: string;
  proofs: Record<string, Proof | null>;
  dev: Dev | null;
  heldout: Heldout | null;
  setups: Record<string, SetupConfig>;
  decision_rule: { baseline: string; confidence: number; max_quality_loss: number };
}

export function isResults(x: unknown): x is Results {
  if (typeof x !== "object" || x === null) return false;
  const r = x as Record<string, unknown>;
  return typeof r.generated_at === "string" && typeof r.proofs === "object" && "dev" in r;
}
