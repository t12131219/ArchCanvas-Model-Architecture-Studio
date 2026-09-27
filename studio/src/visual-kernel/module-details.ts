import type { Bounds, NodeDetailKind, Point } from "./types";
import {
  buildCatalogDetail,
  CATALOG_DETAIL_KIND_NAMES,
  CATALOG_EXPANDED_DETAIL_SIZES,
  isCatalogDetailKind,
} from "./catalog-details";

export type DetailTone = "neutral" | "blue" | "green" | "pink" | "orange" | "violet";

export type DetailPrimitive =
  | { kind: "rect"; x: number; y: number; width: number; height: number; rx: number; label?: string; note?: string; tone: DetailTone; variant?: "box" | "frame" | "capsule" }
  | { kind: "circle"; cx: number; cy: number; radius: number; label: string; tone: DetailTone }
  | { kind: "matrix"; x: number; y: number; width: number; height: number; columns: number; rows: number; label?: string; tone: DetailTone; depth?: number }
  | { kind: "flow"; points: Point[]; marker?: boolean; tone?: DetailTone; channel?: string }
  | { kind: "text"; x: number; y: number; value: string; anchor?: "start" | "middle" | "end"; emphasis?: boolean; tone?: DetailTone };

export interface ModuleDetailDiagram {
  kind: NodeDetailKind;
  entryPoint: Point;
  exitPoint: Point;
  primitives: DetailPrimitive[];
}

export const DETAIL_KIND_NAMES: Record<NodeDetailKind, string> = {
  attention: "多头注意力内部数据流",
  feedforward: "前馈网络内部数据流",
  "add-norm": "残差相加与归一化",
  convolution: "卷积特征提取数据流",
  "tensor-transform": "张量变换数据流",
  embedding: "词元与位置嵌入数据流",
  recurrent: "LSTM 循环状态数据流",
  "mixture-of-experts": "稀疏专家路由数据流",
  pooling: "池化降采样数据流",
  ...CATALOG_DETAIL_KIND_NAMES,
};

export const EXPANDED_DETAIL_SIZES: Record<NodeDetailKind, Pick<Bounds, "width" | "height">> = {
  attention: { width: 900, height: 380 },
  feedforward: { width: 600, height: 260 },
  "add-norm": { width: 560, height: 260 },
  convolution: { width: 620, height: 280 },
  "tensor-transform": { width: 540, height: 240 },
  embedding: { width: 680, height: 300 },
  recurrent: { width: 900, height: 380 },
  "mixture-of-experts": { width: 820, height: 360 },
  pooling: { width: 560, height: 260 },
  ...CATALOG_EXPANDED_DETAIL_SIZES,
};

function rect(
  x: number,
  y: number,
  width: number,
  height: number,
  label: string,
  tone: DetailTone = "neutral",
  note?: string,
  variant: "box" | "frame" | "capsule" = "box",
): DetailPrimitive {
  return { kind: "rect", x, y, width, height, rx: variant === "capsule" ? height / 2 : 4, label, note, tone, variant };
}

function matrix(
  x: number,
  y: number,
  width: number,
  height: number,
  label: string,
  tone: DetailTone,
  columns = 4,
  rows = 3,
  depth = 0,
): DetailPrimitive {
  return { kind: "matrix", x, y, width, height, columns, rows, label, tone, depth };
}

function flow(...points: Point[]): DetailPrimitive {
  return { kind: "flow", points };
}

function semanticFlow(tone: DetailTone, channel: string, ...points: Point[]): DetailPrimitive {
  return { kind: "flow", points, tone, channel };
}

function wire(...points: Point[]): DetailPrimitive {
  return { kind: "flow", points, marker: false };
}

function text(x: number, y: number, value: string, emphasis = false, tone?: DetailTone): DetailPrimitive {
  return { kind: "text", x, y, value, anchor: "middle", emphasis, tone };
}

function boundaryPoints(bounds: Bounds): { entryPoint: Point; exitPoint: Point } {
  return {
    entryPoint: { x: bounds.x, y: bounds.y + bounds.height / 2 },
    exitPoint: { x: bounds.x + bounds.width, y: bounds.y + bounds.height / 2 },
  };
}

