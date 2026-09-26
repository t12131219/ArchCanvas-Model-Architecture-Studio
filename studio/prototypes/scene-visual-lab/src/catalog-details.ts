import type { Bounds, NodeDetailKind, Point } from "./types";
import type { DetailPrimitive, DetailTone } from "./module-details";

type CatalogKind = Exclude<NodeDetailKind,
  | "attention"
  | "feedforward"
  | "add-norm"
  | "convolution"
  | "tensor-transform"
  | "embedding"
  | "recurrent"
  | "mixture-of-experts"
  | "pooling"
>;

type Step = {
  label: string;
  note?: string;
  tone?: DetailTone;
  visual?: "box" | "matrix" | "circle";
};

const CATALOG_KINDS: readonly CatalogKind[] = [
  "linear-model", "kernel-machine", "decision-tree", "ensemble", "clustering", "decomposition",
  "mlp", "normalization", "residual-block", "dense-connection", "inception", "depthwise-convolution",
  "unet", "vision-transformer", "gru", "bidirectional-recurrent", "seq2seq", "state-space",
  "autoencoder", "variational-autoencoder", "gan", "diffusion", "normalizing-flow",
  "graph-message-passing", "time-series-forecast", "dual-encoder", "dqn", "actor-critic",
  "distillation", "adapter-lora",
];

export const CATALOG_DETAIL_KIND_NAMES: Record<CatalogKind, string> = {
  "linear-model": "线性与广义线性预测链",
  "kernel-machine": "核映射、间隔与支持向量",
  "decision-tree": "特征阈值与二叉决策路径",
  ensemble: "并行基学习器与集成汇聚",
  clustering: "分配、质心更新与迭代收敛",
  decomposition: "矩阵分解与低维表示",
  mlp: "多层感知机与门控前馈",
  normalization: "统计量、标准化与仿射恢复",
  "residual-block": "残差变换与恒等捷径",
  "dense-connection": "逐层特征复用与拼接",
  inception: "多尺度卷积分支与拼接",
  "depthwise-convolution": "逐通道卷积与逐点混合",
  unet: "编码器、跨层跳连与解码器",
  "vision-transformer": "图像分块、词元化与 Transformer",
  gru: "GRU 重置门、更新门与隐状态",
  "bidirectional-recurrent": "正反向状态编码与合并",
  seq2seq: "编码器上下文、注意力与解码器",
  "state-space": "选择性状态扫描与门控输出",
  autoencoder: "编码、潜变量与重建",
  "variational-autoencoder": "分布参数、重参数采样与生成",
  gan: "生成器与判别器的对抗数据流",
  diffusion: "加噪、噪声预测与逐步去噪",
  "normalizing-flow": "可逆变换与对数雅可比",
  "graph-message-passing": "邻居消息、聚合与节点更新",
  "time-series-forecast": "趋势季节分解与预测汇合",
  "dual-encoder": "图文双编码与对比相似度",
  dqn: "Q 网络、环境与经验回放闭环",
  "actor-critic": "策略、价值与优势更新闭环",
  distillation: "教师软目标与学生联合损失",
  "adapter-lora": "冻结主干与低秩增量支路",
};

export const CATALOG_EXPANDED_DETAIL_SIZES: Record<CatalogKind, Pick<Bounds, "width" | "height">> =
  Object.fromEntries(CATALOG_KINDS.map((kind) => [kind, { width: 760, height: 300 }])) as Record<CatalogKind, Pick<Bounds, "width" | "height">>;

Object.assign(CATALOG_EXPANDED_DETAIL_SIZES, {
  "decision-tree": { width: 760, height: 340 },
  ensemble: { width: 780, height: 340 },
  normalization: { width: 780, height: 330 },
  "residual-block": { width: 780, height: 330 },
  "dense-connection": { width: 820, height: 340 },
  inception: { width: 820, height: 380 },
  unet: { width: 900, height: 380 },
  "vision-transformer": { width: 860, height: 320 },
  gru: { width: 900, height: 380 },
  "bidirectional-recurrent": { width: 800, height: 340 },
  seq2seq: { width: 860, height: 350 },
  "state-space": { width: 860, height: 350 },
  "variational-autoencoder": { width: 860, height: 350 },
  gan: { width: 820, height: 350 },
  diffusion: { width: 860, height: 340 },
  "graph-message-passing": { width: 840, height: 360 },
  "dual-encoder": { width: 840, height: 360 },
  dqn: { width: 900, height: 340 },
  "actor-critic": { width: 900, height: 370 },
  distillation: { width: 860, height: 360 },
  "adapter-lora": { width: 820, height: 340 },
});

function rect(x: number, y: number, width: number, height: number, label: string, tone: DetailTone = "neutral", note?: string, variant: "box" | "frame" | "capsule" = "box"): DetailPrimitive {
  return { kind: "rect", x, y, width, height, rx: variant === "capsule" ? height / 2 : 4, label, note, tone, variant };
}

function matrix(x: number, y: number, width: number, height: number, label: string, tone: DetailTone, columns = 4, rows = 3, depth = 0): DetailPrimitive {
  return { kind: "matrix", x, y, width, height, columns, rows, label, tone, depth };
}

