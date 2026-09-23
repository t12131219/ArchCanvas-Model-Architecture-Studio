const { test, expect } = require('@playwright/test')
const { readFileSync } = require('node:fs')

test('Transformer expands in place and direct-full preserves canonical identity', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/?tierA=transformer')
  const canvas = page.locator('.tier-a-svg')
  await expect(canvas).toBeVisible()
  await expect(canvas.locator('[data-canonical-id="encoder"]')).toHaveCount(1)
  await expect(canvas.locator('[data-canonical-id="enc_attn"]')).toHaveCount(0)
  await canvas.locator('[data-canonical-id="encoder"]').click()
  await expect(canvas.locator('[data-canonical-id="enc_attn"]')).toHaveCount(1)
  await expect(canvas.locator('[data-canonical-id="e_score"]')).toHaveCount(0)
  await page.getByRole('button', { name: 'Open full' }).click()
  await expect(canvas.locator('[data-canonical-id="e_score"]')).toHaveCount(1)
  await expect(canvas.locator('[data-canonical-id="s_mask"]')).toHaveCount(1)
  await expect(canvas.locator('[data-canonical-id="logits"]')).toHaveCount(1)
  await expect(canvas.locator('[data-canonical-id="softmax"]')).toHaveCount(0)
  await expect(canvas.locator('[data-target-port="K_in"].tier-a-memory')).toHaveCount(1)
  await expect(canvas.locator('[data-target-port="V_in"].tier-a-memory')).toHaveCount(1)
  const fullIds = await canvas.locator('[data-canonical-id]').evaluateAll((elements) => elements.map((element) => element.getAttribute('data-canonical-id')))
  expect(fullIds.length).toBe(new Set(fullIds).size)
  await page.getByRole('button', { name: 'L1' }).click()
  await expect(canvas.locator('[data-canonical-id="e_score"]')).toHaveCount(0)
  await page.getByRole('button', { name: 'Open full' }).click()
  expect(await canvas.locator('[data-canonical-id]').evaluateAll((elements) => elements.map((element) => element.getAttribute('data-canonical-id')))).toEqual(fullIds)
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export architecture SVG' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('archcanvas-transformer-architecture.svg')
  const svg = readFileSync(await download.path(), 'utf8')
  expect(svg).toContain('data-canonical-id="e_score"')
  expect(svg).toContain('data-target-port="K_in"')
  expect(svg).toContain('<circle')
  expect(svg).toContain('data-tensor-role="Q"')
  expect(svg).toMatch(/fill:\s*rgb\(/)
  expect(svg).toMatch(/stroke:\s*rgb\(/)
  for (const id of ['e_q', 'e_k', 'e_v']) {
    await expect(canvas.locator(`[data-canonical-id="${id}"]`)).toHaveAttribute('data-primitive', 'projection-tensor')
  }
  const q = await canvas.locator('[data-canonical-id="e_q"] .tier-a-hit').boundingBox()
  const k = await canvas.locator('[data-canonical-id="e_k"] .tier-a-hit').boundingBox()
  const v = await canvas.locator('[data-canonical-id="e_v"] .tier-a-hit').boundingBox()
  expect(q && k && v && q.x < k.x && k.x < v.x && q.y === k.y && k.y === v.y).toBe(true)
  await expect(canvas.locator('[data-tensor-role="Q"]')).toHaveCount(3)
  await expect(canvas.locator('[data-tensor-role="K"]')).toHaveCount(3)
  await expect(canvas.locator('[data-tensor-role="V"]')).toHaveCount(3)
  await expect(canvas.locator('[data-source-id="e_q"][data-target-id="e_k"], [data-source-id="e_k"][data-target-id="e_v"]')).toHaveCount(0)
  await expect(canvas.locator('[data-canonical-id="enc_add1"] .tier-a-merge-circle')).toHaveCount(1)
  await expect(canvas.locator('[data-canonical-id="enc_add1"] .tier-a-norm-capsule')).toHaveCount(1)
  await expect(canvas.locator('[data-canonical-id="s_mask"] .tier-a-condition-shape')).toHaveCount(1)
  await expect(canvas.locator('[data-canonical-id="encoder"] .tier-a-stack-back')).toHaveCount(1)
  await expect(canvas.locator('.tier-a-edge-label-memory')).toHaveText(['K memory', 'V memory'])
  const linear = await canvas.locator('[data-canonical-id="ef_linear1"] .tier-a-hit').boundingBox()
  const relu = await canvas.locator('[data-canonical-id="ef_relu"] .tier-a-hit').boundingBox()
  const output = await canvas.locator('[data-canonical-id="ef_linear2"] .tier-a-hit').boundingBox()
  expect(linear && relu && output && linear.x < relu.x && relu.x < output.x && linear.y === relu.y && relu.y === output.y).toBe(true)
  await canvas.locator('[data-canonical-id="enc_attn"]').click({ position: { x: 24, y: 18 } })
  await page.getByRole('button', { name: 'Collapse', exact: true }).click()
  await expect(canvas.locator('[data-canonical-id="e_q"]')).toHaveCount(0)
  await page.reload()
  await expect(canvas.locator('[data-canonical-id="e_q"]')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'L4' })).toHaveAttribute('aria-pressed', 'true')
  await canvas.locator('[data-canonical-id="enc_attn"]').click()
  await expect(canvas.locator('[data-canonical-id="e_q"]')).toHaveCount(1)
})

