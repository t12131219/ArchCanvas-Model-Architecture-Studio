import { useState } from 'react';

const TASKS = [
  '打开 Transformer 总览，展开 Encoder 和第一层，再定位 self attention。',
  '为 Encoder 设置显示别名和填充颜色，修改一条图例及说明文字。',
  '移动一个对象，固定另一个对象；撤销并重做一次。',
  '保存画布，刷新页面重开；核对别名、样式、图例与固定位置。',
  '导出当前 SVG 或 PDF，打开文件并检查文字和连接。',
];
type Observation = { at: string; documentId: string | null; visualRevision: string | null; sourceDigest: string | null; irDigest: string | null; visibleNodes: number; expandedNodes: string[]; exportLinks: string[] };
type Checkpoint = { task: number; selfReportedComplete: boolean; elapsedMs: number; observation: Observation };
type Study = { schemaVersion: 1; protocol: 'archcanvas-m4-research-task/1'; participantCode: string; participantKind: 'researcher' | 'automation'; startedAt: string; finishedAt: string | null; outcome: 'running' | 'completed' | 'abandoned'; checkpoints: Checkpoint[]; notes: string; environment: { userAgent: string; viewport: { width: number; height: number; devicePixelRatio: number } }; limitations: string[] };
const KEY = 'archcanvas.m4-study.v1';
function observe(): Observation {
  const svg = document.querySelector('.publication-scene svg');
  let metadata: Record<string, string> = {};
  try { metadata = JSON.parse(svg?.querySelector('metadata')?.textContent ?? '{}'); } catch { /* No scene yet. */ }
  return { at: new Date().toISOString(), documentId: svg?.getAttribute('data-document-id') ?? null, visualRevision: svg?.getAttribute('data-revision') ?? null,
    sourceDigest: metadata.sourceDigest ?? null, irDigest: metadata.irDigest ?? null,
    visibleNodes: document.querySelectorAll('.publication-scene [data-canonical-id]').length,
    expandedNodes: [...document.querySelectorAll('[data-tree-node-id][aria-expanded="true"]')].map(node => node.getAttribute('data-tree-node-id')!),
    exportLinks: [...document.querySelectorAll<HTMLAnchorElement>('.export-result a')].map(link => link.href) };
}
function restore(): Study | null {
  try { const stored = JSON.parse(sessionStorage.getItem(KEY) ?? 'null') as Study | null;
    if (!stored || stored.schemaVersion !== 1 || stored.protocol !== 'archcanvas-m4-research-task/1' ||
      typeof stored.participantCode !== 'string' || !/^[A-Za-z0-9_-]{1,40}$/.test(stored.participantCode) ||
      !['researcher', 'automation'].includes(stored.participantKind) ||
      !['running', 'completed', 'abandoned'].includes(stored.outcome) ||
      typeof stored.startedAt !== 'string' || !Number.isFinite(Date.parse(stored.startedAt)) ||
      typeof stored.notes !== 'string' || !Array.isArray(stored.checkpoints) || stored.checkpoints.length > TASKS.length ||
      (stored.outcome === 'running' && stored.checkpoints.length === TASKS.length) ||
      (stored.outcome === 'completed' && stored.checkpoints.length !== TASKS.length)) return null;
    if (stored.checkpoints.some((checkpoint, index) => !checkpoint || checkpoint.task !== index + 1 ||
      checkpoint.selfReportedComplete !== true || !Number.isFinite(checkpoint.elapsedMs) || checkpoint.elapsedMs < 0 ||
      !checkpoint.observation || typeof checkpoint.observation !== 'object')) return null;
    return stored;
  } catch { return null; }
}

