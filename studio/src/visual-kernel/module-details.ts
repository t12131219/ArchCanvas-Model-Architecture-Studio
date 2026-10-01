import type { Bounds, NodeDetailKind, Point, PortSide } from "./types";
import {
  buildCatalogDetail,
  CATALOG_DETAIL_KIND_NAMES,
  CATALOG_EXPANDED_DETAIL_SIZES,
  isCatalogDetailKind,
} from "./catalog-details";

export type DetailTone = "neutral" | "blue" | "green" | "pink" | "orange" | "violet";
export type DetailFrameRole = "containment" | "semantic-group";

export type DetailPrimitive =
  | { kind: "rect"; x: number; y: number; width: number; height: number; rx: number; label?: string; note?: string; tone: DetailTone; variant?: "box" | "frame" | "capsule"; frameRole?: DetailFrameRole }
  | { kind: "circle"; cx: number; cy: number; radius: number; label: string; tone: DetailTone }
  | { kind: "matrix"; x: number; y: number; width: number; height: number; columns: number; rows: number; label?: string; tone: DetailTone; depth?: number }
  | { kind: "flow"; points: Point[]; marker?: boolean; tone?: DetailTone; channel?: string; targetPortRole?: string }
  | { kind: "text"; x: number; y: number; value: string; anchor?: "start" | "middle" | "end"; emphasis?: boolean; tone?: DetailTone };

export interface ModuleDetailDiagram {
  kind: NodeDetailKind;
  entryPoint: Point;
  exitPoint: Point;
  semanticInputPorts?: Record<string, { point: Point; side: PortSide }>;
  primitives: DetailPrimitive[];
}

