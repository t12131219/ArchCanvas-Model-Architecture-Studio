/* Native Stage 6 acceptance test through Tauri's WebDriver bridge. */
const assert = require('node:assert/strict')
const { createHash } = require('node:crypto')
const { existsSync, mkdtempSync, rmSync, readFileSync } = require('node:fs')
const { tmpdir } = require('node:os')
const { resolve } = require('node:path')
const { spawn, spawnSync } = require('node:child_process')
const { remote } = require('webdriverio')

const desktopRoot = resolve(__dirname, '..')
const repositoryRoot = resolve(desktopRoot, '..')
const binary = resolve(desktopRoot, 'src-tauri/target/debug/archcanvas-desktop')
const fixtureRoot = resolve(repositoryRoot, 'fixtures/transformer_static_v1/source')
const fixtureSource = resolve(fixtureRoot, 'model.py')
const nativeDriver = process.env.ARCHCANVAS_WEBKIT_DRIVER ?? 'WebKitWebDriver'
const tauriDriver = process.env.ARCHCANVAS_TAURI_DRIVER ?? 'tauri-driver'
const python = process.env.ARCHCANVAS_ENGINE_PYTHON
const cacheRoot = process.env.ARCHCANVAS_ENGINE_CACHE_ROOT ?? mkdtempSync(resolve(tmpdir(), 'archcanvas-tauri-e2e-'))
const ownedCache = !process.env.ARCHCANVAS_ENGINE_CACHE_ROOT
const driverPort = Number(process.env.ARCHCANVAS_TAURI_DRIVER_PORT ?? 4444)
const nativeDriverPort = Number(process.env.ARCHCANVAS_NATIVE_DRIVER_PORT ?? 4445)

function sha256(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex')
}

function requireExecutable(command, description) {
  if (existsSync(command) || spawnSync('which', [command], { stdio: 'ignore' }).status === 0) return
  throw new Error(`${description} is unavailable: ${command}. Install/configure it before native E2E.`)
}

async function waitForDriver(child, driverLog) {
  let lastError
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const client = await remote({
        hostname: '127.0.0.1', port: driverPort, path: '/',
        capabilities: {
          browserName: 'wry',
          'tauri:options': { application: binary },
          // WebKitGTK does not expose WebDriver BiDi; avoid webdriverio injecting webSocketUrl.
          'wdio:enforceWebDriverClassic': true,
        },
        logLevel: 'error',
      })
      return client
    } catch (error) {
      lastError = error
      if (child.exitCode !== null) break
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 250))
    }
  }
  const diagnostic = driverLog.join('').trim()
  const failure = lastError ?? new Error('tauri-driver did not accept a session')
  if (diagnostic) failure.message += `\nNative driver output:\n${diagnostic}`
  throw failure
}

async function openProject(browser) {
  const projectId = await browser.$('#project-id')
  await browser.pause(300)
  const openButton = await browser.$('button=Open project')
  if (!await projectId.isDisplayed()) await openButton.click()
  await projectId.waitForDisplayed()
  await setReactInput(browser, '#project-id', 'project:tauri-transformer')
  for (const [selector, value] of [
    ['#approved-root', fixtureRoot],
    ['#entrypoint', 'model.py:EncoderModel'],
    ['#python-executable', python],
    ['#environment-name', 'TFB_py311'],
  ]) {
    const field = await setReactInput(browser, selector, value)
    assert.equal(await field.getValue(), value, `${selector} must retain the approved test input before submit`)
  }
  await (await browser.$('button=Open and analyze')).click()
  try {
    await browser.waitUntil(async () => (await browser.$$('.architecture-node')).length > 0, {
      timeout: 20_000, timeoutMsg: 'Engine analysis should create canvas nodes',
    })
  } catch (error) {
    const body = await (await browser.$('body')).getText().catch(() => 'Unable to read native page text.')
    throw new Error(`${error.message}\nNative page state:\n${body}`)
  }
  const size = await (await browser.$('.architecture-node')).getSize()
  assert(size.width > 0 && size.height > 0, 'Canvas nodes must have non-zero rendered geometry')
}

async function setReactInput(browser, selector, value) {
  await browser.execute((inputSelector, nextValue) => {
    const field = document.querySelector(inputSelector)
    if (!(field instanceof HTMLInputElement)) throw new Error(`Input not found: ${inputSelector}`)
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
    setValue?.call(field, nextValue)
    field.dispatchEvent(new Event('input', { bubbles: true }))
    field.dispatchEvent(new Event('change', { bubbles: true }))
  }, selector, value)
  return browser.$(selector)
}