function circle(cx: number, cy: number, label: string, tone: DetailTone, radius = 15): DetailPrimitive {
  return { kind: "circle", cx, cy, radius, label, tone };
}

function flow(...points: Point[]): DetailPrimitive {
  return { kind: "flow", points };
}

function wire(...points: Point[]): DetailPrimitive {
  return { kind: "flow", points, marker: false };
}

function text(x: number, y: number, value: string, emphasis = false, tone?: DetailTone): DetailPrimitive {
  return { kind: "text", x, y, value, anchor: "middle", emphasis, tone };
}

function pipeline(bounds: Bounds, steps: Step[], note: string): DetailPrimitive[] {
  const cy = bounds.y + bounds.height / 2;
  const left = bounds.x + 30;
  const right = bounds.x + bounds.width - 30;
  const gap = (right - left) / steps.length;
  const primitives: DetailPrimitive[] = [flow({ x: bounds.x, y: cy }, { x: left, y: cy })];
  steps.forEach((step, index) => {
    const cx = left + gap * (index + 0.5);
    const width = Math.min(104, gap - 20);
    const tone = step.tone ?? (["blue", "violet", "green", "orange"] as DetailTone[])[index % 4];
    if (step.visual === "matrix") primitives.push(matrix(cx - width / 2, cy - 31, width, 62, step.label, tone, 5, 4, 7));
    else if (step.visual === "circle") primitives.push(circle(cx, cy, step.label, tone, Math.min(22, width / 2)));
    else primitives.push(rect(cx - width / 2, cy - 27, width, 54, step.label, tone, step.note));
    const endX = index === steps.length - 1 ? bounds.x + bounds.width : left + gap * (index + 1);
    primitives.push(flow({ x: cx + (step.visual === "circle" ? Math.min(22, width / 2) : width / 2), y: cy }, { x: endX, y: cy }));
  });
  primitives.push(text(bounds.x + bounds.width / 2, bounds.y + bounds.height - 35, note));
  return primitives;
}

function splitMerge(bounds: Bounds, branches: Array<{ label: string; note?: string; tone: DetailTone }>, mergeLabel: string, note: string): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  const branchX = x + 42;
  const rows = branches.map((_, index) => y + 92 + index * ((height - 164) / Math.max(1, branches.length - 1)));
  const mergeX = x + width - 290;
  const p: DetailPrimitive[] = [wire({ x, y: cy }, { x: branchX, y: cy })];
  branches.forEach((branch, index) => {
    const row = rows[index];
    p.push(flow({ x: branchX, y: cy }, { x: branchX + 12, y: row }, { x: x + 78, y: row }));
    p.push(rect(x + 78, row - 23, 170, 46, branch.label, branch.tone, branch.note));
    p.push(flow({ x: x + 248, y: row }, { x: mergeX - 24, y: row }, { x: mergeX - 24, y: cy }, { x: mergeX, y: cy }));
  });
  p.push(rect(mergeX, cy - 28, 108, 56, mergeLabel, "orange"));
  p.push(flow({ x: mergeX + 108, y: cy }, { x: x + width, y: cy }));
  p.push(text(x + width / 2, y + height - 28, note));
  return p;
}

function linearModel(bounds: Bounds): DetailPrimitive[] {
  return pipeline(bounds, [
    { label: "X", visual: "matrix", tone: "blue" },
    { label: "Xw + b", note: "linear score", tone: "violet" },
    { label: "link", note: "identity / sigmoid / softmax", tone: "green" },
    { label: "ŷ", visual: "matrix", tone: "orange" },
  ], "回归、Logistic、Softmax 与 GLM 共享线性预测器；link 与损失由模型证据决定");
}

function kernelMachine(bounds: Bounds): DetailPrimitive[] {
  return pipeline(bounds, [
    { label: "x", visual: "matrix", tone: "blue" },
    { label: "φ(x)", note: "kernel feature", tone: "violet" },
    { label: "Σ αᵢK(xᵢ,x)", note: "support vectors", tone: "orange" },
    { label: "margin", note: "sign / regression", tone: "green" },
  ], "核函数隐式映射特征；只有支持向量的系数参与最终决策");
}

function decisionTree(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  const rootX = x + 142;
  const leafX = x + 456;
  const rows = [y + 116, y + 246];
  return [
    flow({ x, y: cy }, { x: x + 40, y: cy }), matrix(x + 40, cy - 29, 58, 58, "x", "blue", 4, 4),
    flow({ x: x + 98, y: cy }, { x: rootX, y: cy }), rect(rootX, cy - 29, 122, 58, "feature j ≤ t?", "orange", "split node"),
    flow({ x: rootX + 122, y: cy }, { x: x + 308, y: cy }, { x: x + 308, y: rows[0] }, { x: x + 344, y: rows[0] }),
    flow({ x: rootX + 122, y: cy }, { x: x + 308, y: cy }, { x: x + 308, y: rows[1] }, { x: x + 344, y: rows[1] }),
    rect(x + 344, rows[0] - 24, 112, 48, "left child", "green", "true"), rect(x + 344, rows[1] - 24, 112, 48, "right child", "pink", "false"),
    flow({ x: leafX, y: rows[0] }, { x: x + 532, y: rows[0] }, { x: x + 532, y: cy }, { x: x + 564, y: cy }),
    flow({ x: leafX, y: rows[1] }, { x: x + 532, y: rows[1] }, { x: x + 532, y: cy }, { x: x + 564, y: cy }),
    rect(x + 564, cy - 30, 112, 60, "leaf value", "violet", "class / response"),
    flow({ x: x + 676, y: cy }, { x: x + width, y: cy }), text(x + width / 2, y + height - 30, "每个样本只沿一条阈值路径到达叶节点；图中汇合表示统一预测出口"),
  ];
}

