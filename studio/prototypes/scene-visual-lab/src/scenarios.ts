import type {
  EdgeLabelStyle,
  EdgeRelation,
  LabEdge,
  LabNode,
  LabScene,
  NodeDetailKind,
  NodeShape,
  NodeVisualStyle,
  RouteStyle,
  VisualOptions,
} from "./types";

function node(
  id: string,
  x: number,
  y: number,
  label: string,
  secondary: string,
  shape: NodeShape = "operation",
  width = 148,
  height = 68,
  detailKind?: NodeDetailKind,
): LabNode {
  return {
    scene_node_id: id,
    bounds: { x, y, width, height },
    shape,
    label,
    secondary_label: secondary,
    detail_kind: detailKind,
  };
}

function edge(
  id: string,
  source: string,
  target: string,
  relation: EdgeRelation = "flow",
  label: string = relation,
): LabEdge {
  return {
    scene_edge_id: id,
    source_scene_node_id: source,
    target_scene_node_id: target,
    relation,
    label,
  };
}

function scene(
  id: string,
  title: string,
  description: string,
  nodes: LabNode[],
  edges: LabEdge[],
  paperWidth = 1120,
  paperHeight = 680,
): LabScene {
  return {
    scene_id: id,
    title,
    description,
    paper_width: paperWidth,
    paper_height: paperHeight,
    nodes,
    edges,
  };
}

const linear = scene(
  "linear-chain",
  "线性长链",
  "连续算子、均匀尺寸和短标签。",
  [
    node("input", 52, 290, "Input tokens", "B x T", "io", 132),
    node("embed", 236, 290, "Embedding", "lookup + position", "tensor"),
    node("attention", 440, 290, "Self attention", "multi-head", "attention", 164),
    node("norm", 658, 290, "Layer norm", "pre-norm", "normalization"),
    node("output", 864, 290, "Projection", "vocabulary logits", "operation", 168),
  ],
  [
    edge("e1", "input", "embed", "flow", "tokens"),
    edge("e2", "embed", "attention", "flow", "features"),
    edge("e3", "attention", "norm", "flow", "context"),
    edge("e4", "norm", "output", "flow", "normalized"),
  ],
);

const fanOut = scene(
  "fan-out",
  "扇出分支",
  "单一来源连接多个并行分支并再次汇聚。",
  [
    node("source", 52, 292, "Hidden state", "shared input", "tensor", 144),
    node("query", 340, 86, "Query", "linear projection", "operation", 156),
    node("key", 340, 226, "Key", "linear projection", "operation", 156),
    node("value", 340, 366, "Value", "linear projection", "operation", 156),
    node("gate", 340, 506, "Gate", "conditional mask", "condition", 156),
    node("join", 700, 274, "Attention", "scaled dot product", "attention", 190, 94),
    node("output", 946, 287, "Output", "mixed context", "io", 128),
  ],
  [
    edge("e1", "source", "query", "branch", "Q"),
    edge("e2", "source", "key", "branch", "K"),
    edge("e3", "source", "value", "branch", "V"),
    edge("e4", "source", "gate", "condition", "mask"),
    edge("e5", "query", "join", "merge", "query"),
    edge("e6", "key", "join", "merge", "key"),
    edge("e7", "value", "join", "merge", "value"),
    edge("e8", "gate", "join", "condition", "enabled"),
    edge("e9", "join", "output", "flow", "context"),
  ],
);