async function captureRepeatPosition(browser) {
  const repeat = await browser.$('.node-repeat_group')
  await repeat.waitForExist()
  const beforeScreen = await repeat.getLocation()
  const beforeCanvas = await canvasPosition(repeat)
  await browser.action('pointer', { parameters: { pointerType: 'mouse' } })
    .move({ origin: repeat, x: 80, y: 36 })
    .down({ button: 0 })
    .move({ origin: 'pointer', x: 100, y: 0 })
    .up({ button: 0 })
    .perform()
  await browser.pause(250)
  const afterScreen = await repeat.getLocation()
  assert.notDeepEqual(afterScreen, beforeScreen, 'visual drag must move the repeat group')
  return { before: beforeCanvas, after: await canvasPosition(repeat) }
}

async function canvasPosition(node) {
  const style = await node.getAttribute('style')
  const matches = [...(style ?? '').matchAll(/translate\(([-\d.]+)px,\s*([-\d.]+)px\)/g)]
  const transform = matches.at(-1)
  if (!transform) throw new Error(`Canvas node has no readable canvas translation: ${style}`)
  return { x: Number(transform[1]), y: Number(transform[2]) }
}

async function panCanvas(browser) {
  const stage = await browser.$('[data-canvas-stage]')
  const world = await browser.$('.canvas-world')
  const before = await world.getAttribute('style')
  await browser.action('pointer', { parameters: { pointerType: 'mouse' } })
    .move({ origin: stage, x: 0, y: 0 })
    .down({ button: 1 })
    .move({ origin: 'pointer', x: 64, y: 32 })
    .up({ button: 1 })
    .perform()
  await browser.pause(100)
  const after = await world.getAttribute('style')
  assert.notEqual(after, before, 'middle-mouse pan must update the viewport transform')
}

async function verifyZoomAndSelection(browser) {
  const readout = await browser.$('.zoom-readout')
  await browser.pause(200)
  const beforeZoom = await readout.getText()
  await (await browser.$('button[title="Zoom in"]')).click()
  await browser.waitUntil(async () => await readout.getText() !== beforeZoom, {
    timeout: 3_000, timeoutMsg: 'zoom control must update the viewport readout',
  })
  await (await browser.$('button[title="Zoom out"]')).click()

  const embedding = await browser.$('[data-id="publication-node:encodermodel-embedding"]')
  const head = await browser.$('[data-id="publication-node:encodermodel-head"]')
  await embedding.click()
  assert.equal(await (await browser.$('.inspector-content h1')).getText(), 'Token embedding', 'single selection must update the inspector')
  await browser.action('key').down('\uE008').perform(true)
  try { await head.click() }
  finally { await browser.action('key').up('\uE008').perform() }
  const selected = await browser.execute(() => [...document.querySelectorAll('.architecture-node.is-selected')].map((node) => node.getAttribute('data-id')))
  assert.deepEqual(selected.sort(), ['publication-node:encodermodel-embedding', 'publication-node:encodermodel-head'].sort(), 'Shift-click must create a multi-selection')
}

