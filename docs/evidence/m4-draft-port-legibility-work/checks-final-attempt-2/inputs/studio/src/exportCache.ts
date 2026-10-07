import type { CanvasDocument } from './core/types.ts';
import type { ExportArtifact } from './api.ts';

/** A receipt alone cannot establish freshness after a renderer update. */
export function readExportCache(raw: string | null, document: CanvasDocument, currentSvg: string): ExportArtifact | null {
  try {
    const cached = JSON.parse(raw ?? 'null');
    if (cached?.schemaVersion !== 2 || cached.sceneSvg !== currentSvg) return null;
    const artifact = cached.artifact as ExportArtifact | undefined;
    if (!artifact || !['svg', 'pdf', 'png'].includes(artifact.format) || typeof artifact.url !== 'string' || typeof artifact.receiptUrl !== 'string') return null;
    const receipt = artifact.receipt;
    const scope = receipt?.exportScope as { kind?: string } | undefined;
    return receipt?.documentId === document.id && receipt.revision === document.revision &&
      receipt.sourceDigest === document.architecture.sourceDigest && receipt.irDigest === document.architecture.irDigest &&
      receipt.widthMm === document.pageSpec.widthMm && scope?.kind === 'document' &&
      (artifact.format !== 'png' || receipt.dpi === 300) ? artifact : null;
  } catch { return null; }
}

export function writeExportCache(artifact: ExportArtifact, sceneSvg: string): string {
  return JSON.stringify({ schemaVersion: 2, artifact, sceneSvg });
}
