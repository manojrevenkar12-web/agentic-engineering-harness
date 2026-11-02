import { useCallback, useEffect, useState } from "react";
import { isResults, type Results } from "./results";

export type Load<T> = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: T };

export const RESULTS_URL = `${import.meta.env.BASE_URL}data/results.json`;

export function useResults(url: string = RESULTS_URL): { state: Load<Results>; retry: () => void } {
  const [state, setState] = useState<Load<Results>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    setState({ status: "loading" });
    fetch(`${url}?attempt=${attempt}`, { signal: ctrl.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error(`The results file answered ${res.status}. Run \`aeh report\`, then \`npm run sync\`.`);
        const body: unknown = await res.json();
        if (!isResults(body)) throw new Error("The results file is not in the format `aeh report` writes.");
        setState({ status: "ready", data: body });
      })
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setState({ status: "error", message: e instanceof Error ? e.message : String(e) });
      });
    return () => ctrl.abort();
  }, [url, attempt]);

  const retry = useCallback(() => setAttempt((a) => a + 1), []);
  return { state, retry };
}
