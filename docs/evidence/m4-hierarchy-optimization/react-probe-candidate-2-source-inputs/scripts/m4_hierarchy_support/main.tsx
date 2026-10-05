import { useCallback, useLayoutEffect, useMemo, useReducer, useRef, version } from 'react';
import { createRoot } from 'react-dom/client';
import type { Architecture, ArchitectureNode, CanvasDocument } from './core';
import { TreeNode as LegacyTreeNode } from './LegacyTree';
import { HierarchyTree } from './HierarchyTree';
import './probe.css';

type Json = Record<string, unknown>;
type Input = { source: string; type: string; isTrusted: boolean | null; nativeIsTrusted: boolean | null; target: string | null };
type Counts = { id: number; label: number; children: number; total: number };
type Fixture = { document: CanvasDocument; revision: number };
type ProbeState = { document: CanvasDocument; selected: string[]; stableStep: number; camera: number; preview: number; box: number; portDraft: number; sequence: number; action: string; input: Input | null };
type Action = { type: string; input: Input; id?: string; expanded?: boolean };
type PropsSnapshot = { architecture: Architecture; document: CanvasDocument; selected: string[]; onSelect: unknown; onExpand: unknown };

const output = document.getElementById('probe-report') as HTMLTextAreaElement;
const report: Json = {
  schemaVersion: 1,
  probe: 'actual-production-React-hierarchy-updates',
  status: 'loading',
  rounds: [],
  pendingDomHashes: 0,
  limits: [
    'Independent production React harness. This does not execute the complete Studio canvas path.',
    'Property reads measure render work in this instrumented tree. They do not measure FPS, paint, input latency, or presented frames.',
    'Only DOM nativeEvent.isTrusted records actual browser input; programmatic state variants are harness scenarios, not semantic edits.',
    'Same-ID architecture variants intentionally change display topology facts while preserving the original source bytes and digest fields. They are synthetic test inputs, not newly analyzed IR.',
    'Proxy instrumentation adds overhead. No timing is collected or converted into performance claims.',
  ],
};
const rounds = report.rounds as Json[];
let lastTreeInput: Input = { source: 'tree', type: 'unknown', isTrusted: null, nativeIsTrusted: null, target: null };
function publish() { output.value = JSON.stringify(report, null, 2); }
publish();
window.addEventListener('error', event => { report.errors = [...(report.errors as unknown[] ?? []), { message: event.message, stack: event.error?.stack ?? null }]; publish(); });
window.addEventListener('unhandledrejection', event => { report.errors = [...(report.errors as unknown[] ?? []), { rejection: String(event.reason), stack: event.reason?.stack ?? null }]; publish(); });