function ensemble(bounds: Bounds): DetailPrimitive[] {
  return splitMerge(bounds, [
    { label: "Tree / learner 1", note: "sample / stage 1", tone: "blue" },
    { label: "Tree / learner 2", note: "sample / residual", tone: "green" },
    { label: "Tree / learner 3", note: "sample / residual", tone: "violet" },
  ], "Vote / Σ", "Bagging 并行投票；Boosting 按残差串行拟合。模板以汇聚结构表达共同输出");
}

function clustering(bounds: Bounds): DetailPrimitive[] {
  const p = pipeline(bounds, [
    { label: "samples", visual: "matrix", tone: "blue" },
    { label: "assign", note: "nearest center", tone: "violet" },
    { label: "centroids", visual: "circle", tone: "orange" },
    { label: "update", note: "cluster mean", tone: "green" },
    { label: "clusters", visual: "matrix", tone: "pink" },
  ], "K-Means 在分配与质心更新间迭代；密度和层次方法使用不同的邻接/合并规则");
  const { x, y, width, height } = bounds;
  p.push(wire({ x: x + width * 0.47, y: y + 118 }, { x: x + width * 0.47, y: y + 84 }, { x: x + width * 0.79, y: y + 84 }, { x: x + width * 0.79, y: y + 118 }));
  p.push(text(x + width * 0.63, y + 77, "iterate", true, "orange"));
  return p;
}

function decomposition(bounds: Bounds): DetailPrimitive[] {
  return pipeline(bounds, [
    { label: "X", visual: "matrix", tone: "blue" },
    { label: "center / scale", tone: "neutral" },
    { label: "basis", note: "V / W", visual: "matrix", tone: "violet" },
    { label: "project", note: "XV or WH", tone: "green" },
    { label: "Z", visual: "matrix", tone: "orange" },
  ], "PCA/SVD 投影到正交基；NMF、ICA、字典学习替换基与约束但保留分解语义");
}

function mlp(bounds: Bounds): DetailPrimitive[] {
  return pipeline(bounds, [
    { label: "x", visual: "matrix", tone: "blue" },
    { label: "Linear ↑", note: "d → d_hidden", tone: "violet" },
    { label: "φ / gate", note: "GELU · GLU", visual: "circle", tone: "green" },
    { label: "Linear ↓", note: "d_hidden → d", tone: "violet" },
    { label: "y", visual: "matrix", tone: "orange" },
  ], "普通 MLP 是单支路；GLU/GEGLU/SwiGLU 在激活处增加并行门控乘法");
}

function normalization(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  return [
    wire({ x, y: cy }, { x: x + 44, y: cy }), matrix(x + 44, cy - 31, 62, 62, "x", "blue", 5, 4),
    flow({ x: x + 106, y: cy }, { x: x + 154, y: cy }, { x: x + 154, y: y + 116 }, { x: x + 186, y: y + 116 }),
    flow({ x: x + 106, y: cy }, { x: x + 154, y: cy }, { x: x + 154, y: y + 238 }, { x: x + 186, y: y + 238 }),
    rect(x + 186, y + 91, 120, 50, "statistics", "orange", "μ, σ² or RMS"),
    rect(x + 186, y + 213, 120, 50, "identity x", "blue", "unscaled stream"),
    flow({ x: x + 306, y: y + 116 }, { x: x + 354, y: y + 116 }, { x: x + 354, y: cy }, { x: x + 390, y: cy }),
    flow({ x: x + 306, y: y + 238 }, { x: x + 354, y: y + 238 }, { x: x + 354, y: cy }, { x: x + 390, y: cy }),
    circle(x + 410, cy, "−/÷", "green", 20), flow({ x: x + 430, y: cy }, { x: x + 466, y: cy }),
    rect(x + 466, cy - 29, 126, 58, "γ · x̂ + β", "violet", "affine optional"),
    flow({ x: x + 592, y: cy }, { x: x + width, y: cy }),
    text(x + width / 2, y + height - 27, "Batch/Layer/Group/Instance/RMSNorm 的核心差异是统计维度与是否减均值"),
  ];
}

