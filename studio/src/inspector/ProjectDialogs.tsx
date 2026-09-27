import React from "react";
import {
  AlertTriangle, Box, ChevronDown, ChevronRight, CircleDot, CornerDownLeft, FileCode2, FolderOpen,
  Link2, Play, Plus, RefreshCw, Search, Trash2, X,
} from "lucide-react";
import { visibleProjectEntrypoints } from "../tree";
import { Field } from "./InspectorPanels";
import type { CanonicalDeleteImpact, DraftEdgePolicy } from "../app/studio-types";
import type { DirectoryBrowserState, PendingProject, ProjectEntrypoint } from "../app/project-actions";
export interface DraftPortOption { port_id: string; role: string; node_label: string; draft: boolean; }
export interface ProjectDialogsProps {
  tx: (english: string, chinese: string) => string; projectDialog: boolean; setProjectDialog: (value: boolean) => void;
  condaEnvironments: Array<{ name: string; path: string; active: boolean; python: string }>; environmentLoading: boolean;
  condaEnvironment: string; setCondaEnvironment: (value: string) => void;
  setCondaEnvironments: React.Dispatch<React.SetStateAction<Array<{ name: string; path: string; active: boolean; python: string }>>>;
  projectRoot: string; setProjectRoot: (value: string) => void; projectScanning: boolean;
  setProjectError: (value: string) => void; projectError: string; openProject: () => void;
  pendingProject: PendingProject | null; setPendingProject: (value: PendingProject | null) => void; folderPicker: DirectoryBrowserState | null;
  setFolderPicker: (value: DirectoryBrowserState | null) => void; selectedFolderPath: string | null;
  setSelectedFolderPath: (value: string | null) => void; folderLoading: boolean; browseFolders: (path?: string) => void;
  projectModelExpansions: Set<string>; setProjectModelExpansions: React.Dispatch<React.SetStateAction<Set<string>>>;
  projectEntrypoint: string; setProjectEntrypoint: (value: string) => void; projectFramework: string;
  setProjectFramework: (value: string) => void; projectConfig: string; setProjectConfig: (value: string) => void;
  selectProjectEntrypoint: (candidate: ProjectEntrypoint) => void; analyzeProject: () => void;
  draftDialog: boolean; setDraftDialog: (value: boolean) => void; draftName: string; setDraftName: (value: string) => void;
  draftType: string; setDraftType: (value: string) => void; selectedCanonicalIds: string[]; createDraftNode: () => void;
  draftEdgeDialog: boolean; setDraftEdgeDialog: (value: boolean) => void; draftEdgeSource: string;
  setDraftEdgeSource: (value: string) => void; draftEdgeTarget: string; setDraftEdgeTarget: (value: string) => void;
  draftEdgePolicy: DraftEdgePolicy; setDraftEdgePolicy: (value: DraftEdgePolicy) => void;
  draftSourcePorts: DraftPortOption[]; draftTargetPorts: DraftPortOption[]; draftPortLabels: Map<string, string>;
  createDraftEdge: () => void; deleteImpact: CanonicalDeleteImpact | null;
  setDeleteImpact: (value: CanonicalDeleteImpact | null) => void; createCanonicalDeleteIntent: () => void;
}
export function ProjectDialogs(props: ProjectDialogsProps) {
  const {
    tx, projectDialog, setProjectDialog, condaEnvironments, environmentLoading, condaEnvironment,
    setCondaEnvironment, setCondaEnvironments, projectRoot, setProjectRoot, projectScanning, setProjectError,
    projectError, openProject, pendingProject, setPendingProject, folderPicker, setFolderPicker, selectedFolderPath,
    setSelectedFolderPath, folderLoading, browseFolders, projectModelExpansions, setProjectModelExpansions,
    projectEntrypoint, setProjectEntrypoint, projectFramework, setProjectFramework, projectConfig, setProjectConfig,
    selectProjectEntrypoint, analyzeProject, draftDialog, setDraftDialog, draftName, setDraftName, draftType,
    setDraftType, selectedCanonicalIds, createDraftNode, draftEdgeDialog, setDraftEdgeDialog, draftEdgeSource,
    setDraftEdgeSource, draftEdgeTarget, setDraftEdgeTarget, draftEdgePolicy, setDraftEdgePolicy, draftSourcePorts,
    draftTargetPorts, draftPortLabels, createDraftEdge, deleteImpact, setDeleteImpact, createCanonicalDeleteIntent,
  } = props;
  return (
    <>
      {projectDialog && <div className="dialog-backdrop" role="presentation" onPointerDown={(event) => { if (event.target === event.currentTarget) setProjectDialog(false); }}>
        <section className="project-dialog project-launcher" role="dialog" aria-modal="true" aria-label={tx("Open model", "打开模型")}>
          <header>
            <div className="launcher-title"><Box size={18} /><div><strong>{tx("Open model", "打开模型")}</strong><span>ArchCanvas Model Architecture Studio</span></div></div>
            <button className="icon-button" title={tx("Close", "关闭")} aria-label={tx("Close", "关闭")} onClick={() => setProjectDialog(false)}><X /></button>
          </header>

          <div className="launcher-field">
            <div className="launcher-label"><span>1</span><div><strong>{tx("Conda environment", "Conda 环境")}</strong><small>{environmentLoading ? tx("Loading", "正在加载") : `${condaEnvironments.length} ${tx("available", "个可用")}`}</small></div><button className="icon-button launcher-refresh" aria-label={tx("Reload environments", "重新加载环境")} title={tx("Reload environments", "重新加载环境")} onClick={() => setCondaEnvironments([])} disabled={environmentLoading}><RefreshCw size={14} /></button></div>
            <select aria-label={tx("Conda environment", "Conda 环境")} value={condaEnvironment} disabled={environmentLoading} onChange={(event) => { setCondaEnvironment(event.target.value); setPendingProject(null); }}>
              <option value="">{tx("Studio environment (static analysis)", "Studio 环境（静态分析）")}</option>
              {condaEnvironments.map((item) => <option key={item.path} value={item.path}>{item.active ? "● " : ""}{item.name} — {item.path}</option>)}
            </select>
          </div>

          <div className="launcher-field">
            <div className="launcher-label"><span>2</span><div><strong>{tx("Model location", "模型存放路径")}</strong><small>{tx("Parent folders are supported", "支持选择上级文件夹")}</small></div></div>
            <div className="path-scan-row"><div className="path-input"><FolderOpen size={15} /><input aria-label={tx("Model location", "模型存放路径")} value={projectRoot} onChange={(event) => { setProjectRoot(event.target.value); setPendingProject(null); setProjectError(""); }} onKeyDown={(event) => { if (event.key === "Enter") void openProject(); }} /></div><button className="folder-button icon-button" aria-label={tx("Browse folders", "浏览文件夹")} title={tx("Browse folders", "浏览文件夹")} onClick={() => void browseFolders()}><FolderOpen size={14} /></button><button className="prepare-button" disabled={!projectRoot.trim() || projectScanning} onClick={() => void openProject()}>{projectScanning ? <RefreshCw className="spin" size={14} /> : <Search size={14} />} {tx("Scan", "扫描")}</button></div>
          </div>

          {folderPicker && <div className="folder-picker" role="dialog" aria-label={tx("Choose model folder", "选择模型文件夹")}>
            <div className="folder-picker-header"><strong>{tx("Choose folder", "选择文件夹")}</strong><button className="icon-button" aria-label={tx("Close folder picker", "关闭文件夹选择器")} onClick={() => { setFolderPicker(null); setSelectedFolderPath(null); }}><X size={14} /></button></div>
            <div className="folder-breadcrumbs">{folderPicker.breadcrumbs.map((crumb) => <button key={crumb.path} onClick={() => void browseFolders(crumb.path)}>{crumb.name}</button>)}</div>
            <div className="folder-picker-toolbar"><button className="icon-button" disabled={!folderPicker.parent || folderLoading} aria-label={tx("Parent folder", "上级文件夹")} title={tx("Parent folder", "上级文件夹")} onClick={() => folderPicker.parent && void browseFolders(folderPicker.parent)}><CornerDownLeft size={14} /></button><code>{folderPicker.path}</code></div>
            <div className="folder-list">{folderPicker.directories.map((directory) => <button key={directory.path} className={selectedFolderPath === directory.path ? "selected" : ""} aria-pressed={selectedFolderPath === directory.path} onDoubleClick={() => void browseFolders(directory.path)} onClick={() => setSelectedFolderPath(directory.path)}><FolderOpen size={14} /><span>{directory.name}</span></button>)}{!folderPicker.directories.length && <span className="folder-empty">{tx("No subfolders", "没有子文件夹")}</span>}</div>
            <div className="folder-picker-actions"><button onClick={() => { setFolderPicker(null); setSelectedFolderPath(null); }}>{tx("Cancel", "取消")}</button><button className="primary-action" onClick={() => { setProjectRoot(selectedFolderPath ?? folderPicker.path); setPendingProject(null); setFolderPicker(null); setSelectedFolderPath(null); }}>{selectedFolderPath ? tx("Choose selected folder", "选择已选文件夹") : tx("Choose this folder", "选择此文件夹")}</button></div>
          </div>}

          {projectError && <div className="launcher-error" role="alert"><AlertTriangle size={14} /><span>{projectError}</span></div>}

          {pendingProject && <div className="project-options">
            <div className="launcher-label"><span>3</span><div><strong>{tx("Detected model hierarchy", "检测到的模型层级")}</strong><small>{pendingProject.discovery.entrypoints.filter((item) => item.top_level).length} {tx("top-level models", "个顶层模型")} · {pendingProject.discovery.entrypoints.filter((item) => !item.top_level).length} {tx("components", "个组件")} · {pendingProject.discovery.scanned_files} {tx("files scanned", "个文件已扫描")}</small></div></div>
            {pendingProject.discovery.entrypoints.length ? <div className="model-candidate-list" role="radiogroup" aria-label={tx("Detected models", "检测到的模型")}>
              {visibleProjectEntrypoints(pendingProject.discovery.entrypoints, projectModelExpansions).map((item) => {
                const selected = projectEntrypoint === item.entrypoint;
                const symbolName = item.entrypoint.includes(":") ? item.entrypoint.split(":").at(-1)! : item.path.split("/").at(-1)!;
                const sourceName = item.path.split("/").at(-1)!.replace(/\.py$/i, "");
                const name = item.top_level && symbolName === "Model" && sourceName.toLowerCase() !== "model" ? sourceName : symbolName;
                const categoryLabels: Record<ProjectEntrypoint["category"], string> = { model: tx("Model", "完整模型"), encoder: "Encoder", decoder: "Decoder", backbone: "Backbone", attention: "Attention", head: "Head", block: "Block", layer: "Layer", component: tx("Component", "组件") };
                const expanded = projectModelExpansions.has(item.entrypoint);
                return <div key={item.entrypoint} className={`model-candidate-row depth-${Math.min(item.depth, 8)}`} style={{ "--candidate-depth": item.depth } as React.CSSProperties}>
                  <button className="candidate-chevron" aria-label={expanded ? tx("Collapse children", "收起子级") : tx("Expand children", "展开子级")} disabled={!item.child_count} onClick={() => setProjectModelExpansions((current) => { const next = new Set(current); if (next.has(item.entrypoint)) next.delete(item.entrypoint); else next.add(item.entrypoint); return next; })}>{item.child_count ? (expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : null}</button>
                  <button className={`model-candidate ${selected ? "selected" : ""} ${item.top_level ? "top-level" : ""}`} role="radio" aria-checked={selected} onClick={() => selectProjectEntrypoint(item)}><span className="candidate-check">{selected ? <CircleDot size={15} /> : <span />}</span><span className="candidate-main"><strong>{name}</strong><span className={`category-badge category-${item.category}`}>{categoryLabels[item.category]}</span><code>{item.entrypoint}</code><small><FileCode2 size={12} />{item.path}</small></span><span className={`framework-badge framework-${item.framework}`}>{item.framework}</span></button>
                </div>;
              })}
            </div> : <div className="launcher-empty"><Search size={18} /><span>{tx("No supported models found", "未找到支持的模型")}</span></div>}
            {projectEntrypoint && <div className="launcher-options"><label><span>{tx("Framework", "框架")}</span><select value={projectFramework} onChange={(event) => setProjectFramework(event.target.value)}>{["auto", "pytorch", "keras", "jax", "onnx", "python"].map((item) => <option key={item}>{item}</option>)}</select></label><label><span>{tx("Config", "配置")}</span><select value={projectConfig} onChange={(event) => setProjectConfig(event.target.value)}><option value="">{tx("No config", "无配置")}</option>{pendingProject.discovery.configs.filter((item) => pendingProject.discovery.entrypoints.find((candidate) => candidate.entrypoint === projectEntrypoint)?.config_paths.includes(item.path)).map((item) => <option key={item.path}>{item.path}</option>)}</select></label></div>}
            <div className="launcher-actions"><button onClick={() => setProjectDialog(false)}>{tx("Cancel", "取消")}</button><button className="primary-action" disabled={!projectEntrypoint} onClick={() => void analyzeProject()}><Play size={14} /> {tx("Open model", "打开模型")}</button></div>
          </div>}
        </section>
      </div>}
      {draftDialog && <div className="dialog-backdrop" role="presentation" onPointerDown={(event) => { if (event.target === event.currentTarget) setDraftDialog(false); }}>
        <section className="project-dialog draft-dialog" role="dialog" aria-modal="true" aria-label={tx("Create draft node", "创建草稿节点")}>
          <header><div><strong>{tx("Create draft node", "创建草稿节点")}</strong><span>{projectFramework} · DraftGraphDocument</span></div><button className="icon-button" title={tx("Close", "关闭")} aria-label={tx("Close", "关闭")} onClick={() => setDraftDialog(false)}><X /></button></header>
          <label className="model-field"><span>{tx("Semantic name", "语义名称")}</span><input autoFocus value={draftName} onChange={(event) => setDraftName(event.target.value)} /></label>
          <label className="model-field"><span>{tx("Node type", "节点类型")}</span><input value={draftType} onChange={(event) => setDraftType(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void createDraftNode(); }} /></label>
          <Field label={tx("Parent anchor", "父级锚点")} value={selectedCanonicalIds[0] ?? tx("Architecture root", "架构根节点")} mono />
          <div className="launcher-actions"><button onClick={() => setDraftDialog(false)}>{tx("Cancel", "取消")}</button><button className="primary-action" disabled={!draftName.trim() || !draftType.trim()} onClick={() => void createDraftNode()}><Plus size={14} /> {tx("Create draft", "创建草稿")}</button></div>
        </section>
      </div>}
      {draftEdgeDialog && <div className="dialog-backdrop" role="presentation" onPointerDown={(event) => { if (event.target === event.currentTarget) setDraftEdgeDialog(false); }}>
        <section className="project-dialog draft-dialog" role="dialog" aria-modal="true" aria-label={tx("Create draft connection", "创建草稿连接")}>
          <header><div><strong>{tx("Create draft connection", "创建草稿连接")}</strong><span>DraftGraphDocument · {tx("source remains unchanged", "不修改源码")}</span></div><button className="icon-button" title={tx("Close", "关闭")} aria-label={tx("Close", "关闭")} onClick={() => setDraftEdgeDialog(false)}><X /></button></header>
          <label className="model-field"><span>{tx("Source output", "源输出端口")}</span><select autoFocus value={draftEdgeSource} onChange={(event) => setDraftEdgeSource(event.target.value)}>{draftSourcePorts.map((port) => <option key={port.port_id} value={port.port_id}>{draftPortLabels.get(port.port_id)} · {port.role}</option>)}</select></label>
          <label className="model-field"><span>{tx("Target input", "目标输入端口")}</span><select value={draftEdgeTarget} onChange={(event) => setDraftEdgeTarget(event.target.value)}>{draftTargetPorts.map((port) => <option key={port.port_id} value={port.port_id}>{draftPortLabels.get(port.port_id)} · {port.role}</option>)}</select></label>
          <label className="model-field"><span>{tx("Connection policy", "连接策略")}</span><select value={draftEdgePolicy} onChange={(event) => setDraftEdgePolicy(event.target.value as DraftEdgePolicy)}><option value="replace-input">{tx("Replace input", "替换输入")}</option><option value="add-residual">{tx("Add residual", "添加残差")}</option><option value="concat">{tx("Concatenate", "拼接")}</option><option value="fanout">{tx("Fan out", "扇出")}</option><option value="disconnect">{tx("Disconnect", "断开")}</option></select></label>
          <div className="launcher-actions"><button onClick={() => setDraftEdgeDialog(false)}>{tx("Cancel", "取消")}</button><button className="primary-action" disabled={!draftEdgeSource || !draftEdgeTarget} onClick={() => void createDraftEdge()}><Link2 size={14} /> {tx("Create connection", "创建连接")}</button></div>
        </section>
      </div>}
      {deleteImpact && <div className="dialog-backdrop" role="presentation" onPointerDown={(event) => { if (event.target === event.currentTarget) setDeleteImpact(null); }}>
        <section className="project-dialog impact-dialog" role="dialog" aria-modal="true" aria-label={tx("Deletion impact preview", "删除影响预览")}>
          <header><div><strong>{tx("Deletion impact preview", "删除影响预览")}</strong><span>{deleteImpact.semantic_name} · {deleteImpact.node_id}</span></div><button className="icon-button" title={tx("Close", "关闭")} aria-label={tx("Close", "关闭")} onClick={() => setDeleteImpact(null)}><X /></button></header>
          <div className="impact-warning"><AlertTriangle size={16} /><span>{tx("This preview creates an intent only. Exact IR and source stay unchanged.", "此预览只会创建意图，Exact IR 与源码保持不变。")}</span></div>
          <div className="impact-metrics"><div><strong>{deleteImpact.incoming_edge_ids.length}</strong><span>{tx("incoming edges", "条入边")}</span></div><div><strong>{deleteImpact.outgoing_edge_ids.length}</strong><span>{tx("outgoing edges", "条出边")}</span></div><div><strong>{deleteImpact.produced_tensor_ids.length}</strong><span>{tx("produced tensors", "个输出 Tensor")}</span></div><div><strong>{deleteImpact.downstream_node_ids.length}</strong><span>{tx("downstream nodes", "个下游节点")}</span></div></div>
          <section className="impact-details"><h3>{tx("Structural impact", "结构影响")}</h3><dl><dt>Fanout</dt><dd>{deleteImpact.fanout_ids.length}</dd><dt>{tx("Shared parameters", "共享参数节点")}</dt><dd>{deleteImpact.shared_parameter_node_ids.length}</dd><dt>{tx("Children", "子节点")}</dt><dd>{deleteImpact.child_node_ids.length}</dd><dt>Repeat</dt><dd>{deleteImpact.repeat_id ?? tx("None", "无")}</dd><dt>{tx("Source anchors", "源码锚点")}</dt><dd>{deleteImpact.source_evidence_ids.length}</dd><dt>{tx("Runtime evidence", "运行时证据")}</dt><dd>{deleteImpact.runtime_evidence_ids.length}</dd></dl></section>
          <section className="impact-details"><h3>{tx("Required decisions", "必须决策")}</h3><p>{deleteImpact.required_action}</p>{deleteImpact.blocking_reasons.length ? <ul>{deleteImpact.blocking_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <p>{tx("Adapter lowering proof is still required.", "仍需适配器 lowering 证明。")}</p>}</section>
          <div className="launcher-actions"><button onClick={() => setDeleteImpact(null)}>{tx("Cancel", "取消")}</button><button className="danger-action" onClick={() => void createCanonicalDeleteIntent()}><Trash2 size={14} /> {tx("Create blocked intent", "创建阻断意图")}</button></div>
        </section>
      </div>}
    </>
  );
}
