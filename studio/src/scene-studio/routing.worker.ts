/// <reference lib="webworker" />

import { measureScene, routeScene } from "./routing";
import type { RoutingWorkerRequest, RoutingWorkerResponse } from "./routing-worker-protocol";

function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

self.onmessage = (event: MessageEvent<RoutingWorkerRequest>) => {
  const request = event.data;
  if (request.type !== "route") return;
  const startedAt = performance.now();
  try {
    const routes = routeScene(request.scene, request.style, request.boundaryPorts);
    const response: RoutingWorkerResponse = {
      type: "route-complete",
      requestId: request.requestId,
      durationMs: performance.now() - startedAt,
      routes,
      metrics: measureScene(request.scene, routes),
    };
    self.postMessage(response);
  } catch (error) {
    const response: RoutingWorkerResponse = {
      type: "route-failed",
      requestId: request.requestId,
      message: messageFor(error),
    };
    self.postMessage(response);
  }
};

export {};
