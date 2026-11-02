import { setupName, taskName } from "../../shared/lib/labels";
import type { Results } from "../../shared/lib/results";
import s from "./tasks.module.css";

/** Merged changes per task and setup: where setups differ, and which tasks no setup can do. */
export function TaskMatrix({ r }: { r: Results }) {
  const dev = r.dev!;
  const setups = Object.keys(dev.per_task);
  const tasks = [...new Set(setups.flatMap((k) => Object.keys(dev.per_task[k])))].sort();
  return (
    <section className={s.wrap} aria-label="Merged changes by task and setup" tabIndex={0}>
      <table className={s.table}>
        <thead>
          <tr>
            <th scope="col">Task</th>
            {setups.map((k) => (
              <th key={k} scope="col">
                {setupName(k, r.setups[k])}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => (
            <tr key={t}>
              <th scope="row">{taskName(t)}</th>
              {setups.map((k) => {
                const c = dev.per_task[k][t];
                const tone = !c || c.accepted === 0 ? s.none : c.accepted === c.of ? s.all : s.some;
                return (
                  <td key={k} className={`${s.cell} ${tone}`}>
                    {c ? `${c.accepted}/${c.of}` : "–"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