async function run() {
  if (!python) throw new Error('ARCHCANVAS_ENGINE_PYTHON must name the approved Engine interpreter.')
  requireExecutable(binary, 'Native ArchCanvas binary')
  requireExecutable(nativeDriver, 'WebKit WebDriver')
  const sourceBefore = sha256(fixtureSource)
  const environment = {
    ...process.env,
    TAURI_AUTOMATION: 'true',
    ARCHCANVAS_ENGINE_PYTHON: python,
    ARCHCANVAS_ENGINE_CACHE_ROOT: cacheRoot,
  }
  const driver = spawn(
    tauriDriver,
    ['--port', String(driverPort), '--native-port', String(nativeDriverPort), '--native-driver', nativeDriver],
    { env: environment, stdio: 'pipe' },
  )
  const driverLog = []
  driver.stdout.on('data', (chunk) => driverLog.push(chunk.toString()))
  driver.stderr.on('data', (chunk) => driverLog.push(chunk.toString()))
  let browser
  let restarted
  try {
    browser = await waitForDriver(driver, driverLog)
    await browser.waitUntil(async () => (await browser.$('[data-canonical-id="encoder"]')).isExisting(), {
      timeout: 8_000, timeoutMsg: 'Bundled Tier A Transformer graph should load in native Tauri',
    })
    await (await browser.$('button=Open full')).click()
    await browser.waitUntil(async () => (await browser.$('[data-canonical-id="s_apply_mask"]')).isExisting(), {
      timeout: 5_000, timeoutMsg: 'Native Tier A direct-full should show the causal-mask operator',
    })
    assert.equal(await (await browser.$('[data-target-port="K_in"].tier-a-memory')).isExisting(), true)
    assert.equal(await (await browser.$('[data-target-port="V_in"].tier-a-memory')).isExisting(), true)
    await openProject(browser)
    const publicationCount = await browser.$$('.architecture-node').then((nodes) => nodes.length)
    assert(publicationCount >= 5, 'Transformer publication view should render recovered nodes')
    await verifyZoomAndSelection(browser)
    await panCanvas(browser)
    const movedPosition = await captureRepeatPosition(browser)
    await (await browser.$('button[aria-label="Undo visual edit"]')).click()
    assert.deepEqual(await canvasPosition(await browser.$('.node-repeat_group')), movedPosition.before, 'one drag must be undone as one history item')
    await (await browser.$('button[aria-label="Redo visual edit"]')).click()
    assert.deepEqual(await canvasPosition(await browser.$('.node-repeat_group')), movedPosition.after, 'redo must restore the completed drag')
    await (await browser.$('button[title="Fit canvas"]')).click()
    const repeat = await browser.$('.node-repeat_group')
    await browser.execute(() => document.querySelector('.node-repeat_group')?.focus())
    await browser.keys(' ')
    await browser.execute(() => {
      const button = [...document.querySelectorAll('.inspector-content button')]
        .find((candidate) => candidate.textContent?.includes('Expand visual group'))
      if (!(button instanceof HTMLButtonElement)) throw new Error('Inspector expansion command missing')
      button.click()
    })
    try {
      await browser.waitUntil(async () => await repeat.getAttribute('aria-expanded') === 'true', {
        timeout: 3_000, timeoutMsg: 'Inspector command must expand the visual repeat group',
      })
    } catch (error) {
      const state = await browser.execute(() => ({
        expanded: document.querySelector('.node-repeat_group')?.getAttribute('aria-expanded'),
        inspector: document.querySelector('.inspector-content h1')?.textContent,
        buttons: [...document.querySelectorAll('.inspector-content button')].map((button) => button.textContent),
        notice: document.querySelector('.notice')?.textContent,
      }))
      throw new Error(`${error.message}: ${JSON.stringify(state)}`)
    }
    await (await browser.$('button=Save visual document')).click()
    await browser.pause(250)
    await browser.deleteSession()
    browser = undefined

    restarted = await waitForDriver(driver, driverLog)
    await openProject(restarted)
    const restored = await canvasPosition(await restarted.$('.node-repeat_group'))
    assert.equal(restored.x, movedPosition.after.x, 'restart must restore the saved canvas x position')
    assert.equal(restored.y, movedPosition.after.y, 'restart must restore the saved canvas y position')
    await (await restarted.$('button=Exact Architecture')).click()
    await restarted.waitUntil(
      async () => (await restarted.$('[data-id="node:encodermodel.layers"]')).isExisting(),
      { timeout: 5_000, timeoutMsg: 'Exact view should render the source-backed ModuleList node' },
    )
    assert.equal(await (await restarted.$('.node-repeat_group')).isExisting(), false, 'Exact view must not render the Publication repeat-group abstraction')
    await (await restarted.$('[data-id="node:encodermodel.norm"]')).click()
    assert.equal(
      await (await restarted.$('button=Plan LayerNorm insertion')).isExisting(),
      false,
      'unregistered projects must not expose structural authoring controls',
    )
    assert.equal(sha256(fixtureSource), sourceBefore, 'visual E2E must leave source bytes identical')
  } finally {
    await restarted?.deleteSession().catch(() => {})
    await browser?.deleteSession().catch(() => {})
    driver.kill()
    if (ownedCache) rmSync(cacheRoot, { recursive: true, force: true })
  }
}

run().catch((error) => {
  console.error(error.stack ?? error)
  process.exitCode = 1
})