const fanIn = scene(
  "fan-in",
  "多路汇聚",
  "多个专家共享一个汇聚目标，测试目标端口拥挤。",
  [
    node("expert1", 80, 74, "Expert 1", "temporal", "operation"),
    node("expert2", 80, 208, "Expert 2", "frequency", "operation"),
    node("expert3", 80, 342, "Expert 3", "seasonal", "operation"),
    node("expert4", 80, 476, "Expert 4", "trend", "operation"),
    node("router", 418, 274, "Weighted merge", "router scores", "merge", 176, 104),
    node("norm", 720, 292, "Normalize", "mixture output", "normalization", 162),
    node("head", 942, 292, "Prediction", "task head", "io", 132),
  ],
  [
    edge("e1", "expert1", "router", "merge", "weight 0"),
    edge("e2", "expert2", "router", "merge", "weight 1"),
    edge("e3", "expert3", "router", "merge", "weight 2"),
    edge("e4", "expert4", "router", "merge", "weight 3"),
    edge("e5", "router", "norm", "flow", "mixture"),
    edge("e6", "norm", "head", "flow", "features"),
  ],
);

const residual = scene(
  "residual-skip",
  "残差跨越",
  "主链、长距离跳连和条件分支同时存在。",
  [
    node("input", 52, 284, "Input", "residual source", "io", 126),
    node("attention", 248, 206, "Attention", "main branch", "attention", 164, 82),
    node("dropout", 476, 206, "Dropout", "training only", "condition", 154, 82),
    node("add", 708, 278, "Residual add", "skip merge", "add", 96, 88),
    node("norm", 932, 286, "Layer norm", "block output", "normalization", 146),
  ],
  [
    edge("e1", "input", "attention", "flow", "hidden"),
    edge("e2", "attention", "dropout", "flow", "context"),
    edge("e3", "dropout", "add", "merge", "branch"),
    edge("e4", "input", "add", "residual", "residual"),
    edge("e5", "add", "norm", "flow", "summed"),
  ],
);

const feedback = scene(
  "feedback-loop",
  "状态反馈",
  "回路、状态更新和条件出口。",
  [
    node("state", 112, 276, "State", "t - 1", "tensor", 140),
    node("cell", 394, 244, "Recurrent cell", "state transition", "operation", 188, 112),
    node("output", 738, 168, "Emission", "current output", "io", 150),
    node("condition", 738, 392, "Continue?", "sequence gate", "condition", 150),
    node("sink", 950, 168, "Collector", "sequence", "operation", 132),
  ],
  [
    edge("e1", "state", "cell", "flow", "previous state"),
    edge("e2", "cell", "output", "flow", "emission"),
    edge("e3", "cell", "condition", "condition", "stop rule"),
    edge("e4", "condition", "state", "feedback", "next state"),
    edge("e5", "output", "sink", "flow", "append"),
  ],
);

const bipartite = scene(
  "dense-bipartite",
  "稠密双部图",
  "三对三全连接，集中暴露交叉和标签碰撞。",
  [
    node("a1", 70, 100, "Encoder A", "scale 1", "operation", 142),
    node("a2", 70, 292, "Encoder B", "scale 2", "operation", 142),
    node("a3", 70, 484, "Encoder C", "scale 3", "operation", 142),
    node("b1", 840, 100, "Decoder X", "head 1", "operation", 142),
    node("b2", 840, 292, "Decoder Y", "head 2", "operation", 142),
    node("b3", 840, 484, "Decoder Z", "head 3", "operation", 142),
  ],
  ["a1", "a2", "a3"].flatMap((source, sourceIndex) => ["b1", "b2", "b3"].map((target, targetIndex) => (
    edge(`e${sourceIndex}-${targetIndex}`, source, target, "memory", `memory ${sourceIndex + 1}.${targetIndex + 1}`)
  ))),
);

