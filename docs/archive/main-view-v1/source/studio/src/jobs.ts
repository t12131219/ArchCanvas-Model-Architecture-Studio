export type StudioJobState =
  | "queued"
  | "running"
  | "cancelling"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "stale";

export interface StudioJob<TDiagnostic = unknown> {
  job_id: string;
  state: StudioJobState;
  progress: number;
  profile: string;
  diagnostics?: TDiagnostic[];
}

interface TimerScheduler {
  setInterval(callback: () => void, delay: number): ReturnType<typeof setInterval>;
  clearInterval(handle: ReturnType<typeof setInterval>): void;
}

const DEFAULT_SCHEDULER: TimerScheduler = {
  setInterval: (callback, delay) => globalThis.setInterval(callback, delay),
  clearInterval: (handle) => globalThis.clearInterval(handle),
};

const TERMINAL_STATES = new Set<StudioJobState>([
  "succeeded",
  "failed",
  "cancelled",
  "stale",
]);

export function isTerminalJobState(state: string): state is StudioJobState {
  return TERMINAL_STATES.has(state as StudioJobState);
}

export class JobPollingController<TState> {
  private readonly pollers = new Map<
    string,
    ReturnType<typeof setInterval>
  >();

  private readonly inFlight = new Set<string>();

  constructor(
    private readonly fetcher: typeof fetch,
    private readonly onState: (state: TState) => void,
    private readonly interval = 300,
    private readonly scheduler: TimerScheduler = DEFAULT_SCHEDULER,
  ) {}

  get activeCount(): number {
    return this.pollers.size;
  }

  async refreshState(): Promise<TState | null> {
    const response = await this.fetcher("/api/state", { cache: "no-store" });
    if (!response.ok) return null;
    const state = await response.json() as TState;
    this.onState(state);
    return state;
  }

  start(jobId: string, onTerminal?: (job: StudioJob) => void): void {
    this.stop(jobId);
    const poller = this.scheduler.setInterval(() => {
      void this.check(jobId, onTerminal);
    }, this.interval);
    this.pollers.set(jobId, poller);
  }

  async check(
    jobId: string,
    onTerminal?: (job: StudioJob) => void,
  ): Promise<StudioJob | null> {
    if (this.inFlight.has(jobId)) return null;
    this.inFlight.add(jobId);
    try {
      const response = await this.fetcher(`/api/jobs/${jobId}`, {
        cache: "no-store",
      });
      if (!response.ok) return null;
      const job = await response.json() as StudioJob;
      await this.refreshState();
      if (isTerminalJobState(job.state)) {
        this.stop(jobId);
        onTerminal?.(job);
      }
      return job;
    } catch {
      return null;
    } finally {
      this.inFlight.delete(jobId);
    }
  }

  async cancel(jobId: string, sessionNonce?: string): Promise<StudioJob> {
    const response = await this.fetcher(`/api/jobs/${jobId}/cancel`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(sessionNonce ? { "X-ArchCanvas-Nonce": sessionNonce } : {}),
      },
      body: "{}",
    });
    if (!response.ok) throw new Error(await response.text());
    const job = await response.json() as StudioJob;
    await this.refreshState();
    return job;
  }

  stop(jobId: string): void {
    const poller = this.pollers.get(jobId);
    if (poller === undefined) return;
    this.scheduler.clearInterval(poller);
    this.pollers.delete(jobId);
  }

  dispose(): void {
    for (const jobId of this.pollers.keys()) this.stop(jobId);
    this.inFlight.clear();
  }
}
