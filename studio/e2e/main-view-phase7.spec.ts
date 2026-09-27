import { expect, test, type Download, type Page } from "@playwright/test";
import { mkdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";

async function closeOpenDialog(page: Page) {
  const dialog = page.getByRole("dialog", { name: "Open model" });
  try {
    await dialog.waitFor({ state: "visible", timeout: 5_000 });
    await dialog.getByRole("button", { name: "Close" }).click();
  } catch {
    // The launcher is optional once a project is active.
  }
}

async function downloadFromMenu(page: Page, itemName: RegExp): Promise<Download> {
  await page.locator('summary[aria-label="Export main view"]').click();
  const pending = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: itemName }).click();
  return pending;
}

test("Phase 7 exports the exact kernel scene to SVG, PNG, and PDF", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("archcanvas.locale", "en"));
  await page.goto("/");
  await closeOpenDialog(page);

  const expandable = page.locator(".kernel-module-toggle.collapsed").first();
  if (await expandable.count()) {
    const response = page.waitForResponse((candidate) => candidate.url().endsWith("/api/patch-batch"));
    await expandable.click();
    expect((await response).ok()).toBe(true);
  }

  const screen = page.locator("svg.kernel-scene");
  await expect(screen).toHaveAttribute("data-kernel-render-digest", /^kernel-render:/);
  const screenSnapshot = await screen.evaluate((svg) => ({
    digest: svg.getAttribute("data-kernel-render-digest"),
    sourceDigest: svg.getAttribute("data-source-digest"),
    nodes: svg.querySelectorAll("[data-kernel-node-id]").length,
    edges: svg.querySelectorAll(".kernel-edge[data-kernel-edge-id]").length,
    paths: [...svg.querySelectorAll<SVGPathElement>(".kernel-edge > path:first-child")].map((path) => path.getAttribute("d")),
    labels: [...svg.querySelectorAll<SVGGElement>(".kernel-edge-label")].map((label) => ({
      transform: label.getAttribute("transform"),
      text: label.textContent,
    })),
    detailSlots: svg.querySelectorAll("[data-detail-slot-id]").length,
    portals: svg.querySelectorAll("[data-portal-id]").length,
  }));
  const visibleLegendCount = await page.locator(".kernel-relation-legend span").count();

  const svgDownload = await downloadFromMenu(page, /SVG Main view vector/);
  const svgPath = await svgDownload.path();
  if (!svgPath) throw new Error("SVG download has no local path");
  const svgText = await readFile(svgPath, "utf8");
  const exported = await page.evaluate((source) => {
    const root = new DOMParser().parseFromString(source, "image/svg+xml").documentElement;
    return {
      parseError: root.querySelector("parsererror")?.textContent ?? null,
      digest: root.getAttribute("data-render-digest"),
      sourceDigest: root.getAttribute("data-source-digest"),
      version: root.getAttribute("data-kernel-version"),
      nodes: root.querySelectorAll("[data-kernel-node-id]").length,
      edges: root.querySelectorAll(".kernel-edge[data-kernel-edge-id]").length,
      paths: [...root.querySelectorAll(".kernel-edge > path")].map((path) => path.getAttribute("d")),
      labels: [...root.querySelectorAll(".kernel-edge-label")].map((label) => ({
        transform: label.getAttribute("transform"),
        text: label.textContent,
      })),
      detailSlots: root.querySelectorAll("[data-detail-slot-id]").length,
      portals: root.querySelectorAll("[data-portal-id]").length,
      legend: Number(root.querySelector(".kernel-export-legend")?.getAttribute("data-relation-count")),
      provenance: {
        canonicalNodes: root.querySelectorAll("[data-canonical-node-ids]").length,
        canonicalEdges: root.querySelectorAll("[data-canonical-edge-ids]").length,
        portEndpoints: root.querySelectorAll("[data-source-port-id][data-target-port-id]").length,
        evidence: root.querySelectorAll("[data-evidence-ids]").length,
        bindings: root.querySelectorAll("[data-template-binding-id]").length,
      },
    };
  }, svgText);

  expect(exported.parseError).toBeNull();
  expect(exported.version).toBe("visual-kernel-svg-v1");
  expect(exported.digest).toBe(screenSnapshot.digest);
  expect(exported.sourceDigest).toBe(screenSnapshot.sourceDigest);
  expect(exported.nodes).toBe(screenSnapshot.nodes);
  expect(exported.edges).toBe(screenSnapshot.edges);
  expect(exported.paths).toEqual(screenSnapshot.paths);
  expect(exported.labels).toEqual(screenSnapshot.labels);
  expect(exported.detailSlots).toBe(screenSnapshot.detailSlots);
  expect(exported.portals).toBe(screenSnapshot.portals);
  expect(exported.legend).toBe(visibleLegendCount);
  expect(exported.provenance.canonicalNodes).toBeGreaterThan(0);
  expect(exported.provenance.canonicalEdges).toBe(exported.edges);
  expect(exported.provenance.portEndpoints).toBe(exported.edges);
  expect(exported.provenance.evidence).toBeGreaterThan(0);

  const qaDirectory = resolve(process.cwd(), "../tmp/pdfs");
  await mkdir(qaDirectory, { recursive: true });
  const pngDownload = await downloadFromMenu(page, /PNG Main view image/);
  const pngOutput = resolve(qaDirectory, "phase7-main-view.png");
  await pngDownload.saveAs(pngOutput);
  const png = await readFile(pngOutput);
  expect(png.subarray(0, 8)).toEqual(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
  expect(png.readUInt32BE(16)).toBeGreaterThan(100);
  expect(png.readUInt32BE(20)).toBeGreaterThan(100);

  const pdfDownload = await downloadFromMenu(page, /PDF Main view document/);
  const pdfOutput = resolve(qaDirectory, "phase7-main-view.pdf");
  await pdfDownload.saveAs(pdfOutput);
  expect((await readFile(pdfOutput)).subarray(0, 5).toString()).toBe("%PDF-");

  const publication = await page.request.get("/api/publication-export");
  expect(publication.ok()).toBe(true);
  expect(publication.headers()["x-archcanvas-export-scope"]).toBe("publication");
  expect(publication.headers()["deprecation"]).toBeUndefined();
  const legacy = await page.request.get("/api/export");
  expect(legacy.headers()["x-archcanvas-export-scope"]).toBe("publication");
  expect(legacy.headers()["deprecation"]).toBe("true");
  expect(legacy.headers()["link"]).toContain("/api/publication-export");
});