function residualBlock(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  return [
    wire({ x, y: cy }, { x: x + 46, y: cy }), matrix(x + 46, cy - 29, 58, 58, "x", "blue", 4, 4),
    flow({ x: x + 104, y: cy }, { x: x + 142, y: cy }, { x: x + 142, y: y + 112 }, { x: x + 188, y: y + 112 }),
    flow({ x: x + 104, y: cy }, { x: x + 142, y: cy }, { x: x + 142, y: y + 244 }, { x: x + 522, y: y + 244 }, { x: x + 522, y: cy }, { x: x + 548, y: cy }),
    rect(x + 188, y + 86, 112, 52, "Conv / Linear", "violet", "F₁"), flow({ x: x + 300, y: y + 112 }, { x: x + 334, y: y + 112 }),
    rect(x + 334, y + 86, 112, 52, "Norm + φ", "green", "F₂"), flow({ x: x + 446, y: y + 112 }, { x: x + 522, y: y + 112 }, { x: x + 522, y: cy }, { x: x + 548, y: cy }),
    circle(x + 566, cy, "+", "orange", 18), flow({ x: x + 584, y: cy }, { x: x + 628, y: cy }),
    rect(x + 628, cy - 27, 84, 54, "φ", "green", "optional"), flow({ x: x + 712, y: cy }, { x: x + width, y: cy }),
    text(x + width / 2, y + height - 25, "恒等/投影捷径与变换支路在逐元素加法处汇合"),
  ];
}

function denseConnection(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  const xs = [x + 70, x + 245, x + 420, x + 595];
  const p: DetailPrimitive[] = [flow({ x, y: cy }, { x: xs[0], y: cy })];
  xs.forEach((cx, index) => {
    p.push(rect(cx, cy - 25, 92, 50, index ? `H${index}` : "x₀", index ? "green" : "blue", index ? "BN·φ·Conv" : "features"));
    if (index < xs.length - 1) p.push(flow({ x: cx + 92, y: cy }, { x: xs[index + 1], y: cy }));
  });
  [0, 1].forEach((from, index) => p.push(wire(
    { x: xs[from] + 92, y: cy }, { x: xs[from] + 112, y: y + 94 - index * 22 },
    { x: xs[3] - 22, y: y + 94 - index * 22 }, { x: xs[3] - 22, y: cy }, { x: xs[3], y: cy },
  )));
  p.push(flow({ x: xs[3] + 92, y: cy }, { x: x + width, y: cy }));
  p.push(text(x + width / 2, y + 78, "[x₀, x₁, …] channel concat", true, "violet"));
  p.push(text(x + width / 2, y + height - 28, "DenseNet 把所有先前特征拼接给后续层；CSP 只让部分通道穿越密集块"));
  return p;
}

function inception(bounds: Bounds): DetailPrimitive[] {
  return splitMerge(bounds, [
    { label: "1×1 Conv", tone: "blue" },
    { label: "1×1 → 3×3 Conv", tone: "green" },
    { label: "1×1 → 5×5 Conv", tone: "violet" },
    { label: "3×3 Pool → 1×1", tone: "pink" },
  ], "Concat", "与 D2L/GoogLeNet 图一致：四条多尺度支路在通道轴拼接");
}

function depthwiseConvolution(bounds: Bounds): DetailPrimitive[] {
  return pipeline(bounds, [
    { label: "feature maps", visual: "matrix", tone: "blue" },
    { label: "DW k×k", note: "one filter / channel", visual: "matrix", tone: "orange" },
    { label: "BN + φ", tone: "green" },
    { label: "PW 1×1", note: "mix channels", visual: "matrix", tone: "violet" },
    { label: "output", visual: "matrix", tone: "pink" },
  ], "MobileNet/Xception 的关键是把空间滤波与通道混合拆开");
}

function unet(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  const enc = [x + 50, x + 184, x + 318];
  const dec = [x + 536, x + 670, x + 804];
  const p: DetailPrimitive[] = [flow({ x, y: cy }, { x: enc[0], y: cy })];
  enc.forEach((cx, index) => {
    p.push(matrix(cx, cy - 34 + index * 10, 72, 68 - index * 12, `Enc ${index + 1}`, "blue", 4, 4, 7));
    if (index < 2) p.push(flow({ x: cx + 79, y: cy }, { x: enc[index + 1], y: cy }));
  });
  p.push(flow({ x: enc[2] + 79, y: cy }, { x: x + 428, y: cy }));
  p.push(rect(x + 428, cy - 27, 82, 54, "bottleneck", "violet"));
  p.push(flow({ x: x + 510, y: cy }, { x: dec[0], y: cy }));
  dec.forEach((cx, index) => {
    p.push(matrix(cx, cy - 22 - index * 10, 72, 44 + index * 12, `Dec ${index + 1}`, "green", 4, 4, 7));
    if (index < 2) p.push(flow({ x: cx + 79, y: cy }, { x: dec[index + 1], y: cy }));
  });
  enc.forEach((cx, index) => p.push(wire(
    { x: cx + 36, y: cy - 38 }, { x: cx + 36, y: y + 88 - index * 10 },
    { x: dec[2 - index] + 36, y: y + 88 - index * 10 }, { x: dec[2 - index] + 36, y: cy - 38 },
  )));
  p.push(flow({ x: dec[2] + 79, y: cy }, { x: x + width, y: cy }));
  p.push(text(x + width / 2, y + 67, "skip: copy / crop / concat", true, "orange"));
  p.push(text(x + width / 2, y + height - 25, "收缩路径提取语义，扩张路径恢复分辨率；同尺度特征跨层拼接"));
  return p;
}

