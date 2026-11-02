import { describe, expect, it } from "vitest";
import { points, share, usd } from "./format";
import { setupName, taskName } from "./labels";
import { linear } from "./scale";

describe("format", () => {
  it("formats shares, dollars and signed points", () => {
    expect(share(0.583)).toBe("58%");
    expect(share(null)).toBe("n/a");
    expect(usd(1.234)).toBe("$1.23");
    expect(usd(null)).toBe("none accepted");
    expect(points(-0.25)).toBe("−25 pts");
    expect(points(0.1)).toBe("+10 pts");
  });
});

describe("labels", () => {
  it("names setups from their configuration", () => {
    expect(setupName("sonnet-review", { model: "sonnet", flow: "review" })).toBe("Sonnet, agent + reviewer");
    expect(setupName("x")).toBe("x");
    expect(taskName("D06-provider-keys-tenancy")).toBe("provider keys tenancy");
  });
});

describe("scale", () => {
  it("includes zero and maps onto 0..100", () => {
    const s = linear([0.2, 0.6]);
    expect(s.ticks).toContain(0);
    expect(s.at(s.domain[1])).toBe(100);
  });
});
