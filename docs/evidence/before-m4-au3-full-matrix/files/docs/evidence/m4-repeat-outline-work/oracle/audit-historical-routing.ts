import { readFileSync, writeFileSync } from 'node:fs';
import { buildScene, buildExportScene, createHistory, reduceHistory } from '../../../../studio/src/core/index.ts';
import { metrics, intrusions } from '../../m4-routing-refinement/independent/oracle.ts';
import { analyzeSvg, parseSvg } from './oracle.ts';
import { renderSvg } from '../../../../studio/src/core/index.ts';
import type { CanvasDocument, Scene } from '../../../../studio/src/core/types.ts';
const root = new URL('../../../../', import.meta.url), priorRoot = new URL('../../m4-routing-refinement/independent/', import.meta.url);
const frozen = JSON.parse(readFileSync(new URL('before/capture.json', priorRoot), 'utf8'));
const rows = [];
for (const record of frozen.records) {
  const frontier = frozen.records.find((item: any) => item.caseId === record.caseId && item.kind === 'frontier');
  const document = JSON.parse(readFileSync(new URL(frontier.inputPath, root), 'utf8')) as CanvasDocument;
  const prior = JSON.parse(readFileSync(new URL(`before/${record.key}.scene.json`, priorRoot), 'utf8')) as Scene;
  const scene = record.kind === 'detail' ? buildExportScene(document, { nodeId: record.nodeId }) : record.kind === 'move'
    ? buildScene(reduceHistory(createHistory(document), { type: 'apply', baseRevision: document.revision, operations: [{ type: 'move', ids: [record.nodeId], dx: record.dx, dy: record.dy }] }).document) : buildScene(document);
  const oldMetrics = metrics(prior), newMetrics = metrics(scene);
  const nodes = scene.nodes.filter((node, index) => JSON.stringify(node) !== JSON.stringify(prior.nodes[index])).map((node, index) => {
    const old = prior.nodes.find(item => item.id === node.id)!;
    return { id: node.id, repeat: node.repeat, expanded: node.expanded, priorPorts: old.ports, currentPorts: node.ports,
      otherFieldsEqual: JSON.stringify({ ...node, ports: [] }) === JSON.stringify({ ...old, ports: [] }) };
  });
  rows.push({ key: record.key, kind: record.kind, before: { distinctTensor: oldMetrics.distinctTensor, disjointOwners: oldMetrics.disjointOwners,
    reversals: oldMetrics.totalReversals, bends: oldMetrics.totalBends, intrusions: intrusions(prior) }, after: { distinctTensor: newMetrics.distinctTensor, disjointOwners: newMetrics.disjointOwners,
    reversals: newMetrics.totalReversals, bends: newMetrics.totalBends, intrusions: intrusions(scene) }, changedNodes: nodes,
    changedFields: ['annotations', 'legend', 'exportScope', 'hiddenEdges', 'sourceFacts'].filter(field => JSON.stringify((scene as any)[field]) !== JSON.stringify((prior as any)[field])),
    svgCards: [...parseSvg(renderSvg(scene)).cards], publicReport: analyzeSvg(scene, renderSvg(scene)), diagnostics: scene.diagnostics, edgePaths: scene.edges.map(edge => ({ id: edge.id, path: edge.path })) });
}
const rawMetricRegressions = rows.flatMap(row => ['distinctTensor', 'disjointOwners'].flatMap(group => ['crossingPairs', 'crossingPairPoints', 'overlapPairs']
  .filter(metric => (row.after as any)[group][metric] > (row.before as any)[group][metric])
  .map(metric => ({ key: row.key, group, metric, before: (row.before as any)[group][metric], after: (row.after as any)[group][metric] }))));
writeFileSync(new URL('historical-routing-metrics.json', import.meta.url), JSON.stringify({ schemaVersion: 1, scope: 'All frozen historical routing cases against current implementation, actual raw metrics without tolerance or baseline rewriting', rawMetricRegressions, records: rows }, null, 2) + '\n');
console.log(JSON.stringify({ cases: rows.length, changedNodes: rows.filter(row => row.changedNodes.length).map(row => ({ key: row.key, nodes: row.changedNodes.map(node => ({ id: node.id, otherFieldsEqual: node.otherFieldsEqual })), changedFields: row.changedFields })), rawMetricRegressions }));