const hub = scene(
  "shared-hub",
  "共享中心",
  "高连接度中心节点与环形消费者。",
  [
    node("hub", 460, 278, "Shared memory", "global context", "tensor", 194, 104),
    node("n1", 74, 84, "Tokenizer", "producer", "operation", 140),
    node("n2", 452, 62, "Encoder", "producer", "attention", 140),
    node("n3", 876, 100, "Decoder A", "consumer", "operation", 140),
    node("n4", 876, 480, "Decoder B", "consumer", "operation", 140),
    node("n5", 452, 536, "Head", "consumer", "io", 140),
    node("n6", 74, 470, "Cache", "state", "tensor", 140),
  ],
  [
    edge("e1", "n1", "hub", "memory", "write tokens"),
    edge("e2", "n2", "hub", "memory", "write features"),
    edge("e3", "hub", "n3", "memory", "read A"),
    edge("e4", "hub", "n4", "memory", "read B"),
    edge("e5", "hub", "n5", "flow", "predict"),
    edge("e6", "hub", "n6", "feedback", "update cache"),
    edge("e7", "n6", "hub", "memory", "cached values"),
  ],
);

const crossing = scene(
  "crossing-pressure",
  "反向交叉",
  "左右两列逆序连接，测试布线分流能力。",
  [
    ...[0, 1, 2, 3].map((index) => node(`left${index}`, 62, 62 + index * 148, `Stage ${index + 1}`, "left lane", "operation", 138)),
    ...[0, 1, 2, 3].map((index) => node(`right${index}`, 914, 62 + index * 148, `Target ${index + 1}`, "right lane", "operation", 138)),
  ],
  [0, 1, 2, 3].map((index) => edge(`e${index}`, `left${index}`, `right${3 - index}`, "flow", `route ${index + 1}`)),
);

const parallel = scene(
  "parallel-relations",
  "并行关系",
  "相同端点承载多个语义关系。",
  [
    node("source", 120, 278, "Encoder block", "shared source", "attention", 190, 94),
    node("target", 786, 278, "Decoder block", "shared target", "attention", 190, 94),
    node("gate", 456, 98, "Mask", "condition", "condition", 150),
    node("state", 456, 494, "Cache", "memory state", "tensor", 150),
  ],
  [
    edge("e1", "source", "target", "flow", "hidden state"),
    edge("e2", "source", "target", "memory", "key / value"),
    edge("e3", "source", "target", "residual", "skip state"),
    edge("e4", "gate", "target", "condition", "attention mask"),
    edge("e5", "state", "target", "memory", "cached context"),
    edge("e6", "target", "state", "feedback", "cache update"),
  ],
);

const longLabels = scene(
  "long-labels",
  "长文本压力",
  "长节点名、长次级说明与长连线标签。",
  [
    node("input", 42, 272, "Historical multivariate observations", "batch x lookback x channels", "io", 238, 94),
    node("transform", 356, 250, "Frequency enhanced decomposition block", "seasonal and trend representation", "operation", 260, 138),
    node("output", 754, 272, "Probabilistic forecasting distribution", "quantiles for every prediction horizon", "io", 282, 94),
  ],
  [
    edge("e1", "input", "transform", "flow", "normalized temporal feature sequence"),
    edge("e2", "transform", "output", "flow", "decoded multi-horizon representation"),
    edge("e3", "input", "output", "residual", "direct autoregressive residual projection"),
  ],
);

const asymmetric = scene(
  "asymmetric-sizes",
  "异形尺寸",
  "高矮宽窄混排与非矩形节点。",
  [
    node("tiny", 68, 96, "Bias", "scalar", "tensor", 84, 48),
    node("tall", 270, 70, "Conditional feature selector", "gated channels", "condition", 150, 176),
    node("wide", 502, 282, "Wide multi-resolution representation", "concatenated feature pyramid", "operation", 308, 76),
    node("merge", 884, 114, "Add", "merge", "merge", 92, 92),
    node("output", 900, 460, "Output", "tensor", "io", 132, 54),
  ],
  [
    edge("e1", "tiny", "wide", "branch", "broadcast"),
    edge("e2", "tall", "wide", "condition", "selected channels"),
    edge("e3", "wide", "merge", "flow", "features"),
    edge("e4", "tiny", "merge", "residual", "bias"),
    edge("e5", "wide", "output", "flow", "projection"),
    edge("e6", "merge", "output", "merge", "combined"),
  ],
);