export const DETAIL_KIND_NAMES: Record<NodeDetailKind, string> = {
  attention: "多头注意力内部数据流",
  feedforward: "前馈网络内部数据流",
  "add-norm": "残差相加与归一化",
  "sinusoidal-embedding": "词元缩放与正弦位置编码",
  "transformer-encoder": "经典 Transformer Encoder Layer × 6",
  "transformer-decoder": "经典 Transformer Decoder Layer × 6",
  "tensor2tensor-encoder": "Tensor2Tensor Encoder Layer × 6",
  "tensor2tensor-decoder": "Tensor2Tensor Decoder Layer × 6",
  "paper-transformer-encoder": "论文视图 · Encoder Layer × 6",
  "paper-transformer-decoder": "论文视图 · Decoder Layer × 6",
  "paper-tensor2tensor-encoder": "论文视图 · Tensor2Tensor Encoder × 6",
  "paper-tensor2tensor-decoder": "论文视图 · Tensor2Tensor Decoder × 6",
  "paper-sinusoidal-embedding": "论文视图 · 词元缩放与正弦位置编码",
  "paper-tensor-transform": "论文视图 · 张量变换数据流",
  "paper-attention": "论文视图 · Multi-Head Attention",
  "paper-feedforward": "论文视图 · Position-wise FFN",
  "paper-add-norm": "论文视图 · Residual + LayerNorm",
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
  "sinusoidal-embedding": { width: 720, height: 320 },
  "transformer-encoder": { width: 1060, height: 440 },
  "transformer-decoder": { width: 1420, height: 540 },
  "tensor2tensor-encoder": { width: 1060, height: 440 },
  "tensor2tensor-decoder": { width: 1420, height: 540 },
  "paper-transformer-encoder": { width: 560, height: 780 },
  "paper-transformer-decoder": { width: 620, height: 1040 },
  "paper-tensor2tensor-encoder": { width: 560, height: 780 },
  "paper-tensor2tensor-decoder": { width: 620, height: 1040 },
  "paper-sinusoidal-embedding": { width: 720, height: 320 },
  "paper-tensor-transform": { width: 540, height: 240 },
  "paper-attention": { width: 900, height: 420 },
  "paper-feedforward": { width: 600, height: 300 },
  "paper-add-norm": { width: 560, height: 300 },
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
  frameRole?: DetailFrameRole,
): DetailPrimitive {
  return { kind: "rect", x, y, width, height, rx: variant === "capsule" ? height / 2 : 4, label, note, tone, variant, frameRole };
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

function semanticInputFlow(
  tone: DetailTone,
  channel: string,
  targetPortRole: string,
  ...points: Point[]
): DetailPrimitive {
  return { kind: "flow", points, tone, channel, targetPortRole };
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
    rect(x + 250, y + 72, 330, 230, "", "orange", undefined, "frame", "semantic-group"),
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

function sinusoidalEmbeddingDiagram(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  const upper = y + 110;
  const lower = y + 228;
  return [
    wire({ x, y: cy }, { x: x + 28, y: cy }),
    semanticFlow("blue", "token-ids", { x: x + 28, y: cy }, { x: x + 42, y: upper }, { x: x + 58, y: upper }),
    matrix(x + 58, upper - 24, 62, 48, "token ids", "blue", 6, 2),
    semanticFlow("blue", "embedding", { x: x + 120, y: upper }, { x: x + 148, y: upper }),
    rect(x + 148, upper - 30, 126, 60, "TokenEmbedding", "blue", "lookup × √d_model"),
    semanticFlow("blue", "token-embedding", { x: x + 274, y: upper }, { x: x + 380, y: upper }, { x: x + 380, y: cy }, { x: x + 405, y: cy }),
    semanticFlow("orange", "position", { x: x + 28, y: cy }, { x: x + 42, y: lower }, { x: x + 58, y: lower }),
    matrix(x + 58, lower - 24, 62, 48, "position", "orange", 6, 2),
    semanticFlow("orange", "fixed-position", { x: x + 120, y: lower }, { x: x + 148, y: lower }),
    rect(x + 148, lower - 32, 180, 64, "Sinusoidal PE", "orange", "sin/cos · max_seq_len=5000"),
    semanticFlow("orange", "position-encoding", { x: x + 328, y: lower }, { x: x + 380, y: lower }, { x: x + 380, y: cy }, { x: x + 405, y: cy }),
    { kind: "circle", cx: x + 423, cy, radius: 18, label: "+", tone: "orange" },
    flow({ x: x + 441, y: cy }, { x: x + 474, y: cy }),
    rect(x + 474, cy - 29, 96, 58, "Dropout", "neutral", "p = 0.1"),
    flow({ x: x + 570, y: cy }, { x: x + 602, y: cy }),
    matrix(x + 602, cy - 29, 70, 58, "[B,L,D]", "violet", 5, 3, 6),
    flow({ x: x + 678, y: cy }, { x: x + width, y: cy }),
    text(x + width / 2, y + height - 25, "固定位置编码无可训练参数；源端与目标端使用相同公式", false),
  ];
}

function transformerEncoderDiagram(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  const inputX = x + 38;
  const attentionX = x + 150;
  const dropout1X = x + 318;
  const addNorm1X = x + 424;
  const ffnX = x + 570;
  const dropout2X = x + 720;
  const addNorm2X = x + 826;
  const p: DetailPrimitive[] = [
    {
      kind: "text",
      x: x + 18,
      y: y + 72,
      value: "EncoderLayer × 6 · d_model=512 · 8 heads · d_ff=2048",
      anchor: "start",
      emphasis: true,
      tone: "violet",
    },
    wire({ x, y: cy }, { x: inputX, y: cy }),
    matrix(inputX, cy - 27, 62, 54, "x", "blue", 5, 3, 6),
    flow({ x: inputX + 68, y: cy }, { x: attentionX, y: cy }),
    rect(attentionX, cy - 36, 138, 72, "Self-attention", "blue", "Q = K = V = x"),
    flow({ x: attentionX + 138, y: cy }, { x: dropout1X, y: cy }),
    rect(dropout1X, cy - 27, 78, 54, "Dropout", "neutral", "0.1"),
    flow({ x: dropout1X + 78, y: cy }, { x: addNorm1X, y: cy }),
    rect(addNorm1X, cy - 31, 112, 62, "Add & Norm", "green", "post-LN"),
    flow({ x: addNorm1X + 112, y: cy }, { x: ffnX, y: cy }),
    rect(ffnX, cy - 36, 122, 72, "Feed-forward", "violet", "Linear · ReLU · Linear"),
    flow({ x: ffnX + 122, y: cy }, { x: dropout2X, y: cy }),
    rect(dropout2X, cy - 27, 78, 54, "Dropout", "neutral", "0.1"),
    flow({ x: dropout2X + 78, y: cy }, { x: addNorm2X, y: cy }),
    rect(addNorm2X, cy - 31, 112, 62, "Add & Norm", "green", "post-LN"),
    flow({ x: addNorm2X + 112, y: cy }, { x: x + width - 74, y: cy }),
    matrix(x + width - 74, cy - 27, 52, 54, "memory", "orange", 3, 3),
    flow({ x: x + width - 22, y: cy }, { x: x + width, y: cy }),
    semanticInputFlow("orange", "src-padding-mask", "mask", { x: x + 101, y: y + 154 }, { x: attentionX + 69, y: y + 174 }, { x: attentionX + 69, y: cy - 36 }),
    rect(x + 40, y + 116, 122, 38, "Source padding mask", "orange", "[B,1,1,S]"),
    semanticFlow("blue", "residual-1", { x: inputX + 31, y: cy - 27 }, { x: inputX + 31, y: y + 184 }, { x: addNorm1X + 56, y: y + 184 }, { x: addNorm1X + 56, y: cy - 31 }),
    semanticFlow("green", "residual-2", { x: addNorm1X + 56, y: cy + 31 }, { x: addNorm1X + 56, y: cy + 75 }, { x: addNorm2X + 56, y: cy + 75 }, { x: addNorm2X + 56, y: cy + 31 }),
    text(x + width / 2, y + height - 26, "每层保持 [B,S,512]；同一 padding mask 广播到全部 attention heads", false),
  ];
  return p;
}

function transformerDecoderDiagram(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  const inputX = x + 34;
  const selfX = x + 128;
  const add1X = x + 390;
  const crossX = x + 535;
  const add2X = x + 805;
  const ffnX = x + 950;
  const add3X = x + 1190;
  return [
    {
      kind: "text",
      x: x + 18,
      y: y + 70,
      value: "DecoderLayer × 6 · masked self-attention + encoder-decoder attention",
      anchor: "start",
      emphasis: true,
      tone: "violet",
    },
    wire({ x, y: cy }, { x: inputX, y: cy }),
    matrix(inputX, cy - 26, 54, 52, "y", "blue", 5, 3, 5),
    flow({ x: inputX + 60, y: cy }, { x: selfX, y: cy }),
    rect(selfX, cy - 36, 146, 72, "Masked self-attn", "blue", "causal + target padding"),
    flow({ x: selfX + 146, y: cy }, { x: x + 300, y: cy }),
    rect(x + 300, cy - 25, 62, 50, "Drop", "neutral", "0.1"),
    flow({ x: x + 362, y: cy }, { x: add1X, y: cy }),
    rect(add1X, cy - 31, 108, 62, "Add & Norm", "green", "post-LN"),
    flow({ x: add1X + 108, y: cy }, { x: crossX, y: cy }),
    rect(crossX, cy - 38, 154, 76, "Cross-attention", "orange", "Q=decoder · K,V=memory"),
    flow({ x: crossX + 154, y: cy }, { x: x + 715, y: cy }),
    rect(x + 715, cy - 25, 62, 50, "Drop", "neutral", "0.1"),
    flow({ x: x + 777, y: cy }, { x: add2X, y: cy }),
    rect(add2X, cy - 31, 108, 62, "Add & Norm", "green", "post-LN"),
    flow({ x: add2X + 108, y: cy }, { x: ffnX, y: cy }),
    rect(ffnX, cy - 36, 124, 72, "Feed-forward", "violet", "Linear · ReLU · Linear"),
    flow({ x: ffnX + 124, y: cy }, { x: x + 1100, y: cy }),
    rect(x + 1100, cy - 25, 62, 50, "Drop", "neutral", "0.1"),
    flow({ x: x + 1162, y: cy }, { x: add3X, y: cy }),
    rect(add3X, cy - 31, 108, 62, "Add & Norm", "green", "post-LN"),
    flow({ x: add3X + 108, y: cy }, { x: x + width - 78, y: cy }),
    matrix(x + width - 78, cy - 26, 54, 52, "decoded", "pink", 3, 3),
    flow({ x: x + width - 24, y: cy }, { x: x + width, y: cy }),
    rect(x + 70, y + 130, 166, 44, "Target pad ∧ causal mask", "orange", "[B,1,T,T]"),
    semanticInputFlow("orange", "target-mask", "mask", { x: x + 153, y: y + 174 }, { x: selfX + 73, y: y + 196 }, { x: selfX + 73, y: cy - 36 }),
    matrix(x + 510, y + 126, 72, 54, "memory", "orange", 5, 3, 7),
    semanticFlow("orange", "encoder-memory", { x: x + 582, y: y + 153 }, { x: crossX + 77, y: y + 202 }, { x: crossX + 77, y: cy - 38 }),
    rect(x + 300, y + 126, 150, 54, "Source padding mask", "orange", "cross-attention keys"),
    semanticInputFlow("orange", "memory-mask", "mask", { x: x + 375, y: y + 180 }, { x: crossX + 108, y: y + 220 }, { x: crossX + 108, y: cy - 38 }),
    semanticFlow("blue", "residual-1", { x: inputX + 27, y: cy - 26 }, { x: inputX + 27, y: y + 246 }, { x: add1X + 54, y: y + 246 }, { x: add1X + 54, y: cy - 31 }),
    semanticFlow("green", "residual-2", { x: add1X + 54, y: cy + 31 }, { x: add1X + 54, y: cy + 70 }, { x: add2X + 54, y: cy + 70 }, { x: add2X + 54, y: cy + 31 }),
    semanticFlow("violet", "residual-3", { x: add2X + 54, y: cy + 31 }, { x: add2X + 54, y: cy + 102 }, { x: add3X + 54, y: cy + 102 }, { x: add3X + 54, y: cy + 31 }),
    text(x + width / 2, y + height - 25, "每个目标位置只能看见自身及更早位置；cross-attention 读取完整 Encoder memory", false),
  ];
}

function tensor2tensorEncoderDiagram(bounds: Bounds): DetailPrimitive[] {
  return transformerEncoderDiagram(bounds).map((primitive) => {
    if (primitive.kind === "text" && primitive.value.includes("EncoderLayer")) {
      return { ...primitive, value: "EncoderLayer × 6 · hidden=512 · heads=8 · filter=2048" };
    }
    if (primitive.kind === "rect" && primitive.label === "Feed-forward") {
      return { ...primitive, note: "conv_hidden_relu · filter=2048" };
    }
    if (primitive.kind === "rect" && primitive.label === "Source padding mask") {
      return { ...primitive, label: "Encoder attention bias", note: "ignore padding · [B,1,1,S]" };
    }
    if (primitive.kind === "text" && primitive.value.includes("每层保持")) {
      return { ...primitive, value: "每层使用 attention bias；conv_hidden_relu 保持 [B,S,H]" };
    }
    return primitive;
  });
}

function tensor2tensorDecoderDiagram(bounds: Bounds): DetailPrimitive[] {
  return transformerDecoderDiagram(bounds).map((primitive) => {
    if (primitive.kind === "text" && primitive.value.includes("DecoderLayer")) {
      return { ...primitive, value: "DecoderLayer × 6 · bias-masked attention + conv_hidden_relu" };
    }
    if (primitive.kind === "rect" && primitive.label === "Feed-forward") {
      return { ...primitive, note: "conv_hidden_relu · filter=2048" };
    }
    if (primitive.kind === "rect" && primitive.label === "Target pad ∧ causal mask") {
      return { ...primitive, label: "Decoder self-attention bias", note: "lower triangle · [B,T,T]" };
    }
    if (primitive.kind === "rect" && primitive.label === "Source padding mask") {
      return { ...primitive, label: "Encoder-decoder bias", note: "encoder padding" };
    }
    if (primitive.kind === "text" && primitive.value.includes("每个目标位置")) {
      return { ...primitive, value: "bias-masked self-attention；cross-attention 读取完整 Encoder output" };
    }
    return primitive;
  });
}

function sameDiagramPoint(first: Point, second: Point): boolean {
  return Math.abs(first.x - second.x) < 0.01 && Math.abs(first.y - second.y) < 0.01;
}

function paperVerticalBoundary(
  primitives: DetailPrimitive[],
  bounds: Bounds,
): DetailPrimitive[] {
  const horizontalEntry = { x: bounds.x, y: bounds.y + bounds.height / 2 };
  const horizontalExit = { x: bounds.x + bounds.width, y: bounds.y + bounds.height / 2 };
  const verticalEntry = { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height };
  const verticalExit = { x: bounds.x + bounds.width / 2, y: bounds.y };
  return primitives.map((primitive) => {
    if (primitive.kind !== "flow") return primitive;
    if (sameDiagramPoint(primitive.points[0], horizontalEntry)) {
      const target = primitive.points.at(-1)!;
      return {
        ...primitive,
        points: [
          verticalEntry,
          { x: verticalEntry.x, y: verticalEntry.y - 18 },
          { x: target.x, y: verticalEntry.y - 18 },
          target,
        ],
      };
    }
    if (sameDiagramPoint(primitive.points.at(-1)!, horizontalExit)) {
      const source = primitive.points[0];
      const outerX = bounds.x + bounds.width - 12;
      return {
        ...primitive,
        points: [
          source,
          { x: outerX, y: source.y },
          { x: outerX, y: bounds.y + 18 },
          { x: verticalExit.x, y: bounds.y + 18 },
          verticalExit,
        ],
      };
    }
    return primitive;
  });
}

function paperTransformerEncoderDiagram(bounds: Bounds, tensor2tensor = false): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cx = x + width / 2;
  const attention = { x: x + 70, y: y + 540, width: width - 140, height: 130 };
  const addNorm1 = { x: x + 94, y: y + 440, width: width - 188, height: 72 };
  const feedforward = { x: x + 70, y: y + 250, width: width - 140, height: 140 };
  const addNorm2 = { x: x + 94, y: y + 150, width: width - 188, height: 72 };
  const input = { x: cx - 42, y: y + 714, width: 84, height: 38 };
  const output = { x: cx - 42, y: y + 82, width: 84, height: 40 };
  const maskLabel = tensor2tensor ? "Encoder attention bias" : "Source padding mask";
  const ffnNote = tensor2tensor ? "conv_hidden_relu · filter=2048" : "Linear · ReLU/GELU · Linear";
  return [
    {
      kind: "text",
      x: x + 42,
      y: y + 80,
      value: tensor2tensor
        ? "Encoder Layer × 6 · hidden=512 · heads=8 · filter=2048"
        : "Encoder Layer × 6 · d_model=512 · heads=8 · d_ff=2048",
      anchor: "start",
      emphasis: true,
      tone: "blue",
    },
    flow({ x: cx, y: y + height }, { x: cx, y: input.y + input.height }),
    matrix(input.x, input.y, input.width, input.height, "x", "blue", 6, 3, 5),
    flow({ x: cx, y: input.y }, { x: cx, y: attention.y + attention.height }),
    rect(attention.x, attention.y, attention.width, attention.height, "Self-attention", "orange", "Q = K = V · split heads"),
    flow({ x: cx, y: attention.y }, { x: cx, y: addNorm1.y + addNorm1.height }),
    rect(addNorm1.x, addNorm1.y, addNorm1.width, addNorm1.height, "Add & Norm", "green", "residual + LayerNorm"),
    flow({ x: cx, y: addNorm1.y }, { x: cx, y: feedforward.y + feedforward.height }),
    rect(feedforward.x, feedforward.y, feedforward.width, feedforward.height, "Feed-forward", "blue", ffnNote),
    flow({ x: cx, y: feedforward.y }, { x: cx, y: addNorm2.y + addNorm2.height }),
    rect(addNorm2.x, addNorm2.y, addNorm2.width, addNorm2.height, "Add & Norm", "green", "residual + LayerNorm"),
    flow({ x: cx, y: addNorm2.y }, { x: cx, y: output.y + output.height }),
    matrix(output.x, output.y, output.width, output.height, "memory", "blue", 6, 3, 5),
    flow({ x: cx, y: output.y }, { x: cx, y }),
    {
      kind: "text",
      x: x + 42,
      y: y + 708,
      value: `${maskLabel} · ${tensor2tensor ? "negative bias" : "[B,1,1,S]"}`,
      anchor: "start",
      emphasis: true,
      tone: "orange",
    },
    semanticInputFlow("orange", "encoder-mask", "mask",
      { x, y: attention.y + attention.height / 2 },
      { x: attention.x, y: attention.y + attention.height / 2 },
    ),
    semanticFlow("blue", "residual-1",
      { x: cx, y: input.y },
      { x: x + 48, y: input.y },
      { x: x + 48, y: addNorm1.y + addNorm1.height / 2 },
      { x: addNorm1.x, y: addNorm1.y + addNorm1.height / 2 },
    ),
    semanticFlow("green", "residual-2",
      { x: cx, y: addNorm1.y },
      { x: x + width - 48, y: addNorm1.y },
      { x: x + width - 48, y: addNorm2.y + addNorm2.height / 2 },
      { x: addNorm2.x + addNorm2.width, y: addNorm2.y + addNorm2.height / 2 },
    ),
  ];
}

function paperTransformerDecoderDiagram(bounds: Bounds, tensor2tensor = false): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cx = x + width / 2;
  const selfAttention = { x: x + 70, y: y + 800, width: width - 140, height: 150 };
  const addNorm1 = { x: x + 106, y: y + 700, width: width - 212, height: 66 };
  const crossAttention = { x: x + 70, y: y + 500, width: width - 140, height: 150 };
  const addNorm2 = { x: x + 106, y: y + 400, width: width - 212, height: 66 };
  const feedforward = { x: x + 70, y: y + 220, width: width - 140, height: 130 };
  const addNorm3 = { x: x + 106, y: y + 128, width: width - 212, height: 66 };
  const input = { x: cx - 42, y: y + 976, width: 84, height: 38 };
  const output = { x: cx - 42, y: y + 66, width: 84, height: 38 };
  const causalLabel = tensor2tensor ? "Decoder self-attention bias" : "Target pad + causal mask";
  const memoryLabel = tensor2tensor ? "Encoder output + bias" : "Encoder memory + source mask";
  const ffnNote = tensor2tensor ? "conv_hidden_relu · filter=2048" : "Linear · ReLU/GELU · Linear";
  return [
    {
      kind: "text",
      x: x + 42,
      y: y + 80,
      value: tensor2tensor
        ? "Decoder Layer × 6 · bias-masked attention + conv_hidden_relu"
        : "Decoder Layer × 6 · masked self-attention + cross-attention",
      anchor: "start",
      emphasis: true,
      tone: "pink",
    },
    flow({ x: cx, y: y + height }, { x: cx, y: input.y + input.height }),
    matrix(input.x, input.y, input.width, input.height, "y", "pink", 6, 3, 5),
    flow({ x: cx, y: input.y }, { x: cx, y: selfAttention.y + selfAttention.height }),
    rect(selfAttention.x, selfAttention.y, selfAttention.width, selfAttention.height, "Masked self-attn", "orange", "Q = K = V · causal"),
    flow({ x: cx, y: selfAttention.y }, { x: cx, y: addNorm1.y + addNorm1.height }),
    rect(addNorm1.x, addNorm1.y, addNorm1.width, addNorm1.height, "Add & Norm", "green", "residual + LayerNorm"),
    flow({ x: cx, y: addNorm1.y }, { x: cx, y: crossAttention.y + crossAttention.height }),
    rect(crossAttention.x, crossAttention.y, crossAttention.width, crossAttention.height, "Cross-attention", "orange", "Q=decoder · K,V=memory"),
    flow({ x: cx, y: crossAttention.y }, { x: cx, y: addNorm2.y + addNorm2.height }),
    rect(addNorm2.x, addNorm2.y, addNorm2.width, addNorm2.height, "Add & Norm", "green", "residual + LayerNorm"),
    flow({ x: cx, y: addNorm2.y }, { x: cx, y: feedforward.y + feedforward.height }),
    rect(feedforward.x, feedforward.y, feedforward.width, feedforward.height, "Feed-forward", "blue", ffnNote),
    flow({ x: cx, y: feedforward.y }, { x: cx, y: addNorm3.y + addNorm3.height }),
    rect(addNorm3.x, addNorm3.y, addNorm3.width, addNorm3.height, "Add & Norm", "green", "residual + LayerNorm"),
    flow({ x: cx, y: addNorm3.y }, { x: cx, y: output.y + output.height }),
    matrix(output.x, output.y, output.width, output.height, "decoded", "pink", 6, 3, 5),
    flow({ x: cx, y: output.y }, { x: cx, y }),
    {
      kind: "text",
      x: x + 578,
      y: y + 980,
      value: `${causalLabel} · ${tensor2tensor ? "lower triangle" : "[B,1,T,T]"}`,
      anchor: "end",
      emphasis: true,
      tone: "orange",
    },
    semanticInputFlow("orange", "decoder-mask", "mask",
      { x: x + width, y: selfAttention.y + selfAttention.height / 2 },
      { x: selfAttention.x + selfAttention.width, y: selfAttention.y + selfAttention.height / 2 },
    ),
    {
      kind: "text",
      x: x + 42,
      y: y + 544,
      value: `${memoryLabel} · K,V`,
      anchor: "start",
      emphasis: true,
      tone: "blue",
    },
    semanticInputFlow("blue", "encoder-memory", "memory",
      { x, y: y + 575 },
      { x: crossAttention.x, y: crossAttention.y + crossAttention.height / 2 },
    ),
    semanticFlow("pink", "residual-1",
      { x: cx, y: input.y },
      { x: x + 46, y: input.y },
      { x: x + 46, y: addNorm1.y + addNorm1.height / 2 },
      { x: addNorm1.x, y: addNorm1.y + addNorm1.height / 2 },
    ),
    semanticFlow("green", "residual-2",
      { x: cx, y: addNorm1.y },
      { x: x + width - 46, y: addNorm1.y },
      { x: x + width - 46, y: addNorm2.y + addNorm2.height / 2 },
      { x: addNorm2.x + addNorm2.width, y: addNorm2.y + addNorm2.height / 2 },
    ),
    semanticFlow("violet", "residual-3",
      { x: cx, y: addNorm2.y },
      { x: x + 46, y: addNorm2.y },
      { x: x + 46, y: addNorm3.y + addNorm3.height / 2 },
      { x: addNorm3.x, y: addNorm3.y + addNorm3.height / 2 },
    ),
  ];
}

