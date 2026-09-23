const { test, expect } = require('@playwright/test')

for (const viewport of [
  { name: 'publication-1440x900', width: 1440, height: 900 },
  { name: 'publication-1280x800', width: 1280, height: 800 },
]) {
  test(`${viewport.name} retains the paper-and-instrument canvas`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/')
    await expect(page.getByLabel('Model architecture canvas')).toBeVisible()
    await expect(page).toHaveScreenshot(`${viewport.name}.png`, {
      animations: 'disabled',
      caret: 'hide',
      fullPage: true,
      maxDiffPixelRatio: 0.001,
    })
  })
}

test('publication miniatures appear only at detail zoom with provenance disclosure', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  await page.getByTitle('Zoom in').click()
  await expect(page.locator('[data-miniature-kind]')).toHaveCount(3)
  await expect(page.locator('[data-miniature-kind="signal_preview"]')).toHaveAttribute('data-disclosure', 'illustrative')
  await expect(page.locator('[data-miniature-kind="equation_note"]')).toHaveAttribute('data-disclosure', 'evidence')
  const repeatNode = page.locator('[data-canvas-node="publication-node:transformer-encoder"]')
  await expect(repeatNode.locator('.node-label')).toHaveText('Transformer encoder x 6')
  await expect(repeatNode.locator('.miniature-equation_note em')).toBeHidden()
  await expect(repeatNode.locator('.miniature-inset_callout em')).toBeHidden()
  await expect(page).toHaveScreenshot('publication-miniatures-1440x900.png', {
    animations: 'disabled',
    caret: 'hide',
    fullPage: true,
    maxDiffPixelRatio: 0.001,
  })
  await repeatNode.click()
  await expect(page.getByText('Visual evidence')).toBeVisible()
  await expect(page.getByText('N x repeated encoder block')).toBeVisible()
})

test('repeat disclosure handles double-click and keyboard without changing node identity', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  const repeat = page.locator('[data-canvas-node="publication-node:transformer-encoder"]')
  await expect(repeat).toHaveAttribute('aria-expanded', 'false')
  await repeat.dblclick()
  await expect(repeat).toHaveAttribute('aria-expanded', 'true')
  await repeat.focus()
  await page.keyboard.press('Enter')
  await expect(repeat).toHaveAttribute('aria-expanded', 'false')
  await expect(page.locator('[data-canvas-node="publication-node:transformer-encoder"]')).toHaveCount(1)
})