const vertical = scene(
  "vertical-dag",
  "纵向 DAG",
  "上下布局中的分叉、跨层连接与汇聚。",
  [
    node("input", 480, 30, "Input", "sequence", "io", 148),
    node("left", 220, 176, "Temporal path", "convolution", "operation", 164),
    node("right", 728, 176, "Frequency path", "spectral", "operation", 164),
    node("middle", 474, 330, "Cross attention", "fusion", "attention", 176, 82),
    node("skip", 82, 354, "Skip transform", "projection", "operation", 154),
    node("merge", 488, 500, "Concat", "feature axis", "concat", 104, 88),
    node("output", 860, 514, "Forecast", "output", "io", 148),
  ],
  [
    edge("e1", "input", "left", "branch", "time"),
    edge("e2", "input", "right", "branch", "frequency"),
    edge("e3", "left", "middle", "flow", "local"),
    edge("e4", "right", "middle", "memory", "global"),
    edge("e5", "input", "skip", "residual", "skip"),
    edge("e6", "skip", "merge", "merge", "projected"),
    edge("e7", "middle", "merge", "merge", "fused"),
    edge("e8", "merge", "output", "flow", "decoded"),
  ],
);

const wrongSide = scene(
  "nearest-side-regression",
  "最近侧回归",
  "目标位于左侧且中间有障碍，验证连线不会从右侧反向绕行。",
  [
    node("target", 72, 286, "Left target", "nearest west route", "tensor", 164, 86),
    node("blocker", 438, 242, "Unrelated block", "clearance obstacle", "operation", 204, 172),
    node("source", 866, 286, "Right source", "must leave left", "convolution", 176, 86),
    node("upper", 690, 74, "Upper source", "diagonal case", "operation", 158),
    node("lower", 690, 520, "Lower source", "diagonal case", "operation", 158),
  ],
  [
    edge("e1", "source", "target", "flow", "left-facing flow"),
    edge("e2", "upper", "target", "memory", "upper context"),
    edge("e3", "lower", "target", "residual", "lower residual"),
  ],
);

const terminalFanIn = scene(
  "terminal-fan-in",
  "终点扇入",
  "多条边进入同一目标，检查端口分散、箭头末段长度和头部遮挡。",
  [
    ...[0, 1, 2, 3, 4, 5].map((index) => node(
      `source${index}`,
      index % 2 === 0 ? 72 : 320,
      54 + index * 96,
      `Branch ${index + 1}`,
      index % 2 === 0 ? "local feature" : "global feature",
      index % 3 === 0 ? "convolution" : "operation",
      154,
      64,
    )),
    node("target", 842, 238, "Fusion target", "six independent input ports", "attention", 206, 192),
  ],
  [0, 1, 2, 3, 4, 5].map((index) => edge(
    `e${index}`,
    `source${index}`,
    "target",
    index % 2 ? "memory" : "merge",
    `input branch ${index + 1}`,
  )),
);

const fourSidePorts = scene(
  "four-side-ports",
  "四侧入射",
  "中心算子同时接收上下左右输入，验证端口侧选择与角点净距。",
  [
    node("center", 514, 292, "Add", "four-side merge", "add", 92, 92),
    node("left1", 80, 210, "Left feature A", "west", "tensor", 156),
    node("left2", 80, 394, "Left feature B", "west", "convolution", 156),
    node("right1", 884, 210, "Right feature A", "east", "tensor", 156),
    node("right2", 884, 394, "Right feature B", "east", "convolution", 156),
    node("top1", 344, 54, "Top context", "north", "attention", 156),
    node("top2", 622, 54, "Top mask", "north", "condition", 156),
    node("bottom1", 344, 548, "Bottom state", "south", "tensor", 156),
    node("bottom2", 622, 548, "Bottom scale", "south", "multiply", 92, 82),
  ],
  [
    edge("e1", "left1", "center", "flow", "left A"),
    edge("e2", "left2", "center", "merge", "left B"),
    edge("e3", "right1", "center", "memory", "right A"),
    edge("e4", "right2", "center", "merge", "right B"),
    edge("e5", "top1", "center", "memory", "top context"),
    edge("e6", "top2", "center", "condition", "top mask"),
    edge("e7", "bottom1", "center", "residual", "bottom state"),
    edge("e8", "bottom2", "center", "merge", "bottom scale"),
  ],
);

