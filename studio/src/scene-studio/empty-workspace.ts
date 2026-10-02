import type { LabScene } from "./types";

export const EMPTY_WORKSPACE_SCENE: LabScene = {
  scene_id: "workspace:empty",
  title: "空工作区",
  description: "尚未加载源码项目",
  paper_width: 1120,
  paper_height: 680,
  nodes: [],
  edges: [],
};

export const EMPTY_WORKSPACE_SCENES: readonly LabScene[] = [EMPTY_WORKSPACE_SCENE];