function freezeDeep<T>(value: T): T {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const item of Object.values(value)) freezeDeep(item);
    Object.freeze(value);
  }
  return value;
}
async function sha256(value: string) {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return [...new Uint8Array(hash)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}
function nodeCounter() {
  const counters: Counts = { id: 0, label: 0, children: 0, total: 0 };
  let enabled = false;
  return {
    reset() { counters.id = 0; counters.label = 0; counters.children = 0; counters.total = 0; enabled = true; },
    stop() { enabled = false; return { ...counters }; },
    architecture(source: Architecture): Architecture {
      return { ...source, nodes: source.nodes.map(node => new Proxy(node, {
        get(target, key, receiver) {
          if (enabled && (key === 'id' || key === 'label' || key === 'children')) { counters[key]++; counters.total++; }
          return Reflect.get(target, key, receiver);
        },
      })) };
    },
  };
}
const oldCounter = nodeCounter();
const newCounter = nodeCounter();
function input(event: React.MouseEvent, source: string): Input {
  return { source, type: event.type, isTrusted: event.isTrusted, nativeIsTrusted: event.nativeEvent.isTrusted, target: (event.target as HTMLElement).closest('button')?.getAttribute('aria-label') ?? (event.target as HTMLElement).closest('button')?.textContent ?? null };
}
function sameProps(current: PropsSnapshot, previous: PropsSnapshot | null) {
  return previous ? {
    architecture: current.architecture === previous.architecture,
    document: current.document === previous.document,
    selected: current.selected === previous.selected,
    onSelect: current.onSelect === previous.onSelect,
    onExpand: current.onExpand === previous.onExpand,
  } : null;
}
function facts(tree: HTMLDivElement, ids: string[]) {
  const items = [...tree.querySelectorAll<HTMLDivElement>('[data-tree-node-id]')];
  return {
    visibleNodeCount: items.length,
    visibleIds: items.map(item => item.dataset.treeNodeId),
    targets: ids.map(id => {
      const item = items.find(candidate => candidate.dataset.treeNodeId === id);
      const row = item?.querySelector<HTMLDivElement>(':scope > .tree-row');
      return { id, visible: !!item, depth: item?.getAttribute('data-tree-depth') ?? null, expanded: item?.getAttribute('aria-expanded') ?? null, selected: item?.getAttribute('aria-selected') ?? null, label: row?.querySelector('.tree-label > span:nth-child(2)')?.textContent ?? null, repeat: row?.querySelector('small')?.textContent ?? null, pinIcon: !!row?.querySelector(':scope > svg'), toggleLabel: row?.querySelector('.tree-toggle')?.getAttribute('aria-label') ?? null };
    }),
  };
}

function Probe({ fixture, fixtureText, sourceBindings, buildBindings }: { fixture: Fixture; fixtureText: string; sourceBindings: Json; buildBindings: Json }) {
  const initial = fixture.document;
  const root = initial.architecture.nodes.find(node => !node.parentId)!;
  const branch = initial.architecture.nodes.find(node => node.children.length > 20)!;
  const leaf = initial.architecture.nodes.find(node => node.id === branch.children[0])!;
  const secondLeaf = initial.architecture.nodes.find(node => node.id === branch.children[1])!;
  const targets = [root.id, branch.id, leaf.id, secondLeaf.id];
  const reducer = useCallback((state: ProbeState, action: Action): ProbeState => {
    const next = { ...state, sequence: state.sequence + 1, action: action.type, input: action.input };
    if (action.type === 'stable-parent') {
      const kinds = ['camera', 'preview', 'box', 'portDraft', 'camera'] as const;
      const kind = kinds[state.stableStep % kinds.length];
      return { ...next, stableStep: state.stableStep + 1, [kind]: state[kind] + 1, action: `stable-${kind}-${state.stableStep + 1}` };
    }
    if (action.type === 'selection') return { ...next, selected: [action.id ?? leaf.id] };
    if (action.type === 'document-replacement') return { ...next, document: { ...state.document } };
    if (action.type === 'alias-empty') return { ...next, document: { ...state.document, displayAliases: { ...state.document.displayAliases, [leaf.id]: '' } } };
    if (action.type === 'pin') return { ...next, document: { ...state.document, pinnedObjects: [...new Set([...state.document.pinnedObjects, leaf.id])] } };
    if (action.type === 'collapse' || action.type === 'expand' || action.type === 'tree-expand') {
      const id = action.id ?? branch.id;
      const expanded = action.type === 'tree-expand' ? !!action.expanded : action.type === 'expand';
      return { ...next, document: { ...state.document, expandedIds: expanded ? [...new Set([...state.document.expandedIds, id])] : state.document.expandedIds.filter(value => value !== id) } };
    }
    if (action.type.startsWith('architecture-')) {
      const architecture = state.document.architecture;
      const nodes = architecture.nodes.map(node => {
        if (action.type === 'architecture-label' && node.id === root.id) return { ...node, label: `${root.label} · same-ID replacement` };
        if (action.type === 'architecture-repeat' && node.id === branch.id) return { ...node, repeat: { count: 299, sharing: 'independent' as const } };
        if (action.type === 'architecture-topology' && node.id === branch.id) return { ...node, children: [...node.children].reverse() };
        return { ...node };
      });
      return { ...next, document: { ...state.document, architecture: { ...architecture, nodes } } };
    }
    throw new Error(`Unsupported harness action: ${action.type}`);
  }, [initial, root.id, root.label, branch.id, leaf.id]);
  const [state, dispatch] = useReducer(reducer, { document: initial, selected: [], stableStep: 0, camera: 0, preview: 0, box: 0, portDraft: 0, sequence: 0, action: 'initial', input: null });
  const onSelect = useCallback((id: string) => dispatch({ type: 'selection', id, input: { ...lastTreeInput } }), []);
  const onExpand = useCallback((id: string, expanded: boolean) => dispatch({ type: 'tree-expand', id, expanded, input: { ...lastTreeInput } }), []);
  oldCounter.reset(); newCounter.reset();
  const oldArchitecture = useMemo(() => oldCounter.architecture(state.document.architecture), [state.document.architecture]);
  const newArchitecture = useMemo(() => newCounter.architecture(state.document.architecture), [state.document.architecture]);
  const oldDocument = useMemo(() => ({ ...state.document, architecture: oldArchitecture }), [state.document, oldArchitecture]);
  const newDocument = useMemo(() => ({ ...state.document, architecture: newArchitecture }), [state.document, newArchitecture]);
  const oldOnSelect = (id: string) => dispatch({ type: 'selection', id, input: { ...lastTreeInput } });
  const oldOnExpand = (id: string, expanded: boolean) => dispatch({ type: 'tree-expand', id, expanded, input: { ...lastTreeInput } });
  const oldTree = useRef<HTMLDivElement>(null);
  const newTree = useRef<HTMLDivElement>(null);
  const prior = useRef<{ old: PropsSnapshot; new: PropsSnapshot } | null>(null);
  const lastSequence = useRef<number | null>(null);
  useLayoutEffect(() => {
    const oldReads = oldCounter.stop();
    const newReads = newCounter.stop();
    if (!oldTree.current || !newTree.current) throw new Error('Committed tree containers are missing');
    if (lastSequence.current === state.sequence) throw new Error('Unexpected duplicate React layout effect for one probe sequence');
    lastSequence.current = state.sequence;
    const oldDom = oldTree.current.innerHTML;
    const newDom = newTree.current.innerHTML;
    const oldProps: PropsSnapshot = { architecture: oldArchitecture, document: oldDocument, selected: state.selected, onSelect: oldOnSelect, onExpand: oldOnExpand };
    const newProps: PropsSnapshot = { architecture: newArchitecture, document: newDocument, selected: state.selected, onSelect, onExpand };
    const newStable = sameProps(newProps, prior.current?.new ?? null);
    const oldStable = sameProps(oldProps, prior.current?.old ?? null);
    const oldFacts = facts(oldTree.current, targets);
    const newFacts = facts(newTree.current, targets);
    const stableUpdate = state.action.startsWith('stable-');
    const refreshedUpdate = state.sequence > 0 && !stableUpdate;
    const round: Json = {
      sequence: state.sequence, action: state.action, input: state.input,
      parentState: { camera: state.camera, preview: state.preview, box: state.box, portDraft: state.portDraft, stableStep: state.stableStep },
      inputReferencesEqualToPrior: { old: oldStable, new: newStable },
      nodePropertyReads: { old: oldReads, new: newReads },
      dom: { exactEqual: oldDom === newDom, oldLength: oldDom.length, newLength: newDom.length, oldSha256: null, newSha256: null, firstMismatch: oldDom === newDom ? null : [...oldDom].findIndex((character, i) => character !== newDom[i]), oldFacts, newFacts },
      checks: {
        treesHaveExactlyEqualDom: oldDom === newDom,
        stableInputReferences: stableUpdate ? Object.values(newStable ?? {}).every(Boolean) && Object.keys(newStable ?? {}).length === 5 : null,
        stableUpdateSkipsNewTree: stableUpdate ? newReads.total === 0 : null,
        stableUpdateReadsOldTree: stableUpdate ? oldReads.total > 0 : null,
        replacementOrVisualStateRefreshesNewTree: refreshedUpdate ? newReads.total > 0 : null,
        sourceDigestUnchanged: state.document.architecture.sourceDigest === initial.architecture.sourceDigest,
        irDigestFieldUnchanged: state.document.architecture.irDigest === initial.architecture.irDigest,
        sourceBindingDigestUnchanged: state.document.sourceBindingDigest === initial.sourceBindingDigest,
        sourceArrayUnchangedByReference: state.document.architecture.sources === initial.architecture.sources,
        originalFixtureDeepFrozen: Object.isFrozen(fixture) && Object.isFrozen(initial.architecture.nodes) && initial.architecture.nodes.every(Object.isFrozen),
        emptyAliasRendered: state.action === 'alias-empty' ? newFacts.targets.find(item => item.id === leaf.id)?.label === '' : null,
        pinRendered: state.action === 'pin' ? newFacts.targets.find(item => item.id === leaf.id)?.pinIcon === true : null,
        collapsedChildrenHidden: state.action === 'collapse' ? !newFacts.targets.find(item => item.id === leaf.id)?.visible : null,
        expandedChildrenShown: state.action === 'expand' ? newFacts.targets.find(item => item.id === leaf.id)?.visible === true : null,
        sameIdNewLabelRendered: state.action === 'architecture-label' ? newFacts.targets.find(item => item.id === root.id)?.label === `${root.label} · same-ID replacement` : null,
        sameIdNewRepeatRendered: state.action === 'architecture-repeat' ? newFacts.targets.find(item => item.id === branch.id)?.repeat === '×299' : null,
        sameIdNewChildOrderRendered: state.action === 'architecture-topology' ? newFacts.visibleIds.indexOf(branch.children.at(-1)) < newFacts.visibleIds.indexOf(branch.children[0]) : null,
      },
    };
    rounds.push(round);
    prior.current = { old: oldProps, new: newProps };
    report.status = 'ready';
    report.fixture = { documentId: initial.id, nodeCount: initial.architecture.nodes.length, fixtureEnvelopeStorageRevision: fixture.revision, fixtureVisualRevision: initial.revision, sourceDigest: initial.architecture.sourceDigest, irDigest: initial.architecture.irDigest, sourceBindingDigest: initial.sourceBindingDigest, targetIds: targets, sourceBindings, buildBindings };
    report.pendingDomHashes = Number(report.pendingDomHashes) + 1;
    report.currentSummary = { rounds: rounds.length, stableRounds: rounds.filter(item => String(item.action).startsWith('stable-')).length, checksPassedSoFar: rounds.every(item => Object.values(item.checks as Json).every(value => value === null || value === true)), allObservedDomEqual: rounds.every(item => (item.dom as Json).exactEqual) };
    publish();
    void Promise.all([sha256(oldDom), sha256(newDom), sha256(fixtureText), sha256(JSON.stringify(fixture))]).then(([oldSha, newSha, fixtureSha, originalParsedSha]) => {
      Object.assign(round.dom as Json, { oldSha256: oldSha, newSha256: newSha });
      report.originalFixtureSha256 = fixtureSha;
      report.originalParsedFixtureSha256 = originalParsedSha;
      report.pendingDomHashes = Number(report.pendingDomHashes) - 1;
      publish();
    });
  });
  const button = (type: string, label: string) => <button key={type} aria-label={label} onClick={event => dispatch({ type, input: input(event, 'probe-control') })}>{label}</button>;
  return <>
    <h1>层级树 React 更新探针</h1>
    <p>同一份 source-bound Stress300 文档，旧正式树与新正式树并排。每次按钮输入产生一次真实 React 父更新；只统计树读取 id、label、children 的次数，并在提交后比较完整树 DOM。计数不代表 FPS 或输入延迟。</p>
    <div className="controls">
      {button('stable-parent', `下一次稳定父更新（${state.stableStep + 1}）`)}
      {button('selection', '替换选择数组')}
      {button('document-replacement', '替换文档对象')}
      {button('alias-empty', '测试空字符串别名')}
      {button('pin', '固定首个节点')}
      {button('collapse', '收起网络')}
      {button('expand', '展开网络')}
      {button('architecture-label', '同 ID 架构改标签')}
      {button('architecture-repeat', '同 ID 架构改重复数')}
      {button('architecture-topology', '同 ID 架构改子节点序')}
    </div>
    <div className="status" role="status" aria-label="探针当前序列">序列 {state.sequence} · {state.action} · React {version} · production build</div>
    <div className="panels">
      <section className="panel"><h2>旧正式树 · 全树查找与每轮 inline callbacks</h2><div ref={oldTree} className="tree" role="tree" aria-label="旧正式模型层级" onClickCapture={event => { lastTreeInput = input(event, 'old-tree'); }}>
        {oldArchitecture.nodes.filter(node => !node.parentId).map(node => <LegacyTreeNode key={node.id} node={node} architecture={oldArchitecture} document={oldDocument} selected={state.selected} onSelect={oldOnSelect} onExpand={oldOnExpand} />)}
      </div></section>
      <section className="panel"><h2>新正式树 · 索引与稳定 memo 边界</h2><div ref={newTree} className="tree" role="tree" aria-label="新正式模型层级" onClickCapture={event => { lastTreeInput = input(event, 'new-tree'); }}>
        <HierarchyTree architecture={newArchitecture} document={newDocument} selected={state.selected} onSelect={onSelect} onExpand={onExpand} />
      </div></section>
    </div>
  </>;
}

async function start() {
  const [fixtureResponse, sourceResponse, buildResponse] = await Promise.all([fetch('./fixture.json', { cache: 'no-store' }), fetch('./source-bindings.json', { cache: 'no-store' }), fetch('./build-bindings.json', { cache: 'no-store' })]);
  if (![fixtureResponse, sourceResponse, buildResponse].every(response => response.ok)) throw new Error('Probe inputs or build bindings failed to load');
  const fixtureText = await fixtureResponse.text();
  const sourceBindings = await sourceResponse.json() as Json;
  const buildBindings = await buildResponse.json() as Json;
  const fixture = freezeDeep(JSON.parse(fixtureText) as Fixture);
  const fixtureBinding = sourceBindings.fixture as Json;
  if (await sha256(fixtureText) !== fixtureBinding.sha256) throw new Error('Fixture bytes do not match preparation binding');
  report.runtime = { reactVersion: version, userAgent: navigator.userAgent, viewport: { width: window.innerWidth, height: window.innerHeight }, devicePixelRatio: window.devicePixelRatio, loadedUrl: location.href, mode: import.meta.env.MODE, production: import.meta.env.PROD, harnessUsesStrictMode: false };
  createRoot(document.getElementById('probe-root')!).render(<Probe fixture={fixture} fixtureText={fixtureText} sourceBindings={sourceBindings} buildBindings={buildBindings} />);
}
void start().catch(error => { report.status = 'failed'; report.loadError = { message: String(error), stack: error.stack ?? null }; document.getElementById('probe-root')!.textContent = `Probe failed: ${String(error)}`; publish(); });
