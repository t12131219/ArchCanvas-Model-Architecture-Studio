/** Bounded barycenter sweeps for explicit hierarchical arrangement.
 * Layer assignment and saved object coordinates remain the caller's responsibility. */
export function orderedLayers(ids: readonly string[], ranks: ReadonlyMap<string, number>, links: readonly (readonly [string, string])[]): Map<number, string[]> {
  let rows = new Map<number, string[]>();
  for (const id of ids) { const rank = ranks.get(id)!; const row = rows.get(rank) ?? []; row.push(id); rows.set(rank, row); }
  if (ids.length > 128 || links.length > 384) return rows;
  const levels = [...rows.keys()].sort((a, b) => a - b);
  const positions = (layout: Map<number, string[]>) => new Map([...layout.values()].flatMap(row => row.map((id, i) => [id, (i + .5) / row.length] as const)));
  const crossings = (layout: Map<number, string[]>) => {
    const p = positions(layout); let count = 0;
    const at = (edge: readonly [string, string], rank: number) => {
      const [s, t] = edge, first = ranks.get(s)!, last = ranks.get(t)!;
      return p.get(s)! + (p.get(t)! - p.get(s)!) * (rank - first) / (last - first);
    };
    for (let i = 0; i < links.length; i++) for (const second of links.slice(i + 1)) {
      const first = links[i]; if (first.some(id => second.includes(id))) continue;
      const low = Math.max(ranks.get(first[0])!, ranks.get(second[0])!), high = Math.min(ranks.get(first[1])!, ranks.get(second[1])!);
      if (low < high && (at(first, low) - at(second, low)) * (at(first, high) - at(second, high)) < 0) count++;
    }
    return count;
  };
  let best = crossings(rows);
  for (let pass = 0; pass < 4; pass++) {
    const down = pass % 2 === 0;
    for (const level of down ? levels : levels.slice().reverse()) {
      const row = rows.get(level)!; if (row.length < 2) continue;
      const p = positions(rows), scores = new Map(row.map((id, i) => {
        const peers = links.flatMap(([s, t]) => down && t === id ? [s] : !down && s === id ? [t] : []);
        return [id, peers.length ? peers.reduce((sum, peer) => sum + p.get(peer)!, 0) / peers.length : (i + .5) / row.length] as const;
      }));
      const candidate = new Map(rows);
      candidate.set(level, row.slice().sort((a, b) => scores.get(a)! - scores.get(b)! || row.indexOf(a) - row.indexOf(b)));
      const cost = crossings(candidate);
      if (cost < best) { rows = candidate; best = cost; }
    }
  }
  return rows;
}
