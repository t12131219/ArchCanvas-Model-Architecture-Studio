import { expect, test, type Locator, type Page } from "@playwright/test";

async function drag(page: Page, locator: Locator, dx: number, dy: number) {
  const box = await locator.boundingBox();
  if (!box) throw new Error("drag target is not visible");
  const start = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(start.x + dx, start.y + dy, { steps: 8 });
  await page.mouse.up();
}

async function setExpanded(page: Page, label: string, expanded: boolean) {
  const navigation = page.locator(".left-panel");
  const desired = expanded ? `Expand ${label}` : `Collapse ${label}`;
  const settled = expanded ? `Collapse ${label}` : `Expand ${label}`;
  const button = navigation.getByRole("button", { name: desired, exact: true });
  if (await button.count()) {
    const response = page.waitForResponse((candidate) => (
      candidate.url().endsWith("/api/navigation") && candidate.request().method() === "POST"
    ));
    await button.click();
    expect((await response).ok()).toBe(true);
    await expect(navigation.getByRole("button", { name: settled, exact: true })).toBeVisible();
  } else {
    const settledButton = navigation.getByRole("button", { name: settled, exact: true });
    if (await settledButton.count()) await expect(settledButton).toBeVisible();
    else if (expanded) throw new Error(`module ${label} is not available for expansion`);
  }
}

test("Phase 5 main view supports hierarchy and direct manipulation across viewports", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("archcanvas.locale", "en"));
  await page.goto("/");
  await page.getByRole("dialog", { name: "Open model" }).getByRole("button", { name: "Close" }).click();

  const scene = page.locator("svg.kernel-scene");
  await expect(scene).toBeVisible();
  await expect(page.locator(".kernel-node").first()).toBeVisible();
  expect(await page.locator(".kernel-edge-hit").count()).toBeGreaterThan(0);
  await page.screenshot({ path: "/tmp/archcanvas-phase5-desktop.png", fullPage: true });

  await setExpanded(page, "q", false);
  await setExpanded(page, "k", false);
  await setExpanded(page, "encoder", false);
  await setExpanded(page, "encoder", true);
  const encoder = page.locator(".kernel-expanded-module").filter({ hasText: /^encoder/ }).first();
  await expect(encoder).toBeVisible();
  await setExpanded(page, "q", true);
  await setExpanded(page, "k", true);
  await expect.poll(async () => page.locator(".kernel-expanded-module").count()).toBeGreaterThanOrEqual(4);

  await encoder.locator(".kernel-expanded-title").click();
  await page.locator(".kernel-control-strip").getByRole("button", { name: "Focus selection" }).click();
  const encoderHandle = page.locator(".kernel-resize-handle").first();
  await expect(encoderHandle).toBeVisible();
  const encoderWidth = Number(await encoder.locator(".kernel-expanded-surface").getAttribute("width"));
  await drag(page, encoderHandle, 54, 34);
  await expect.poll(async () => Number(await encoder.locator(".kernel-expanded-surface").getAttribute("width"))).toBeGreaterThan(encoderWidth);

  const encoderBounds = await encoder.locator(".kernel-expanded-surface").evaluate((element) => ({
    x: Number(element.getAttribute("x")),
    y: Number(element.getAttribute("y")),
    width: Number(element.getAttribute("width")),
    height: Number(element.getAttribute("height")),
  }));
  const nestedNodeId = await page.locator(".kernel-node").evaluateAll((elements, bounds) => elements
    .map((element) => {
      const body = element.querySelector<SVGGraphicsElement>(".kernel-node-body");
      const box = body?.getBBox();
      return box ? { id: (element as SVGGElement).dataset.kernelNodeId, box } : null;
    })
    .filter((item): item is { id: string; box: DOMRect } => Boolean(item?.id)
      && item!.box.x >= bounds.x
      && item!.box.y >= bounds.y + 50
      && item!.box.x + item!.box.width <= bounds.x + bounds.width
      && item!.box.y + item!.box.height <= bounds.y + bounds.height)
    .sort((left, right) => left.box.x + left.box.y - right.box.x - right.box.y)[0]?.id, encoderBounds);
  if (!nestedNodeId) throw new Error("expanded encoder has no interactive child");
  const nestedNode = page.locator(`.kernel-node[data-kernel-node-id="${nestedNodeId}"]`);
  await nestedNode.click();
  const nestedBody = nestedNode.locator(".kernel-node-body");
  const beforeX = Number(await nestedBody.getAttribute("x"));
  await drag(page, nestedNode, 24, 18);
  await expect.poll(async () => Number(await nestedBody.getAttribute("x"))).not.toBe(beforeX);

  await nestedNode.click();
  const resizeHandle = page.locator(".kernel-resize-handle").first();
  await expect(resizeHandle).toBeVisible();
  const beforeWidth = Number(await nestedBody.getAttribute("width"));
  await drag(page, resizeHandle, 30, 20);
  await expect.poll(async () => Number(await nestedBody.getAttribute("width"))).toBeGreaterThan(beforeWidth);

  const nodeBoxes = await page.locator(".kernel-node").evaluateAll((elements) => elements.slice(0, 3).map((element) => element.getBoundingClientRect().toJSON()));
  const sceneBox = await scene.boundingBox();
  if (!sceneBox || nodeBoxes.length < 2) throw new Error("selection fixture is not visible");
  const end = {
    x: Math.min(...nodeBoxes.map((box) => box.x)) - 6,
    y: Math.min(...nodeBoxes.map((box) => box.y)) - 6,
  };
  await page.keyboard.down("Shift");
  await page.mouse.move(sceneBox.x + sceneBox.width - 12, sceneBox.y + sceneBox.height - 12);
  await page.mouse.down();
  await page.mouse.move(end.x, end.y, { steps: 10 });
  await page.mouse.up();
  await page.keyboard.up("Shift");
  await expect.poll(async () => page.locator(".kernel-node.selected").count()).toBeGreaterThan(1);

  const edgeTarget = await page.locator(".kernel-edge-hit").evaluateAll((paths) => {
    for (const path of paths as SVGPathElement[]) {
      const matrix = path.getScreenCTM();
      if (!matrix) continue;
      const length = path.getTotalLength();
      for (const ratio of [0.2, 0.35, 0.5, 0.65, 0.8]) {
        const point = path.getPointAtLength(length * ratio).matrixTransform(matrix);
        if (document.elementFromPoint(point.x, point.y) === path) {
          return { x: point.x, y: point.y, edgeId: path.parentElement?.getAttribute("data-kernel-edge-id") };
        }
      }
    }
    return null;
  });
  if (!edgeTarget?.edgeId) throw new Error("no visible edge hit target");
  await page.mouse.click(edgeTarget.x, edgeTarget.y);
  await expect(page.locator(`[data-kernel-edge-id="${edgeTarget.edgeId}"]`)).toHaveClass(/selected/);
  await expect(page.getByText("Canonical architecture relation", { exact: true })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(scene).toBeVisible();
  const mobileSceneBox = await scene.boundingBox();
  expect(mobileSceneBox?.width).toBeGreaterThan(250);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole("button", { name: "Open inspector" }).click();
  await expect(page.locator(".right-panel.mobile-open")).toBeVisible();
  await page.screenshot({ path: "/tmp/archcanvas-phase5-mobile.png", fullPage: true });

  await page.setViewportSize({ width: 1440, height: 900 });
  await setExpanded(page, "q", false);
  await setExpanded(page, "k", false);
  await setExpanded(page, "encoder", false);
  await page.locator(".kernel-paper").click({ position: { x: 12, y: 12 }, force: true });
});