function attentionDiagram(bounds: Bounds): DetailPrimitive[] {
  const { x, y } = bounds;
  const cy = y + bounds.height / 2;
  const branchX = x + 28;
  const rows = [y + 105, y + 170, y + 255];
  const labels = ["Q", "K", "V"];
  const tones: DetailTone[] = ["blue", "green", "pink"];
  const p: DetailPrimitive[] = [
    rect(x + 250, y + 72, 330, 230, "", "orange", undefined, "frame"),
    text(x + 415, y + 91, "Scaled dot-product attention / head", true, "orange"),
    wire({ x, y: cy }, { x: branchX, y: cy }),
  ];

  rows.forEach((row, index) => {
    p.push(semanticFlow(tones[index], labels[index],
      { x: branchX, y: cy },
      { x: branchX + 8, y: row },
      { x: x + 46, y: row },
    ));
    p.push(matrix(x + 46, row - 20, 46, 40, labels[index], tones[index], 4, 3));
    p.push(semanticFlow(tones[index], labels[index], { x: x + 92, y: row }, { x: x + 110, y: row }));
    p.push(rect(x + 110, row - 20, 54, 40, "Linear", tones[index]));
    p.push(semanticFlow(tones[index], labels[index], { x: x + 164, y: row }, { x: x + 180, y: row }));
    p.push(matrix(x + 180, row - 20, 52, 40, `h × ${labels[index]}`, tones[index], 4, 3, 5));
  });

  p.push(semanticFlow("blue", "Q", { x: x + 232, y: rows[0] }, { x: x + 260, y: rows[0] }, { x: x + 260, y: y + 129 }, { x: x + 286, y: y + 129 }));
  p.push(semanticFlow("green", "K", { x: x + 232, y: rows[1] }, { x: x + 252, y: rows[1] }, { x: x + 252, y: y + 142 }, { x: x + 273, y: y + 142 }));
  p.push({ kind: "circle", cx: x + 286, cy: y + 142, radius: 13, label: "×", tone: "orange" });
  p.push(flow({ x: x + 299, y: y + 142 }, { x: x + 312, y: y + 142 }));
  p.push(rect(x + 312, y + 120, 65, 44, "Scale", "neutral", "1 / √d_k"));
  p.push(flow({ x: x + 377, y: y + 142 }, { x: x + 397, y: y + 142 }));
  p.push(rect(x + 397, y + 120, 70, 44, "Softmax", "green"));
  p.push(semanticFlow("green", "attention-weights", { x: x + 467, y: y + 142 }, { x: x + 487, y: y + 142 }));
  p.push(matrix(x + 487, y + 122, 48, 40, "weights", "green", 4, 4));
  p.push(semanticFlow("green", "attention-weights", { x: x + 535, y: y + 142 }, { x: x + 560, y: y + 142 }, { x: x + 560, y: cy - 13 }));
  p.push(semanticFlow("pink", "V", { x: x + 232, y: rows[2] }, { x: x + 500, y: rows[2] }, { x: x + 500, y: cy }, { x: x + 547, y: cy }));
  p.push({ kind: "circle", cx: x + 560, cy, radius: 13, label: "×", tone: "orange" });
  p.push(flow({ x: x + 573, y: cy }, { x: x + 592, y: cy }));
  p.push(matrix(x + 592, cy - 24, 56, 48, "context", "orange", 4, 4));
  p.push(flow({ x: x + 648, y: cy }, { x: x + 666, y: cy }));
  p.push(matrix(x + 666, cy - 22, 62, 44, "Concat h", "violet", 6, 3));
  p.push(flow({ x: x + 728, y: cy }, { x: x + 744, y: cy }));
  p.push(rect(x + 744, cy - 24, 76, 48, "Output Wᴼ", "violet", "h·d_k → d_model"));
  p.push(flow({ x: x + 820, y: cy }, { x: x + 838, y: cy }));
  p.push(matrix(x + 838, cy - 22, 42, 44, "Output", "blue", 4, 3));
  p.push(flow({ x: x + 880, y: cy }, { x: x + bounds.width, y: cy }));
  p.push(text(x + 126, y + 329, "Q / K / V projections", false));
  p.push(text(x + 729, y + 329, "merge heads → project → next module", false));
  return p;
}

