import { createContext, useContext, useMemo, useReducer } from "react";
import type { Dispatch, PropsWithChildren } from "react";

import type { StudioJob } from "../../jobs";
import type { SourceBackedScene, StudioStatePayload, ViewPresetId } from "../domain/source-backed-scene";
import type { LabPatch, Selection } from "../types";

export type StudioMode = "explore" | "layout" | "model";

export interface SceneStudioState {
  projectSlice: {
    status: "booting" | "idle" | "ready" | "opening" | "analyzing" | "error";
    error: string | null;
    source: StudioStatePayload | null;
  };
  semanticSlice: {
    exactIrDigest: string | null;
    evidenceCount: number;
    diagnosticCount: number;
  };
  viewSlice: {
    presetId: ViewPresetId;
    scenes: SourceBackedScene[];
    selection: Selection;
    visualRevision: number;
  };
  interactionSlice: {
    mode: StudioMode;
  };
  jobSlice: {
    active: StudioJob | null;
  };
  transactionSlice: {
    status: "idle" | "preparing" | "review" | "committing" | "failed";
  };
  sourceSlice: {
    activePath: string | null;
    dirtyPaths: string[];
  };
}

export type SceneStudioAction =
  | { type: "source-loaded"; source: StudioStatePayload; scenes: SourceBackedScene[] }
  | { type: "status"; status: SceneStudioState["projectSlice"]["status"]; error?: string | null }
  | { type: "preset"; presetId: ViewPresetId }
  | { type: "selection"; selection: Selection }
  | { type: "mode"; mode: StudioMode }
  | { type: "job"; job: StudioJob | null }
  | { type: "visual-patch"; patch: LabPatch };

export const initialSceneStudioState: SceneStudioState = {
  projectSlice: { status: "booting", error: null, source: null },
  semanticSlice: { exactIrDigest: null, evidenceCount: 0, diagnosticCount: 0 },
  viewSlice: { presetId: "engineering-flow", scenes: [], selection: null, visualRevision: 0 },
  interactionSlice: { mode: "explore" },
  jobSlice: { active: null },
  transactionSlice: { status: "idle" },
  sourceSlice: { activePath: null, dirtyPaths: [] },
};

export function sceneStudioReducer(state: SceneStudioState, action: SceneStudioAction): SceneStudioState {
  if (action.type === "source-loaded") {
    const currentSelection = state.viewSlice.selection;
    const sameProject = state.projectSlice.source?.project.project_id === action.source.project.project_id;
    const selectionStillExists = Boolean(currentSelection && action.scenes.some((scene) => (
      currentSelection.kind === "node"
        ? scene.nodes.some((node) => node.scene_node_id === currentSelection.id)
        : scene.edges.some((edge) => edge.scene_edge_id === currentSelection.id)
    )));
    return {
      ...state,
      projectSlice: { status: "ready", error: null, source: action.source },
      semanticSlice: {
        exactIrDigest: action.source.integrity?.exact_ir_digest ?? action.source.semantic_overlay?.exact_ir_digest ?? null,
        evidenceCount: action.source.evidence.length,
        diagnosticCount: 0,
      },
      viewSlice: {
        ...state.viewSlice,
        scenes: action.scenes,
        selection: sameProject && selectionStillExists ? currentSelection : null,
      },
    };
  }
  if (action.type === "status") {
    return { ...state, projectSlice: { ...state.projectSlice, status: action.status, error: action.error ?? null } };
  }
  if (action.type === "preset") return { ...state, viewSlice: { ...state.viewSlice, presetId: action.presetId, selection: null } };
  if (action.type === "selection") {
    const current = state.viewSlice.selection;
    if (current === action.selection || (
      current?.kind === action.selection?.kind
      && current?.id === action.selection?.id
    )) return state;
    return { ...state, viewSlice: { ...state.viewSlice, selection: action.selection } };
  }
  if (action.type === "mode") return { ...state, interactionSlice: { mode: action.mode } };
  if (action.type === "job") return { ...state, jobSlice: { active: action.job } };
  return { ...state, viewSlice: { ...state.viewSlice, visualRevision: state.viewSlice.visualRevision + 1 } };
}

const StateContext = createContext<SceneStudioState | null>(null);
const DispatchContext = createContext<Dispatch<SceneStudioAction> | null>(null);

export function SceneStudioProvider({ children }: PropsWithChildren) {
  const [state, dispatch] = useReducer(sceneStudioReducer, initialSceneStudioState);
  const value = useMemo(() => state, [state]);
  return <StateContext.Provider value={value}><DispatchContext.Provider value={dispatch}>{children}</DispatchContext.Provider></StateContext.Provider>;
}

export function useSceneStudioState(): SceneStudioState {
  const state = useContext(StateContext);
  if (!state) throw new Error("useSceneStudioState must be used inside SceneStudioProvider");
  return state;
}

export function useSceneStudioDispatch(): Dispatch<SceneStudioAction> {
  const dispatch = useContext(DispatchContext);
  if (!dispatch) throw new Error("useSceneStudioDispatch must be used inside SceneStudioProvider");
  return dispatch;
}