function visionTransformer(bounds: Bounds): DetailPrimitive[] {
  return pipeline(bounds, [
    { label: "image", visual: "matrix", tone: "blue" },
    { label: "patchify", note: "P×P grid", visual: "matrix", tone: "orange" },
    { label: "Linear", note: "patch embedding", tone: "violet" },
    { label: "+ pos / CLS", visual: "circle", tone: "green" },
    { label: "Transformer ×L", note: "MSA + MLP", tone: "violet" },
    { label: "head", note: "CLS / pooling", tone: "pink" },
  ], "ViT 把图像网格重排为 patch token 序列，再复用 Transformer 编码器");
}

function gru(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  return [
    wire({ x, y: cy }, { x: x + 20, y: cy }),
    flow({ x: x + 20, y: cy }, { x: x + 26, y: y + 134 }, { x: x + 38, y: y + 134 }),
    flow({ x: x + 20, y: cy }, { x: x + 26, y: y + 260 }, { x: x + 38, y: y + 260 }),
    matrix(x + 38, y + 110, 58, 48, "x_t", "blue", 4, 3), matrix(x + 38, y + 236, 58, 48, "h_{t-1}", "orange", 4, 3),
    flow({ x: x + 96, y: y + 134 }, { x: x + 150, y: y + 134 }), flow({ x: x + 96, y: y + 260 }, { x: x + 132, y: y + 260 }, { x: x + 132, y: y + 134 }, { x: x + 150, y: y + 134 }),
    rect(x + 150, y + 105, 92, 58, "z_t", "green", "update σ"), rect(x + 150, y + 231, 92, 58, "r_t", "pink", "reset σ"),
    flow({ x: x + 242, y: y + 260 }, { x: x + 290, y: y + 260 }),
    flow({ x: x + 96, y: y + 260 }, { x: x + 116, y: y + 260 }, { x: x + 116, y: y + 310 }, { x: x + 280, y: y + 310 }, { x: x + 280, y: y + 260 }, { x: x + 290, y: y + 260 }),
    circle(x + 310, y + 260, "×", "pink"),
    flow({ x: x + 330, y: y + 260 }, { x: x + 370, y: y + 260 }, { x: x + 370, y: cy }, { x: x + 398, y: cy }),
    flow({ x: x + 96, y: y + 134 }, { x: x + 116, y: y + 134 }, { x: x + 116, y: y + 82 }, { x: x + 370, y: y + 82 }, { x: x + 370, y: cy }, { x: x + 398, y: cy }),
    rect(x + 398, cy - 29, 112, 58, "h̃_t", "violet", "tanh candidate"),
    flow({ x: x + 510, y: cy }, { x: x + 566, y: cy }), flow({ x: x + 242, y: y + 134 }, { x: x + 548, y: y + 134 }, { x: x + 548, y: cy }, { x: x + 566, y: cy }),
    circle(x + 586, cy, "mix", "orange", 20), flow({ x: x + 606, y: cy }, { x: x + 650, y: cy }),
    matrix(x + 650, cy - 28, 66, 56, "h_t", "green", 4, 3), flow({ x: x + 716, y: cy }, { x: x + width, y: cy }),
    text(x + width / 2, y + height - 26, "h_t = (1-z_t)⊙h_{t-1} + z_t⊙h̃_t；单状态替代 LSTM 的 h/c 双状态"),
  ];
}

function bidirectionalRecurrent(bounds: Bounds): DetailPrimitive[] {
  return splitMerge(bounds, [
    { label: "→ RNN / LSTM / GRU", note: "t = 1…T", tone: "blue" },
    { label: "← RNN / LSTM / GRU", note: "t = T…1", tone: "pink" },
  ], "Concat / Σ", "正向与反向状态在每个时间步合并；在线因果推理不能使用反向分支");
}

function seq2seq(bounds: Bounds): DetailPrimitive[] {
  return pipeline(bounds, [
    { label: "source tokens", visual: "matrix", tone: "blue" },
    { label: "Encoder", note: "states h₁…hₙ", tone: "violet" },
    { label: "Attention", note: "context c_t", visual: "circle", tone: "orange" },
    { label: "Decoder", note: "y_{<t}, c_t", tone: "green" },
    { label: "Softmax", note: "next token", tone: "pink" },
    { label: "target", visual: "matrix", tone: "blue" },
  ], "Teacher forcing 改变训练输入；beam search 改变解码搜索，不改变编码器—解码器主拓扑");
}