function feedforwardDiagram(bounds: Bounds): DetailPrimitive[] {
  const { x, y } = bounds;
  const cy = y + bounds.height / 2;
  return [
    flow({ x, y: cy }, { x: x + 24, y: cy }),
    matrix(x + 24, cy - 25, 48, 50, "x", "blue", 4, 4),
    flow({ x: x + 72, y: cy }, { x: x + 96, y: cy }),
    rect(x + 96, cy - 28, 90, 56, "Linear", "violet", "d_model → d_ff"),
    flow({ x: x + 186, y: cy }, { x: x + 210, y: cy }),
    rect(x + 210, cy - 24, 62, 48, "GELU", "green"),
    flow({ x: x + 272, y: cy }, { x: x + 296, y: cy }),
    rect(x + 296, cy - 24, 74, 48, "Dropout", "neutral"),
    flow({ x: x + 370, y: cy }, { x: x + 394, y: cy }),
    rect(x + 394, cy - 28, 94, 56, "Linear", "violet", "d_ff → d_model"),
    flow({ x: x + 488, y: cy }, { x: x + 516, y: cy }),
    matrix(x + 516, cy - 25, 56, 50, "FFN(x)", "blue", 4, 3),
    flow({ x: x + 572, y: cy }, { x: x + bounds.width, y: cy }),
    text(x + 300, y + 211, "position-wise channel expansion and contraction", false),
  ];
}

function addNormDiagram(bounds: Bounds): DetailPrimitive[] {
  const { x, y } = bounds;
  const cy = y + bounds.height / 2;
  const branchX = x + 28;
  return [
    wire({ x, y: cy }, { x: branchX, y: cy }),
    flow({ x: branchX, y: cy }, { x: x + 36, y: y + 99 }, { x: x + 48, y: y + 99 }),
    flow({ x: branchX, y: cy }, { x: x + 36, y: y + 181 }, { x: x + 48, y: y + 181 }),
    matrix(x + 48, y + 78, 58, 42, "F(x)", "violet", 4, 3),
    matrix(x + 48, y + 160, 58, 42, "x", "blue", 4, 3),
    text(x + 77, y + 220, "residual branch", false),
    flow({ x: x + 106, y: y + 99 }, { x: x + 136, y: y + 99 }, { x: x + 136, y: cy }, { x: x + 154, y: cy }),
    flow({ x: x + 106, y: y + 181 }, { x: x + 136, y: y + 181 }, { x: x + 136, y: cy }, { x: x + 154, y: cy }),
    { kind: "circle", cx: x + 170, cy, radius: 16, label: "+", tone: "orange" },
    flow({ x: x + 186, y: cy }, { x: x + 208, y: cy }),
    rect(x + 208, cy - 28, 120, 56, "LayerNorm", "green", "μ, σ, γ, β", "capsule"),
    flow({ x: x + 328, y: cy }, { x: x + 360, y: cy }),
    matrix(x + 360, cy - 27, 62, 54, "y", "green", 4, 4),
    flow({ x: x + 422, y: cy }, { x: x + bounds.width, y: cy }),
    text(x + 480, y + 165, "normalized output", false),
  ];
}

function convolutionDiagram(bounds: Bounds): DetailPrimitive[] {
  const { x, y } = bounds;
  const cy = y + bounds.height / 2;
  return [
    flow({ x, y: cy }, { x: x + 24, y: cy }),
    matrix(x + 24, cy - 37, 64, 74, "Input", "blue", 6, 6, 10),
    flow({ x: x + 98, y: cy }, { x: x + 118, y: cy }),
    matrix(x + 118, cy - 27, 54, 54, "k × k", "orange", 3, 3),
    flow({ x: x + 172, y: cy }, { x: x + 200, y: cy }),
    matrix(x + 200, cy - 40, 74, 80, "Conv maps", "green", 6, 6, 12),
    flow({ x: x + 286, y: cy }, { x: x + 310, y: cy }),
    rect(x + 310, cy - 23, 58, 46, "ReLU", "green"),
    flow({ x: x + 368, y: cy }, { x: x + 392, y: cy }),
    matrix(x + 392, cy - 31, 54, 62, "Pool", "violet", 3, 4, 6),
    flow({ x: x + 452, y: cy }, { x: x + 474, y: cy }),
    matrix(x + 474, cy - 34, 66, 68, "Output", "blue", 5, 5, 8),
    flow({ x: x + 548, y: cy }, { x: x + bounds.width, y: cy }),
    text(x + 310, y + 229, "local receptive field → channel stack → downsample", false),
  ];
}

