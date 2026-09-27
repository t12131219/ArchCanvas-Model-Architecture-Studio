import type { CSSProperties, KeyboardEvent, PointerEvent, ReactNode, RefObject } from "react";
import {
  Box,
  Braces,
  Download,
  Eye,
  Move,
  PanelBottom,
  PanelLeft,
  PanelRight,
  Play,
  Redo2,
  ShieldCheck,
  Undo2,
  X,
} from "lucide-react";

import type { KernelExportArtifact } from "../visual-kernel/export";

export type StudioMode = "explore" | "layout" | "model";
export type StudioLocale = "en" | "zh";
export type ShellTx = (english: string, chinese: string) => string;
export type PanelResizeEdge = "left" | "right" | "top" | "bottom";

export interface TopBarProps {
  entrypointName: string;
  revision: string;
  mode: StudioMode;
  modeLabels: Record<StudioMode, string>;
  locale: StudioLocale;
  canUndo: boolean;
  canRedo: boolean;
  writebackBlocked: boolean;
  invalidProofs: number;
  unprovenProofs: number;
  validationProfile: string;
  diagnosticCount: number;
  kernelExport: KernelExportArtifact | null;
  exportBusy: "png" | "pdf" | null;
  exportMenuRef: RefObject<HTMLDetailsElement>;
  tx: ShellTx;
  onOpenProject: () => void;
  onModeChange: (mode: StudioMode) => void;
  onLocaleChange: (locale: StudioLocale) => void;
  onUndo: () => void;
  onRedo: () => void;
  onValidationProfileChange: (profile: string) => void;
  onValidate: () => void;
  onExport: (format: "svg" | "png" | "pdf") => void;
}

export function TopBar(props: TopBarProps) {
  const {
    entrypointName, revision, mode, modeLabels, locale, canUndo, canRedo,
    writebackBlocked, invalidProofs, unprovenProofs, validationProfile,
    diagnosticCount, kernelExport, exportBusy, exportMenuRef, tx,
  } = props;
  return <header className="topbar">
    <div className="product"><Box size={17} /> ArchCanvas</div>
    <button className="project-meta" onClick={props.onOpenProject} title={tx("Open or switch project", "打开或切换项目")}>
      <strong>{entrypointName}</strong><span>{revision}</span>
    </button>
    <div className="mode-switch" aria-label={tx("Studio mode", "Studio 模式")}>
      {(["explore", "layout", "model"] as StudioMode[]).map((item) => <button
        key={item}
        className={mode === item ? "active" : ""}
        onClick={() => props.onModeChange(item)}
      >
        {item === "explore" ? <Eye size={14} /> : item === "layout" ? <Move size={14} /> : <Braces size={14} />}
        {modeLabels[item]}
      </button>)}
    </div>
    <div className="top-actions">
      <div className="language-switch" role="group" aria-label={tx("Interface language", "界面语言")}>
        <button className={locale === "en" ? "active" : ""} aria-pressed={locale === "en"} onClick={() => props.onLocaleChange("en")}>EN</button>
        <button className={locale === "zh" ? "active" : ""} aria-pressed={locale === "zh"} onClick={() => props.onLocaleChange("zh")}>中文</button>
      </div>
      <button className="icon-button" title={tx("Undo", "撤销")} aria-label={tx("Undo", "撤销")} disabled={!canUndo} onClick={props.onUndo}><Undo2 /></button>
      <button className="icon-button" title={tx("Redo", "重做")} aria-label={tx("Redo", "重做")} disabled={!canRedo} onClick={props.onRedo}><Redo2 /></button>
      <div className={`writeback-gate ${writebackBlocked ? "blocked" : "ready"}`} title={writebackBlocked ? tx("Review blockers before committing", "提交前请检查阻断项") : tx("No draft blockers", "没有草稿阻断项")}>
        <ShieldCheck size={14} />{writebackBlocked ? `${invalidProofs} ${tx("invalid", "无效")} · ${unprovenProofs} ${tx("unproven", "未证明")}` : tx("Writeback clear", "可安全回写")}
      </div>
      <select className="profile-select" aria-label={tx("Validation profile", "验证配置")} value={validationProfile} onChange={(event) => props.onValidationProfileChange(event.target.value)}>
        <option value="fast-static">{tx("Fast", "快速")}</option><option value="publication">{tx("Publication", "发布")}</option><option value="full">{tx("Full", "完整")}</option>
      </select>
      <button className="validate-button" onClick={props.onValidate}><Play size={14} /> {tx("Validate", "验证")} <span>{diagnosticCount}</span></button>
      <details className="export-menu" ref={exportMenuRef}>
        <summary className="primary-action" aria-label={tx("Export main view", "导出主视图")}><Download size={14} /> {tx("Export", "导出")}</summary>
        <div className="export-menu-popover" role="menu">
          <button type="button" role="menuitem" disabled={!kernelExport} onClick={() => props.onExport("svg")}><strong>SVG</strong><span>{tx("Main view vector", "主视图矢量图")}</span></button>
          <button type="button" role="menuitem" disabled={!kernelExport || exportBusy !== null} onClick={() => props.onExport("png")}><strong>PNG</strong><span>{exportBusy === "png" ? tx("Rendering", "正在渲染") : tx("Main view image", "主视图图片")}</span></button>
          <button type="button" role="menuitem" disabled={!kernelExport || exportBusy !== null} onClick={() => props.onExport("pdf")}><strong>PDF</strong><span>{exportBusy === "pdf" ? tx("Rendering", "正在渲染") : tx("Main view document", "主视图文档")}</span></button>
          <a role="menuitem" href="/api/publication-export"><strong>SVG</strong><span>{tx("Publication export", "出版导出")}</span></a>
        </div>
      </details>
    </div>
  </header>;
}