const verticalLabels = scene(
  "vertical-edge-labels",
  "纵向标签",
  "长纵向线段上的标签应旋转 90 度，并与节点和相邻边保持净距。",
  [
    node("topA", 254, 44, "Temporal encoder", "top lane", "convolution", 178, 78),
    node("topB", 688, 44, "Frequency encoder", "top lane", "tensor", 178, 78),
    node("midA", 254, 296, "Temporal mixer", "middle lane", "attention", 178, 78),
    node("midB", 688, 296, "Frequency mixer", "middle lane", "attention", 178, 78),
    node("bottomA", 254, 550, "Temporal output", "bottom lane", "io", 178, 70),
    node("bottomB", 688, 550, "Frequency output", "bottom lane", "io", 178, 70),
  ],
  [
    edge("e1", "topA", "midA", "flow", "temporal representation"),
    edge("e2", "midA", "bottomA", "flow", "decoded temporal features"),
    edge("e3", "topB", "midB", "memory", "frequency representation"),
    edge("e4", "midB", "bottomB", "flow", "decoded frequency features"),
    edge("e5", "topA", "midB", "residual", "cross-scale residual"),
    edge("e6", "topB", "midA", "memory", "cross-frequency memory"),
  ],
);

const semanticGlyphs = scene(
  "semantic-glyph-library",
  "语义图元库",
  "对照神经网络论文常见表达，检查张量、卷积、注意力与专用汇合符号。",
  [
    node("input", 40, 118, "Input tensor", "B x T x C", "tensor", 166, 88),
    node("conv", 260, 118, "Conv feature maps", "k=3, channels=64", "convolution", 180, 88),
    node("attention", 500, 118, "QKV attention", "scaled dot product", "attention", 184, 88),
    node("norm", 744, 118, "Layer norm", "mu / sigma", "normalization", 166, 88),
    node("residual", 936, 116, "Add", "residual", "add", 88, 88),
    node("gate", 286, 410, "Multiply", "gated feature", "multiply", 96, 88),
    node("concat", 526, 410, "Concat", "channel axis", "concat", 102, 88),
    node("output", 772, 410, "Output tensor", "B x H x C", "tensor", 176, 88),
  ],
  [
    edge("e1", "input", "conv", "flow", "signal"),
    edge("e2", "conv", "attention", "flow", "feature maps"),
    edge("e3", "attention", "norm", "flow", "context"),
    edge("e4", "norm", "residual", "merge", "normalized"),
    edge("e5", "input", "residual", "residual", "skip"),
    edge("e6", "conv", "gate", "branch", "feature"),
    edge("e7", "gate", "concat", "merge", "gated"),
    edge("e8", "residual", "concat", "merge", "residual stream"),
    edge("e9", "concat", "output", "flow", "joined features"),
  ],
);

const denseChannels = scene(
  "dense-channel-separation",
  "密集分槽",
  "高密度平行边与交叉边共同出现，检查共享线段惩罚和分槽稳定性。",
  [
    ...[0, 1, 2, 3, 4].map((index) => node(`left${index}`, 62, 42 + index * 128, `Source ${index + 1}`, "encoder lane", "operation", 150, 62)),
    ...[0, 1, 2, 3, 4].map((index) => node(`right${index}`, 908, 42 + index * 128, `Target ${index + 1}`, "decoder lane", "operation", 150, 62)),
    node("bridge", 486, 286, "Shared tensor", "routing obstacle", "tensor", 158, 94),
  ],
  [
    ...[0, 1, 2, 3, 4].map((index) => edge(`straight${index}`, `left${index}`, `right${index}`, "flow", `lane ${index + 1}`)),
    ...[0, 1, 2, 3, 4].map((index) => edge(`cross${index}`, `left${index}`, `right${4 - index}`, "memory", `cross ${index + 1}`)),
    edge("bridge-in", "left2", "bridge", "memory", "write shared"),
    edge("bridge-out", "bridge", "right2", "memory", "read shared"),
  ],
);