function stateSpace(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  return [
    flow({ x, y: cy }, { x: x + 34, y: cy }), matrix(x + 34, cy - 28, 58, 56, "x", "blue", 4, 4),
    wire({ x: x + 92, y: cy }, { x: x + 130, y: cy }),
    flow({ x: x + 130, y: cy }, { x: x + 154, y: y + 126 }, { x: x + 188, y: y + 126 }),
    flow({ x: x + 130, y: cy }, { x: x + 154, y: y + 250 }, { x: x + 188, y: y + 250 }),
    rect(x + 188, y + 99, 116, 54, "Conv1d + SiLU", "green", "local branch"),
    rect(x + 188, y + 223, 116, 54, "gate z", "pink", "input projection"),
    flow({ x: x + 304, y: y + 126 }, { x: x + 348, y: y + 126 }), rect(x + 348, y + 96, 148, 60, "Selective SSM", "violet", "Δ, B, C → scan"),
    flow({ x: x + 496, y: y + 126 }, { x: x + 548, y: y + 126 }, { x: x + 548, y: cy }, { x: x + 574, y: cy }),
    flow({ x: x + 304, y: y + 250 }, { x: x + 548, y: y + 250 }, { x: x + 548, y: cy }, { x: x + 574, y: cy }),
    circle(x + 594, cy, "×", "orange", 20), flow({ x: x + 614, y: cy }, { x: x + 656, y: cy }),
    rect(x + 656, cy - 27, 110, 54, "out project", "blue"), flow({ x: x + 766, y: cy }, { x: x + width, y: cy }),
    text(x + width / 2, y + height - 26, "Mamba 类块用输入依赖的 Δ/B/C 执行选择性扫描，再与门控支路逐元素相乘"),
  ];
}

function autoencoder(bounds: Bounds): DetailPrimitive[] {
  return pipeline(bounds, [
    { label: "x", visual: "matrix", tone: "blue" },
    { label: "Encoder", note: "compress", tone: "violet" },
    { label: "z", visual: "circle", tone: "orange" },
    { label: "Decoder", note: "expand", tone: "green" },
    { label: "x̂", visual: "matrix", tone: "pink" },
  ], "Undercomplete、Denoising、Sparse 与 Convolutional AE 主要改变瓶颈约束和编码器类型");
}

function variationalAutoencoder(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  return [
    flow({ x, y: cy }, { x: x + 35, y: cy }), matrix(x + 35, cy - 28, 58, 56, "x", "blue", 4, 4), flow({ x: x + 93, y: cy }, { x: x + 132, y: cy }),
    rect(x + 132, cy - 30, 110, 60, "Encoder", "violet", "qφ(z|x)"), wire({ x: x + 242, y: cy }, { x: x + 270, y: cy }),
    flow({ x: x + 270, y: cy }, { x: x + 292, y: y + 123 }, { x: x + 324, y: y + 123 }),
    flow({ x: x + 270, y: cy }, { x: x + 292, y: y + 245 }, { x: x + 324, y: y + 245 }),
    rect(x + 324, y + 98, 92, 50, "μ", "blue"), rect(x + 324, y + 220, 92, 50, "log σ²", "orange"),
    flow({ x: x + 416, y: y + 123 }, { x: x + 462, y: y + 123 }, { x: x + 462, y: cy }, { x: x + 488, y: cy }),
    flow({ x: x + 416, y: y + 245 }, { x: x + 462, y: y + 245 }, { x: x + 462, y: cy }, { x: x + 488, y: cy }),
    circle(x + 510, cy, "μ+σε", "green", 22),
    rect(x + 474, y + 45, 72, 44, "ε", "green", "N(0,I)", "capsule"),
    flow({ x: x + 510, y: y + 89 }, { x: x + 510, y: cy - 22 }),
    flow({ x: x + 532, y: cy }, { x: x + 568, y: cy }), rect(x + 568, cy - 28, 106, 56, "Decoder", "violet", "pθ(x|z)"),
    flow({ x: x + 674, y: cy }, { x: x + 706, y: cy }), matrix(x + 706, cy - 28, 58, 56, "x̂", "pink", 4, 4), flow({ x: x + 764, y: cy }, { x: x + width, y: cy }),
    text(x + width / 2, y + height - 26, "重参数技巧保持采样可微；训练目标联合重建项与 KL(qφ||p)"),
  ];
}

function gan(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  const branchX = x + 24;
  return [
    wire({ x, y: cy }, { x: branchX, y: cy }),
    flow({ x: branchX, y: cy }, { x: x + 32, y: y + 128 }, { x: x + 42, y: y + 128 }),
    flow({ x: branchX, y: cy }, { x: x + 32, y: y + 254 }, { x: x + 42, y: y + 254 }),
    matrix(x + 42, y + 102, 58, 52, "z", "violet", 4, 3), matrix(x + 42, y + 228, 58, 52, "real x", "blue", 4, 3),
    flow({ x: x + 100, y: y + 128 }, { x: x + 146, y: y + 128 }), rect(x + 146, y + 99, 118, 58, "Generator G", "green"),
    flow({ x: x + 264, y: y + 128 }, { x: x + 316, y: y + 128 }), matrix(x + 316, y + 102, 68, 52, "fake G(z)", "pink", 4, 3),
    flow({ x: x + 384, y: y + 128 }, { x: x + 442, y: y + 128 }, { x: x + 442, y: cy }, { x: x + 478, y: cy }),
    flow({ x: x + 100, y: y + 254 }, { x: x + 442, y: y + 254 }, { x: x + 442, y: cy }, { x: x + 478, y: cy }),
    rect(x + 478, cy - 34, 130, 68, "Discriminator D", "orange", "shared classifier"),
    flow({ x: x + 608, y: cy }, { x: x + 650, y: cy }), rect(x + 650, cy - 27, 96, 54, "real / fake", "blue"),
    flow({ x: x + 746, y: cy }, { x: x + width, y: cy }), text(x + width / 2, y + height - 27, "D 同时接收真实与生成样本；G 通过 D 的梯度学习欺骗判别器"),
  ];
}

