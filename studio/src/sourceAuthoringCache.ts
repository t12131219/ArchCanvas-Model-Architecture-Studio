import { parseAuthoringWorkspace, sourceAuthoringKey } from './sourceAuthoringSession.ts';
import type { AuthoringWorkspace } from './sourceAuthoringSession.ts';
import type { CanvasDocument } from './core/types.ts';
import { readWorkspaceCache, writeWorkspaceCache } from './generatedWorkspace.ts';
import { AUTHORING_WORKSPACE_CACHE } from './authoringWorkspaceCache.ts';

const PREFIX = 'archcanvas.source-authoring.v1:';
const bindingError = () => new Error('源码编辑恢复记录与当前文档、源码或 IR 不一致；原记录与当前画布均已保留。');
const canonical = (value: unknown): unknown => Array.isArray(value) ? value.map(canonical) :
  value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).filter(([, value]) => value !== undefined)
    .sort(([a], [b]) => a.localeCompare(b)).map(([key, value]) => [key, canonical(value)])) : value;

function matchesSource(workspace: AuthoringWorkspace, document: CanvasDocument) {
  const source = workspace.draft.sourceProvenance;
  return !!source && source.documentId === document.id && source.sourceDigest === document.sourceBindingDigest &&
    source.sourceDigest === document.architecture.sourceDigest && source.irDigest === document.architecture.irDigest &&
    JSON.stringify(canonical(source.architecture)) === JSON.stringify(canonical(document.architecture));
}

/** A source session belongs to one immutable document/source/IR tuple. The
 * global editor cache is only a migration candidate, never an override. */
export function createSourceAuthoringCache(read: (key: string) => Promise<unknown> = readWorkspaceCache,
  write: (key: string, value: unknown) => Promise<void> = writeWorkspaceCache,
  legacy?: Pick<Storage, 'getItem'>) {
  type Waiter = { resolve: () => void; reject: (reason: unknown) => void };
  type Queue = { running: boolean; pending?: { workspace: AuthoringWorkspace; waiters: Waiter[] } };
  const queues = new Map<string, Queue>();
  async function drain(key: string, queue: Queue) {
    queue.running = true;
    while (queue.pending) {
      const next = queue.pending; queue.pending = undefined;
      try {
        await write(key, { schemaVersion: 1, workspace: next.workspace });
        next.waiters.forEach(waiter => waiter.resolve());
      } catch (reason) { next.waiters.forEach(waiter => waiter.reject(reason)); }
    }
    queue.running = false; queues.delete(key);
  }
  function save(workspace: AuthoringWorkspace) {
    const source = workspace.draft.sourceProvenance;
    if (!source) return Promise.resolve();
    const key = PREFIX + JSON.stringify([source.documentId, source.sourceDigest, source.irDigest]);
    let queue = queues.get(key);
    if (!queue) { queue = { running: false }; queues.set(key, queue); }
    const target = queue;
    return new Promise<void>((resolve, reject) => {
      if (target.pending) { target.pending.workspace = workspace; target.pending.waiters.push({ resolve, reject }); }
      else target.pending = { workspace, waiters: [{ resolve, reject }] };
      if (!target.running) void drain(key, target);
    });
  }
  async function restore(document: CanvasDocument): Promise<AuthoringWorkspace | null> {
    let raw: { schemaVersion?: number; workspace?: unknown } | undefined, failed: unknown;
    try { raw = await read(PREFIX + sourceAuthoringKey(document)) as typeof raw; }
    catch (error) { failed = error; }
    if (raw !== undefined && raw !== null) {
      const workspace = raw.schemaVersion === 1 ? parseAuthoringWorkspace(raw.workspace) : null;
      if (!workspace || !matchesSource(workspace, document)) throw bindingError();
      return workspace;
    }
    // Preserve older original-source sessions created before per-source keys.
    // A global draft for another model simply remains in its own workspace.
    let candidate: unknown;
    try { candidate = await read(AUTHORING_WORKSPACE_CACHE); } catch { /* Legacy browser text can still migrate. */ }
    if (candidate === undefined || candidate === null) {
      try { candidate = JSON.parse((legacy ?? localStorage).getItem(AUTHORING_WORKSPACE_CACHE) ?? 'null'); }
      catch { if (failed) throw failed; return null; }
    }
    const workspace = parseAuthoringWorkspace(candidate);
    if (!workspace || !matchesSource(workspace, document)) { if (failed) throw failed; return null; }
    try { await save(workspace); }
    catch { /* Keep the readable migration copy; live editor persistence reports failures. */ }
    return workspace;
  }
  return { read: restore, write: save };
}

// Shared across edit/view mounts so pointer snapshots never accumulate full
// corpora or commit after a later snapshot for the same source generation.
const sourceAuthoringCache = createSourceAuthoringCache();
export const readSourceAuthoringWorkspace = sourceAuthoringCache.read;
export const writeSourceAuthoringWorkspace = sourceAuthoringCache.write;
