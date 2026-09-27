import { createHash } from "node:crypto";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

import { chromium } from "playwright";

const STUDIO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPOSITORY = resolve(STUDIO, "..");
const ACCEPTANCE = resolve(REPOSITORY, "docs/acceptance/main-view-p0");
const BUILD = resolve(ACCEPTANCE, "build");
const PRODUCTION = resolve(ACCEPTANCE, "production");
const PROTOTYPE_URL = "http://127.0.0.1:4316";

const viewports = [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 1024, height: 768 },
  { width: 390, height: 844 },
];

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function pngDimensions(path) {
  const image = readFileSync(path);
  return { screenshotWidth: image.readUInt32BE(16), screenshotHeight: image.readUInt32BE(20) };
}

async function waitForServer(url) {
  let lastError;
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 100));
  }
  throw lastError ?? new Error(`Timed out waiting for ${url}`);
}

async function renderSvg(page, source, target, viewport) {
  const svg = readFileSync(source, "utf8").replace(/^<\?xml[^>]*>\s*/, "");
  await page.setViewportSize(viewport);
  await page.setContent(`<!doctype html><html><head><style>
    html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#e6ebe8}
    body{display:grid;place-items:center}.frame{box-sizing:border-box;width:100%;height:100%;padding:12px}
    svg{display:block;width:100%;height:100%;background:#fbfcfa;box-shadow:0 1px 8px rgba(22,32,28,.18)}
  </style></head><body><div class="frame">${svg}</div></body></html>`);
  const box = await page.locator(".frame > svg").boundingBox();
  if (!box || box.width < 1 || box.height < 1) throw new Error(`Blank SVG: ${source}`);
  await page.screenshot({ path: target });
  return {
    renderedWidth: box.width,
    renderedHeight: box.height,
    ...pngDimensions(target),
    bytes: readFileSync(target).byteLength,
  };
}

async function captureInteractiveBuild(page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${PROTOTYPE_URL}/?scene=parent-child-expansion&expand=attention`);
  const detail = page.locator(".detail-interactive-node").first();
  await detail.waitFor({ state: "visible" });
  const box = await detail.boundingBox();
  if (!box) throw new Error("Prototype detail node is not visible");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 30, box.y + box.height / 2 + 22, { steps: 8 });
  await page.mouse.up();
  await page.screenshot({ path: resolve(BUILD, "parent-child-internal-drag.png") });
  writeFileSync(
    resolve(BUILD, "parent-child-internal-drag.svg"),
    await page.locator("svg.lab-canvas").evaluate((element) => element.outerHTML),
  );

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`${PROTOTYPE_URL}/?scene=sequence-generative-catalog&expand=bidirectional-recurrent&drilldown=rnn`);
  await page.locator(".nested-inline-detail").first().waitFor({ state: "visible" });
  await page.screenshot({ path: resolve(BUILD, "recursive-formal-hierarchy.png") });
  writeFileSync(
    resolve(BUILD, "recursive-formal-hierarchy.svg"),
    await page.locator("svg.lab-canvas").evaluate((element) => element.outerHTML),
  );
}

const server = spawn(
  resolve(REPOSITORY, ".venv/bin/python"),
  ["-m", "http.server", "4316", "--bind", "127.0.0.1", "--directory", resolve(REPOSITORY, "build/scene-visual-lab")],
  { cwd: REPOSITORY, stdio: "ignore" },
);
const browser = await chromium.launch();
try {
  await waitForServer(PROTOTYPE_URL);
  const page = await browser.newPage();
  const ids = readdirSync(PRODUCTION)
    .filter((name) => name.endsWith(".svg"))
    .map((name) => name.slice(0, -4))
    .sort();
  const cases = [];
  for (let index = 0; index < ids.length; index += 1) {
    const id = ids[index];
    const viewport = viewports[index % viewports.length];
    const buildPng = resolve(BUILD, `${id}.png`);
    const productionPng = resolve(PRODUCTION, `${id}.png`);
    const build = await renderSvg(page, resolve(BUILD, `${id}.svg`), buildPng, viewport);
    const production = await renderSvg(page, resolve(PRODUCTION, `${id}.svg`), productionPng, viewport);
    cases.push({
      id,
      viewport,
      build: { file: `build/${id}.png`, sha256: sha256(buildPng), ...build },
      production: { file: `production/${id}.png`, sha256: sha256(productionPng), ...production },
      checks: {
        build_nonblank: build.bytes > 1024,
        production_nonblank: production.bytes > 1024,
        stable_viewport: build.screenshotWidth === viewport.width
          && build.screenshotHeight === viewport.height
          && production.screenshotWidth === viewport.width
          && production.screenshotHeight === viewport.height,
      },
    });
  }
  const writeReport = () => writeFileSync(
    resolve(ACCEPTANCE, "browser-differences.json"),
    `${JSON.stringify({
      schema_version: "1.0",
      generated_by: "studio/tools/capture-p0-acceptance.mjs",
      cases,
    }, null, 2)}\n`,
  );
  writeReport();
  await captureInteractiveBuild(page);
  for (const id of ["parent-child-internal-drag", "recursive-formal-hierarchy"]) {
    const record = cases.find((candidate) => candidate.id === id);
    if (record) {
      const path = resolve(BUILD, `${id}.png`);
      record.build = {
        ...record.build,
        sha256: sha256(path),
        bytes: readFileSync(path).byteLength,
        ...pngDimensions(path),
        interactive: true,
      };
      record.checks.stable_viewport = record.build.screenshotWidth === record.viewport.width
        && record.build.screenshotHeight === record.viewport.height
        && record.production.screenshotWidth === record.viewport.width
        && record.production.screenshotHeight === record.viewport.height;
    }
  }
  writeReport();
} finally {
  await browser.close();
  server.kill("SIGTERM");
}
