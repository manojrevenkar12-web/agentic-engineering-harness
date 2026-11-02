import type { SetupConfig } from "./results";

const flowLabel: Record<SetupConfig["flow"], string> = {
  solo: "one agent",
  review: "agent + reviewer",
  best_of: "best of two",
};

const modelLabel: Record<string, string> = { haiku: "Haiku", sonnet: "Sonnet", opus: "Opus" };

/** "Sonnet, agent + reviewer" from the setup's configuration, falling back to its key. */
export function setupName(key: string, cfg?: SetupConfig): string {
  if (!cfg) return key;
  return `${modelLabel[cfg.model] ?? cfg.model}, ${flowLabel[cfg.flow] ?? cfg.flow}`;
}

export function taskName(id: string): string {
  return id.replace(/^[A-Z]\d+-/, "").replaceAll("-", " ");
}
