import { createHash } from "node:crypto";
import { inflateSync } from "node:zlib";
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

function decodePng(path) {
  const buffer = readFileSync(path);
  if (buffer.toString("ascii", 1, 4) !== "PNG") throw new Error(`Not a PNG: ${path}`);
  let offset = 8;
  let width;
  let height;
  let bitDepth;
  let colorType;
  const chunks = [];
  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.toString("ascii", offset + 4, offset + 8);
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    offset += 12 + length;
    if (type === "IHDR") {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
    } else if (type === "IDAT") chunks.push(data);
    else if (type === "IEND") break;
  }
  if (width === undefined || height === undefined || bitDepth !== 8 || ![2, 6].includes(colorType)) {
    throw new Error(`Expected 8-bit RGB/RGBA PNG: ${path}`);
  }
  const raw = inflateSync(Buffer.concat(chunks));
  const sourceBytesPerPixel = colorType === 6 ? 4 : 3;
  const sourceStride = width * sourceBytesPerPixel;
  const stride = width * 4;
  const pixels = Buffer.alloc(height * stride);
  let source = 0;
  for (let y = 0; y < height; y += 1) {
    const filter = raw[source++];
    const sourceRow = y * sourceStride;
    const row = y * stride;
    const unfiltered = Buffer.alloc(sourceStride);
    for (let x = 0; x < sourceStride; x += 1) {
      const value = raw[source++];
      const left = x >= sourceBytesPerPixel ? unfiltered[x - sourceBytesPerPixel] : 0;
      const up = y > 0 ? pixels[(y - 1) * stride + Math.floor(x / sourceBytesPerPixel) * 4 + (x % sourceBytesPerPixel)] : 0;
      const upperLeft = y > 0 && x >= sourceBytesPerPixel
        ? pixels[(y - 1) * stride + Math.floor((x - sourceBytesPerPixel) / sourceBytesPerPixel) * 4 + ((x - sourceBytesPerPixel) % sourceBytesPerPixel)]
        : 0;
      if (filter === 0) unfiltered[x] = value;
      else if (filter === 1) unfiltered[x] = (value + left) & 0xff;
      else if (filter === 2) unfiltered[x] = (value + up) & 0xff;
      else if (filter === 3) unfiltered[x] = (value + Math.floor((left + up) / 2)) & 0xff;
      else if (filter === 4) {
        const p = left + up - upperLeft;
        const pa = Math.abs(p - left);
        const pb = Math.abs(p - up);
        const pc = Math.abs(p - upperLeft);
        unfiltered[x] = (value + (pa <= pb && pa <= pc ? left : pb <= pc ? up : upperLeft)) & 0xff;
      } else throw new Error(`Unsupported PNG filter ${filter}`);
    }
    for (let x = 0; x < width; x += 1) {
      const sourceIndex = x * sourceBytesPerPixel;
      const targetIndex = row + x * 4;
      pixels[targetIndex] = unfiltered[sourceIndex];
      pixels[targetIndex + 1] = unfiltered[sourceIndex + 1];
      pixels[targetIndex + 2] = unfiltered[sourceIndex + 2];
      pixels[targetIndex + 3] = colorType === 6 ? unfiltered[sourceIndex + 3] : 255;
    }
  }
  return { width, height, pixels };
}

