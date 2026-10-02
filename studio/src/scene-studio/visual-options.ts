import type {
  EdgeLabelStyle,
  NodeVisualStyle,
  RouteStyle,
  VisualOptions,
} from "./types";

export const ROUTE_STYLES: readonly RouteStyle[] = [
  "adaptive",
  "direct",
  "orthogonal",
  "channel",
  "curve",
];

export const NODE_STYLES: readonly NodeVisualStyle[] = [
  "semantic",
  "technical",
  "compact",
];

export const LABEL_STYLES: readonly EdgeLabelStyle[] = [
  "plain",
  "plate",
  "endpoint",
];

export const DEFAULT_OPTIONS: VisualOptions = {
  routeStyle: "adaptive",
  nodeStyle: "semantic",
  labelStyle: "plate",
};

export const ROUTE_NAMES: Record<RouteStyle, string> = {
  adaptive: "自适应端口",
  direct: "直连",
  orthogonal: "正交",
  channel: "分槽",
  curve: "曲线",
};

export const NODE_STYLE_NAMES: Record<NodeVisualStyle, string> = {
  semantic: "语义形状",
  technical: "技术铭牌",
  compact: "紧凑块",
};

export const LABEL_STYLE_NAMES: Record<EdgeLabelStyle, string> = {
  plain: "描边文字",
  plate: "标签底板",
  endpoint: "终点标注",
};
