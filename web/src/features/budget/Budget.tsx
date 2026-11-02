import { usd } from "../../shared/lib/format";
import { setupName } from "../../shared/lib/labels";
import type { Results } from "../../shared/lib/results";
import s from "../graders/graders.module.css";

/** What the benchmark cost, and the checks that the money was accounted for. */
export function Budget({ r }: { r: Results }) {
  const dev = r.dev!;
  const spent = Object.values(dev.setups).reduce((a, x) => a + x.cost_usd_total, 0);
  const denied = Object.values(dev.setups).reduce((a, x) => a + x.denied_actions, 0);
  const ok = dev.ledgers.every((l) => l.within_budget && l.open_reservations_match && l.settled_match);
  const fastest = Object.entries(dev.setups)
    .filter(([, x]) => x.median_minutes != null)
    .sort((a, b) => (a[1].median_minutes ?? 0) - (b[1].median_minutes ?? 0))[0];
  return (
    <div className={s.grid}>
      <div className={s.fact}>
        <b>{usd(spent)}</b>
        <span>spent on the dev benchmark, agents and review judge, at list prices</span>
      </div>
      <div className={s.fact}>
        <b>{ok ? "Balanced" : "Check"}</b>
        <span>
          {dev.ledgers.map((l) => `${l.run}: ${usd(l.committed_usd)} of ${usd(l.budget_usd)} budget`).join("; ")}; the spend log matches the record
        </span>
      </div>
      <div className={s.fact}>
        <b>{denied}</b>
        <span>actions refused by the agents' permissions (network, installs, files outside the worktree)</span>
      </div>
      {fastest ? (
        <div className={s.fact}>
          <b>{fastest[1].median_minutes} min</b>
          <span>median agent time per attempt, fastest setup ({setupName(fastest[0], r.setups[fastest[0]])})</span>
        </div>
      ) : null}
    </div>
  );
}
