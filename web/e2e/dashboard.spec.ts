import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import fixture from "../src/test/fixture.json" with { type: "json" };

const serve = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });

test.describe("dashboard", () => {
  test("shows the decision and passes axe in light and dark", async ({ page }) => {
    await page.route("**/data/results.json*", (r) => r.fulfill(serve(fixture)));
    for (const scheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
      await page.goto("/");
      await expect(page.getByText(/^Adopt /)).toBeVisible();
      const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      expect(axe.violations.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
    }
  });

  test("has no horizontal page scroll", async ({ page }) => {
    await page.route("**/data/results.json*", (r) => r.fulfill(serve(fixture)));
    await page.goto("/");
    await expect(page.getByText(/^Adopt /)).toBeVisible();
    const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(over).toBeLessThanOrEqual(0);
  });

  test("explains a missing results file and recovers on retry", async ({ page }) => {
    let calls = 0;
    await page.route("**/data/results.json*", (r) => (++calls === 1 ? r.fulfill({ status: 404, body: "" }) : r.fulfill(serve(fixture))));
    await page.goto("/");
    const alert = page.getByRole("alert").first();
    await expect(alert).toContainText("404");
    await alert.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByText(/^Adopt /)).toBeVisible();
  });
});
