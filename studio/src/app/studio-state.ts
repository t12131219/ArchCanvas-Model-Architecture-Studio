import { studioModelIdentity } from "../tree";
import type { Projection, StudioState } from "./studio-types";

export function embeddedStudioState(documentRoot: Document = document): StudioState | null {
  const element = documentRoot.getElementById("archcanvas-studio-data");
  if (!element?.textContent) return null;
  return JSON.parse(element.textContent) as StudioState;
}

export function initialExpansionState(state: StudioState | null): Record<Projection, Set<string>> {
  const defaults = (kind: Projection) => new Set(
    state?.navigation?.projections[kind].nodes
      .filter((item) => item.depth === 0 && item.child_count > 0)
      .map((item) => item.id) ?? [],
  );
  return {
    module: state?.view_state.module_expansion
      ? new Set(state.view_state.module_expansion)
      : defaults("module"),
    source: state?.view_state.source_expansion
      ? new Set(state.view_state.source_expansion)
      : defaults("source"),
  };
}

export class StudioStateAcceptance {
  private identity: string;

  constructor(initial: StudioState | null) {
    this.identity = studioModelIdentity(initial);
  }

  accept(next: StudioState): { state: StudioState; modelChanged: boolean } {
    const identity = studioModelIdentity(next);
    const modelChanged = identity !== this.identity;
    this.identity = identity;
    return { state: next, modelChanged };
  }
}
