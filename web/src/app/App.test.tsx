import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import fixture from "../test/fixture.json";
import { App } from "./App";

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("App", () => {
  it("shows skeletons, then the decision and every setup", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok(fixture));
    render(<App url="/data/results.json" />);
    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
    expect(await screen.findByText(/^Adopt /)).toBeTruthy();
    for (const key of Object.keys(fixture.dev.setups)) expect(screen.getByTestId(`setup-${key}`)).toBeTruthy();
    expect(screen.getByTestId("proof-D06-provider-keys-tenancy")).toBeTruthy();
  });

  it("shows an empty state when the held-out set has not run", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok(fixture));
    render(<App url="/data/results.json" />);
    expect(await screen.findByText("The held-out tasks have not run")).toBeTruthy();
  });

  it("shows an empty state for every benchmark section before the first run", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok({ ...fixture, dev: null }));
    render(<App url="/data/results.json" />);
    expect((await screen.findAllByText("No benchmark has run yet")).length).toBe(4);
  });

  it("explains a failure and retries", async () => {
    const f = vi
      .spyOn(globalThis, "fetch")
      .mockImplementationOnce(() => Promise.resolve(new Response("nope", { status: 404 })))
      .mockImplementation(() => ok(fixture));
    render(<App url="/data/results.json" />);
    const alerts = await screen.findAllByRole("alert");
    expect(alerts[0].textContent).toMatch(/404/);
    fireEvent.click(within(alerts[0]).getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/^Adopt /)).toBeTruthy();
    expect(f).toHaveBeenCalledTimes(2);
  });

  it("rejects a file in the wrong format", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok({ hello: 1 }));
    render(<App url="/data/results.json" />);
    expect((await screen.findAllByRole("alert"))[0].textContent).toMatch(/not in the format/);
  });
});
