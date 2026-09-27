import { describe, expect, it, vi } from "vitest";

import { isTerminalJobState, JobPollingController } from "./jobs";

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("JobPollingController", () => {
  it("refreshes state and stops polling on a terminal job", async () => {
    const states: Array<{ revision: number }> = [];
    const cleared: unknown[] = [];
    const scheduler = {
      setInterval: vi.fn(() => 17 as unknown as ReturnType<typeof setInterval>),
      clearInterval: vi.fn((handle: unknown) => cleared.push(handle)),
    };
    let terminal = false;
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/state") return jsonResponse({ revision: terminal ? 2 : 1 });
      return jsonResponse({
        job_id: "job:1",
        profile: "static-analysis",
        state: terminal ? "succeeded" : "running",
        progress: terminal ? 1 : 0.5,
      });
    }) as unknown as typeof fetch;
    const controller = new JobPollingController(
      fetcher,
      (state: { revision: number }) => states.push(state),
      300,
      scheduler,
    );
    const onTerminal = vi.fn();

    controller.start("job:1", onTerminal);
    await controller.check("job:1", onTerminal);
    terminal = true;
    await controller.check("job:1", onTerminal);

    expect(states).toEqual([{ revision: 1 }, { revision: 2 }]);
    expect(onTerminal).toHaveBeenCalledWith(expect.objectContaining({ state: "succeeded" }));
    expect(controller.activeCount).toBe(0);
    expect(cleared).toEqual([17]);
  });

  it("sends the session nonce when cancelling", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push({ url, init });
      if (url === "/api/state") return jsonResponse({ revision: 3 });
      return jsonResponse({
        job_id: "job:2",
        profile: "validation:publication",
        state: "cancelling",
        progress: 0.5,
      });
    }) as unknown as typeof fetch;
    const controller = new JobPollingController(fetcher, () => undefined);

    const job = await controller.cancel("job:2", "nonce-123");

    expect(job.state).toBe("cancelling");
    expect(calls[0]).toEqual({
      url: "/api/jobs/job:2/cancel",
      init: expect.objectContaining({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-ArchCanvas-Nonce": "nonce-123",
        },
      }),
    });
  });
});

describe("isTerminalJobState", () => {
  it.each(["succeeded", "failed", "cancelled", "stale"])(
    "recognizes %s as terminal",
    (state) => expect(isTerminalJobState(state)).toBe(true),
  );

  it.each(["queued", "running", "cancelling"])(
    "keeps %s active",
    (state) => expect(isTerminalJobState(state)).toBe(false),
  );
});