const parentChildExpansion = scene(
  "parent-child-expansion",
  "父子模块展开",
  "点击模块右上角展开内部数据流；下游节点增量平移，外部连线重新吸附并避让放大的父模块。",
  [
    node("expand-input", 32, 349, "Input", "B × T × C", "io", 118, 82),
    node("expand-transform", 194, 344, "Tensor transform", "permute + reshape", "tensor", 152, 92, "tensor-transform"),
    node("expand-conv", 390, 344, "Convolution", "feature extraction", "convolution", 156, 92, "convolution"),
    node("expand-attention", 590, 340, "Multi-head attention", "QKV + scaled dot product", "attention", 170, 100, "attention"),
    node("expand-add-norm", 806, 343, "Add & Norm", "residual + LayerNorm", "normalization", 160, 94, "add-norm"),
    node("expand-ffn", 1010, 343, "Feed-forward", "Linear + GELU + Linear", "operation", 160, 94, "feedforward"),
    node("expand-output", 1214, 349, "Output", "B × T × D", "io", 126, 82),
  ],
  [
    edge("expand-e1", "expand-input", "expand-transform", "flow", "features"),
    edge("expand-e2", "expand-transform", "expand-conv", "flow", "reshaped"),
    edge("expand-e3", "expand-conv", "expand-attention", "flow", "feature maps"),
    edge("expand-e4", "expand-attention", "expand-add-norm", "flow", "context"),
    edge("expand-e5", "expand-add-norm", "expand-ffn", "flow", "normalized"),
    edge("expand-e6", "expand-ffn", "expand-output", "flow", "encoded"),
  ],
  1380,
  780,
);

const extendedModuleCatalog = scene(
  "extended-module-catalog",
  "扩展模型模块目录",
  "以统一的左入右出契约展开 Embedding、LSTM、稀疏 MoE 与 Pooling，并验证外部数据流连续性。",
  [
    node("catalog-input", 32, 349, "Input", "ids / features", "io", 118, 82),
    node("catalog-embedding", 194, 344, "Embedding", "lookup + position", "tensor", 158, 92, "embedding"),
    node("catalog-recurrent", 396, 340, "LSTM cell", "gates + recurrent state", "operation", 160, 100, "recurrent"),
    node("catalog-moe", 600, 340, "Sparse MoE", "router + top-k experts", "condition", 166, 100, "mixture-of-experts"),
    node("catalog-pooling", 810, 344, "Pooling", "spatial reduction", "convolution", 154, 92, "pooling"),
    node("catalog-head", 1008, 344, "Task head", "projection", "operation", 154, 92),
    node("catalog-output", 1206, 349, "Output", "prediction", "io", 126, 82),
  ],
  [
    edge("catalog-e1", "catalog-input", "catalog-embedding", "flow", "indices"),
    edge("catalog-e2", "catalog-embedding", "catalog-recurrent", "flow", "embeddings"),
    edge("catalog-e3", "catalog-recurrent", "catalog-moe", "flow", "sequence state"),
    edge("catalog-e4", "catalog-moe", "catalog-pooling", "flow", "mixed features"),
    edge("catalog-e5", "catalog-pooling", "catalog-head", "flow", "pooled features"),
    edge("catalog-e6", "catalog-head", "catalog-output", "flow", "logits"),
  ],
  1375,
  780,
);