function tensorTransformDiagram(bounds: Bounds): DetailPrimitive[] {
  const { x, y } = bounds;
  const cy = y + bounds.height / 2;
  return [
    flow({ x, y: cy }, { x: x + 24, y: cy }),
    matrix(x + 24, cy - 32, 58, 64, "B×T×C", "blue", 4, 4, 8),
    flow({ x: x + 90, y: cy }, { x: x + 108, y: cy }),
    rect(x + 108, cy - 27, 88, 54, "Permute", "neutral", "B×C×T"),
    flow({ x: x + 196, y: cy }, { x: x + 220, y: cy }),
    rect(x + 220, cy - 27, 78, 54, "Reshape", "violet", "BT×C"),
    flow({ x: x + 298, y: cy }, { x: x + 322, y: cy }),
    rect(x + 322, cy - 27, 82, 54, "Project", "green", "C → D"),
    flow({ x: x + 404, y: cy }, { x: x + 430, y: cy }),
    matrix(x + 430, cy - 32, 58, 64, "BT×D", "green", 4, 4, 8),
    flow({ x: x + 496, y: cy }, { x: x + bounds.width, y: cy }),
    text(x + 270, y + 199, "axis order, reshape and feature projection stay explicit", false),
  ];
}

function embeddingDiagram(bounds: Bounds): DetailPrimitive[] {
  const { x, y } = bounds;
  const cy = y + bounds.height / 2;
  const branchX = x + 28;
  return [
    wire({ x, y: cy }, { x: branchX, y: cy }),
    flow({ x: branchX, y: cy }, { x: x + 36, y: y + 106 }, { x: x + 48, y: y + 106 }),
    flow({ x: branchX, y: cy }, { x: x + 36, y: y + 208 }, { x: x + 48, y: y + 208 }),
    matrix(x + 48, y + 84, 54, 44, "token ids", "blue", 5, 2),
    matrix(x + 48, y + 186, 54, 44, "position", "orange", 5, 2),
    flow({ x: x + 102, y: y + 106 }, { x: x + 126, y: y + 106 }),
    flow({ x: x + 102, y: y + 208 }, { x: x + 126, y: y + 208 }),
    rect(x + 126, y + 80, 84, 52, "Token lookup", "blue", "vocab × d_model"),
    rect(x + 126, y + 182, 84, 52, "Position", "orange", "max_len × d_model"),
    flow({ x: x + 210, y: y + 106 }, { x: x + 234, y: y + 106 }),
    flow({ x: x + 210, y: y + 208 }, { x: x + 234, y: y + 208 }),
    matrix(x + 234, y + 82, 62, 48, "token E", "blue", 5, 3),
    matrix(x + 234, y + 184, 62, 48, "position E", "orange", 5, 3),
    flow({ x: x + 296, y: y + 106 }, { x: x + 324, y: y + 106 }, { x: x + 324, y: cy }, { x: x + 340, y: cy }),
    flow({ x: x + 296, y: y + 208 }, { x: x + 324, y: y + 208 }, { x: x + 324, y: cy }, { x: x + 340, y: cy }),
    { kind: "circle", cx: x + 356, cy, radius: 16, label: "+", tone: "orange" },
    flow({ x: x + 372, y: cy }, { x: x + 398, y: cy }),
    rect(x + 398, cy - 27, 106, 54, "LayerNorm", "green", "optional"),
    flow({ x: x + 504, y: cy }, { x: x + 526, y: cy }),
    rect(x + 526, cy - 24, 72, 48, "Dropout", "neutral"),
    flow({ x: x + 598, y: cy }, { x: x + 620, y: cy }),
    matrix(x + 620, cy - 25, 40, 50, "E", "violet", 4, 3),
    flow({ x: x + 660, y: cy }, { x: x + bounds.width, y: cy }),
  ];
}

