export interface RoutingContractEdge {
  source_port_id?: string | null;
  target_port_id?: string | null;
  portal_ids?: readonly string[];
}

export function routingContractSignature(edge: RoutingContractEdge): string | null {
  if (!edge.source_port_id || !edge.target_port_id) return null;
  return [edge.source_port_id, ...(edge.portal_ids ?? []), edge.target_port_id].join(" > ");
}
