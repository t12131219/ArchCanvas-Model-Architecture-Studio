/** Versioned M4 algorithm observations for exact historical oracle suites.
 * These exports are test-only and refer to the formal Beta.2 implementation,
 * never the failed prototype. The current runtime has no fallback or import
 * path to this archive. Current atomic folding and routing have their own
 * independent public-path/body/port/source/history/export assertions. */
export * from '../../docs/evidence/atomic-frontier-routing-v1/before-core/index.ts';
export * from '../../docs/evidence/atomic-frontier-routing-v1/before-core/orthogonalRouter.ts';
export * from '../../docs/evidence/atomic-frontier-routing-v1/before-core/movePreview.ts';
export { buildSceneRouteBaseline } from '../../docs/evidence/atomic-frontier-routing-v1/before-core/scene.ts';
import { renderSvg as historicalRenderSvg } from '../../docs/evidence/atomic-frontier-routing-v1/before-core/svg.ts';
import type { Scene as HistoricalScene } from '../../docs/evidence/atomic-frontier-routing-v1/before-core/types.ts';
/** The frozen renderer does not consume diagnostics. New diagnostic codes do
 * not change its historical geometry/metadata contract or the archived oracle. */
export function renderSvg(scene: Omit<HistoricalScene, 'diagnostics'> & { diagnostics: readonly unknown[] }, options: { interactive?: boolean; background?: boolean } = {}) {
  return historicalRenderSvg({ ...scene, diagnostics: [] }, options);
}
