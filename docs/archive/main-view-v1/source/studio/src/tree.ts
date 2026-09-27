interface NavigationTreeNode {
  id: string;
  parent_id: string | null;
}

interface ProjectTreeEntrypoint {
  entrypoint: string;
  parent_entrypoint: string | null;
}

interface StudioModelState {
  project: {
    project_id: string;
    generation: number;
  };
  architecture: {
    entrypoint: string;
  };
  document: {
    source_digest: string;
  };
}

export function studioModelIdentity(state: StudioModelState | null): string {
  if (!state) return "";
  return [
    state.project.project_id,
    state.project.generation,
    state.architecture.entrypoint,
    state.document.source_digest,
  ].join("\u0000");
}

export function visibleNavigationRows<T extends NavigationTreeNode>(
  nodes: T[],
  expanded: Set<string>,
): T[] {
  const children = new Map<string | null, T[]>();
  for (const item of nodes) {
    const siblings = children.get(item.parent_id) ?? [];
    siblings.push(item);
    children.set(item.parent_id, siblings);
  }
  const rows: T[] = [];
  const visit = (parentId: string | null, visible: boolean) => {
    if (!visible) return;
    for (const item of children.get(parentId) ?? []) {
      rows.push(item);
      visit(item.id, item.parent_id === null || expanded.has(item.id));
    }
  };
  visit(null, true);
  return rows;
}

export function visibleProjectEntrypoints<T extends ProjectTreeEntrypoint>(
  items: T[],
  expanded: Set<string>,
): T[] {
  const byId = new Map(items.map((item) => [item.entrypoint, item]));
  return items.filter((item) => {
    let parent = item.parent_entrypoint;
    const visited = new Set<string>();
    while (parent) {
      if (visited.has(parent) || !expanded.has(parent)) return false;
      visited.add(parent);
      parent = byId.get(parent)?.parent_entrypoint ?? null;
    }
    return true;
  });
}