function recurrentDiagram(bounds: Bounds): DetailPrimitive[] {
  const { x, y } = bounds;
  const cy = y + bounds.height / 2;
  const gateX = x + 242;
  return [
    rect(x + 224, y + 66, 102, 232, "", "violet", undefined, "frame"),
    text(x + 275, y + 84, "LSTM gates", true, "violet"),
    wire({ x, y: cy }, { x: x + 26, y: cy }),
    flow({ x: x + 26, y: cy }, { x: x + 34, y: y + 110 }, { x: x + 46, y: y + 110 }),
    flow({ x: x + 26, y: cy }, { x: x + 34, y: y + 176 }, { x: x + 46, y: y + 176 }),
    flow({ x: x + 26, y: cy }, { x: x + 34, y: y + 270 }, { x: x + 46, y: y + 270 }),
    matrix(x + 46, y + 90, 56, 40, "x_t", "blue", 4, 3),
    matrix(x + 46, y + 156, 56, 40, "h_{t-1}", "violet", 4, 3),
    matrix(x + 46, y + 250, 56, 40, "c_{t-1}", "orange", 4, 3),
    flow({ x: x + 102, y: y + 110 }, { x: x + 126, y: y + 110 }, { x: x + 126, y: y + 151 }),
    flow({ x: x + 102, y: y + 176 }, { x: x + 126, y: y + 176 }, { x: x + 126, y: y + 151 }),
    rect(x + 126, y + 121, 78, 60, "Concat", "neutral", "[x_t, h_{t-1}]"),
    wire({ x: x + 204, y: y + 151 }, { x: x + 218, y: y + 151 }),
    ...[
      ["i_t", "σ", y + 104, "green"],
      ["g_t", "tanh", y + 150, "blue"],
      ["f_t", "σ", y + 204, "orange"],
      ["o_t", "σ", y + 254, "pink"],
    ].flatMap(([label, activation, row, tone]) => [
      flow({ x: x + 218, y: y + 151 }, { x: x + 230, y: row as number }, { x: gateX, y: row as number }),
      rect(gateX, (row as number) - 18, 62, 36, label as string, tone as DetailTone, activation as string),
    ]),
    flow({ x: gateX + 62, y: y + 104 }, { x: x + 350, y: y + 104 }, { x: x + 350, y: y + 127 }, { x: x + 367, y: y + 127 }),
    flow({ x: gateX + 62, y: y + 150 }, { x: x + 344, y: y + 150 }, { x: x + 344, y: y + 127 }, { x: x + 367, y: y + 127 }),
    { kind: "circle", cx: x + 380, cy: y + 127, radius: 13, label: "×", tone: "green" },
    flow({ x: gateX + 62, y: y + 204 }, { x: x + 346, y: y + 204 }, { x: x + 346, y: y + 227 }, { x: x + 367, y: y + 227 }),
    flow({ x: x + 102, y: y + 270 }, { x: x + 330, y: y + 270 }, { x: x + 330, y: y + 227 }, { x: x + 367, y: y + 227 }),
    { kind: "circle", cx: x + 380, cy: y + 227, radius: 13, label: "×", tone: "orange" },
    flow({ x: x + 393, y: y + 127 }, { x: x + 426, y: y + 127 }, { x: x + 426, y: y + 177 }, { x: x + 442, y: y + 177 }),
    flow({ x: x + 393, y: y + 227 }, { x: x + 426, y: y + 227 }, { x: x + 426, y: y + 177 }, { x: x + 442, y: y + 177 }),
    { kind: "circle", cx: x + 458, cy: y + 177, radius: 16, label: "+", tone: "orange" },
    flow({ x: x + 474, y: y + 177 }, { x: x + 494, y: y + 177 }),
    matrix(x + 494, y + 153, 56, 48, "c_t", "orange", 4, 3),
    flow({ x: x + 550, y: y + 177 }, { x: x + 574, y: y + 177 }),
    rect(x + 574, y + 153, 62, 48, "tanh", "green"),
    flow({ x: x + 636, y: y + 177 }, { x: x + 660, y: y + 177 }),
    flow({ x: gateX + 62, y: y + 254 }, { x: x + 647, y: y + 254 }, { x: x + 647, y: y + 177 }, { x: x + 660, y: y + 177 }),
    { kind: "circle", cx: x + 676, cy: y + 177, radius: 16, label: "×", tone: "pink" },
    flow({ x: x + 692, y: y + 177 }, { x: x + 716, y: y + 177 }),
    matrix(x + 716, y + 153, 58, 48, "h_t", "blue", 4, 3),
    flow({ x: x + 774, y: y + 177 }, { x: x + 800, y: y + 177 }, { x: x + 800, y: cy }, { x: x + 820, y: cy }),
    matrix(x + 820, cy - 24, 56, 48, "h_t,c_t", "violet", 4, 3),
    flow({ x: x + 876, y: cy }, { x: x + bounds.width, y: cy }),
  ];
}

