import { postStudioJson } from "../api/studio-client";
import type { Projection, StudioState } from "./studio-types";

export interface NavigationExpansionPayload {
  projection: Projection;
  expansions: Record<Projection, string[]>;
}

export function persistNavigation(
  payload: NavigationExpansionPayload,
  nonce: string | null | undefined,
) {
  return postStudioJson<StudioState>("/api/navigation", payload, { nonce: nonce ?? undefined });
}

export function navigationExpansion(
  projection: Projection,
  expansions: Record<Projection, Set<string>>,
): NavigationExpansionPayload {
  return {
    projection,
    expansions: {
      module: [...expansions.module].sort(),
      source: [...expansions.source].sort(),
    },
  };
}
