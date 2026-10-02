import { describe, expect, it, vi } from "vitest";

import { createPythonSyntaxService } from "./python-syntax-worker-client";
import type { PythonSyntaxWorkerRequest, PythonSyntaxWorkerResponse } from "./python-syntax-protocol";

function fakeWorker() {
  return {
    onmessage: null as ((event: MessageEvent<PythonSyntaxWorkerResponse>) => void) | null,
    onerror: null as ((event: ErrorEvent) => void) | null,
    postMessage: vi.fn<(message: PythonSyntaxWorkerRequest) => void>(),
    terminate: vi.fn(),
  };
}

describe("python syntax worker client", () => {
  it("keeps one worker alive for an incremental parse sequence", async () => {
    const worker = fakeWorker();
    const service = createPythonSyntaxService(() => worker);
    const first = service.parse({ text: "def model():\n    pass\n", previousLength: null, edits: [] });
    const request = worker.postMessage.mock.calls[0][0];
    worker.onmessage?.(new MessageEvent("message", { data: {
      type: "python-syntax-complete",
      requestId: request.requestId,
      source: "editor-local",
      parseMode: "full",
      durationMs: 2,
      diagnostics: [],
      folds: [{ from: 12, to: 21, line: 1 }],
      symbols: [{ kind: "function", name: "model", from: 0, to: 21, line: 1 }],
    } satisfies PythonSyntaxWorkerResponse }));

    await expect(first).resolves.toMatchObject({ source: "editor-local", parseMode: "full" });
    expect(worker.terminate).not.toHaveBeenCalled();
    service.terminate();
    expect(worker.terminate).toHaveBeenCalledOnce();
  });

  it("rejects a worker parse failure without presenting it as a source diagnostic", async () => {
    const worker = fakeWorker();
    const service = createPythonSyntaxService(() => worker);
    const result = service.parse({ text: "x =", previousLength: null, edits: [] });
    const request = worker.postMessage.mock.calls[0][0];
    worker.onmessage?.(new MessageEvent("message", { data: {
      type: "python-syntax-failed",
      requestId: request.requestId,
      message: "grammar unavailable",
    } satisfies PythonSyntaxWorkerResponse }));
    await expect(result).rejects.toThrow("grammar unavailable");
    service.terminate();
  });
});