function diffusion(bounds: Bounds): DetailPrimitive[] {
  return pipeline(bounds, [
    { label: "x₀", visual: "matrix", tone: "blue" },
    { label: "+ ε", note: "forward q(x_t|x₀)", visual: "circle", tone: "orange" },
    { label: "x_t", visual: "matrix", tone: "pink" },
    { label: "εθ(x_t,t,c)", note: "U-Net / DiT", tone: "violet" },
    { label: "scheduler", note: "reverse step", tone: "green" },
    { label: "x_{t-1}", visual: "matrix", tone: "blue" },
  ], "训练随机采样 t 并预测噪声；生成时从 x_T 反复执行调度器到 x₀");
}

function normalizingFlow(bounds: Bounds): DetailPrimitive[] {
  return pipeline(bounds, [
    { label: "x", visual: "matrix", tone: "blue" },
    { label: "f₁ ↔", note: "coupling", tone: "violet" },
    { label: "f₂ ↔", note: "permute + scale", tone: "green" },
    { label: "f_K ↔", note: "invertible", tone: "violet" },
    { label: "z ~ p(z)", visual: "matrix", tone: "orange" },
    { label: "log p(x)", note: "base + Σ log|det J|", tone: "pink" },
  ], "NICE/RealNVP/Glow/MAF 的差异在可逆变换族与雅可比计算方式");
}

function graphMessagePassing(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  return [
    wire({ x, y: cy }, { x: x + 38, y: cy }),
    circle(x + 72, y + 112, "u₁", "blue"), circle(x + 72, cy, "v", "orange"), circle(x + 72, y + 272, "u₂", "green"),
    flow({ x: x + 90, y: y + 112 }, { x: x + 154, y: y + 112 }), flow({ x: x + 90, y: cy }, { x: x + 154, y: cy }), flow({ x: x + 90, y: y + 272 }, { x: x + 154, y: y + 272 }),
    rect(x + 154, y + 87, 120, 50, "message φ", "blue", "m_{u→v}"), rect(x + 154, cy - 25, 120, 50, "self state", "orange", "h_v"), rect(x + 154, y + 247, 120, 50, "message φ", "green", "m_{u→v}"),
    flow({ x: x + 274, y: y + 112 }, { x: x + 330, y: y + 112 }, { x: x + 330, y: cy }, { x: x + 364, y: cy }),
    flow({ x: x + 274, y: y + 272 }, { x: x + 330, y: y + 272 }, { x: x + 330, y: cy }, { x: x + 364, y: cy }),
    circle(x + 386, cy, "Σ", "violet", 22), flow({ x: x + 408, y: cy }, { x: x + 446, y: cy }),
    flow({ x: x + 274, y: cy }, { x: x + 432, y: cy }, { x: x + 446, y: cy }), rect(x + 446, cy - 31, 136, 62, "update γ", "green", "h'_v = γ(h_v,m_v)"),
    flow({ x: x + 582, y: cy }, { x: x + 624, y: cy }), circle(x + 648, cy, "v'", "orange", 24), flow({ x: x + 672, y: cy }, { x: x + width, y: cy }),
    text(x + width / 2, y + height - 25, "GCN/SAGE/GAT/GIN 主要改变消息、聚合和更新函数；关系图再按边类型分参数"),
  ];
}

function timeSeriesForecast(bounds: Bounds): DetailPrimitive[] {
  return splitMerge(bounds, [
    { label: "Trend / level", note: "moving average · linear", tone: "blue" },
    { label: "Seasonal / residual", note: "Fourier · attention · mixer", tone: "violet" },
    { label: "Covariates", note: "known future / static", tone: "green" },
  ], "Forecast Σ", "ARIMA/ETS/Prophet 显式建模成分；深度模型以卷积、注意力或 MLP 学习相同依赖");
}

function dualEncoder(bounds: Bounds): DetailPrimitive[] {
  return splitMerge(bounds, [
    { label: "Image → image encoder", note: "CNN / ViT → v_i", tone: "blue" },
    { label: "Text → text encoder", note: "Transformer → t_j", tone: "green" },
  ], "v · tᵀ / τ", "CLIP/ALIGN/CLAP 双塔独立编码，批内相似度矩阵以双向对比损失对齐");
}

function dqn(bounds: Bounds): DetailPrimitive[] {
  return pipeline(bounds, [
    { label: "state s", visual: "matrix", tone: "blue" },
    { label: "Qθ(s,·)", note: "online network", tone: "violet" },
    { label: "argmax / ε", note: "action a", visual: "circle", tone: "orange" },
    { label: "Environment", note: "step(a)", tone: "green" },
    { label: "r, s'", visual: "matrix", tone: "blue" },
    { label: "Replay + target", note: "TD update", tone: "pink" },
  ], "经验回放打破样本相关性；目标网络构造稳定的 Bellman bootstrap 目标");
}

