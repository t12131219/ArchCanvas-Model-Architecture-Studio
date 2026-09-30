import { describe, expect, it } from "vitest";

import {
  canvasGridSize,
  fitCanvasCamera,
  MAX_CANVAS_ZOOM,
  MIN_CANVAS_ZOOM,
  shouldBeginCanvasPan,
  wheelZoomFactor,
  zoomCameraAt,
} from "./canvas-viewport";

describe("infinite canvas camera", () => {
  it("keeps the world point under the pointer fixed while zooming", () => {
    const camera = { x: 80, y: 40, zoom: 0.5 };
    const anchor = { x: 320, y: 220 };
    const worldBefore = {
      x: (anchor.x - camera.x) / camera.zoom,
      y: (anchor.y - camera.y) / camera.zoom,
    };
    const next = zoomCameraAt(camera, 1.25, anchor);

    expect((anchor.x - next.x) / next.zoom).toBeCloseTo(worldBefore.x);
    expect((anchor.y - next.y) / next.zoom).toBeCloseTo(worldBefore.y);
  });

  it("clamps zoom without shifting an origin anchor", () => {
    const camera = { x: 0, y: 0, zoom: 1 };
    expect(zoomCameraAt(camera, 100, { x: 0, y: 0 })).toEqual({ x: 0, y: 0, zoom: MAX_CANVAS_ZOOM });
    expect(zoomCameraAt(camera, 0.001, { x: 0, y: 0 })).toEqual({ x: 0, y: 0, zoom: MIN_CANVAS_ZOOM });
  });

  it("centers and fits the scene inside the viewport", () => {
    const camera = fitCanvasCamera({ width: 1000, height: 700 }, { x: 200, y: 100, width: 1800, height: 900 }, 50);
    expect(camera.zoom).toBeCloseTo(0.5);
    expect(camera.x).toBeCloseTo(-50);
    expect(camera.y).toBeCloseTo(75);
  });

  it("keeps the visible dot grid legible across zoom levels", () => {
    for (const zoom of [MIN_CANVAS_ZOOM, 0.28, 1, 2, MAX_CANVAS_ZOOM]) {
      expect(canvasGridSize(zoom)).toBeGreaterThanOrEqual(18);
      expect(canvasGridSize(zoom)).toBeLessThanOrEqual(36);
    }
  });

  it("maps every wheel event to a stable zoom direction", () => {
    expect(wheelZoomFactor(-100, 0)).toBeGreaterThan(1);
    expect(wheelZoomFactor(100, 0)).toBeLessThan(1);
    expect(wheelZoomFactor(-1, 1)).toBeGreaterThan(1);
    expect(wheelZoomFactor(0, 0)).toBe(1);
  });

  it("starts middle-button panning over both nodes and empty canvas", () => {
    expect(shouldBeginCanvasPan(1, false, false)).toBe(true);
    expect(shouldBeginCanvasPan(1, true, false)).toBe(true);
    expect(shouldBeginCanvasPan(0, true, false)).toBe(true);
    expect(shouldBeginCanvasPan(0, false, false)).toBe(false);
    expect(shouldBeginCanvasPan(1, false, true)).toBe(false);
  });
});
