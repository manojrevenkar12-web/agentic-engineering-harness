// Copies the generated results into the dashboard (reports/results.json is the single source).
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
const src = new URL("../../reports/results.json", import.meta.url);
mkdirSync(new URL("../public/data/", import.meta.url), { recursive: true });
if (existsSync(src)) copyFileSync(src, new URL("../public/data/results.json", import.meta.url));
else console.warn("reports/results.json not found; run `aeh report` first");