function mixtureOfExpertsDiagram(bounds: Bounds): DetailPrimitive[] {
  const { x, y } = bounds;
  const cy = y + bounds.height / 2;
  const branchX = x + 300;
  const expertRows = [y + 112, y + 180, y + 248];
  return [
    flow({ x, y: cy }, { x: x + 24, y: cy }),
    matrix(x + 24, cy - 26, 54, 52, "tokens", "blue", 5, 3),
    flow({ x: x + 78, y: cy }, { x: x + 102, y: cy }),
    rect(x + 102, cy - 34, 88, 68, "Router", "orange", "softmax scores"),
    flow({ x: x + 190, y: cy }, { x: x + 214, y: cy }),
    rect(x + 214, cy - 25, 64, 50, "Top-k", "violet", "k = 1 or 2"),
    wire({ x: x + 278, y: cy }, { x: branchX, y: cy }),
    ...expertRows.flatMap((row, index) => [
      flow({ x: branchX, y: cy }, { x: x + 312, y: row }, { x: x + 334, y: row }),
      rect(x + 334, row - 24, 98, 48, `Expert ${index + 1}`, index === 1 ? "green" : "blue", "FFN"),
      flow({ x: x + 432, y: row }, { x: x + 510, y: row }, { x: x + 510, y: cy }, { x: x + 540, y: cy }),
    ]),
    { kind: "circle", cx: x + 556, cy, radius: 16, label: "Σ", tone: "orange" },
    text(x + 556, y + 91, "router-weighted merge", false),
    flow({ x: x + 572, y: cy }, { x: x + 600, y: cy }),
    matrix(x + 600, cy - 28, 66, 56, "mixed", "green", 4, 4),
    flow({ x: x + 666, y: cy }, { x: x + 692, y: cy }),
    rect(x + 692, cy - 25, 70, 50, "Output", "violet"),
    flow({ x: x + 762, y: cy }, { x: x + bounds.width, y: cy }),
  ];
}

function poolingDiagram(bounds: Bounds): DetailPrimitive[] {
  const { x, y } = bounds;
  const cy = y + bounds.height / 2;
  return [
    flow({ x, y: cy }, { x: x + 24, y: cy }),
    matrix(x + 24, cy - 38, 70, 76, "feature map", "blue", 7, 7, 10),
    flow({ x: x + 104, y: cy }, { x: x + 130, y: cy }),
    matrix(x + 130, cy - 28, 56, 56, "window", "orange", 2, 2),
    flow({ x: x + 186, y: cy }, { x: x + 214, y: cy }),
    rect(x + 214, cy - 31, 112, 62, "Max / Average", "green", "reduce k × k"),
    flow({ x: x + 326, y: cy }, { x: x + 354, y: cy }),
    matrix(x + 354, cy - 32, 64, 64, "pooled", "violet", 4, 4, 7),
    flow({ x: x + 426, y: cy }, { x: x + 456, y: cy }),
    rect(x + 456, cy - 23, 62, 46, "Output", "blue"),
    flow({ x: x + 518, y: cy }, { x: x + bounds.width, y: cy }),
    text(x + 280, y + 211, "spatial reduction preserves channel identity", false),
  ];
}

export function buildModuleDetail(kind: NodeDetailKind, bounds: Bounds): ModuleDetailDiagram {
  if (isCatalogDetailKind(kind)) {
    return { kind, ...boundaryPoints(bounds), primitives: buildCatalogDetail(kind, bounds) };
  }
  const builders: Record<NodeDetailKind, (value: Bounds) => DetailPrimitive[]> = {
    attention: attentionDiagram,
    feedforward: feedforwardDiagram,
    "add-norm": addNormDiagram,
    convolution: convolutionDiagram,
    "tensor-transform": tensorTransformDiagram,
    embedding: embeddingDiagram,
    recurrent: recurrentDiagram,
    "mixture-of-experts": mixtureOfExpertsDiagram,
    pooling: poolingDiagram,
  } as Record<NodeDetailKind, (value: Bounds) => DetailPrimitive[]>;
  return { kind, ...boundaryPoints(bounds), primitives: builders[kind](bounds) };
}
