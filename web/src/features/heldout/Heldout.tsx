import { usd } from "../../shared/lib/format";
import { setupName, taskName } from "../../shared/lib/labels";
import type { Heldout as H, SetupConfig } from "../../shared/lib/results";
import s from "../tasks/tasks.module.css";

/** The blind set, run once with the setups the benchmark chose between. */
export function Heldout({ h, setups }: { h: H; setups: Record<string, SetupConfig> }) {
  const keys = Object.keys(h.setups);
  return (
    <div>
      <p>
        Recorded {new Date(h.recorded_at).toLocaleDateString("en-GB", { dateStyle: "long" })} and kept as recorded.{" "}
        {keys.map((k) => `${setupName(k, setups[k])}: ${h.setups[k].accepted} of ${h.setups[k].attempts} merged (${usd(h.setups[k].cost_usd)} in all)`).join("; ")}.
      </p>
      <section className={s.wrap} aria-label="Held-out tasks" tabIndex={0}>
        <table className={s.table}>
          <thead>
            <tr>
              <th scope="col">Task</th>
              {keys.map((k) => (
                <th key={k} scope="col">
                  {setupName(k, setups[k])}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {h.tasks.map((t) => (
              <tr key={t}>
                <th scope="row">{taskName(t)}</th>
                {keys.map((k) => {
                  const v = h.setups[k].per_task[t];
                  return (
                    <td key={k} className={`${s.cell} ${v ? s.all : s.none}`}>
                      {v === undefined ? "–" : v ? "Merged" : "Not merged"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
