import { test, expect } from "@playwright/test";

test("the example mission produces a planner verdict", async ({ page }) => {
  test.setTimeout(150_000);
  const baseUrl = process.env.BASE_URL || "http://127.0.0.1:5175";
  await page.goto(baseUrl);
  const example = page.getByRole("button", { name: "Try an example mission" });
  await expect(example).toBeEnabled({ timeout: 70_000 });
  await example.click();
  await expect(page.locator(".result-verdict")).toBeVisible({
    timeout: 70_000,
  });
  await expect(page.locator(".result-verdict h3")).not.toBeEmpty();
});