function paperAttentionDiagram(bounds: Bounds): DetailPrimitive[] {
  return paperVerticalBoundary(attentionDiagram(bounds), bounds);
}

function paperFeedforwardDiagram(bounds: Bounds): DetailPrimitive[] {
  return paperVerticalBoundary(feedforwardDiagram(bounds), bounds);
}

function paperAddNormDiagram(bounds: Bounds): DetailPrimitive[] {
  return paperVerticalBoundary(addNormDiagram(bounds), bounds);
}

function paperSinusoidalEmbeddingDiagram(bounds: Bounds): DetailPrimitive[] {
  return paperVerticalBoundary(sinusoidalEmbeddingDiagram(bounds), bounds);
}

function paperTensorTransformDiagram(bounds: Bounds): DetailPrimitive[] {
  return paperVerticalBoundary(tensorTransformDiagram(bounds), bounds);
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
    rect(x + 224, y + 66, 102, 232, "", "violet", undefined, "frame", "semantic-group"),
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
    "sinusoidal-embedding": sinusoidalEmbeddingDiagram,
    "transformer-encoder": transformerEncoderDiagram,
    "transformer-decoder": transformerDecoderDiagram,
    "tensor2tensor-encoder": tensor2tensorEncoderDiagram,
    "tensor2tensor-decoder": tensor2tensorDecoderDiagram,
    "paper-transformer-encoder": (value) => paperTransformerEncoderDiagram(value),
    "paper-transformer-decoder": (value) => paperTransformerDecoderDiagram(value),
    "paper-tensor2tensor-encoder": (value) => paperTransformerEncoderDiagram(value, true),
    "paper-tensor2tensor-decoder": (value) => paperTransformerDecoderDiagram(value, true),
    "paper-sinusoidal-embedding": paperSinusoidalEmbeddingDiagram,
    "paper-tensor-transform": paperTensorTransformDiagram,
    "paper-attention": paperAttentionDiagram,
    "paper-feedforward": paperFeedforwardDiagram,
    "paper-add-norm": paperAddNormDiagram,
    convolution: convolutionDiagram,
    "tensor-transform": tensorTransformDiagram,
    embedding: embeddingDiagram,
    recurrent: recurrentDiagram,
    "mixture-of-experts": mixtureOfExpertsDiagram,
    pooling: poolingDiagram,
  } as Record<NodeDetailKind, (value: Bounds) => DetailPrimitive[]>;
  let semanticInputPorts: ModuleDetailDiagram["semanticInputPorts"];
  if (kind === "attention" || kind === "paper-attention") {
    semanticInputPorts = {
      mask: {
        point: { x: bounds.x + 432, y: bounds.y + 120 },
        side: "top",
      },
    };
  } else if (kind === "paper-transformer-encoder" || kind === "paper-tensor2tensor-encoder") {
    semanticInputPorts = {
      mask: {
        point: { x: bounds.x + 70, y: bounds.y + 595 },
        side: "left",
      },
    };
  } else if (kind === "paper-transformer-decoder" || kind === "paper-tensor2tensor-decoder") {
    semanticInputPorts = {
      mask: {
        point: { x: bounds.x + bounds.width - 70, y: bounds.y + 885 },
        side: "right",
      },
      memory: {
        point: { x: bounds.x + 70, y: bounds.y + 575 },
        side: "left",
      },
    };
  }
  const vertical = kind.startsWith("paper-");
  const boundaries = vertical ? {
    entryPoint: { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height },
    exitPoint: { x: bounds.x + bounds.width / 2, y: bounds.y },
  } : boundaryPoints(bounds);
  return { kind, ...boundaries, semanticInputPorts, primitives: builders[kind](bounds) };
}