function pixelDiff(leftPath, rightPath) {
  const left = decodePng(leftPath);
  const right = decodePng(rightPath);
  if (left.width !== right.width || left.height !== right.height) {
    return {
      comparable: false,
      changed_pixels: null,
      changed_ratio: 1,
      mean_absolute_rgb_delta: null,
      max_rgb_delta: null,
      changed_region: null,
    };
  }
  let changed = 0;
  let totalDelta = 0;
  let maxDelta = 0;
  let minX = left.width;
  let minY = left.height;
  let maxX = -1;
  let maxY = -1;
  for (let y = 0; y < left.height; y += 1) {
    for (let x = 0; x < left.width; x += 1) {
      const index = (y * left.width + x) * 4;
      const delta = Math.abs(left.pixels[index] - right.pixels[index])
        + Math.abs(left.pixels[index + 1] - right.pixels[index + 1])
        + Math.abs(left.pixels[index + 2] - right.pixels[index + 2]);
      totalDelta += delta;
      maxDelta = Math.max(maxDelta, delta);
      if (delta > 30) {
        changed += 1;
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
    }
  }
  const totalPixels = left.width * left.height;
  return {
    comparable: true,
    changed_pixels: changed,
    changed_ratio: Number((changed / totalPixels).toFixed(6)),
    mean_absolute_rgb_delta: Number((totalDelta / totalPixels / 3).toFixed(4)),
    max_rgb_delta: maxDelta,
    changed_region: maxX < 0 ? null : { x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1 },
  };
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
    await page.locator("svg.lab-canvas").evaluate((element) => {
      const css = [...document.styleSheets].flatMap((sheet) => {
        try { return [...sheet.cssRules].map((rule) => rule.cssText); } catch { return []; }
      }).join("\n");
      const clone = element.cloneNode(true);
      clone.querySelectorAll("foreignObject, .detail-selection").forEach((item) => item.remove());
      clone.querySelectorAll(".selected").forEach((item) => item.classList.remove("selected"));
      return clone.outerHTML
        .replace(/\sstyle="[^"]*"/, "")
        .replace("<defs>", `<style>${css}\n.lab-canvas{display:block!important;width:100%!important;min-width:0!important;height:100%!important;border:0!important;box-shadow:none!important}</style><defs>`);
    }),
  );

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`${PROTOTYPE_URL}/?scene=sequence-generative-catalog&expand=bidirectional-recurrent&drilldown=rnn`);
  await page.locator(".nested-inline-detail").first().waitFor({ state: "visible" });
  await page.screenshot({ path: resolve(BUILD, "recursive-formal-hierarchy.png") });
  writeFileSync(
    resolve(BUILD, "recursive-formal-hierarchy.svg"),
    await page.locator("svg.lab-canvas").evaluate((element) => {
      const css = [...document.styleSheets].flatMap((sheet) => {
        try { return [...sheet.cssRules].map((rule) => rule.cssText); } catch { return []; }
      }).join("\n");
      const clone = element.cloneNode(true);
      clone.querySelectorAll("foreignObject, .detail-selection").forEach((item) => item.remove());
      clone.querySelectorAll(".selected").forEach((item) => item.classList.remove("selected"));
      return clone.outerHTML
        .replace(/\sstyle="[^"]*"/, "")
        .replace("<defs>", `<style>${css}\n.lab-canvas{display:block!important;width:100%!important;min-width:0!important;height:100%!important;border:0!important;box-shadow:none!important}</style><defs>`);
    }),
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
  const interactionOnly = new Set(["parent-child-internal-drag", "recursive-formal-hierarchy"]);
  for (let index = 0; index < ids.length; index += 1) {
    const id = ids[index];
    const viewport = viewports[index % viewports.length];
    const buildPng = resolve(BUILD, `${id}.png`);
    const productionPng = resolve(PRODUCTION, `${id}.png`);
    const build = await renderSvg(page, resolve(BUILD, `${id}.svg`), buildPng, viewport);
    const production = await renderSvg(page, resolve(PRODUCTION, `${id}.svg`), productionPng, viewport);
    const visualDiff = pixelDiff(buildPng, productionPng);
    cases.push({
      id,
      viewport,
      build: { file: `build/${id}.png`, sha256: sha256(buildPng), ...build },
      production: { file: `production/${id}.png`, sha256: sha256(productionPng), ...production },
      visual_diff: visualDiff,
      checks: {
        build_nonblank: build.bytes > 1024,
        production_nonblank: production.bytes > 1024,
        stable_viewport: build.screenshotWidth === viewport.width
          && build.screenshotHeight === viewport.height
          && production.screenshotWidth === viewport.width
          && production.screenshotHeight === viewport.height,
        visual_match: interactionOnly.has(id) ? null : visualDiff.comparable
          && visualDiff.changed_ratio <= 0.35
          && visualDiff.mean_absolute_rgb_delta <= 18,
        visual_comparison_scope: interactionOnly.has(id) ? "interaction-only" : "static-export",
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
      const svgPath = resolve(BUILD, `${id}.svg`);
      const rendered = await renderSvg(page, svgPath, path, record.viewport);
      record.build = {
        ...record.build,
        sha256: sha256(path),
        ...rendered,
        interactive: true,
      };
      record.visual_diff = pixelDiff(path, resolve(PRODUCTION, `${id}.png`));
      record.checks.stable_viewport = record.build.screenshotWidth === record.viewport.width
        && record.build.screenshotHeight === record.viewport.height
        && record.production.screenshotWidth === record.viewport.width
        && record.production.screenshotHeight === record.viewport.height;
      record.checks.visual_match = null;
      record.checks.visual_comparison_scope = "interaction-only";
    }
  }
  writeReport();
} finally {
  await browser.close();
  server.kill("SIGTERM");
}
