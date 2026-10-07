import type { DraftCatalog, DraftFlow, DraftModule, DraftNode, DraftPort } from './authoring.ts';

export const DRAFT_WIDTH = 176;
export const DRAFT_HEIGHT = 100;
export const DRAFT_PORT_PITCH = 32;
const FIRST_SIDE_PORT_Y = 66;
const LAST_SIDE_PORT_CLEARANCE = 42;

/** Presentation dimensions come from declared ports, never an operator name. */
export function draftModuleSize(module: Pick<DraftModule, 'ports'>) {
  const sideCount = Math.max(1, ...(['in', 'out'] as const).map(direction => module.ports.filter(port => port.direction === direction).length));
  return { width: DRAFT_WIDTH, height: sideCount > 1 ? FIRST_SIDE_PORT_Y + (sideCount - 1) * DRAFT_PORT_PITCH + LAST_SIDE_PORT_CLEARANCE : DRAFT_HEIGHT };
}

export function draftNodeSize(node: Pick<DraftNode, 'kind' | 'presentation'>, catalog: DraftCatalog) {
  if (node.presentation) return { width: node.presentation.width, height: node.presentation.height };
  const module = catalog.modules.find(item => item.kind === node.kind);
  // A saved unknown node still occupies the base body while the catalog/UI
  // reports its unsupported kind. No registered port or shape is invented.
  return module ? draftModuleSize(module) : { width: DRAFT_WIDTH, height: DRAFT_HEIGHT };
}

export function draftNodeBounds(node: DraftNode, catalog: DraftCatalog) {
  return { x: node.position.x, y: node.position.y, ...draftNodeSize(node, catalog) };
}

export function draftPortSpacing(module: DraftModule, direction: DraftPort['direction'], flow: DraftFlow) {
  const count = module.ports.filter(port => port.direction === direction).length;
  return count > 1 ? flow === 'horizontal' ? DRAFT_PORT_PITCH : DRAFT_WIDTH / (count + 1) : Infinity;
}

/** The rendered circle, hit/label projection and route endpoint share this anchor. */
export function draftPortPoint(node: DraftNode, module: DraftModule, portId: string, flow: DraftFlow) {
  const port = module.ports.find(item => item.id === portId);
  if (!port) throw new Error('未知端口');
  const retained = node.presentation?.ports[portId];
  if (retained) return { x: node.position.x + retained.x, y: node.position.y + retained.y };
  const peers = module.ports.filter(item => item.direction === port.direction), index = peers.indexOf(port);
  const size = draftModuleSize(module);
  if (flow === 'vertical') return { x: node.position.x + (index + 1) * size.width / (peers.length + 1), y: node.position.y + (port.direction === 'in' ? 0 : size.height) };
  return { x: node.position.x + (port.direction === 'in' ? 0 : size.width), y: node.position.y + FIRST_SIDE_PORT_Y + index * DRAFT_PORT_PITCH };
}