export function PanelResizers({ sizes, tx, onPointerDown, onPointerMove, onPointerEnd, onReset, onKeyDown }: {
  sizes: Record<PanelResizeEdge, number>;
  tx: ShellTx;
  onPointerDown: (event: PointerEvent<HTMLDivElement>, edge: PanelResizeEdge) => void;
  onPointerMove: (event: PointerEvent<HTMLDivElement>) => void;
  onPointerEnd: () => void;
  onReset: (edge: PanelResizeEdge) => void;
  onKeyDown: (event: KeyboardEvent<HTMLDivElement>, edge: PanelResizeEdge) => void;
}) {
  return <>{(["left", "right", "top", "bottom"] as PanelResizeEdge[]).map((edge) => {
    const vertical = edge === "left" || edge === "right";
    const label = {
      left: tx("Resize left sidebar", "调整左侧栏宽度"),
      right: tx("Resize right sidebar", "调整右侧栏宽度"),
      top: tx("Resize top bar", "调整顶部栏高度"),
      bottom: tx("Resize bottom panel", "调整底部面板高度"),
    }[edge];
    return <div key={edge} className={`panel-resizer resize-${edge}`} role="separator"
      aria-label={label} aria-orientation={vertical ? "vertical" : "horizontal"}
      aria-valuenow={sizes[edge]} tabIndex={0}
      title={`${label} · ${tx("Double-click to reset", "双击恢复默认")}`}
      onPointerDown={(event) => onPointerDown(event, edge)} onPointerMove={onPointerMove}
      onPointerUp={onPointerEnd} onPointerCancel={onPointerEnd}
      onDoubleClick={() => onReset(edge)} onKeyDown={(event) => onKeyDown(event, edge)} />;
  })}</>;
}

export function NavigationPanel({ children, tx }: { children: ReactNode; tx: ShellTx }) {
  return <aside className="left-panel panel"><div className="panel-title"><PanelLeft size={15} /> {tx("Model", "模型")}</div>{children}</aside>;
}

export function InspectorPanel({ mobileOpen, activeTab, labels, onTabChange, onClose, children, tx }: {
  mobileOpen: boolean;
  activeTab: string;
  labels: Record<string, string>;
  onTabChange: (tab: string) => void;
  onClose: () => void;
  children: ReactNode;
  tx: ShellTx;
}) {
  return <aside className={`right-panel panel ${mobileOpen ? "mobile-open" : ""}`}>
    <div className="panel-title"><PanelRight size={15} /> {tx("Inspector", "检查器")}<button className="icon-button mobile-only inspector-close" title={tx("Close inspector", "关闭检查器")} onClick={onClose}><X /></button></div>
    <div className="tab-strip">{Object.keys(labels).map((tab) => <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => onTabChange(tab)}>{labels[tab]}</button>)}</div>
    {children}
  </aside>;
}

export function BottomPanel({ activeTab, labels, badges, onTabChange, children }: {
  activeTab: string;
  labels: Record<string, string>;
  badges: Record<string, number | boolean | undefined>;
  onTabChange: (tab: string) => void;
  children: ReactNode;
}) {
  return <section className="bottom-panel">
    <div className="bottom-tabs"><PanelBottom size={14} />{Object.keys(labels).map((tab) => <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => onTabChange(tab)}>{labels[tab]}{badges[tab] ? <span>{typeof badges[tab] === "number" ? badges[tab] : 1}</span> : null}</button>)}</div>
    <div className="bottom-content">{children}</div>
  </section>;
}

export function shellLayoutStyle(sizes: Record<PanelResizeEdge, number>, sourceWorkspaceOpen: boolean): CSSProperties {
  return {
    "--left-panel-width": `${sizes.left}px`,
    "--right-panel-width": `${sizes.right}px`,
    "--top-panel-height": `${sizes.top}px`,
    "--bottom-panel-height": `${sourceWorkspaceOpen ? Math.max(320, sizes.bottom) : sizes.bottom}px`,
  } as CSSProperties;
}
