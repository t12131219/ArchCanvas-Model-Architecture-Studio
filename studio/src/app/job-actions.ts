import type { Dispatch, SetStateAction } from "react";
import type { JobPollingController, StudioJob } from "../jobs";
import type { StudioState } from "./studio-types";

export function pollStudioJob(
  controller: JobPollingController<StudioState>,
  jobId: string,
  onSuccess?: () => void,
) {
  controller.start(jobId, (job: StudioJob) => {
    if (job.state === "succeeded") onSuccess?.();
  });
}

export async function cancelStudioJob(
  controller: JobPollingController<StudioState>,
  jobId: string,
  nonce: string | null | undefined,
  setActivity: Dispatch<SetStateAction<string[]>>,
  labels: { success: string; failure: string },
) {
  try {
    await controller.cancel(jobId, nonce ?? undefined);
    setActivity((items) => [`${labels.success} · ${jobId}`, ...items].slice(0, 20));
  } catch (error) {
    setActivity((items) => [`${labels.failure} · ${String(error)}`, ...items].slice(0, 20));
  }
}
