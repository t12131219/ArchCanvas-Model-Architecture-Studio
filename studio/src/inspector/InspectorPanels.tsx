import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { Braces, CircleDot, FileCode2, GitBranch, Link2, ShieldCheck, Trash2, X } from "lucide-react";
import { getStudioJson } from "../api/studio-client";
import type { RenderEdge, RenderNode, Bounds as Rect } from "../visual-kernel/types";
import type {
  AgentProposal,
  ArchitectureNodeView,
  ArchitectureTensor,
  Evidence,
  PublicationNode,
  SourceExcerpt,
  SourceTransaction,
  StudioState,
} from "../app/studio-types";

export interface InspectorLanguageValue {
  tx: (english: string, chinese: string) => string;
}

export const InspectorLanguageContext = createContext<InspectorLanguageValue>({
  tx: (_english, chinese) => chinese,
});

function useInspectorLanguage(): InspectorLanguageValue {
  return useContext(InspectorLanguageContext);
}

export function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="field"><label>{label}</label><div className={mono ? "mono" : ""}>{value}</div></div>;
}

export function EdgeInspector({ edge, evidence }: { edge: RenderEdge; evidence: Evidence[] }) {
  const { tx } = useInspectorLanguage();
  return <div className="structure-inspector edge-inspector">
    <header className="inspector-heading"><div><h2>{edge.label || tx("Connection", "连接")}</h2><span>{tx("Canonical architecture relation", "规范架构关系")}</span></div><Link2 size={18} /></header>
    <div className="status-row"><span>{edge.relation}</span><b>{edge.semanticChannel}</b></div>
    <Field label={tx("Source port", "源端口")} value={edge.sourcePortId} mono />
    <Field label={tx("Target port", "目标端口")} value={edge.targetPortId} mono />
    <Field label={tx("Role / channel", "角色 / 通道")} value={`${edge.semanticChannel} / ${edge.relation}`} />
    <Field label={tx("Canonical edge IDs", "规范边 ID")} value={edge.canonicalEdgeIds.join(", ") || tx("Projected relation", "投影关系")} mono />
    <Field label={tx("Evidence", "证据")} value={`${evidence.length} ${tx("records", "条记录")} · ${evidence[0]?.confidence ?? tx("not linked", "未关联")}`} mono />
  </div>;
}

function structureKind(label: string, nodes: ArchitectureNodeView[]): "tensor" | "encoder" | "decoder" | "ffn" | "norm" | "attention" | "residual" | "convolution" | "pooling" | "recurrent" | "graph" | "moe" | "diffusion" | "state-space" | "embedding" | "activation" | "dropout" | "generic" {
  const normalizedLabel = label.trim().toLowerCase();
  const text = `${normalizedLabel} ${nodes.map((node) => `${node.semantic_name} ${String(node.attributes.op_type ?? "")}`).join(" ")}`.toLowerCase();
  if (["q", "k", "v", "query", "key", "value"].includes(normalizedLabel)) return "tensor";
  if (normalizedLabel.includes("residual") || normalizedLabel.includes("skip") || normalizedLabel === "add") return "residual";
  if (text.includes("diffusion") || text.includes("denois") || text.includes("timestep") || text.includes("noise schedule") || text.includes("unet")) return "diffusion";
  if (text.includes("mixture of expert") || text.includes("moe") || text.includes("expert") || text.includes("router") || text.includes("gating")) return "moe";
  if (text.includes("state space") || text.includes("ssm") || text.includes("mamba") || text.includes("selective scan")) return "state-space";
  if (text.includes("lstm") || text.includes("gru") || text.includes("rnn") || text.includes("recurrent") || text.includes("hidden state")) return "recurrent";
  if (text.includes("graph") || text.includes("gcn") || text.includes("gat") || text.includes("neighbor") || text.includes("message passing")) return "graph";
  if (text.includes("conv1d") || text.includes("conv2d") || text.includes("convolution") || text.includes("conv ")) return "convolution";
  if (text.includes("pool") || text.includes("adaptive avg") || text.includes("global avg")) return "pooling";
  if (text.includes("residual") || text.includes("skip connection") || normalizedLabel === "add" || normalizedLabel === "skip") return "residual";
  if (text.includes("multihead") || text.includes("multi-head") || text.includes("attention") || text.includes("qkv")) return "attention";
  if (text.includes("embedding") || text.includes("positional") || text.includes("token embedding")) return "embedding";
  if (text.includes("dropout")) return "dropout";
  if (text.includes("activation") || text.includes("relu") || text.includes("gelu") || text.includes("silu") || text.includes("swish")) return "activation";
  if (normalizedLabel.includes("encoder")) return nodes.length > 2 ? "encoder" : "norm";
  if (normalizedLabel.includes("decoder") || normalizedLabel === "cross") return "decoder";
  if (text.includes("ffn") || text.includes("feed forward") || text.includes("mlp")) return "ffn";
  if (text.includes("norm")) return "norm";
  if (text.includes("split") || text.includes("transpose") || text.includes("projection")) return "tensor";
  return "generic";
}

