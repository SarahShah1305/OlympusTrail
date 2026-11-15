import { test, expect } from "@playwright/test";
const fixtures = {
  sites: [
    {
      position: { lat: 49, lon: -165 },
      score: 0.9,
      ice_consistency: 0.81,
      slope_deg: 2,
    },
    {
      position: { lat: 46, lon: -167 },
      score: 0.8,
      ice_consistency: 0.71,
      slope_deg: 3,
    },
  ],
};
test.beforeEach(async ({ page }) => {
  await page.route("**/sites?**", (route) => route.fulfill({ json: fixtures }));
});
test("panning remains stable after changing overlay opacity", async ({
  page,
}) => {
  await page.goto("/");
  await page.locator(".candidate button").first().click();
  const marker = page.locator(".trail-marker-site.selected");
  await expect(marker).toBeVisible();
  const map = await page.locator(".leaflet-map").boundingBox();
  await page.mouse.move(map.x + map.width * 0.6, map.y + map.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(
    map.x + map.width * 0.6 + 80,
    map.y + map.height * 0.5 + 50,
    { steps: 12 },
  );
  await page.mouse.up();
  await page.waitForTimeout(400);
  const before = await marker.boundingBox();
  await page.locator(".trail-opacity input").fill("80");
  await page.getByRole("button", { name: "Ice evidence", exact: true }).click();
  const after = await marker.boundingBox();
  expect(Math.abs(before.x - after.x)).toBeLessThan(2);
  expect(Math.abs(before.y - after.y)).toBeLessThan(2);
});
test("drawer traps keyboard focus and restores its trigger", async ({
  page,
}) => {
  await page.goto("/");
  const trigger = page.getByRole("button", {
    name: "Ask the guide",
    exact: true,
  });
  await trigger.click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("button", { name: "Close", exact: true }),
  ).toBeFocused();
  for (let i = 0; i < 18; i++) {
    await page.keyboard.press("Tab");
    expect(
      await dialog.evaluate((el) => el.contains(document.activeElement)),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
});
for (const reducedMotion of ["no-preference", "reduce"])
  test(`route animation respects ${reducedMotion}`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion });
    await page.route("**/route", (route) =>
      route.fulfill({
        json: {
          status: "ok",
          budget: { oxygen_hours: 4, battery_wh: 1000 },
          route: {
            geojson: {
              geometry: {
                coordinates: [
                  [-165, 49],
                  [-164.9, 49.03],
                ],
              },
            },
          },
        },
      }),
    );
    await page.goto("/");
    await page.getByRole("button", { name: "Try an example mission" }).click();
    const route = page.locator("path.trail-route");
    await expect(route).toHaveCount(1);
    expect(
      await route.evaluate((el) => getComputedStyle(el).animationName),
    ).toBe(reducedMotion === "reduce" ? "none" : "route-reveal");
    expect(await route.getAttribute("class")).not.toContain(
      "leaflet-interactive",
    );
  });
