import { taskName } from "../../shared/lib/labels";
import type { Proof } from "../../shared/lib/results";
import s from "./graders.module.css";

const layerName: Record<string, string> = {
  tests: "tests",
  static: "static checks",
  diff: "diff checks",
  judge: "review judge",
  none: "nothing",
};

/** Before any agent is graded: every task's grader rejects known-wrong changes and accepts the reference. */
export function Graders({ p }: { p: Proof }) {
  const caught = p.unmergeable_rejected_by;
  return (
    <div>
      <div className={s.grid}>
        <div className={s.fact}>
          <b>
            {p.proven}/{p.tasks}
          </b>
          <span>tasks proven: the bug is real, the suite is green, the reference is accepted</span>
        </div>
        <div className={s.fact}>
          <b>
            {p.mutants_caught}/{p.mutants}
          </b>
          <span>plausible wrong changes caught by the hidden tests</span>
        </div>
        <div className={s.fact}>
          <b>
            {p.unmergeable_rejected}/{p.unmergeable}
          </b>
          <span>
            test-passing but unmergeable changes stopped ({caught.judge ?? 0} by the review judge, {caught.diff ?? 0} by diff checks,{" "}
            {caught.static ?? 0} by static checks)
          </span>
        </div>
        <div className={s.fact}>
          <b>{p.judge_passes_references}</b>
          <span>reference changes the review judge let through</span>
        </div>
      </div>
      {/* biome-ignore lint/a11y/noNoninteractiveTabindex: a table that scrolls sideways must be reachable by keyboard */}
      <section className={s.wrap} aria-label={`Grader proofs, ${p.set} set`} tabIndex={0}>
        <table className={s.table}>
          <thead>
            <tr>
              <th scope="col">Task</th>
              <th scope="col">Hidden tests failing before</th>
              <th scope="col">Wrong changes caught</th>
              <th scope="col">Unmergeable changes stopped by</th>
            </tr>
          </thead>
          <tbody>
            {p.tasks_detail.map((t) => (
              <tr key={t.task} data-testid={`proof-${t.task}`}>
                <th scope="row">{taskName(t.task)}</th>
                <td>{t.state.hidden_failed}</td>
                <td className={t.mutants.every((m) => m.caught) ? s.ok : s.no}>
                  {t.mutants.filter((m) => m.caught).length} of {t.mutants.length}
                </td>
                <td>
                  {t.unmergeable.length
                    ? t.unmergeable.map((u) => (
                        <span key={u.name} className={u.rejected_by === "none" ? `${s.layer} ${s.no}` : s.layer} title={u.why}>
                          {layerName[u.rejected_by] ?? u.rejected_by}
                        </span>
                      ))
                    : "none written"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
