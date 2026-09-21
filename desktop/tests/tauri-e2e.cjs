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
  await projectId.clearValue()
  await projectId.setValue('project:tauri-transformer')
  for (const [selector, value] of [
    ['#approved-root', fixtureRoot],
    ['#entrypoint', 'model.py:EncoderModel'],
    ['#python-executable', python],
    ['#environment-name', 'TFB_py311'],
  ]) {
    const field = await browser.$(selector)
    await field.clearValue()
    await field.setValue(value)
  }
  await (await browser.$('button=Open and analyze')).click()
  await (await browser.$('.architecture-node')).waitForDisplayed({ timeout: 20_000 })
}

async function captureRepeatPosition(browser) {
  const repeat = await browser.$('.node-repeat_group')
  await repeat.waitForDisplayed()
  const beforeScreen = await repeat.getLocation()
  await browser.action('pointer', { parameters: { pointerType: 'mouse' } })
    .move({ origin: repeat, x: 80, y: 36 })
    .down({ button: 0 })
    .move({ origin: 'pointer', x: 100, y: 0 })
    .up({ button: 0 })
    .perform()
  await browser.pause(250)
  const afterScreen = await repeat.getLocation()
  assert.notDeepEqual(afterScreen, beforeScreen, 'visual drag must move the repeat group')
  return canvasPosition(repeat)
}

async function canvasPosition(node) {
  const style = await node.getAttribute('style')
  const matches = [...(style ?? '').matchAll(/translate\(([-\d.]+)px,\s*([-\d.]+)px\)/g)]
  const transform = matches.at(-1)
  if (!transform) throw new Error(`React Flow node has no readable canvas translation: ${style}`)
  return { x: Number(transform[1]), y: Number(transform[2]) }
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
    await openProject(browser)
    const publicationCount = await browser.$$('.architecture-node').then((nodes) => nodes.length)
    assert(publicationCount >= 5, 'Transformer publication view should render recovered nodes')
    const movedPosition = await captureRepeatPosition(browser)
    await (await browser.$('button=Save visual document')).click()
    await browser.pause(250)
    await browser.deleteSession()
    browser = undefined

    restarted = await waitForDriver(driver, driverLog)
    await openProject(restarted)
    const restored = await canvasPosition(await restarted.$('.node-repeat_group'))
    assert.equal(restored.x, movedPosition.x, 'restart must restore the saved canvas x position')
    assert.equal(restored.y, movedPosition.y, 'restart must restore the saved canvas y position')
    await (await restarted.$('button=Exact Architecture')).click()
    await restarted.waitUntil(
      async () => (await restarted.$('[data-id="node:encodermodel.layers"]')).isDisplayed(),
      { timeout: 5_000, timeoutMsg: 'Exact view should render the source-backed ModuleList node' },
    )
    assert.equal(await (await restarted.$('.node-repeat_group')).isExisting(), false, 'Exact view must not render the Publication repeat-group abstraction')
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
