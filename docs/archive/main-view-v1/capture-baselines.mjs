import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import playwright from "../../../studio/node_modules/@playwright/test/index.js";

const { chromium } = playwright;

const archiveRoot = dirname(fileURLToPath(import.meta.url));
const baselineRoot = resolve(archiveRoot, "baselines");
const fixtureRoot = resolve(archiveRoot, "fixtures");
const baseUrl = process.env.ARCHCANVAS_BASE_URL ?? "http://127.0.0.1:4311";

await mkdir(baselineRoot, { recursive: true });
await mkdir(fixtureRoot, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

await page.addInitScript(() => {
  window.localStorage.setItem("archcanvas.locale", "en");
  window.localStorage.removeItem("archcanvas.theme");
});
await page.goto(baseUrl, { waitUntil: "networkidle" });
await page.getByRole("dialog", { name: "Open model" })
  .getByRole("button", { name: "Close" })
  .click();
await page.locator("svg.scene").waitFor({ state: "visible" });

const state = await page.evaluate(async () => {
  const response = await fetch("/api/state", { cache: "no-store" });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
});
await writeFile(resolve(fixtureRoot, "studio-state.json"), `${JSON.stringify(state, null, 2)}\n`);
await writeFile(resolve(fixtureRoot, "canvas-document.json"), `${JSON.stringify(state.document, null, 2)}\n`);
await writeFile(resolve(fixtureRoot, "architecture.json"), `${JSON.stringify(state.architecture, null, 2)}\n`);

await page.screenshot({ path: resolve(baselineRoot, "desktop-light.png") });

await page.getByRole("button", { name: "Toggle theme" }).click();
await page.screenshot({ path: resolve(baselineRoot, "desktop-dark.png") });
await page.getByRole("button", { name: "Toggle theme" }).click();

await page.getByRole("button", { name: "Expand encoder" }).click();
await page.waitForTimeout(250);
await page.screenshot({ path: resolve(baselineRoot, "expanded-module.png") });

const node = page.locator(".scene-node:not(.root)").first();
await node.click();
await page.screenshot({ path: resolve(baselineRoot, "selected-node.png") });

for (const tab of ["Overview", "Source", "Visual", "Model", "Evidence"]) {
  await page.locator(".tab-strip").getByRole("button", { name: tab, exact: true }).click();
  await page.screenshot({ path: resolve(baselineRoot, `inspector-${tab.toLowerCase()}.png`) });
}
await page.locator(".tab-strip").getByRole("button", { name: "Overview", exact: true }).click();

for (const [tab, file] of [["Problems", "problems"], ["Validation", "validation"], ["Jobs", "jobs"]]) {
  await page.locator(".bottom-tabs").getByRole("button", { name: new RegExp(`^${tab}`) }).click();
  await page.screenshot({ path: resolve(baselineRoot, `bottom-${file}.png`) });
}

const sceneBox = await page.locator("svg.scene").boundingBox();
const candidateBoxes = await page.locator(".scene-node:not(.root)").evaluateAll((elements) =>
  elements.slice(0, 3).map((element) => element.getBoundingClientRect().toJSON()),
);
if (sceneBox && candidateBoxes.length) {
  const targetX = Math.min(...candidateBoxes.map((box) => box.x)) - 6;
  const targetY = Math.min(...candidateBoxes.map((box) => box.y)) - 6;
  await page.keyboard.down("Shift");
  await page.mouse.move(sceneBox.x + sceneBox.width - 12, sceneBox.y + sceneBox.height - 12);
  await page.mouse.down();
  await page.mouse.move(targetX, targetY, { steps: 10 });
  await page.mouse.up();
  await page.keyboard.up("Shift");
  await page.screenshot({ path: resolve(baselineRoot, "post-marquee.png") });
}

const edge = page.locator('[data-scene-edge-id][data-edge-layer="base"]').first();
await edge.click({ force: true });
await page.screenshot({ path: resolve(baselineRoot, "selected-edge.png") });

const nodeBox = await node.boundingBox();
if (nodeBox) {
  const startX = nodeBox.x + nodeBox.width / 2;
  const startY = nodeBox.y + nodeBox.height / 2;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX + 48, startY + 28, { steps: 4 });
  await page.screenshot({ path: resolve(baselineRoot, "dragging-node.png") });
  await page.mouse.up();
}

await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({ path: resolve(baselineRoot, "mobile.png") });

const exportResponse = await page.request.get(`${baseUrl}/api/export`);
if (!exportResponse.ok()) throw new Error(await exportResponse.text());
await writeFile(resolve(baselineRoot, "main-view.svg"), await exportResponse.body());

await browser.close();
