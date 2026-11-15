import { test, expect } from "@playwright/test";

test("mobile map controls remain compact and usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/tiles/Mars/**", (route) => route.abort());
  await page.goto("/");
  expect(
    (await page.locator(".revamp-header").boundingBox()).height,
  ).toBeLessThanOrEqual(110);
  const options = page.locator(".trail-layer-options");
  await expect(options).not.toHaveAttribute("open", "");
  await expect(page.locator(".pointer-tap")).toBeVisible();
  await options.locator("summary").click();
  await expect(page.locator(".trail-opacity input")).toBeVisible();
  for (const selector of [
    ".leaflet-control-zoom-in",
    ".leaflet-control-zoom-out",
    ".trail-map-legend summary",
    ".trail-opacity input",
  ]) {
    const box = await page.locator(selector).boundingBox();
    expect(box.height, selector).toBeGreaterThanOrEqual(44);
  }
  const expandedNotice = page
    .locator(".map-notices .trail-map-notice")
    .filter({ hasText: "basemap tiles" });
  await expect(expandedNotice).toBeVisible();
  await expect
    .poll(
      async () =>
        (await expandedNotice.boundingBox()).y -
        ((await page.locator(".trail-layer-controls").boundingBox()).y +
          (await page.locator(".trail-layer-controls").boundingBox()).height),
    )
    .toBeGreaterThanOrEqual(0);
  await options.locator("summary").click();
  const notice = page
    .locator(".map-notices .trail-map-notice")
    .filter({ hasText: "basemap tiles" });
  await expect(notice).toBeVisible();
  const n = await notice.boundingBox();
  const controls = await page.locator(".trail-layer-controls").boundingBox();
  expect(n.y).toBeGreaterThanOrEqual(controls.y + controls.height);
  await expect(notice).toBeHidden({ timeout: 6000 });
});

test("desktop tile notice clears planner and layer controls", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.route("**/tiles/Mars/**", (route) => route.abort());
  await page.goto("/");
  const notice = page
    .locator(".map-notices .trail-map-notice")
    .filter({ hasText: "basemap tiles" });
  await expect(notice).toBeVisible();
  const n = await notice.boundingBox();
  for (const selector of [".mission-sheet", ".trail-layer-controls"]) {
    const c = await page.locator(selector).boundingBox();
    expect(
      n.x + n.width <= c.x ||
        c.x + c.width <= n.x ||
        n.y + n.height <= c.y ||
        c.y + c.height <= n.y,
      selector,
    ).toBeTruthy();
  }
});
