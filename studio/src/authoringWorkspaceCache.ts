import { parseAuthoringWorkspace } from './sourceAuthoringSession.ts';
import type { AuthoringWorkspace } from './sourceAuthoringSession.ts';
import { readWorkspaceCache, writeWorkspaceCache } from './generatedWorkspace.ts';

export const AUTHORING_WORKSPACE_CACHE = 'archcanvas.authored-workspace.v1';
export const AUTHORING_CACHE_ERROR = '浏览器未能保留草稿；请使用“保存草稿”。';
type LegacyStorage = Pick<Storage, 'getItem' | 'removeItem'>;

/** Explicit sessions take priority. A delayed browser read must never replace
 * one of them, and an unreadable database must not be overwritten by a blank. */
export async function restoreCachedAuthoringWorkspace(fallback: () => AuthoringWorkspace, initial?: AuthoringWorkspace,
  read = readWorkspaceCache, legacy?: LegacyStorage) {
  if (initial) return { workspace: initial, writable: true };
  let failed = false;
  try {
    const workspace = parseAuthoringWorkspace(await read(AUTHORING_WORKSPACE_CACHE));
    if (workspace) return { workspace, writable: true };
  } catch { failed = true; }
  try {
    const workspace = parseAuthoringWorkspace(JSON.parse((legacy ?? localStorage).getItem(AUTHORING_WORKSPACE_CACHE) ?? 'null'));
    if (workspace) return { workspace, writable: true, warning: failed ? AUTHORING_CACHE_ERROR : undefined };
  } catch { /* A damaged legacy record is never used as a source document. */ }
  return { workspace: fallback(), writable: !failed, warning: failed ? AUTHORING_CACHE_ERROR : undefined };
}

/** Keep at most one pending snapshot while an IndexedDB transaction runs.
 * This preserves the latest history and camera without queuing full source
 * corpora for every pointer move. Promises settle only after durable commit. */
export function createAuthoringWorkspaceWriter(write: (key: string, value: AuthoringWorkspace) => Promise<void> = writeWorkspaceCache, legacy?: LegacyStorage) {
  type Waiter = { resolve: () => void; reject: (reason: unknown) => void };
  let pending: { workspace: AuthoringWorkspace; waiters: Waiter[] } | undefined;
  let running = false;
  async function drain() {
    running = true;
    while (pending) {
      const next = pending; pending = undefined;
      try {
        await write(AUTHORING_WORKSPACE_CACHE, next.workspace);
        try { (legacy ?? localStorage).removeItem(AUTHORING_WORKSPACE_CACHE); }
        catch { /* A committed IndexedDB record already has precedence. */ }
        for (const waiter of next.waiters) waiter.resolve();
      } catch (reason) { for (const waiter of next.waiters) waiter.reject(reason); }
    }
    running = false;
  }
  return (workspace: AuthoringWorkspace) => new Promise<void>((resolve, reject) => {
    if (pending) { pending.workspace = workspace; pending.waiters.push({ resolve, reject }); }
    else pending = { workspace, waiters: [{ resolve, reject }] };
    if (!running) void drain();
  });
}

// Edit/view switches remount the editor. Share the queue across those mounts
// so a previous session's pending transaction cannot follow a newer one.
export const writeCachedAuthoringWorkspace = createAuthoringWorkspaceWriter();