function actorCritic(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  return [
    wire({ x, y: cy }, { x: x + 42, y: cy }), matrix(x + 42, cy - 28, 58, 56, "s", "blue", 4, 3),
    flow({ x: x + 100, y: cy }, { x: x + 142, y: y + 126 }, { x: x + 176, y: y + 126 }),
    flow({ x: x + 100, y: cy }, { x: x + 142, y: y + 268 }, { x: x + 176, y: y + 268 }),
    rect(x + 176, y + 97, 126, 58, "Actor πθ(a|s)", "violet", "sample / mean"), rect(x + 176, y + 239, 126, 58, "Critic Vφ(s)", "green", "value baseline"),
    flow({ x: x + 302, y: y + 126 }, { x: x + 356, y: y + 126 }), rect(x + 356, y + 97, 122, 58, "Environment", "orange", "a → r,s'"),
    flow({ x: x + 478, y: y + 126 }, { x: x + 528, y: y + 126 }, { x: x + 528, y: cy }, { x: x + 556, y: cy }),
    flow({ x: x + 302, y: y + 268 }, { x: x + 528, y: y + 268 }, { x: x + 528, y: cy }, { x: x + 556, y: cy }),
    rect(x + 556, cy - 33, 132, 66, "Advantage Â", "pink", "returns − value"), flow({ x: x + 688, y: cy }, { x: x + 730, y: cy }),
    rect(x + 730, cy - 28, 108, 56, "Policy update", "blue", "PPO clip / PG"), flow({ x: x + 838, y: cy }, { x: x + width, y: cy }),
    text(x + width / 2, y + height - 27, "Actor 产生动作，Critic 估计基线；PPO/TRPO/A2C 的差异集中在更新约束与采样方式"),
  ];
}

function distillation(bounds: Bounds): DetailPrimitive[] {
  return splitMerge(bounds, [
    { label: "Teacher → soft logits", note: "frozen · temperature T", tone: "violet" },
    { label: "Student → logits", note: "trainable compact model", tone: "green" },
    { label: "Labels → hard target", note: "optional supervised branch", tone: "blue" },
  ], "KL + CE", "蒸馏联合教师软分布与真实标签；feature distillation 在中间表示再增加对齐损失");
}

function adapterLora(bounds: Bounds): DetailPrimitive[] {
  const { x, y, width, height } = bounds;
  const cy = y + height / 2;
  return [
    wire({ x, y: cy }, { x: x + 42, y: cy }), matrix(x + 42, cy - 28, 58, 56, "x", "blue", 4, 3),
    flow({ x: x + 100, y: cy }, { x: x + 142, y: y + 120 }, { x: x + 178, y: y + 120 }),
    flow({ x: x + 100, y: cy }, { x: x + 142, y: y + 236 }, { x: x + 178, y: y + 236 }),
    rect(x + 178, y + 91, 144, 58, "Frozen W", "neutral", "base projection Wx"),
    rect(x + 178, y + 207, 86, 58, "LoRA A", "violet", "d → r"), flow({ x: x + 264, y: y + 236 }, { x: x + 292, y: y + 236 }), rect(x + 292, y + 207, 86, 58, "LoRA B", "green", "r → d"),
    flow({ x: x + 322, y: y + 120 }, { x: x + 472, y: y + 120 }, { x: x + 472, y: cy }, { x: x + 502, y: cy }),
    flow({ x: x + 378, y: y + 236 }, { x: x + 472, y: y + 236 }, { x: x + 472, y: cy }, { x: x + 502, y: cy }),
    circle(x + 522, cy, "+", "orange", 20), flow({ x: x + 542, y: cy }, { x: x + 584, y: cy }),
    rect(x + 584, cy - 30, 142, 60, "y = Wx + αBAx", "blue", "merge at inference"), flow({ x: x + 726, y: cy }, { x: x + width, y: cy }),
    text(x + width / 2, y + height - 25, "LoRA 训练低秩增量；Adapter/Prefix/Prompt tuning 改为串接瓶颈或可学习上下文"),
  ];
}

const BUILDERS: Record<CatalogKind, (bounds: Bounds) => DetailPrimitive[]> = {
  "linear-model": linearModel,
  "kernel-machine": kernelMachine,
  "decision-tree": decisionTree,
  ensemble,
  clustering,
  decomposition,
  mlp,
  normalization,
  "residual-block": residualBlock,
  "dense-connection": denseConnection,
  inception,
  "depthwise-convolution": depthwiseConvolution,
  unet,
  "vision-transformer": visionTransformer,
  gru,
  "bidirectional-recurrent": bidirectionalRecurrent,
  seq2seq,
  "state-space": stateSpace,
  autoencoder,
  "variational-autoencoder": variationalAutoencoder,
  gan,
  diffusion,
  "normalizing-flow": normalizingFlow,
  "graph-message-passing": graphMessagePassing,
  "time-series-forecast": timeSeriesForecast,
  "dual-encoder": dualEncoder,
  dqn,
  "actor-critic": actorCritic,
  distillation,
  "adapter-lora": adapterLora,
};

export function isCatalogDetailKind(kind: NodeDetailKind): kind is CatalogKind {
  return (CATALOG_KINDS as readonly NodeDetailKind[]).includes(kind);
}

export function buildCatalogDetail(kind: CatalogKind, bounds: Bounds): DetailPrimitive[] {
  return BUILDERS[kind](bounds);
}
