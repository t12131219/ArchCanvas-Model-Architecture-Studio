export type * from './types.ts';
export { createDocument, applyVisualBatch, createHistory, reduceHistory, reconcileDocument, RevisionConflict } from './document.ts';
export { buildScene } from './scene.ts';
export { buildExportScene, publicationPreflight } from './exportScene.ts';
export { renderSvg, svgBody, escapeXml } from './svg.ts';
export { validateArchitecture, validateDocument, ValidationError } from './validate.ts';
export { CATEGORY_STYLES, TOKENS, VISUAL_VERSION } from './tokens.ts';
export { sourceNodeFacts, instanceCalls, outputPathText, compactOutputPath, evidenceText } from './nodeFacts.ts';