function StructureGlyph({ kind, label, count }: { kind: ReturnType<typeof structureKind>; label: string; count: number }) {
  const { tx } = useInspectorLanguage();
  if (kind === "tensor") {
    return <svg className="structure-glyph tensor-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} ${tx("tensor structure", "张量结构")}`}>
      <g className="tensor-planes">
        <rect x="35" y="16" width="132" height="70" />
        <rect x="47" y="25" width="132" height="70" />
        <rect x="59" y="34" width="132" height="70" />
        {[81, 103, 125, 147, 169].map((x) => <line key={`x-${x}`} x1={x} y1="34" x2={x} y2="104" />)}
        {[51, 68, 85].map((y) => <line key={`y-${y}`} x1="59" y1={y} x2="191" y2={y} />)}
      </g>
      <text x="202" y="45">{tx("heads", "头")}</text><text x="202" y="64">{tx("tokens", "词元")}</text><text x="202" y="83">{tx("features", "特征")}</text>
      <text className="glyph-title" x="35" y="112">{tx("stacked matrix", "堆叠矩阵")}</text>
    </svg>;
  }
  if (kind === "encoder" || kind === "decoder") {
    const first = kind === "encoder" ? "Q / K / V" : "Self / Cross";
    return <svg className="structure-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} ${tx("module structure", "模块结构")}`}>
      <g className="module-flow">
        <rect x="8" y="39" width="57" height="36" /><text x="36" y="61">{first}</text>
        <path d="M65 57H84" /><path d="m79 52 6 5-6 5" />
        <rect x="85" y="32" width="72" height="50" /><text x="121" y="53">{tx("Attention", "注意力")}</text><text x="121" y="69">{tx("context", "上下文")}</text>
        <path d="M157 57H176" /><path d="m171 52 6 5-6 5" />
        <rect x="177" y="39" width="74" height="36" /><text x="214" y="53">{tx("Add", "相加")}</text><text x="214" y="68">{tx("Norm", "归一化")}</text>
      </g>
      <text className="glyph-title" x="8" y="108">{count} {tx("executable operations", "个可执行操作")}</text>
    </svg>;
  }
  if (kind === "ffn") {
    return <svg className="structure-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} ${tx("feed-forward structure", "前馈结构")}`}>
      <g className="module-flow ffn-flow">
        <rect x="13" y="40" width="45" height="34" /><text x="35" y="61">D</text>
        <path d="M58 57H84" /><path d="m79 52 6 5-6 5" />
        <rect x="85" y="25" width="78" height="64" /><text x="124" y="54">4D</text><text x="124" y="71">{tx("activation", "激活")}</text>
        <path d="M163 57H189" /><path d="m184 52 6 5-6 5" />
        <rect x="190" y="40" width="45" height="34" /><text x="212" y="61">D</text>
      </g>
      <text className="glyph-title" x="13" y="108">{tx("expand · transform · project", "扩展 · 变换 · 投影")}</text>
    </svg>;
  }
  if (kind === "norm") {
    return <svg className="structure-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} ${tx("normalization structure", "归一化结构")}`}>
      <g className="module-flow">
        <rect x="13" y="40" width="58" height="34" /><text x="42" y="61">{tx("input", "输入")}</text>
        <path d="M71 57H96" /><path d="m91 52 6 5-6 5" />
        <circle cx="130" cy="57" r="29" /><text x="130" y="53">μ · σ</text><text x="130" y="68">γ · β</text>
        <path d="M159 57H184" /><path d="m179 52 6 5-6 5" />
        <rect x="185" y="40" width="62" height="34" /><text x="216" y="61">{tx("normalized", "已归一化")}</text>
      </g>
      <text className="glyph-title" x="13" y="108">{tx("feature-wise normalization", "按特征归一化")}</text>
    </svg>;
  }
  if (kind === "attention") {
    return <svg className="structure-glyph attention-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} attention structure`}>
      <g className="glyph-flow">
        <rect x="8" y="18" width="37" height="22" /><text x="26" y="32">Q</text>
        <rect x="8" y="47" width="37" height="22" /><text x="26" y="61">K</text>
        <rect x="8" y="76" width="37" height="22" /><text x="26" y="90">V</text>
        <path d="M45 29H66M45 58H66M45 87H66" /><path d="m61 24 6 5-6 5M61 53 67 58 61 63M61 82 67 87 61 92" />
        <rect className="attention-score" x="69" y="39" width="46" height="46" />
        {[81, 93, 105].map((x) => <line key={`sx-${x}`} x1={x} y1="39" x2={x} y2="85" />)}
        {[51, 63, 75].map((y) => <line key={`sy-${y}`} x1="69" y1={y} x2="115" y2={y} />)}
        <text x="92" y="94">QKᵀ</text>
        <path d="M115 62H132" /><path d="m127 57 6 5-6 5" />
        <rect x="135" y="45" width="42" height="34" /><text x="156" y="59">softmax</text><text x="156" y="71">A</text>
        <path d="M177 62H194" /><path d="m189 57 6 5-6 5" />
        <rect x="197" y="45" width="46" height="34" /><text x="220" y="59">A V</text><text x="220" y="71">context</text>
      </g>
      <text className="glyph-title" x="8" y="112">multi-head attention · {count} ops</text>
    </svg>;
  }
  if (kind === "residual") {
    return <svg className="structure-glyph residual-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} residual structure`}>
      <g className="glyph-flow">
        <rect x="10" y="45" width="38" height="28" /><text x="29" y="62">x</text>
        <path d="M48 59H74" /><path d="m68 54 6 5-6 5" />
        <rect x="77" y="43" width="59" height="32" /><text x="106" y="57">F(x)</text><text x="106" y="69">block</text>
        <path d="M136 59H166" /><path d="m160 54 6 5-6 5" />
        <circle cx="184" cy="59" r="17" /><text x="184" y="64">+</text>
        <path className="skip-path" d="M29 45V19H184V42" /><path d="m179 37 5 6 5-6" />
        <path d="M201 59H247" /><path d="m241 54 6 5-6 5" /><text x="224" y="50">y</text>
      </g>
      <text className="glyph-title" x="10" y="108">identity skip + transform</text>
    </svg>;
  }
  if (kind === "convolution") {
    return <svg className="structure-glyph convolution-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} convolution structure`}>
      <g className="glyph-flow">
        <rect className="feature-grid" x="10" y="27" width="58" height="58" />
        {[24, 38, 52].map((x) => <line key={`ix-${x}`} x1={x} y1="27" x2={x} y2="85" />)}
        {[41, 55, 69].map((y) => <line key={`iy-${y}`} x1="10" y1={y} x2="68" y2={y} />)}
        <rect className="kernel" x="24" y="41" width="28" height="28" /><text x="38" y="57">K</text>
        <path d="M68 56H88" /><path d="m82 51 6 5-6 5" />
        <rect x="92" y="39" width="61" height="35" /><text x="123" y="53">∑ wᵢxᵢ</text><text x="123" y="66">+ bias</text>
        <path d="M153 56H173" /><path d="m167 51 6 5-6 5" />
        <rect className="feature-grid output-grid" x="177" y="34" width="65" height="45" />
        {[199, 221].map((x) => <line key={`ox-${x}`} x1={x} y1="34" x2={x} y2="79" />)}
        {[49, 64].map((y) => <line key={`oy-${y}`} x1="177" y1={y} x2="242" y2={y} />)}
      </g>
      <text className="glyph-title" x="10" y="108">sliding kernel · feature map</text>
    </svg>;
  }
  if (kind === "pooling") {
    return <svg className="structure-glyph pooling-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} pooling structure`}>
      <g className="glyph-flow">
        <rect className="feature-grid" x="10" y="26" width="70" height="62" />
        {[27, 44, 61].map((x) => <line key={`px-${x}`} x1={x} y1="26" x2={x} y2="88" />)}
        {[41, 57, 73].map((y) => <line key={`py-${y}`} x1="10" y1={y} x2="80" y2={y} />)}
        <rect className="pool-window" x="27" y="41" width="34" height="32" /><text x="44" y="60">max</text>
        <path d="M80 57H109" /><path d="m103 52 6 5-6 5" />
        <circle cx="137" cy="57" r="24" /><text x="137" y="53">max</text><text x="137" y="67">mean</text>
        <path d="M161 57H188" /><path d="m182 52 6 5-6 5" />
        <rect x="192" y="39" width="52" height="36" /><text x="218" y="55">H/2 ×</text><text x="218" y="68">W/2</text>
      </g>
      <text className="glyph-title" x="10" y="108">spatial aggregation</text>
    </svg>;
  }
  if (kind === "recurrent") {
    return <svg className="structure-glyph recurrent-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} recurrent structure`}>
      <g className="glyph-flow">
        <rect x="20" y="43" width="43" height="32" /><text x="41" y="56">cell</text><text x="41" y="68">t−1</text>
        <rect x="91" y="43" width="43" height="32" /><text x="112" y="56">cell</text><text x="112" y="68">t</text>
        <rect x="162" y="43" width="43" height="32" /><text x="183" y="56">cell</text><text x="183" y="68">t+1</text>
        <path d="M63 59H91M134 59H162" /><path d="m85 54 6 5-6 5M156 54 162 59 156 64" />
        <path className="state-loop" d="M41 43V20H183V43" /><path d="m177 37 6 6 6-6" /><text x="112" y="17">hidden state hₜ</text>
        <path d="M41 75V91M112 75V91M183 75V91" /><text x="41" y="103">xₜ₋₁</text><text x="112" y="103">xₜ</text><text x="183" y="103">xₜ₊₁</text>
      </g>
      <text className="glyph-title" x="210" y="112">time</text>
    </svg>;
  }
  if (kind === "graph") {
    return <svg className="structure-glyph graph-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} graph structure`}>
      <g className="graph-links">
        <line x1="40" y1="34" x2="104" y2="57" /><line x1="40" y1="83" x2="104" y2="57" /><line x1="104" y1="57" x2="166" y2="31" /><line x1="104" y1="57" x2="166" y2="84" /><line x1="166" y1="31" x2="222" y2="57" /><line x1="166" y1="84" x2="222" y2="57" />
      </g>
      <g className="graph-nodes"><circle cx="40" cy="34" r="13" /><circle cx="40" cy="83" r="13" /><circle className="graph-center" cx="104" cy="57" r="17" /><circle cx="166" cy="31" r="13" /><circle cx="166" cy="84" r="13" /><circle cx="222" cy="57" r="13" /></g>
      <text x="104" y="61">Σ</text><text className="glyph-title" x="10" y="108">neighbor message passing</text>
    </svg>;
  }
  if (kind === "moe") {
    return <svg className="structure-glyph moe-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} mixture of experts structure`}>
      <g className="glyph-flow">
        <rect x="10" y="43" width="38" height="30" /><text x="29" y="62">x</text>
        <path d="M48 58H68M68 58V28H88M68 58V58H88M68 58V88H88" /><path d="m82 23 6 5-6 5M82 53 88 58 82 63M82 83 88 88 82 93" />
        <rect className="router" x="88" y="43" width="42" height="30" /><text x="109" y="56">router</text><text x="109" y="67">gate</text>
        <path d="M130 58H143M143 58V27H153M143 58V58H153M143 58V89H153" /><path d="m147 22 6 5-6 5M147 53 153 58 147 63M147 84 153 89 147 94" />
        <rect x="153" y="16" width="42" height="22" /><text x="174" y="30">E1</text><rect x="153" y="47" width="42" height="22" /><text x="174" y="61">E2</text><rect x="153" y="78" width="42" height="22" /><text x="174" y="92">E3</text>
        <path d="M195 27H213V58M195 58H213M195 89H213V58M213 58H244" /><path d="m238 53 6 5-6 5" /><text x="226" y="51">weighted sum</text>
      </g>
      <text className="glyph-title" x="10" y="112">sparse expert routing</text>
    </svg>;
  }
  if (kind === "diffusion") {
    return <svg className="structure-glyph diffusion-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} diffusion structure`}>
      <g className="glyph-flow">
        <rect x="8" y="43" width="42" height="30" /><text x="29" y="62">x₀</text>
        <path d="M50 58H66" /><path d="m60 53 6 5-6 5" /><circle cx="83" cy="58" r="17" /><text x="83" y="55">+ ε</text><text x="83" y="68">noise</text>
        <path d="M100 58H116" /><path d="m110 53 6 5-6 5" /><rect x="119" y="43" width="39" height="30" /><text x="138" y="56">xₜ</text><text x="138" y="68">t</text>
        <path d="M158 58H176" /><path d="m170 53 6 5-6 5" /><rect x="179" y="35" width="44" height="46" /><text x="201" y="54">εθ</text><text x="201" y="67">denoise</text>
        <path d="M223 58H247" /><path d="m241 53 6 5-6 5" /><text x="225" y="96">x̂₀</text>
      </g>
      <path className="time-axis" d="M17 19H242" /><path d="m236 14 6 5-6 5" /><text x="17" y="13">forward noise</text><text x="207" y="13">reverse t→0</text>
    </svg>;
  }
  if (kind === "state-space") {
    return <svg className="structure-glyph state-space-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} state space structure`}>
      <g className="glyph-flow">
        <rect x="10" y="45" width="40" height="28" /><text x="30" y="62">uₜ</text>
        <path d="M50 59H73" /><path d="m67 54 6 5-6 5" /><rect x="76" y="39" width="64" height="40" /><text x="108" y="54">ΔA + B</text><text x="108" y="68">state xₜ</text>
        <path d="M140 59H164" /><path d="m158 54 6 5-6 5" /><rect x="167" y="45" width="39" height="28" /><text x="186" y="62">C xₜ</text>
        <path d="M108 39V20H220V59H206" /><path d="m200 54 6 5-6 5" /><text x="145" y="17">selective scan / memory</text>
        <path d="M206 59H247" /><path d="m241 54 6 5-6 5" /><text x="225" y="84">yₜ</text>
      </g>
      <text className="glyph-title" x="10" y="108">continuous state update</text>
    </svg>;
  }
  if (kind === "embedding") {
    return <svg className="structure-glyph embedding-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} embedding structure`}>
      <g className="glyph-flow">
        <rect x="10" y="45" width="45" height="28" /><text x="32" y="62">token id</text>
        <path d="M55 59H74" /><path d="m68 54 6 5-6 5" />
        <rect className="lookup-table" x="78" y="20" width="65" height="78" />
        {[40, 60, 80].map((y) => <line key={y} x1="78" y1={y} x2="143" y2={y} />)}
        {[94, 110, 126].map((x) => <line key={x} x1={x} y1="20" x2={x} y2="98" />)}
        <text x="111" y="112">lookup table</text>
        <path d="M143 59H164" /><path d="m158 54 6 5-6 5" /><rect x="168" y="45" width="76" height="28" /><text x="206" y="62">vector eᵢ</text>
      </g>
      <text className="glyph-title" x="10" y="14">token / positional embedding</text>
    </svg>;
  }
  if (kind === "activation") {
    return <svg className="structure-glyph activation-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} activation structure`}>
      <g className="activation-plot"><path d="M28 91H238M50 104V15" /><path className="activation-curve" d="M51 90C74 90 85 88 101 78S122 50 137 42 163 31 186 28 218 25 236 24" /><path className="activation-relu" d="M51 90H130L236 24" /></g>
      <text x="219" y="101">x</text><text x="39" y="22">f(x)</text><text className="glyph-title" x="10" y="115">non-linear activation</text>
    </svg>;
  }
  if (kind === "dropout") {
    return <svg className="structure-glyph dropout-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} dropout structure`}>
      <g className="dropout-nodes">
        {[28, 53, 78].map((x, index) => <circle key={`di-${x}`} cx={x} cy="45" r="9" className={index === 1 ? "masked" : "kept"} />)}
        {[28, 53, 78].map((x, index) => <circle key={`do-${x}`} cx={x + 151} cy="45" r="9" className={index === 1 ? "masked" : "kept"} />)}
      </g>
      <path d="M87 45H112" /><path d="m106 40 6 5-6 5" /><rect className="mask-box" x="116" y="27" width="38" height="36" /><text x="135" y="42">mask</text><text x="135" y="55">p=0.1</text>
      <path d="M28 54V78H179V54" /><path d="m173 49 6 5-6 5" /><text className="glyph-title" x="10" y="108">stochastic feature masking</text>
    </svg>;
  }
  return <svg className="structure-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} ${tx("contained structure", "包含结构")}`}>
    <g className="generic-glyph">
      <rect x="12" y="20" width="236" height="78" />
      {Array.from({ length: Math.min(5, Math.max(1, count)) }, (_, index) => {
        const x = 29 + index * 43;
        return <g key={x}><circle cx={x} cy="59" r="12" />{index > 0 && <line x1={x - 31} y1="59" x2={x - 12} y2="59" />}</g>;
      })}
    </g>
    <text className="glyph-title" x="12" y="112">{count} {tx("contained operations", "个包含操作")}</text>
  </svg>;
}