function detailCatalogScene(
  id: string,
  title: string,
  description: string,
  modules: Array<{ id: string; label: string; secondary: string; shape: NodeShape; kind: NodeDetailKind }>,
): LabScene {
  const nodes = [
    node(`${id}-input`, 32, 349, "Input", "domain input", "io", 118, 82),
    ...modules.map((module, index) => node(
      `${id}-${module.id}`,
      190 + index * 205,
      344,
      module.label,
      module.secondary,
      module.shape,
      162,
      92,
      module.kind,
    )),
    node(`${id}-output`, 190 + modules.length * 205, 349, "Output", "domain result", "io", 126, 82),
  ];
  return scene(
    id,
    title,
    description,
    nodes,
    nodes.slice(0, -1).map((source, index) => edge(
      `${id}-e${index + 1}`,
      source.scene_node_id,
      nodes[index + 1].scene_node_id,
      "flow",
      index === 0 ? "features" : "representation",
    )),
    190 + modules.length * 205 + 168,
    780,
  );
}

const traditionalMlCatalog = detailCatalogScene(
  "traditional-ml-catalog",
  "传统机器学习结构目录",
  "线性、核方法、树、集成与聚类使用不同的决策和迭代图形，不再统一表现为矩阵块。",
  [
    { id: "linear", label: "Linear / GLM", secondary: "score + link", shape: "operation", kind: "linear-model" },
    { id: "kernel", label: "Kernel machine", secondary: "support vectors", shape: "condition", kind: "kernel-machine" },
    { id: "tree", label: "Decision tree", secondary: "threshold branches", shape: "condition", kind: "decision-tree" },
    { id: "ensemble", label: "Forest / Boosting", secondary: "learners + aggregate", shape: "merge", kind: "ensemble" },
    { id: "cluster", label: "Clustering", secondary: "assign + update", shape: "condition", kind: "clustering" },
  ],
);

const neuralFoundationCatalog = detailCatalogScene(
  "neural-foundation-catalog",
  "表示与连接结构目录",
  "分解、MLP、归一化、残差与密集连接分别展示其统计、捷径和特征复用关系。",
  [
    { id: "decompose", label: "Matrix decomposition", secondary: "basis + projection", shape: "tensor", kind: "decomposition" },
    { id: "mlp", label: "MLP / gated FFN", secondary: "expand + activate", shape: "operation", kind: "mlp" },
    { id: "normalization", label: "Norm layer", secondary: "statistics + affine", shape: "normalization", kind: "normalization" },
    { id: "residual", label: "Residual block", secondary: "transform + identity", shape: "add", kind: "residual-block" },
    { id: "dense", label: "Dense connection", secondary: "feature reuse", shape: "concat", kind: "dense-connection" },
  ],
);

const visionSequenceCatalog = detailCatalogScene(
  "vision-sequence-catalog",
  "视觉与门控序列结构目录",
  "多尺度卷积、轻量卷积、U-Net、ViT 与 GRU 各自保留独有的分支、跳连、分块和门控。",
  [
    { id: "inception", label: "Inception", secondary: "multi-scale branches", shape: "convolution", kind: "inception" },
    { id: "depthwise", label: "Depthwise separable", secondary: "DW + PW conv", shape: "convolution", kind: "depthwise-convolution" },
    { id: "unet", label: "U-Net", secondary: "encoder + skips + decoder", shape: "concat", kind: "unet" },
    { id: "vit", label: "Vision Transformer", secondary: "patch tokens", shape: "attention", kind: "vision-transformer" },
    { id: "gru", label: "GRU cell", secondary: "reset + update gates", shape: "operation", kind: "gru" },
  ],
);

