import type { CanvasDocument, Scene } from './core/types.ts';

/** Source projection is CPU work, so never perform it on the UI event loop. */
export function sourceEditingProjection(document: CanvasDocument, previousEditing?: CanvasDocument, previousView?: CanvasDocument): Promise<{ document: CanvasDocument; scene: Scene }> {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL('./sourceEditingWorker.ts', import.meta.url), { type: 'module' });
    const finish = () => { clearTimeout(deadline); worker.terminate(); };
    const deadline = setTimeout(() => { finish(); reject(new Error('源码组合模块展开超时；原视图和草稿已保留。')); }, 30_000);
    worker.onmessage = event => {
      finish();
      if (event.data.error) reject(new Error(event.data.error)); else resolve(event.data.result);
    };
    worker.onerror = event => { finish(); reject(new Error(event.message || '无法展开源码组合模块；原视图已保留。')); };
    worker.postMessage({ document, previousEditing, previousView });
  });
}
