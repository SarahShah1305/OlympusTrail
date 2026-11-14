import { test, expect } from 'playwright/test'

// Start the real planner (8000) and Vite (5175) before running this test.
// The first request can take a minute while the terrain data loads.
test('the example mission produces a planner verdict', async ({ page }) => {
  test.setTimeout(150_000)
  await page.goto('http://localhost:5175/')
  const example = page.getByRole('button', { name: 'Try an example mission' })
  await expect(example).toBeEnabled({ timeout: 70_000 })
  await example.click()
  await expect(page.locator('.result-verdict')).toBeVisible({ timeout: 70_000 })
  await expect(page.locator('.result-verdict h3')).not.toBeEmpty()
})
