import { expect, test } from "@playwright/test";
import type { Locator } from "@playwright/test";

const SCENES = [
  "classic-transformer",
  "tensor2tensor-transformer",
  "vision-sequence-catalog",
] as const;
const PROTOTYPE_BASE_URL = process.env.ARCHCANVAS_PROTOTYPE_E2E_BASE_URL
  ?? "http://127.0.0.1:4312";

async function firstVisibleCandidate(
  candidates: Locator,
  viewportBounds: { x: number; y: number; width: number; height: number },
) {
  for (let index = 0; index < await candidates.count(); index += 1) {
    const candidate = candidates.nth(index);
    const bounds = await candidate.boundingBox();
    if (bounds
      && bounds.width >= 3
      && bounds.height >= 3
      && bounds.x + bounds.width / 2 >= viewportBounds.x
      && bounds.y + bounds.height / 2 >= viewportBounds.y
      && bounds.x + bounds.width / 2 <= viewportBounds.x + viewportBounds.width
      && bounds.y + bounds.height / 2 <= viewportBounds.y + viewportBounds.height) {
      return { candidate, bounds };
    }
  }
  return undefined;
}

for (const sceneId of SCENES) {
  test(`${sceneId} remains interactive when fully expanded`, async ({ page }) => {
    await page.goto(`${PROTOTYPE_BASE_URL}/?scene=${sceneId}&qa=expanded-interaction`);

    const bulkActions = page.locator(".detail-bulk-actions");
    await page.getByRole("button", { name: "全部展开" }).click();
    await expect(bulkActions).toHaveAttribute("aria-busy", "false", { timeout: 30_000 });
    await expect(page.locator(".expanded-node").first()).toBeVisible();
    await expect(page.locator(".nested-inline-detail").first()).toBeVisible();

    const viewport = page.locator(".canvas-viewport");
    const canvas = page.locator("svg.lab-canvas");
    const viewportBounds = await viewport.boundingBox();
    expect(viewportBounds).not.toBeNull();
    if (!viewportBounds) return;

    const movableCandidates = page.locator(
      ".lab-node:not(.expanded-node) > .node-surface, .expanded-node > .expanded-header",
    );
    const visibleMovable = await firstVisibleCandidate(movableCandidates, viewportBounds);
    expect(visibleMovable).toBeDefined();
    if (!visibleMovable) return;
    const { candidate: movable, bounds: movableBounds } = visibleMovable;
    const xBefore = await movable.getAttribute("x")
      ?? await movable.getAttribute("cx")
      ?? await movable.getAttribute("points");
    await page.mouse.move(
      movableBounds.x + movableBounds.width / 2,
      movableBounds.y + movableBounds.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      movableBounds.x + movableBounds.width / 2 + 45,
      movableBounds.y + movableBounds.height / 2 + 30,
      { steps: 8 },
    );
    await page.mouse.up();
    await expect.poll(async () => (
      await movable.getAttribute("x")
        ?? await movable.getAttribute("cx")
        ?? await movable.getAttribute("points")
    )).not.toBe(xBefore);

    const atomic = await firstVisibleCandidate(page.locator(".detail-interactive-node"), viewportBounds);
    expect(atomic).toBeDefined();
    if (!atomic) return;
    const atomicBoundsBefore = await atomic.candidate.evaluate((element) => {
      const bounds = (element as SVGGElement).getBBox();
      return { x: bounds.x, y: bounds.y };
    });
    const detailFlowPointsBefore = await atomic.candidate.evaluate((element) => (
      [...element.closest(".detail-level")!.querySelectorAll(":scope > .detail-flow")]
        .map((flow) => flow.getAttribute("points"))
    ));
    const detailDragStartedAt = Date.now();
    await page.mouse.move(
      atomic.bounds.x + atomic.bounds.width / 2,
      atomic.bounds.y + atomic.bounds.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      atomic.bounds.x + atomic.bounds.width / 2 + 36,
      atomic.bounds.y + atomic.bounds.height / 2 + 24,
      { steps: 4 },
    );
    await expect.poll(() => atomic.candidate.getAttribute("transform"), { timeout: 1_000 }).toContain("translate(");
    expect(Date.now() - detailDragStartedAt).toBeLessThan(1_000);
    await expect.poll(async () => atomic.candidate.evaluate((element) => (
      [...element.closest(".detail-level")!.querySelectorAll(":scope > .detail-flow")]
        .map((flow) => flow.getAttribute("points"))
    ))).not.toEqual(detailFlowPointsBefore);
    await page.mouse.up();
    await expect.poll(async () => atomic.candidate.evaluate((element) => {
      const bounds = (element as SVGGElement).getBBox();
      return { x: bounds.x, y: bounds.y };
    }), { timeout: 2_000 }).not.toEqual(atomicBoundsBefore);

    const nested = await firstVisibleCandidate(page.locator(".nested-inline-header"), viewportBounds);
    expect(nested).toBeDefined();
    if (!nested) return;
    const nestedXBefore = await nested.candidate.getAttribute("x");
    const nestedDragStartedAt = Date.now();
    await page.mouse.move(
      nested.bounds.x + nested.bounds.width / 2,
      nested.bounds.y + nested.bounds.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      nested.bounds.x + nested.bounds.width / 2 + 32,
      nested.bounds.y + nested.bounds.height / 2 + 20,
      { steps: 4 },
    );
    await expect.poll(() => nested.candidate.locator("..").getAttribute("transform"), { timeout: 1_000 }).toContain("translate(");
    expect(Date.now() - nestedDragStartedAt).toBeLessThan(1_000);
    await page.mouse.up();
    await expect.poll(() => nested.candidate.getAttribute("x"), { timeout: 2_000 }).not.toBe(nestedXBefore);

    const transformBeforePan = await canvas.getAttribute("style");
    const panStart = {
      x: viewportBounds.x + viewportBounds.width * 0.65,
      y: viewportBounds.y + viewportBounds.height * 0.3,
    };
    await page.mouse.move(panStart.x, panStart.y);
    await page.mouse.down({ button: "middle" });
    await page.mouse.move(panStart.x + 90, panStart.y + 70, { steps: 8 });
    await page.mouse.up({ button: "middle" });
    await expect.poll(() => canvas.getAttribute("style")).not.toBe(transformBeforePan);

    const zoomBefore = await page.getByLabel("当前缩放比例").textContent();
    await page.mouse.move(
      viewportBounds.x + viewportBounds.width / 2,
      viewportBounds.y + viewportBounds.height / 2,
    );
    await page.mouse.wheel(0, -240);
    await expect.poll(() => page.getByLabel("当前缩放比例").textContent()).not.toBe(zoomBefore);

    await page.getByRole("button", { name: "全部收起" }).click();
    await expect(page.locator(".expanded-node")).toHaveCount(0);
    await expect(page.locator(".nested-inline-detail")).toHaveCount(0);
  });
}
