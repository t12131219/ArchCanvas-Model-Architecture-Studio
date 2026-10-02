import type {
  PythonSyntaxSuccess,
  PythonSyntaxWorkerRequest,
  PythonSyntaxWorkerResponse,
} from "./python-syntax-protocol";

interface PythonSyntaxWorkerPort {
  onmessage: ((event: MessageEvent<PythonSyntaxWorkerResponse>) => void) | null;
  onerror: ((event: ErrorEvent) => void) | null;
  postMessage(message: PythonSyntaxWorkerRequest): void;
  terminate(): void;
}

interface PendingParse {
  resolve: (result: PythonSyntaxSuccess) => void;
  reject: (reason: unknown) => void;
}

export interface PythonSyntaxService {
  parse(request: Omit<PythonSyntaxWorkerRequest, "type" | "requestId">): Promise<PythonSyntaxSuccess>;
  terminate(): void;
}

function createWorker(): PythonSyntaxWorkerPort {
  return new Worker(new URL("./python-syntax.worker.ts", import.meta.url), { type: "module" });
}

export function createPythonSyntaxService(
  workerFactory: () => PythonSyntaxWorkerPort = createWorker,
): PythonSyntaxService {
  const worker = workerFactory();
  const pending = new Map<string, PendingParse>();
  let terminated = false;

  const rejectAll = (reason: unknown) => {
    for (const task of pending.values()) task.reject(reason);
    pending.clear();
  };
  worker.onmessage = (event) => {
    const task = pending.get(event.data.requestId);
    if (!task) return;
    pending.delete(event.data.requestId);
    if (event.data.type === "python-syntax-failed") task.reject(new Error(event.data.message));
    else task.resolve(event.data);
  };
  worker.onerror = (event) => rejectAll(new Error(event.message || "Python syntax worker failed"));

  return {
    parse(request) {
      if (terminated) return Promise.reject(new Error("Python syntax service is terminated"));
      const requestId = crypto.randomUUID();
      return new Promise<PythonSyntaxSuccess>((resolve, reject) => {
        pending.set(requestId, { resolve, reject });
        worker.postMessage({ type: "parse-python", requestId, ...request });
      });
    },
    terminate() {
      if (terminated) return;
      terminated = true;
      worker.terminate();
      const error = new Error("Python syntax service terminated");
      error.name = "AbortError";
      rejectAll(error);
    },
  };
}
