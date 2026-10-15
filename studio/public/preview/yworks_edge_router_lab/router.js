/* Independent educational reconstruction. No yFiles implementation is used. */
(function (root) {
  'use strict';
  const EPS = 1e-6;
  const SIDE = { left: [-1, 0], right: [1, 0], top: [0, -1], bottom: [0, 1] };
  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const equal = (a, b) => dist(a, b) < EPS;
  const inside = (p, r) => p.x > r.x + EPS && p.x < r.x + r.w - EPS && p.y > r.y + EPS && p.y < r.y + r.h - EPS;
  const expand = (n, margin) => ({ x: n.x - margin, y: n.y - margin, w: n.w + margin * 2, h: n.h + margin * 2, id: n.id });
  // Liang-Barsky on the open rectangle. Boundary travel is permitted.
  function intersectsRect(a, b, r) {
    const dx = b.x - a.x, dy = b.y - a.y;
    const left=r.x+EPS,right=left+(r.w-EPS*2),top=r.y+EPS,bottom=top+(r.h-EPS*2);
    // Visibility-graph links are axis aligned. Clip just their varying axis,
    // preserving the same inset and endpoint parameters as Liang-Barsky.
    // Avoid allocating an inset object and two arrays for every obstacle/link.
    if(dx===0){
      if(a.x-left<0||right-a.x<0)return false;
      if(Math.abs(dy)<EPS)return a.y-top>=0&&bottom-a.y>=0;
      const enter=dy>0?(a.y-top)/-dy:(bottom-a.y)/dy;
      const leave=dy>0?(bottom-a.y)/dy:(a.y-top)/-dy;
      const lo=Math.max(0,enter),hi=Math.min(1,leave);
      return lo<=hi&&hi>EPS&&lo<1-EPS;
    }
    if(dy===0){
      if(a.y-top<0||bottom-a.y<0)return false;
      if(Math.abs(dx)<EPS)return a.x-left>=0&&right-a.x>=0;
      const enter=dx>0?(a.x-left)/-dx:(right-a.x)/dx;
      const leave=dx>0?(right-a.x)/dx:(a.x-left)/-dx;
      const lo=Math.max(0,enter),hi=Math.min(1,leave);
      return lo<=hi&&hi>EPS&&lo<1-EPS;
    }
    let lo = 0, hi = 1;
    const p = [-dx, dx, -dy, dy];
    const q = [a.x - left, right - a.x, a.y - top, bottom - a.y];
    for (let i = 0; i < 4; i++) {
      if (Math.abs(p[i]) < EPS) { if (q[i] < 0) return false; }
      else { const t = q[i] / p[i]; if (p[i] < 0) lo = Math.max(lo, t); else hi = Math.min(hi, t); if (lo > hi) return false; }
    }
    return lo <= hi && hi > EPS && lo < 1 - EPS;
  }
  function simplify(points) {
    const out = [];
    for (const p of points) {
      if (out.length && equal(p, out[out.length - 1])) continue;
      while (out.length > 1) {
        const a = out[out.length - 2], b = out[out.length - 1];
        const cross = (b.x - a.x) * (p.y - b.y) - (b.y - a.y) * (p.x - b.x);
        const dot = (b.x - a.x) * (p.x - b.x) + (b.y - a.y) * (p.y - b.y);
        if (Math.abs(cross) < EPS && dot >= 0) out.pop(); else break;
      }
      out.push({ x: p.x, y: p.y });
    }
    return out;
  }
  function crossing(a, b, c, d) {
    const cross = (p, q, r) => (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x);
    return cross(a, b, c) * cross(a, b, d) < -EPS && cross(c, d, a) * cross(c, d, b) < -EPS;
  }
  function wireContact(a,b,c,d){
    // Search edges can stop exactly on a wire coordinate. Strict segment
    // intersection misses these contacts, letting a path evade crossing cost
    // by putting a bend at the intersection. Shared tensors are filtered by
    // the caller, so an unrelated T contact is also a visual conflict.
    // Keep the fuzzy predicate at every scale: its cross-product tolerance
    // can admit short near-parallel segments beyond an EPS-wide envelope.
    const on=(p,u,v)=>Math.abs((v.x-u.x)*(p.y-u.y)-(v.y-u.y)*(p.x-u.x))<EPS&&
      dist(u,p)>EPS&&dist(v,p)>EPS&&dist(u,p)+dist(p,v)<dist(u,v)+EPS;
    return crossing(a,b,c,d)||on(a,c,d)||on(b,c,d)||on(c,a,b)||on(d,a,b);
  }
  // Geometry only. Callers exclude equal source wire identities and licensed
  // complete shared presentations before invoking this edge-pair helper.
  function wireContacts(first, second, epsilon = 1e-5) {
    const distance = (a, b) => Math.hypot(a.x-b.x, a.y-b.y);
    const atTerminal = (point, route) => distance(point, route[0]) <= epsilon || distance(point, route.at(-1)) <= epsilon;
    const bins = new Map(), contacts = [];
    function add(point, strict) {
      const bx=Math.floor(point.x/epsilon),by=Math.floor(point.y/epsilon);let known;
      for(let x=bx-1;x<=bx+1&&!known;x++)for(let y=by-1;y<=by+1&&!known;y++)
        known=(bins.get(x+':'+y)||[]).find(entry=>distance(entry.point,point)<=epsilon);
      if(known){known.strict ||= strict;return;}
      const entry={point,strict};contacts.push(entry);const key=bx+':'+by,bin=bins.get(key)||[];bin.push(entry);bins.set(key,bin);
    }
    for(let i=1;i<first.length;i++)for(let j=1;j<second.length;j++){
      const a=first[i-1],b=first[i],c=second[j-1],d=second[j],ux=b.x-a.x,uy=b.y-a.y,vx=d.x-c.x,vy=d.y-c.y;
      const lengthA=Math.hypot(ux,uy),lengthB=Math.hypot(vx,vy);if(lengthA<=epsilon||lengthB<=epsilon)continue;
      const determinant=ux*vy-uy*vx;
      if(Math.abs(determinant)<=epsilon*Math.max(1,lengthA,lengthB)){
        // Positive shared runs are already rejected by the overlap validator.
        // Two collinear segments can still meet at an internal single point.
        const lineDistance=Math.abs((c.x-a.x)*uy-(c.y-a.y)*ux)/lengthA;
        if(lineDistance>epsilon)continue;
        const along=p=>((p.x-a.x)*ux+(p.y-a.y)*uy)/lengthA;
        const cAlong=along(c),dAlong=along(d),low=Math.max(0,Math.min(cAlong,dAlong)),high=Math.min(lengthA,Math.max(cAlong,dAlong));
        if(high<low-epsilon||high-low>epsilon)continue;
        const position=Math.max(0,Math.min(lengthA,(low+high)/2)),point={x:a.x+ux*position/lengthA,y:a.y+uy*position/lengthA};
        if(!atTerminal(point,first)||!atTerminal(point,second))add(point,false);
        continue;
      }
      const wx=c.x-a.x,wy=c.y-a.y,t=(wx*vy-wy*vx)/determinant,u=(wx*uy-wy*ux)/determinant;
      if(t < -epsilon/lengthA||t > 1+epsilon/lengthA||u < -epsilon/lengthB||u > 1+epsilon/lengthB)continue;
      const point={x:(a.x+Math.max(0,Math.min(1,t))*ux+c.x+Math.max(0,Math.min(1,u))*vx)/2,
        y:(a.y+Math.max(0,Math.min(1,t))*uy+c.y+Math.max(0,Math.min(1,u))*vy)/2};
      // Coincident actual route terminals are separately governed by port and
      // source contracts. Internal bends count even if both segments end here.
      if(atTerminal(point,first)&&atTerminal(point,second))continue;
      add(point,t>epsilon/lengthA&&t<1-epsilon/lengthA&&u>epsilon/lengthB&&u<1-epsilon/lengthB);
    }
    return contacts.map(({point,strict})=>({point,kind:strict?'crossing':'touch'}));
  }
  function overlap(a, b, c, d) {
    if (Math.abs(a.y - b.y) < EPS && Math.abs(c.y - d.y) < EPS && Math.abs(a.y - c.y) < EPS)
      return Math.max(0, Math.min(Math.max(a.x, b.x), Math.max(c.x, d.x)) - Math.max(Math.min(a.x, b.x), Math.min(c.x, d.x)));
    if (Math.abs(a.x - b.x) < EPS && Math.abs(c.x - d.x) < EPS && Math.abs(a.x - c.x) < EPS)
      return Math.max(0, Math.min(Math.max(a.y, b.y), Math.max(c.y, d.y)) - Math.max(Math.min(a.y, b.y), Math.min(c.y, d.y)));
    return 0;
  }
  class Heap {
    constructor() { this.a = []; }
    push(item) { const a = this.a; a.push(item); let i = a.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (a[p].cost <= item.cost) break; a[i] = a[p]; i = p; } a[i] = item; }
    pop() { const a = this.a, first = a[0], last = a.pop(); if (a.length) { let i = 0; while (i * 2 + 1 < a.length) { let c = i * 2 + 1; if (c + 1 < a.length && a[c + 1].cost < a[c].cost) c++; if (a[c].cost >= last.cost) break; a[i] = a[c]; i = c; } a[i] = last; } return first; }
    get length() { return this.a.length; }
  }
  // Signed headings let the search account for the port stubs at both ends.
  const heading = (a, b) => Math.abs(a.x - b.x) < EPS ? (b.y > a.y ? 2 : 4) : (b.x > a.x ? 1 : 3);
  const reverses = (a, b) => a !== 0 && b !== 0 && Math.abs(a - b) === 2;
  function search(start, end, obstacles, priorPaths, settings, boundary, incoming = 0, outgoing = 0) {
    if (inside(start, boundary) === false || inside(end, boundary) === false || obstacles.some(r => inside(start, r) || inside(end, r))) return null;
    // A straight leg or one elbow can already attain the obstacle-free
    // lower bound, including its signed arrival and departure headings.
    // In that case a complete visibility grid cannot improve its cost.
    // Price wire contacts too; a crossing never qualifies as a free leg.
    if (equal(start, end) && !reverses(incoming, outgoing)) {
      return { points: [{ x: start.x, y: start.y }],
        cost: incoming && outgoing && incoming !== outgoing ? settings.bendCost : 0, expanded: 0 };
    }
    if (!equal(start, end)) {
      const trials = [[start, end], [start, { x: start.x, y: end.y }, end], [start, { x: end.x, y: start.y }, end]];
      let lower = Infinity, best = null;
      for (const raw of trials) {
        const points = simplify(raw);
        if (points.slice(1).some((p, i) => Math.abs(p.x - points[i].x) > EPS && Math.abs(p.y - points[i].y) > EPS)) continue;
        const first = heading(points[0], points[1]), last = heading(points.at(-2), points.at(-1));
        if (reverses(incoming, first) || reverses(last, outgoing)) continue;
        const turns = Math.max(0, points.length - 2) + (incoming && incoming !== first ? 1 : 0) + (outgoing && outgoing !== last ? 1 : 0);
        const free = Math.abs(start.x - end.x) + Math.abs(start.y - end.y) + turns * settings.bendCost;
        lower = Math.min(lower, free);
        if (points.slice(1).some((p, i) => obstacles.some(r => intersectsRect(points[i], p, r)))) continue;
        const cost = routeCost(points, priorPaths, settings) + (turns - Math.max(0, points.length - 2)) * settings.bendCost;
        if (Number.isFinite(cost) && (!best || cost < best.cost)) best = { points, cost, expanded: 0 };
      }
      if (best && best.cost <= lower + EPS) return best;
    }
    let xs = [start.x, end.x, boundary.x, boundary.x + boundary.w], ys = [start.y, end.y, boundary.y, boundary.y + boundary.h];
    for (const r of obstacles) { xs.push(r.x, r.x + r.w); ys.push(r.y, r.y + r.h); }
    // Give overlapping edges a parallel lane, rather than pricing a conflict
    // on a graph that contains only the same obstacle-boundary coordinates.
    if (settings.edgeSpacing > 0) {
      const spacing = settings.edgeSpacing;
      const left = Math.min(start.x, end.x) - spacing * 6, right = Math.max(start.x, end.x) + spacing * 6;
      const top = Math.min(start.y, end.y) - spacing * 6, bottom = Math.max(start.y, end.y) + spacing * 6;
      for (const path of priorPaths) for (let i = 1; i < path.length; i++) {
        const a = path[i - 1], b = path[i];
        const alongVerticalWall=obstacles.some(r=>Math.abs(a.x-r.x)<EPS||Math.abs(a.x-r.x-r.w)<EPS);
        const alongHorizontalWall=obstacles.some(r=>Math.abs(a.y-r.y)<EPS||Math.abs(a.y-r.y-r.h)<EPS);
        // A container detour can leave the endpoint bounding box. Retain a
        // parallel lane beside an occupied wall corridor even there, or a
        // second wire is forced onto the same outer border with no alternative
        // coordinate in the visibility graph.
        if (Math.abs(a.x - b.x) < EPS && (alongVerticalWall || a.x >= left && a.x <= right && Math.max(a.y, b.y) >= top && Math.min(a.y, b.y) <= bottom)){
          xs.push(a.x - spacing, a.x + spacing);
          for(const p of [a,b])if(p.y>=top&&p.y<=bottom)ys.push(p.y-spacing,p.y+spacing);
        }
        if (Math.abs(a.y - b.y) < EPS && (alongHorizontalWall || a.y >= top && a.y <= bottom && Math.max(a.x, b.x) >= left && Math.min(a.x, b.x) <= right)){
          ys.push(a.y - spacing, a.y + spacing);
          for(const p of [a,b])if(p.x>=left&&p.x<=right)xs.push(p.x-spacing,p.x+spacing);
        }
      }
    }
    // Grid controls travel lanes, while short port stubs stay exact.
    if (settings.grid) {
      const step = settings.grid;
      for (let x = boundary.x + step; x < boundary.x + boundary.w; x += step) xs.push(x);
      for (let y = boundary.y + step; y < boundary.y + boundary.h; y += step) ys.push(y);
    }
    xs = [...new Set(xs.filter(x => x >= boundary.x && x <= boundary.x + boundary.w))].sort((a, b) => a - b);
    ys = [...new Set(ys.filter(y => y >= boundary.y && y <= boundary.y + boundary.h))].sort((a, b) => a - b);
    // A narrow corridor can fit a legal lane between its two occupied sides
    // even when the nominal spacing would land inside either wall. Include
    // its center instead of concluding that every available lane is taken.
    if(settings.edgeSpacing>0){const centers=(values,axis,size)=>{const faces=[...new Set(obstacles.flatMap(r=>[r[axis],r[axis]+r[size]]))].sort((a,b)=>a-b);
        return [...new Set([...values,...faces.slice(1).flatMap((v,i)=>v-faces[i]>.1&&v-faces[i]<settings.edgeSpacing?[(v+faces[i])/2]:[])])].sort((a,b)=>a-b);};
      xs=centers(xs,'x','w');ys=centers(ys,'y','h');
    }
    if(settings.maxSearchVertices&&xs.length*ys.length>settings.maxSearchVertices)return null;
    // A visibility link is horizontal or vertical. Filter by its fixed axis
    // first, then retain the original exact inside/intersection predicates.
    // This only removes rectangles that cannot possibly block that row/column.
    const horizontalObstacles = ys.map(y=>obstacles.filter(r=>y>=r.y && y<=r.y+r.h));
    const verticalObstacles = xs.map(x=>obstacles.filter(r=>x>=r.x && x<=r.x+r.w));
    const pts = [], ids = new Map(), neighbors = [];
    for (let yi = 0; yi < ys.length; yi++) for (let xi = 0; xi < xs.length; xi++) {
      const p = { x: xs[xi], y: ys[yi] };
      if (!horizontalObstacles[yi].some(r => inside(p, r))) { ids.set(xi + ':' + yi, pts.length); pts.push(p); neighbors.push([]); }
    }
    function link(u, v, localObstacles) {
      if (u === undefined || v === undefined) return;
      if (!localObstacles.some(r => intersectsRect(pts[u], pts[v], r))) { neighbors[u].push(v); neighbors[v].push(u); }
    }
    for (let y = 0; y < ys.length; y++) { let last; for (let x = 0; x < xs.length; x++) { const id = ids.get(x + ':' + y); if (id !== undefined) { if (last !== undefined) link(last, id, horizontalObstacles[y]); last = id; } } }
    for (let x = 0; x < xs.length; x++) { let last; for (let y = 0; y < ys.length; y++) { const id = ids.get(x + ':' + y); if (id !== undefined) { if (last !== undefined) link(last, id, verticalObstacles[x]); last = id; } } }
    const s = ids.get(xs.indexOf(start.x) + ':' + ys.indexOf(start.y)), t = ids.get(xs.indexOf(end.x) + ':' + ys.indexOf(end.y));
    if (s === undefined || t === undefined) return null;
    const startKey = s * 5 + incoming;
    // Manhattan distance is an admissible lower bound: obstacles, bends,
    // crossings and overlaps only add nonnegative cost. Keep travelled cost
    // separately so stale-entry checks and the optimal-route bound remain exact.
    const remaining=p=>Math.abs(p.x-end.x)+Math.abs(p.y-end.y);
    const costs = new Map([[startKey, 0]]), parent = new Map(), heap = new Heap(); heap.push({ key: startKey, distance:0, cost:remaining(start) });
    // Each geometric link is visited with several arrival headings. Its wire
    // contacts are independent of that heading, so price them once per search.
    const linkCosts = new Map();
    function linkCost(u, v) {
      const key = Math.min(u, v) * pts.length + Math.max(u, v);
      if (linkCosts.has(key)) return linkCosts.get(key);
      const a = pts[u], b = pts[v]; let penalty = 0, blocked = false;
      for (const path of priorPaths) for (let i = 1; i < path.length; i++) {
        if (wireContact(a, b, path[i - 1], path[i])) penalty += settings.crossingCost;
        const shared = overlap(a, b, path[i - 1], path[i]);
        const commonTerminal = shared > EPS && (settings.terminalStems || []).some(stem => {
          const atPort = i === 1 && equal(stem.port, path[0]) ||
            i === path.length - 1 && equal(stem.port, path[path.length - 1]);
          const horizontal = Math.abs(stem.port.y - stem.outer.y) < EPS;
          return path.wire===undefined && atPort && (horizontal ? Math.abs(a.y-stem.port.y)<EPS && Math.abs(b.y-stem.port.y)<EPS :
            Math.abs(a.x-stem.port.x)<EPS && Math.abs(b.x-stem.port.x)<EPS);
        });
        if (settings.edgeSpacing > 0 && shared > EPS && !commonTerminal) blocked = true;
        penalty += shared * settings.overlapCost;
      }
      const value = blocked ? Infinity : penalty;
      linkCosts.set(key, value); return value;
    }
    let finalKey = null, finalCost = Infinity, expanded = 0;
    while (heap.length) {
      const current = heap.pop(), base = costs.get(current.key);
      if (current.distance > base + EPS) continue;
      if (current.cost >= finalCost - EPS) break;
      const u = Math.floor(current.key / 5), direction = current.key % 5; expanded++;
      if (u === t && !reverses(direction, outgoing)) {
        const cost = base + (direction && outgoing && direction !== outgoing ? settings.bendCost : 0);
        if (cost < finalCost) { finalKey = current.key; finalCost = cost; }
      }
      for (const v of neighbors[u]) {
        const a = pts[u], b = pts[v], nextDirection = heading(a, b);
        if (reverses(direction, nextDirection)) continue;
        const wirePenalty = linkCost(u, v);
        if (!Number.isFinite(wirePenalty)) continue;
        const penalty = wirePenalty + ((direction && direction !== nextDirection) ? settings.bendCost : 0);
        const key = v * 5 + nextDirection, cost = base + dist(a, b) + penalty;
        if (cost < (costs.get(key) ?? Infinity) - EPS) { costs.set(key, cost); parent.set(key, current.key); heap.push({ key, distance:cost, cost:cost+remaining(b) }); }
      }
    }
    if (finalKey === null) return null;
    const result = []; for (let k = finalKey; k !== undefined; k = parent.get(k)) result.push(pts[Math.floor(k / 5)]);
    return { points: simplify(result.reverse()), cost: finalCost, expanded };
  }
  function port(node, side, fraction = .5) {
    fraction = Math.max(0, Math.min(1, fraction));
    return { x: side === 'left' ? node.x : side === 'right' ? node.x + node.w : node.x + node.w * fraction,
      y: side === 'top' ? node.y : side === 'bottom' ? node.y + node.h : node.y + node.h * fraction, side, fraction };
  }
  function candidateSides(node, other, rule = 'any', fixed) {
    if (fixed) return [fixed.side];
    const dx = other.x + other.w / 2 - node.x - node.w / 2, dy = other.y + other.h / 2 - node.y - node.h / 2;
    if (rule === 'lr') return dx >= 0 ? ['right', 'left'] : ['left', 'right'];
    if (rule === 'tb') return dy >= 0 ? ['bottom', 'top'] : ['top', 'bottom'];
    const h = dx >= 0 ? ['right', 'left'] : ['left', 'right'], v = dy >= 0 ? ['bottom', 'top'] : ['top', 'bottom'];
    return Math.abs(dx) >= Math.abs(dy) ? [h[0], v[0], v[1], h[1]] : [v[0], h[0], h[1], v[1]];
  }
  function routeCost(points,priorPaths,settings){
    const ps=simplify(points);let cost=Math.max(0,ps.length-2)*settings.bendCost;
    for(let i=1;i<ps.length;i++){
      cost+=dist(ps[i-1],ps[i]);
      for(const path of priorPaths)for(let j=1;j<path.length;j++){
        if(wireContact(ps[i-1],ps[i],path[j-1],path[j]))cost+=settings.crossingCost;
        const shared=overlap(ps[i-1],ps[i],path[j-1],path[j]);
        if(shared>EPS&&settings.edgeSpacing>0&&!(path.wire===undefined&&
          [ps[0],ps.at(-1)].some(p=>equal(p,path[0])||equal(p,path.at(-1)))))return Infinity;
        cost+=shared*settings.overlapCost;
      }
    }
    return cost;
  }
  function routeEdge(edge, nodes, priorPaths = [], options = {}) {
    const settings = { margin: 14, stub: 26, bendCost: 36, crossingCost: 0, overlapCost: 2, edgeSpacing: 0, grid: 0, sides: 'any', preserve: false, ...options };
    const s = nodes.find(n => n.id === edge.source), t = nodes.find(n => n.id === edge.target);
    if (!s || !t) return { ok: false, reason: 'missing endpoint node' };
    // Expanded containers are traversable only at their registered gates. The
    // semantic constraint layer supplies the corresponding wall segments;
    // treating the whole frame as a solid rectangle here would make a legal
    // external-to-nested route impossible (and leaves the old diagonal SVG
    // corridor in place). Unrelated expanded frames remain obstacles.
    const gateFrames = new Set((edge.contract?.gates||[]).map(g=>g.frame));
    const solid = nodes.filter(n => n.routingObstacle !== false && !(n.expanded && gateFrames.has(n.id)));
    const obstacles = [...solid.map(n => expand(n, settings.margin)),...(options.extraObstacles||[])], boundary = { x: 1, y: 1, w: options.width ? options.width - 2 : 1098, h: options.height ? options.height - 2 : 718 };
    const candidates=(node,other,fixed,fraction)=>candidateSides(node,other,settings.sides,fixed).map(side=>fixed||{side,fraction:fraction??.5});
    const portsS=options.sourceCandidates||candidates(s,t,edge.fixedSource,options.sourceFraction),portsT=options.targetCandidates||candidates(t,s,edge.fixedTarget,options.targetFraction);
    let best = null;
    // Fixed interior gate legs recur across physical endpoint candidates.
    // Cache exact solves (including failure) within this route only. An
    // unmarked legacy peer can license a terminal stem, so include stems
    // for those callers; source-tagged peers never use that exemption.
    const legCache = new Map(), taggedPeers = priorPaths.every(path => path.wire !== undefined);
    const solveLeg = (start, end, obstacles, incoming, outgoing) => {
      const key = JSON.stringify([start.x, start.y, end.x, end.y, incoming, outgoing,
        obstacles.map(r => [r.x, r.y, r.w, r.h]), taggedPeers ? null : settings.terminalStems]);
      if (legCache.has(key)) return legCache.get(key);
      const result = search(start, end, obstacles, priorPaths, settings, boundary, incoming, outgoing);
      if (legCache.size < 256) legCache.set(key, result);
      return result;
    };
    const pairs=[];
    // Try exact straight/elbow/balanced paths before adding terminal stubs. In
    // short gaps two fixed stubs can pass each other and invent a tiny detour.
    for(const fs of portsS)for(const ft of portsT){
      const anchored = (n, side, fixed, fraction) => {
        const p = port(n, side, fraction);
        return fixed?.offset ? { ...p, x: n.x + fixed.offset.x, y: n.y + fixed.offset.y } : p;
      };
      const sp=anchored(s,fs.side,fs,fs.fraction),tp=anchored(t,ft.side,ft,ft.fraction);
      const extra=options.obstaclesForPorts?options.obstaclesForPorts(fs,ft):options.extraObstacles||[];
      const approach=(a,b,f)=>((b.x-a.x)*SIDE[f.side][0]+(b.y-a.y)*SIDE[f.side][1])*(f.inward?-1:1)>EPS;
      const straight=(Math.abs(sp.x-tp.x)<EPS||Math.abs(sp.y-tp.y)<EPS)&&approach(sp,tp,fs)&&approach(tp,sp,ft);
      const elbow=[{x:sp.x,y:tp.y},{x:tp.x,y:sp.y}].some(p=>approach(sp,p,fs)&&approach(tp,p,ft));
      const pair={fs,ft,sp,tp,extra,lower:Math.abs(sp.x-tp.x)+Math.abs(sp.y-tp.y)+(straight?0:elbow?1:2)*settings.bendCost};pairs.push(pair);
    }
    const acceptable=(ps,pair)=>{
      const {sp,tp,fs,ft,extra}=pair;ps=simplify(ps);
      if(ps.length<2||ps.some(p=>!Number.isFinite(p.x)||!Number.isFinite(p.y))||ps.slice(1).some((p,i)=>Math.abs(p.x-ps[i].x)>EPS&&Math.abs(p.y-ps[i].y)>EPS))return false;
      for(let i=1;i<ps.length;i++){
        const a=ps[i-1],b=ps[i];if(i>1&&reverses(heading(ps[i-2],a),heading(a,b)))return false;
        if(solid.some(n=>intersectsRect(a,b,(i===1&&n.id===s.id||i===ps.length-1&&n.id===t.id)?n:expand(n,settings.margin)))||extra.some(n=>intersectsRect(a,b,n)))return false;
      }
      if(ps.some(p=>!inside(p,boundary)))return false;
      const approach=(a,b,f)=>((b.x-a.x)*SIDE[f.side][0]+(b.y-a.y)*SIDE[f.side][1])*(f.inward?-1:1)>EPS;
      if(!approach(sp,ps[1],fs)||!approach(tp,ps.at(-2),ft)||dist(tp,ps.at(-2))<(options.minimumTerminal||0)-EPS)return false;
      if(edge.source===edge.target&&ps.length<4)return false;
      return !options.acceptCandidate||options.acceptCandidate(ps,fs,ft);
    };
    const trials=[];
    const waypoints=settings.preserve?(edge.waypoints||[]):[];
    const followsWaypoints=points=>{
      let next=0;
      for(let i=1;i<points.length&&next<waypoints.length;i++){
        const a=points[i-1],b=points[i],length=dist(a,b);let minimum=0;
        while(next<waypoints.length){const p=waypoints[next],along=dist(a,p);
          if(!(along>=minimum-EPS&&along+dist(p,b)<=length+EPS))break;
          minimum=along;next++;
        }
      }return next===waypoints.length;
    };
    if(edge.route?.length>1&&followsWaypoints(edge.route)){const pair=pairs.find(p=>equal(p.sp,edge.route[0])&&equal(p.tp,edge.route.at(-1)));
      if(pair){const cost=routeCost(edge.route,priorPaths,settings);if(Number.isFinite(cost))trials.push({points:simplify(edge.route),cost,pair});}}
    if(!waypoints.length)for(const pair of pairs){
      const {sp:s,tp:t,fs,ft}=pair,ns=SIDE[fs.side],nt=SIDE[ft.side],ss=fs.inward?-1:1,ts=ft.inward?-1:1;
      const add=ps=>{ps=simplify(ps);const cost=routeCost(ps,priorPaths,settings);if(Number.isFinite(cost))trials.push({points:ps,cost,pair});};
      add([s,t]);add([s,{x:s.x,y:t.y},t]);add([s,{x:t.x,y:s.y},t]);
      add([s,{x:s.x,y:(s.y+t.y)/2},{x:t.x,y:(s.y+t.y)/2},t]);
      add([s,{x:(s.x+t.x)/2,y:s.y},{x:(s.x+t.x)/2,y:t.y},t]);
      for(const stub of [...new Set([Math.max(settings.margin+1,options.minimumTerminal||0),settings.stub])]){
        const a={x:s.x+ns[0]*ss*stub,y:s.y+ns[1]*ss*stub},b={x:t.x+nt[0]*ts*stub,y:t.y+nt[1]*ts*stub};
        add([s,a,{x:b.x,y:a.y},b,t]);add([s,a,{x:a.x,y:b.y},b,t]);
      }
    }
    trials.sort((a,b)=>a.cost-b.cost||a.points.length-b.points.length);
    for(const trial of trials)if(acceptable(trial.points,trial.pair)){
      best={ok:true,points:trial.points,cost:trial.cost,expanded:0,sourcePort:trial.pair.sp,targetPort:trial.pair.tp,physicalSource:trial.pair.fs,physicalTarget:trial.pair.ft};break;
    }
    // Recursive presentation changes need a legal settled frontier promptly.
    // Explicit routing retains the default cost optimization over all ports.
    if(best&&settings.firstLegal)return best;
    // A Manhattan route with at most one bend has reached the unobstructed
    // lower bound. Complex corridors use the visibility graph below.
    if(best&&best.cost<=Math.min(...pairs.map(p=>p.lower))+EPS)return best;
    for (const pair of pairs.sort((a,b)=>a.lower-b.lower)) {
      const {fs,ft,sp,tp,extra}=pair;
      if(best&&pair.lower>=best.cost-EPS)continue;
      const obstacles=[...solid.map(n=>expand(n,settings.margin)),...extra];
      const stub = Math.max(settings.stub, settings.margin + (options.stubPadding ?? 6));
      const sourceSign = fs.inward ? -1 : 1, targetSign = ft.inward ? -1 : 1;
      const a = { x: sp.x + SIDE[sp.side][0] * stub * sourceSign, y: sp.y + SIDE[sp.side][1] * stub * sourceSign }, b = { x: tp.x + SIDE[tp.side][0] * stub * targetSign, y: tp.y + SIDE[tp.side][1] * stub * targetSign };
      settings.terminalStems = [{port:sp,outer:a},{port:tp,outer:b}];
      if (solid.some(n => n.id !== s.id && intersectsRect(sp, a, expand(n, .1))) || solid.some(n => n.id !== t.id && intersectsRect(tp, b, expand(n, .1)))) continue;
      if (extra.some(n=>intersectsRect(sp,a,n)||intersectsRect(tp,b,n))) continue;
      if (waypoints.some(p => obstacles.some(r => inside(p, r)))) continue;
      const stops = [a, ...waypoints, b]; let points = [sp], cost = dist(sp,a)+dist(b,tp), expanded = 0, failed = false;
      for (let i = 1; i < stops.length; i++) {
        // Carry the signed arrival heading across waypoints too. A cheapest
        // leg that immediately reverses at a shared fork/gate retraces the
        // previous leg and is rejected only after the entire solve; retaining
        // the heading lets the search find the next legal parallel corridor.
        const joined=simplify(points),incoming=i===1?heading(sp,a):joined.length>1?heading(joined.at(-2),joined.at(-1)):0;
        const result = solveLeg(stops[i - 1], stops[i], obstacles,
          incoming, i === stops.length - 1 ? heading(b, tp) : 0);
        if (!result) { failed = true; break; } points.push(...result.points); cost += result.cost; expanded += result.expanded;
      }
      if (failed) continue;
      points.push(tp); points = simplify(points);
      // Endpoint stubs were outside the search graph. Price them too, and
      // reject a stub that hides a different edge's arrow or terminal segment.
      if (settings.edgeSpacing > 0) {
        for (const path of priorPaths) for (let i = 1; i < path.length; i++) {
          const c = path[i - 1], d = path[i];
          const terminalAt = p => (i === 1 && equal(p, path[0])) ||
            (i === path.length - 1 && equal(p, path[path.length - 1]));
          if (overlap(sp, a, c, d) > EPS && !(path.wire===undefined&&terminalAt(sp))) failed = true;
          if (overlap(b, tp, c, d) > EPS && !(path.wire===undefined&&terminalAt(tp))) failed = true;
        }
        if (failed) continue;
      }
      if(!acceptable(points,pair))continue;
      cost=routeCost(points,priorPaths,settings);
      if(!Number.isFinite(cost))continue;
      if (!best || cost < best.cost-EPS) best = { ok: true, points, cost, expanded, sourcePort: sp, targetPort: tp, physicalSource:fs,physicalTarget:ft,obstacles };
      if(settings.firstLegal)return best;
    }
    return best || { ok: false, reason: 'No valid path with these ports/waypoints. Move nodes or release fixed ports.' };
  }
  function chamfer(points, nodes, radius = 18) {
    const out = [points[0]];
    for (let i = 1; i < points.length - 1; i++) {
      const a = points[i - 1], b = points[i], c = points[i + 1], da = dist(a, b), dc = dist(b, c), r = Math.min(radius, da / 3, dc / 3);
      const p = { x: b.x + (a.x - b.x) / da * r, y: b.y + (a.y - b.y) / da * r }, q = { x: b.x + (c.x - b.x) / dc * r, y: b.y + (c.y - b.y) / dc * r };
      if (r > EPS && !nodes.some(n => n.routingObstacle !== false && intersectsRect(p, q, expand(n, 2)))) out.push(p, q); else out.push(b);
    }
    out.push(points[points.length - 1]); return simplify(out);
  }
  function roundedPath(points, radius = 12) {
    if (points.length < 2) return '';
    const n = v => Math.round(v * 100) / 100;
    let d = `M ${n(points[0].x)} ${n(points[0].y)}`;
    for (let i = 1; i < points.length - 1; i++) {
      const a = points[i - 1], b = points[i], c = points[i + 1], da = dist(a, b), dc = dist(b, c), r = Math.min(radius, da / 3, dc / 3);
      const p = { x: b.x + (a.x - b.x) / da * r, y: b.y + (a.y - b.y) / da * r }, q = { x: b.x + (c.x - b.x) / dc * r, y: b.y + (c.y - b.y) / dc * r };
      d += ` L ${n(p.x)} ${n(p.y)} Q ${n(b.x)} ${n(b.y)} ${n(q.x)} ${n(q.y)}`;
    }
    const last = points[points.length - 1]; return d + ` L ${n(last.x)} ${n(last.y)}`;
  }
  function polylinePath(points) { return points.map((p, i) => `${i ? 'L' : 'M'} ${Math.round(p.x * 100) / 100} ${Math.round(p.y * 100) / 100}`).join(' '); }
  function stats(edges) {
    let length = 0, bends = 0, crossings = 0;
    for (const e of edges) { const ps = e.route || []; for (let i = 1; i < ps.length; i++) length += dist(ps[i - 1], ps[i]); bends += Math.max(0, ps.length - 2); }
    for (let i = 0; i < edges.length; i++) for (let j = i + 1; j < edges.length; j++) { const a = edges[i].route || [], b = edges[j].route || []; for (let u = 1; u < a.length; u++) for (let v = 1; v < b.length; v++) if (crossing(a[u - 1], a[u], b[v - 1], b[v])) crossings++; }
    return { length: Math.round(length), bends, crossings };
  }
  const api = { routeEdge, routeCost, port, candidateSides, simplify, chamfer, roundedPath, polylinePath, stats, intersectsRect, expand, crossing, wireContacts, overlap, dist, SIDE };
  root.EdgeRouterLabRouting = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