/** An opt-in, local study recorder. Checkpoints are self reports, never automatic acceptance. */
export function StudyPanel() {
  const enabled = new URLSearchParams(location.search).get('study') === '1';
  const [study, setStudy] = useState<Study | null>(restore);
  const [code, setCode] = useState('');
  const [kind, setKind] = useState<Study['participantKind']>('researcher');
  const [collapsed, setCollapsed] = useState(false);
  if (!enabled) return null;
  const store = (next: Study) => { sessionStorage.setItem(KEY, JSON.stringify(next)); setStudy(next); };
  function start() {
    const participantCode = code.trim();
    if (!/^[A-Za-z0-9_-]{1,40}$/.test(participantCode)) return;
    store({ schemaVersion: 1, protocol: 'archcanvas-m4-research-task/1', participantCode, participantKind: kind,
      startedAt: new Date().toISOString(), finishedAt: null, outcome: 'running', checkpoints: [], notes: '',
      environment: { userAgent: navigator.userAgent, viewport: { width: innerWidth, height: innerHeight, devicePixelRatio } },
      limitations: ['Task completion is participant self-report; reviewer must inspect saved document/export and screenshots.',
        'Automation sessions are excluded from researcher completion-rate statistics.', 'Recorded task duration includes page reloads and pauses; it is not input-to-paint latency.'] });
  }
  function checkpoint() {
    if (!study || study.outcome !== 'running') return;
    const checkpoints = [...study.checkpoints, { task: study.checkpoints.length + 1, selfReportedComplete: true,
      elapsedMs: Date.now() - Date.parse(study.startedAt), observation: observe() }];
    const finished = checkpoints.length === TASKS.length;
    store({ ...study, checkpoints, outcome: finished ? 'completed' : 'running', finishedAt: finished ? new Date().toISOString() : null });
  }
  function download() {
    if (!study) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(study, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = `m4-study-${study.participantCode}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <aside className="study-recorder" aria-label="研究任务记录">
    <style>{`.study-recorder{position:fixed;z-index:130;left:16px;bottom:42px;width:350px;padding:16px;background:#fffdf7;border:1px solid #d6c9a9;border-radius:12px;box-shadow:0 8px 32px #24334520;color:#283843;font-size:13px}.study-recorder h2{font-size:16px;margin:0 0 10px}.study-recorder p{line-height:1.55;margin:10px 0}.study-recorder label{display:block;margin:10px 0}.study-recorder input,.study-recorder select,.study-recorder textarea{width:100%;box-sizing:border-box;padding:7px;border:1px solid #c4ced4;border-radius:5px}.study-recorder button{padding:7px 10px;margin:4px 5px 0 0;border:1px solid #c4ced4;border-radius:5px;background:#fff;cursor:pointer}.study-recorder .study-json{font:10px monospace;height:110px}.study-recorder .study-actions{display:flex;flex-wrap:wrap}.study-recorder small{color:#647580}`}</style>
    <h2>M4 研究任务记录 <button aria-label="折叠研究任务记录" onClick={() => setCollapsed(value => !value)}>{collapsed ? '展开' : '收起'}</button></h2>
    {!collapsed && <>{!study ? <>
      <p>使用匿名代号。结果只保存在当前浏览器，可下载为 JSON；请另行保存画布、导出文件和审看截图。</p>
      <label>参与者代号<input aria-label="参与者代号" placeholder="R01" value={code} maxLength={40} onChange={event => setCode(event.target.value)} /></label>
      <label>参与者类型<select aria-label="参与者类型" value={kind} onChange={event => setKind(event.target.value as Study['participantKind'])}><option value="researcher">研究使用者</option><option value="automation">自动化冒烟</option></select></label>
      <button disabled={!/^[A-Za-z0-9_-]{1,40}$/.test(code.trim())} onClick={start}>开始任务计时</button>
    </> : <>
      <small>{study.participantCode} · {study.participantKind} · {study.checkpoints.length}/{TASKS.length} 步</small>
      {study.outcome === 'running' ? <><p>{TASKS[study.checkpoints.length]}</p><button onClick={checkpoint}>记录此步已完成</button><button onClick={() => store({ ...study, outcome: 'abandoned', finishedAt: new Date().toISOString() })}>结束并记录未完成</button></> : <p>{study.outcome === 'completed' ? '已记录全部步骤的自报完成结果。' : '已记录未完成结果。'} 复核画布与导出后再计入任务完成率。</p>}
      <label>卡点、错误和审看意见<textarea aria-label="研究任务卡点" value={study.notes} onChange={event => store({ ...study, notes: event.target.value.slice(0, 4000) })} /></label>
      <div className="study-actions"><button onClick={download}>下载任务记录</button><button onClick={() => { sessionStorage.removeItem(KEY); setStudy(null); }}>开始下一份记录</button></div>
      <details><summary>查看本地记录 JSON</summary><textarea aria-label="研究任务 JSON" className="study-json" readOnly value={JSON.stringify(study, null, 2)} /></details>
    </>}</>}
  </aside>;
}