const sequenceGenerativeCatalog = detailCatalogScene(
  "sequence-generative-catalog",
  "序列与潜变量结构目录",
  "双向循环、Seq2Seq、选择性状态空间、自编码器和 VAE 展示不同的上下文与潜变量路径。",
  [
    { id: "bidir", label: "Bidirectional RNN", secondary: "forward + backward", shape: "merge", kind: "bidirectional-recurrent" },
    { id: "seq2seq", label: "Seq2Seq", secondary: "encode + attend + decode", shape: "attention", kind: "seq2seq" },
    { id: "ssm", label: "Mamba / SSM", secondary: "selective scan", shape: "operation", kind: "state-space" },
    { id: "ae", label: "Autoencoder", secondary: "latent bottleneck", shape: "tensor", kind: "autoencoder" },
    { id: "vae", label: "Variational AE", secondary: "distribution + sample", shape: "condition", kind: "variational-autoencoder" },
  ],
);

const generativeGraphCatalog = detailCatalogScene(
  "generative-graph-catalog",
  "生成、图与时间序列目录",
  "对抗、扩散、可逆流、图消息传递和时间序列分解使用不同的数据依赖结构。",
  [
    { id: "gan", label: "GAN", secondary: "generator + discriminator", shape: "condition", kind: "gan" },
    { id: "diffusion", label: "Diffusion", secondary: "noise + denoise", shape: "operation", kind: "diffusion" },
    { id: "flow", label: "Normalizing flow", secondary: "invertible transforms", shape: "tensor", kind: "normalizing-flow" },
    { id: "gnn", label: "Message-passing GNN", secondary: "message + aggregate", shape: "merge", kind: "graph-message-passing" },
    { id: "forecast", label: "Time-series model", secondary: "decompose + forecast", shape: "operation", kind: "time-series-forecast" },
  ],
);

const multimodalRlAdaptationCatalog = detailCatalogScene(
  "multimodal-rl-adaptation-catalog",
  "多模态、强化学习与适配目录",
  "双塔对齐、值函数闭环、Actor-Critic、蒸馏和低秩适配以专用训练数据流表达。",
  [
    { id: "dual", label: "Dual encoder", secondary: "image-text contrast", shape: "merge", kind: "dual-encoder" },
    { id: "dqn", label: "DQN", secondary: "Q + replay + target", shape: "operation", kind: "dqn" },
    { id: "actor-critic", label: "Actor-Critic", secondary: "policy + value", shape: "operation", kind: "actor-critic" },
    { id: "distill", label: "Distillation", secondary: "teacher + student", shape: "merge", kind: "distillation" },
    { id: "lora", label: "LoRA / Adapter", secondary: "frozen + low rank", shape: "add", kind: "adapter-lora" },
  ],
);

export const SCENARIOS: readonly LabScene[] = [
  linear,
  fanOut,
  fanIn,
  residual,
  feedback,
  bipartite,
  hub,
  crossing,
  parallel,
  longLabels,
  asymmetric,
  vertical,
  wrongSide,
  terminalFanIn,
  fourSidePorts,
  verticalLabels,
  semanticGlyphs,
  denseChannels,
  parentChildExpansion,
  extendedModuleCatalog,
  traditionalMlCatalog,
  neuralFoundationCatalog,
  visionSequenceCatalog,
  sequenceGenerativeCatalog,
  generativeGraphCatalog,
  multimodalRlAdaptationCatalog,
];

export const ROUTE_STYLES: readonly RouteStyle[] = ["adaptive", "direct", "orthogonal", "channel", "curve"];
export const NODE_STYLES: readonly NodeVisualStyle[] = ["semantic", "technical", "compact"];
export const LABEL_STYLES: readonly EdgeLabelStyle[] = ["plain", "plate", "endpoint"];

export const DEFAULT_OPTIONS: VisualOptions = {
  routeStyle: "adaptive",
  nodeStyle: "semantic",
  labelStyle: "plate",
};

export function optionCombinations(): VisualOptions[] {
  return ROUTE_STYLES.flatMap((routeStyle) => NODE_STYLES.flatMap((nodeStyle) => LABEL_STYLES.map((labelStyle) => ({
    routeStyle,
    nodeStyle,
    labelStyle,
  }))));
}

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