export function StructureInspector({ label, viewNode, sceneNode, nodes, tensors, evidence }: {
  label: string;
  viewNode: PublicationNode;
  sceneNode: RenderNode;
  nodes: ArchitectureNodeView[];
  tensors: ArchitectureTensor[];
  evidence: Evidence[];
}) {
  const { tx } = useInspectorLanguage();
  const nodeIds = new Set(nodes.map((node) => node.node_id));
  const relevant = tensors.filter((tensor) =>
    nodeIds.has(tensor.producer_id) || tensor.consumer_ids.some((id) => nodeIds.has(id)),
  );
  const nodeOrder = new Map(nodes.map((node, index) => [node.node_id, index]));
  const orderedTensors = [...relevant].sort((left, right) => {
    const leftRank = nodeIds.has(left.producer_id) ? (nodeOrder.get(left.producer_id) ?? 0) + 1 : 0;
    const rightRank = nodeIds.has(right.producer_id) ? (nodeOrder.get(right.producer_id) ?? 0) + 1 : 0;
    return leftRank - rightRank || left.tensor_id.localeCompare(right.tensor_id);
  });
  const shapeStages = orderedTensors.filter(
    (tensor, index, all) => all.findIndex((item) => item.role === tensor.role && item.symbolic_shape === tensor.symbolic_shape) === index,
  ).slice(0, 6);
  const opTypes = [...new Set(nodes.map((node) => String(node.attributes.op_type ?? node.kind)))];
  const kind = structureKind(label, nodes);
  const primaryTensor = [...shapeStages].sort(
    (left, right) => right.semantic_axes.length - left.semantic_axes.length,
  )[0];
  return <div className="structure-inspector">
    <header className="inspector-heading"><div><h2>{label}</h2><span>{kind === "tensor" ? tx("Tensor transformation", "张量变换") : tx("Module structure", "模块结构")}</span></div><b>{nodes.length} {tx("ops", "个操作")}</b></header>
    <div className={`structure-preview preview-${kind}`}><StructureGlyph kind={kind} label={label} count={nodes.length} /></div>
    {shapeStages.length > 0 && <section className="shape-flow"><div className="section-heading">{tx("Tensor shape flow", "张量形状流")}</div><div className="shape-track">{shapeStages.map((tensor, index) => <React.Fragment key={tensor.tensor_id}>{index > 0 && <span className="shape-arrow">→</span>}<div className="shape-step"><strong>{tensor.role}</strong><code>{tensor.symbolic_shape.replaceAll(",", " × ").replace("[", "").replace("]", "")}</code></div></React.Fragment>)}</div></section>}
    {primaryTensor?.semantic_axes.length ? <div className="axis-legend">{primaryTensor.semantic_axes.map((axis, index) => <span key={axis}><b>{primaryTensor.symbolic_shape.replace(/[\[\]]/g, "").split(",")[index] ?? `d${index + 1}`}</b>{axis.replaceAll("_", " ")}</span>)}</div> : null}
    <section className="operation-summary"><div className="section-heading">{tx("Contained operations", "包含的操作")}</div><div className="operation-chips">{opTypes.slice(0, 8).map((item) => <span key={item}>{item}</span>)}</div></section>
    <div className="status-row"><span>Exact IR</span><b>{nodes.length} {tx("canonical", "个规范节点")}</b></div>
    <Field label={tx("Source symbols", "源码符号")} value={[...new Set(nodes.map((node) => node.source_symbol).filter(Boolean))].join(", ") || tx("Structural container", "结构容器")} />
    <Field label={tx("Evidence", "证据")} value={`${evidence.length} ${tx("records", "条记录")} · ${evidence[0]?.confidence ?? "exact"}`} mono />
    <div className="resolution"><div className="section-label">{tx("Resolution", "解析状态")}</div><dl><dt>{tx("Implementation", "实现")}</dt><dd>{viewNode.attributes.resolution ? tx("resolved", "已解析") : tx("exact", "精确")}</dd><dt>{tx("Semantics", "语义")}</dt><dd>{viewNode.collapsed ? tx("grouped", "已分组") : tx("expanded", "已展开")}</dd><dt>{tx("Execution", "执行")}</dt><dd>{sceneNode.canonicalNodeIds.length ? tx("authored", "源码定义") : tx("structural", "结构生成")}</dd></dl></div>
  </div>;
}