for (const [model, expected, forbidden] of [
  ['autoformer', 'enc_corr', 'position'],
  ['itransformer', 'invert', 'decoder'],
  ['patchtst', 'flatten', 'decomp'],
  ['timemixer', 'season', 'conv_mixer'],
]) {
  test(`${model} has a nonblank source-specific full graph`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto(`/?tierA=${model}`)
    const canvas = page.locator('.tier-a-svg')
    await expect(canvas).toBeVisible()
    await page.getByRole('button', { name: 'Open full' }).click()
    await expect(canvas.locator(`[data-canonical-id="${expected}"]`)).toHaveCount(1)
    await expect(canvas.locator(`[data-canonical-id="${forbidden}"]`)).toHaveCount(0)
    expect(await canvas.locator('[data-edge-id]').count()).toBeGreaterThan(4)
    expect(await canvas.evaluate((element) => {
      const rectangle = element.getBoundingClientRect()
      return rectangle.width > 100 && rectangle.height > 200
    })).toBe(true)
    expect(await canvas.locator('[data-primitive]').evaluateAll((elements) => new Set(elements.map((element) => element.getAttribute('data-primitive'))).size)).toBeGreaterThan(2)
    const overflow = await canvas.evaluate((svg) => {
      const labels = [...svg.querySelectorAll('.tier-a-label')]
      const boxes = [...svg.querySelectorAll('.tier-a-node')].map((node) => node.querySelector('.tier-a-hit'))
      return labels.filter((label, index) => label.getBBox().width > boxes[index].getBBox().width - 10)
        .map((label) => label.textContent)
    })
    expect(overflow).toEqual([])
  })
}

test('Autoformer exposes source-backed Q, K and V as parallel projection tensors', async ({ page }) => {
  await page.goto('/?tierA=autoformer')
  await page.getByRole('button', { name: 'Open full' }).click()
  const canvas = page.locator('.tier-a-svg')
  for (const prefix of ['e', 'd', 'c']) {
    const boxes = await Promise.all(['q', 'k', 'v'].map((role) => canvas.locator(`[data-canonical-id="${prefix}_${role}"] .tier-a-hit`).boundingBox()))
    expect(boxes.every(Boolean) && boxes[0].y === boxes[1].y && boxes[1].y === boxes[2].y).toBe(true)
  }
  await expect(canvas.locator('[data-canonical-id$="_qkv"]')).toHaveCount(0)
  await expect(canvas.locator('[data-source-id="memory"][data-target-id="c_k"]')).toHaveCount(1)
  await expect(canvas.locator('[data-source-id="memory"][data-target-id="c_v"]')).toHaveCount(1)
})

test('merge labels do not cover their operator circles', async ({ page }) => {
  await page.goto('/?tierA=timemixer')
  await page.getByRole('button', { name: 'Open full' }).click()
  const canvas = page.locator('.tier-a-svg')
  for (const id of ['merge', 'aggregate', 'season_add', 'trend_add']) {
    const overlap = await canvas.locator(`[data-canonical-id="${id}"]`).evaluate((node) => {
      const circle = node.querySelector('.tier-a-merge-circle').getBBox()
      const labels = [...node.ownerSVGElement.querySelectorAll('.tier-a-label')]
      const index = [...node.ownerSVGElement.querySelectorAll('.tier-a-node')].indexOf(node)
      const label = labels[index].getBBox()
      return label.y < circle.y + circle.height && label.y + label.height > circle.y
    })
    expect(overlap).toBe(false)
  }
})

test('mobile keeps controls on screen and preserves a readable scrollable diagram', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/?tierA=transformer')
  await expect(page.locator('.tier-a-svg')).toBeVisible()
  await page.getByRole('button', { name: 'Open full' }).click()
  const geometry = await page.locator('.tier-a-workspace').evaluate((element) => {
    const toolbar = element.querySelector('.tier-a-toolbar').getBoundingClientRect()
    const scroll = element.querySelector('.tier-a-scroll')
    return { toolbarRight: toolbar.right, clientWidth: scroll.clientWidth, scrollWidth: scroll.scrollWidth }
  })
  expect(geometry.toolbarRight).toBeLessThanOrEqual(391)
  expect(geometry.scrollWidth).toBeGreaterThan(geometry.clientWidth)
  await expect(page.locator('[data-canonical-id="s_apply_mask"]')).toHaveCount(1)
})
