import type { ViewPreset, ViewPresetId } from "./source-backed-scene";

export const VIEW_PRESETS: Record<ViewPresetId, ViewPreset> = {
  "engineering-flow": {
    id: "engineering-flow",
    label: "标准流程图",
    projection: "architecture",
    orientation: "left-to-right",
    layout: "incremental-flow",
    hierarchyDepth: "expanded-frontier",
    templateProfile: "engineering",
    edgePolicy: "all",
  },
  "paper-publication": {
    id: "paper-publication",
    label: "论文级视图",
    projection: "architecture",
    orientation: "bottom-to-top",
    layout: "publication-structural",
    hierarchyDepth: 2,
    templateProfile: "paper",
    edgePolicy: "main-flow",
  },
  "paper-transformer": {
    id: "paper-transformer",
    label: "Transformer 论文兼容视图",
    projection: "architecture",
    orientation: "bottom-to-top",
    layout: "paper-dual-lane",
    hierarchyDepth: 2,
    templateProfile: "paper",
    edgePolicy: "main-flow",
  },
  "module-hierarchy": {
    id: "module-hierarchy",
    label: "模块层级",
    projection: "module",
    orientation: "top-to-bottom",
    layout: "hierarchical",
    hierarchyDepth: "expanded-frontier",
    templateProfile: "technical",
    edgePolicy: "semantic",
  },
  "source-call": {
    id: "source-call",
    label: "源码调用",
    projection: "source",
    orientation: "top-to-bottom",
    layout: "hierarchical",
    hierarchyDepth: "expanded-frontier",
    templateProfile: "technical",
    edgePolicy: "all",
  },
  "tensor-dataflow": {
    id: "tensor-dataflow",
    label: "Tensor 数据流",
    projection: "tensor",
    orientation: "left-to-right",
    layout: "incremental-flow",
    hierarchyDepth: "expanded-frontier",
    templateProfile: "technical",
    edgePolicy: "all",
  },
  "compact-overview": {
    id: "compact-overview",
    label: "紧凑总览",
    projection: "architecture",
    orientation: "left-to-right",
    layout: "compact",
    hierarchyDepth: 1,
    templateProfile: "engineering",
    edgePolicy: "main-flow",
  },
};

export const P0_VIEW_PRESETS: ViewPresetId[] = ["engineering-flow", "paper-publication"];
export const ALL_VIEW_PRESETS: ViewPresetId[] = [
  "engineering-flow",
  "paper-publication",
  "paper-transformer",
  "module-hierarchy",
  "source-call",
  "tensor-dataflow",
  "compact-overview",
];

export function resolveViewPreset(id: ViewPresetId): ViewPreset {
  return VIEW_PRESETS[id];
}