export function SourceInspector({ nodes, evidence }: { nodes: ArchitectureNodeView[]; evidence: Evidence[] }) {
  const { tx } = useInspectorLanguage();
  const sourceEvidence = useMemo(
    () => evidence.filter((record) => record.kind === "source" && record.path && record.span),
    [evidence],
  );
  const sourceKey = sourceEvidence.map((record) => record.evidence_id).join("|");
  const [activeEvidenceId, setActiveEvidenceId] = useState(sourceEvidence[0]?.evidence_id ?? "");
  const [excerpt, setExcerpt] = useState<SourceExcerpt | null>(null);
  const [sourceError, setSourceError] = useState("");
  useEffect(() => {
    setActiveEvidenceId(sourceEvidence[0]?.evidence_id ?? "");
  }, [sourceKey]);
  const activeEvidence = sourceEvidence.find((record) => record.evidence_id === activeEvidenceId) ?? sourceEvidence[0];
  useEffect(() => {
    if (!activeEvidence?.path || !activeEvidence.span) {
      setExcerpt(null);
      return;
    }
    const controller = new AbortController();
    setSourceError("");
    getStudioJson<SourceExcerpt>(`/api/source-excerpt?path=${encodeURIComponent(activeEvidence.path)}&start=${activeEvidence.span.start_line}&end=${activeEvidence.span.end_line}&context=4`, { signal: controller.signal })
      .then(setExcerpt)
      .catch((error) => { if (!controller.signal.aborted) setSourceError(String(error)); });
    return () => controller.abort();
  }, [activeEvidence?.evidence_id]);

  const paths = [...new Set(sourceEvidence.map((record) => record.path).filter((path): path is string => Boolean(path)))];
  return <div className="source-inspector">
    <header className="inspector-heading"><div><h2>{tx("Source structure", "源码结构")}</h2><span>{paths.length} {tx("files", "个文件")} · {nodes.length} {tx("operations", "个操作")}</span></div><FileCode2 size={17} /></header>
    <section className="source-outline"><div className="section-heading">{tx("Containment", "包含关系")}</div>{paths.map((path) => {
      const pathEvidence = sourceEvidence.filter((record) => record.path === path);
      const symbols = [...new Set(pathEvidence.map((record) => record.symbol).filter((symbol): symbol is string => Boolean(symbol)))];
      return <div className="source-file" key={path}><div className="source-file-row"><FileCode2 size={13} /><strong>{path}</strong></div>{symbols.map((symbol) => {
        const symbolEvidenceIds = new Set(pathEvidence.filter((record) => record.symbol === symbol).map((record) => record.evidence_id));
        const symbolNodes = nodes.filter((node) => node.evidence_ids.some((id) => symbolEvidenceIds.has(id)));
        return <div className="source-symbol" key={symbol}><div><Braces size={12} /><b>{symbol}</b></div><div className="source-node-list">{symbolNodes.map((node) => <span key={node.node_id}><CircleDot size={8} />{node.semantic_name}</span>)}</div></div>;
      })}</div>;
    })}</section>
    {sourceEvidence.length > 0 ? <>
      <section className="source-locations"><div className="section-heading">{tx("Evidence locations", "证据位置")}</div>{sourceEvidence.slice(0, 20).map((record) => <button key={record.evidence_id} className={record.evidence_id === activeEvidence?.evidence_id ? "active" : ""} onClick={() => setActiveEvidenceId(record.evidence_id)}><code>{record.path}:{record.span?.start_line}</code><span>{record.symbol}</span></button>)}</section>
      <section className="code-excerpt"><div className="code-header"><span>{excerpt?.path ?? activeEvidence?.path}</span><code>{activeEvidence?.symbol}</code></div>{sourceError ? <div className="source-error">{sourceError}</div> : excerpt ? <pre>{excerpt.lines.map((line) => <div key={line.number} className={line.number >= excerpt.highlight_start_line && line.number <= excerpt.highlight_end_line ? "highlight" : ""}><span>{line.number}</span><code>{line.text || " "}</code></div>)}</pre> : <div className="source-loading">{tx("Loading source...", "正在加载源码...")}</div>}</section>
    </> : <div className="empty-state"><FileCode2 size={20} /><span>{tx("No source evidence", "没有源码证据")}</span></div>}
  </div>;
}

