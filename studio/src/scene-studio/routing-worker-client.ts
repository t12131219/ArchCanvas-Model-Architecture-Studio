import type { LabScene, RouteStyle, SceneBoundaryPortMap } from "./types";
import type {
  RoutingWorkerRequest,
  RoutingWorkerResponse,
  RoutingWorkerSuccess,
} from "./routing-worker-protocol";

interface RoutingWorkerPort {
  onmessage: ((event: MessageEvent<RoutingWorkerResponse>) => void) | null;
  onerror: ((event: ErrorEvent) => void) | null;
  postMessage(message: RoutingWorkerRequest): void;
  terminate(): void;
}

export interface RoutingTask {
  requestId: string;
  promise: Promise<RoutingWorkerSuccess>;
  cancel(): void;
}

function createRoutingWorker(): RoutingWorkerPort {
  return new Worker(new URL("./routing.worker.ts", import.meta.url), { type: "module" });
}

function abortError(): Error {
  const error = new Error("Routing cancelled");
  error.name = "AbortError";
  return error;
}

export function startWorkerRouting(
  scene: LabScene,
  style: RouteStyle,
  boundaryPorts?: SceneBoundaryPortMap,
  workerFactory: () => RoutingWorkerPort = createRoutingWorker,
): RoutingTask {
  const requestId = crypto.randomUUID();
  const worker = workerFactory();
  let settled = false;
  let rejectTask: (reason: unknown) => void = () => undefined;
  const finish = () => {
    if (settled) return false;
    settled = true;
    worker.terminate();
    return true;
  };
  const promise = new Promise<RoutingWorkerSuccess>((resolve, reject) => {
    rejectTask = reject;
    worker.onmessage = (event) => {
      if (event.data.requestId !== requestId || !finish()) return;
      if (event.data.type === "route-failed") reject(new Error(event.data.message));
      else resolve(event.data);
    };
    worker.onerror = (event) => {
      if (!finish()) return;
      reject(new Error(event.message || "Routing worker failed"));
    };
    worker.postMessage({
      type: "route",
      requestId,
      scene,
      style,
      boundaryPorts,
    });
  });
  return {
    requestId,
    promise,
    cancel() {
      if (!finish()) return;
      rejectTask(abortError());
    },
  };
}
