/* Keep the Section 25 visual system centralized rather than allowing a second palette to drift in. */
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { resolve } = require('node:path')

const root = resolve(__dirname, '..')
const tokens = readFileSync(resolve(root, 'src/styles/tokens.css'), 'utf8')
const expected = {
  '--ac-bg': '#f7f6f3',
  '--ac-canvas': '#eaeae6',
  '--ac-surface': '#ffffff',
  '--ac-ink': '#1b1b18',
  '--ac-accent': '#2868b7',
  '--ac-selection': '#2f6fed',
}

for (const [token, value] of Object.entries(expected)) {
  assert.match(tokens, new RegExp(`${token}:\\s*${value};`), `${token} must retain its frozen Section 25 value`)
}

for (const path of ['src/App.css', 'src/canvas/CanvasStage.css', 'src/index.css']) {
  const source = readFileSync(resolve(root, path), 'utf8')
  assert.doesNotMatch(source, /#[0-9a-fA-F]{3,8}\b|\brgba?\(/, `${path} must use semantic tokens instead of a local color literal`)
}