function displayValue(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

function parseValue(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

export function ModelInspector({ node, nodes, transaction, proposal, writebackBlocked, deleteIntentActive, deleteImpactLoading, onPrepareParameter, onPrepareStructural, onProposeConnection, onReviewDelete, onCommit, onDiscard }: {
  node?: StudioState["architecture"]["nodes"][number];
  nodes: StudioState["architecture"]["nodes"];
  transaction: SourceTransaction | null;
  proposal: AgentProposal | null;
  writebackBlocked: boolean;
  deleteIntentActive: boolean;
  deleteImpactLoading: boolean;
  onPrepareParameter: (parameterName: string, newValue: unknown) => Promise<void>;
  onPrepareStructural: (operation: string, parameters: Record<string, unknown>) => Promise<void>;
  onProposeConnection: (sourcePortId: string, targetNodeId: string, targetPortId: string) => Promise<void>;
  onReviewDelete: (nodeId: string) => Promise<void>;
  onCommit: () => Promise<void>;
  onDiscard: () => Promise<void>;
}) {
  const { tx } = useInspectorLanguage();
  const parameters = node?.parameters ?? [];
  const parameterRequest = transaction?.request.operation === "set_parameter" ? transaction.request : null;
  const activeForNode = Boolean(transaction && transaction.request.target_node_id === node?.node_id);
  const initialName = activeForNode && parameterRequest ? parameterRequest.parameter_name : parameters[0]?.name;
  const [name, setName] = useState(initialName ?? "");
  const parameter = parameters.find((item) => item.name === name) ?? parameters[0];
  const [value, setValue] = useState(
    activeForNode && parameterRequest ? displayValue(parameterRequest.new_value) : parameter ? displayValue(parameter.value) : "",
  );
  const currentActivation = String(node?.attributes.op_type ?? "").replace("nn.", "");
  const [replacement, setReplacement] = useState(currentActivation === "ReLU" ? "GELU" : "ReLU");
  const [moduleName, setModuleName] = useState(`${String(node?.attributes.module_path ?? "layer").replace("self.", "")}_norm`);
  const [normalizedShape, setNormalizedShape] = useState("d_model");
  const targetOptions = nodes.filter((item) => item.node_id !== node?.node_id && item.input_ports.length);
  const [targetNodeId, setTargetNodeId] = useState(targetOptions[0]?.node_id ?? "");
  const targetNode = targetOptions.find((item) => item.node_id === targetNodeId) ?? targetOptions[0];
  const [sourcePortId, setSourcePortId] = useState(node?.output_ports[0]?.port_id ?? "");
  const [targetPortId, setTargetPortId] = useState(targetNode?.input_ports[0]?.port_id ?? "");
  useEffect(() => {
    const transactionName = parameterRequest?.parameter_name;
    const transactionParameter = parameterRequest?.target_node_id === node?.node_id && transactionName
      ? node?.parameters.find((item) => item.name === transactionName)
      : undefined;
    const next = transactionParameter ?? node?.parameters[0];
    setName(next?.name ?? "");
    setValue(transactionParameter ? displayValue(parameterRequest?.new_value) : next ? displayValue(next.value) : "");
    const activation = String(node?.attributes.op_type ?? "").replace("nn.", "");
    setReplacement(activation === "ReLU" ? "GELU" : "ReLU");
    setModuleName(`${String(node?.attributes.module_path ?? "layer").replace("self.", "")}_norm`);
    setSourcePortId(node?.output_ports[0]?.port_id ?? "");
  }, [node?.node_id, transaction?.transaction_id]);
  useEffect(() => {
    if (parameter && !activeForNode) setValue(displayValue(parameter.value));
  }, [parameter?.name]);
  useEffect(() => {
    setTargetPortId(targetNode?.input_ports[0]?.port_id ?? "");
  }, [targetNode?.node_id]);
  if (!node) {
    return <div className="empty-state"><Braces size={20} /><span>{tx("No canonical node selected", "未选择规范节点")}</span></div>;
  }
  const active = transaction && transaction.request.target_node_id === node.node_id;
  const affected = active ? transaction.expected_delta.changed_nodes.length : 0;
  const transactionLocked = Boolean(transaction && !["discarded", "committed", "failed"].includes(transaction.state));
  const activationSupported = ["GELU", "ReLU", "SiLU"].includes(currentActivation);
  return <>
    <div className="transaction-banner"><GitBranch size={15} /> {tx("Safe source transaction", "安全源码事务")}</div>
    {parameter ? <section className="model-operation"><div className="section-heading">{tx("Parameter", "参数")}</div><label className="model-field"><span>{tx("Parameter", "参数")}</span><select value={parameter.name} onChange={(event) => setName(event.target.value)}>{parameters.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label><Field label={tx("Current / provenance", "当前值 / 来源")} value={`${displayValue(parameter.value)} · ${parameter.origin}`} mono /><label className="model-field"><span>{tx("Target value", "目标值")}</span><input value={value} onChange={(event) => setValue(event.target.value)} /></label><button className="prepare-button" disabled={transactionLocked || value === displayValue(parameter.value)} onClick={() => void onPrepareParameter(parameter.name, parseValue(value))}><GitBranch size={14} /> {tx("Prepare parameter", "准备参数修改")}</button></section> : <div className="operation-unavailable">{tx("No exact editable parameter on this node.", "此节点没有可精确编辑的参数。")}</div>}
    <section className="model-operation"><div className="section-heading">{tx("Registered transforms", "已注册变换")}</div>{activationSupported && <><label className="model-field"><span>{tx("Activation", "激活函数")}</span><select value={replacement} onChange={(event) => setReplacement(event.target.value)}>{["GELU", "ReLU", "SiLU"].filter((item) => item !== currentActivation).map((item) => <option key={item}>{item}</option>)}</select></label><button className="prepare-button" disabled={transactionLocked} onClick={() => void onPrepareStructural("replace_activation", { replacement })}><GitBranch size={14} /> {tx("Replace activation", "替换激活函数")}</button></>}<label className="model-field"><span>{tx("LayerNorm module", "LayerNorm 模块")}</span><input value={moduleName} onChange={(event) => setModuleName(event.target.value)} /></label><label className="model-field"><span>{tx("Normalized shape", "归一化形状")}</span><input value={normalizedShape} onChange={(event) => setNormalizedShape(event.target.value)} /></label><button className="prepare-button" disabled={transactionLocked || !moduleName || !normalizedShape} onClick={() => void onPrepareStructural("insert_layer_norm", { module_name: moduleName, normalized_shape: parseValue(normalizedShape) })}><GitBranch size={14} /> {tx("Insert LayerNorm", "插入 LayerNorm")}</button></section>
    <section className="model-operation"><div className="section-heading">{tx("Proposed connection", "连接提议")}</div>{node.output_ports.length && targetNode ? <><label className="model-field"><span>{tx("Source output", "源输出")}</span><select value={sourcePortId} onChange={(event) => setSourcePortId(event.target.value)}>{node.output_ports.map((port) => <option key={port.port_id} value={port.port_id}>{port.role} · {port.port_id}</option>)}</select></label><label className="model-field"><span>{tx("Target node", "目标节点")}</span><select value={targetNode.node_id} onChange={(event) => setTargetNodeId(event.target.value)}>{targetOptions.map((item) => <option key={item.node_id} value={item.node_id}>{item.semantic_name}</option>)}</select></label><label className="model-field"><span>{tx("Target input", "目标输入")}</span><select value={targetPortId} onChange={(event) => setTargetPortId(event.target.value)}>{targetNode.input_ports.map((port) => <option key={port.port_id} value={port.port_id}>{port.role} · {port.port_id}</option>)}</select></label><button className="prepare-button" onClick={() => void onProposeConnection(sourcePortId, targetNode.node_id, targetPortId)}><Link2 size={14} /> {tx("Create handoff", "创建交接")}</button></> : <div className="operation-unavailable">{tx("Select a node with an authored output port.", "请选择带源码定义输出端口的节点。")}</div>}</section>
    <section className="model-operation danger-zone"><div className="section-heading">{tx("Canonical deletion", "规范节点删除")}</div><p>{tx("Review graph impact before creating a typed delete intent.", "创建类型化删除意图前先审查图影响。")}</p><button className="prepare-button danger-action" disabled={deleteIntentActive || deleteImpactLoading} onClick={() => void onReviewDelete(node.node_id)}><Trash2 size={14} /> {deleteIntentActive ? tx("Delete intent pending", "删除意图待处理") : deleteImpactLoading ? tx("Calculating impact", "正在计算影响") : tx("Review deletion impact", "审查删除影响")}</button></section>
    {proposal && <div className="proposal-card"><div><ShieldCheck size={15} /><strong>{tx("Agent handoff", "代理交接")}</strong><code>{proposal.reason_code}</code></div><p>{proposal.summary}</p><dl><dt>{tx("Shell", "终端")}</dt><dd>{tx("Denied", "已拒绝")}</dd><dt>{tx("Network", "网络")}</dt><dd>{tx("Denied", "已拒绝")}</dd><dt>{tx("Source write", "源码写入")}</dt><dd>{tx("Denied", "已拒绝")}</dd></dl></div>}
    <Field label={tx("Expected affected nodes / edges", "预计影响的节点 / 边")} value={active ? `${affected} / ${transaction.expected_delta.changed_edges.length}` : tx("Calculated during prepare", "在准备阶段计算")} />
    {active && <div className={`transaction-state ${transaction.state}`}>{transaction.state}</div>}
    {active && transaction.state === "review-ready" && <div className="transaction-actions"><button className="commit-button" disabled={writebackBlocked} title={writebackBlocked ? tx("Resolve draft blockers before committing", "提交前请解决草稿阻断项") : tx("Commit verified source transaction", "提交已验证的源码事务")} onClick={() => void onCommit()}><CircleDot size={14} /> {tx("Commit to source", "提交到源码")}</button><button onClick={() => void onDiscard()}><X size={14} /> {tx("Discard", "放弃")}</button></div>}
    {active && transaction.state === "failed" && <div className="transaction-actions"><span className="agent-handoff-status"><Braces size={14} /> {tx("Agent handoff is unavailable for this failed transaction", "当前失败事务不提供代理交接")}</span><button onClick={() => void onDiscard()}><X size={14} /> {tx("Discard", "放弃")}</button></div>}
  </>;
}

export function VisualInspector({ node, fidelity, pinned, onPatch, onBatch }: {
  node: RenderNode;
  fidelity?: "exact" | "opaque" | "schematic";
  pinned: boolean;
  onPatch: (operation: string, targetId: string | undefined, value: Record<string, unknown>) => Promise<void>;
  onBatch: (description: string, patches: Array<{ operation: string; targetId?: string; value: Record<string, unknown> }>) => Promise<void>;
}) {
  const { tx } = useInspectorLanguage();
  const [bounds, setBounds] = useState(node.bounds);
  useEffect(() => setBounds(node.bounds), [node.nodeId, node.bounds]);
  const update = (key: keyof Rect, value: number) => setBounds((current) => ({ ...current, [key]: value }));
  return <>
    <div className="section-label">{tx("Kernel geometry", "内核几何")}</div>
    <div className="numeric-grid">{(["x", "y", "width", "height"] as const).map((key) => <label key={key}><span>{key.toUpperCase()}</span><input type="number" min={key === "width" || key === "height" ? 1 : 0} value={Math.round(bounds[key])} onChange={(event) => update(key, Number(event.target.value))} /></label>)}</div>
    <button className="apply-visual" onClick={() => void onBatch(tx("Apply geometry", "应用几何设置"), [
      { operation: "set-position", targetId: node.nodeId, value: { x: bounds.x, y: bounds.y } },
      { operation: "set-size", targetId: node.nodeId, value: { width: bounds.width, height: bounds.height } },
    ])}>{tx("Apply geometry", "应用几何设置")}</button>
    <label className="toggle-row"><input type="checkbox" checked={pinned} onChange={() => void onPatch("set-pin", node.nodeId, { enabled: !pinned })} /><span>{tx("Pin during layout", "布局时固定")}</span></label>
    <div className="section-label">{tx("Visual provenance", "视觉来源")}</div>
    <Field label={tx("Kernel node", "内核节点")} value={node.nodeId} mono />
    <Field label={tx("Shape", "图元")} value={node.shape} />
    <Field label={tx("Render role", "渲染角色")} value={node.renderRole} />
    <Field label={tx("Template binding", "模板绑定")} value={node.templateBindingId ?? tx("Generic", "通用")} mono />
    <Field label={tx("Template fidelity", "模板保真度")} value={fidelity ?? tx("Unbound", "未绑定")} />
  </>;
}

