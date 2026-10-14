const test = require('node:test')
const assert = require('node:assert/strict')

const router = require('../router.js')
const fs = require('node:fs')
const path = require('node:path')

const EPS = 1e-6
const baseNodes = [
  { id: 'source', x: 100, y: 220, w: 90, h: 60 },
  { id: 'target', x: 760, y: 360, w: 90, h: 60 },
  // This node forces a detour between the endpoints.
  { id: 'obstacle', x: 420, y: 120, w: 110, h: 390 }
]

function copyNodes(nodes) {
  return nodes.map((node) => ({ ...node }))
}

// An independent geometric oracle: clip a segment's x/y ranges to the open node
// interior. Tests do not reuse the router's collision helper to validate itself.
function entersRectangle(a, b, rect, padding = 0) {
  let start = 0
  let end = 1
  for (const [axis, low, high] of [
    ['x', rect.x - padding + EPS, rect.x + rect.w + padding - EPS],
    ['y', rect.y - padding + EPS, rect.y + rect.h + padding - EPS]
  ]) {
    const delta = b[axis] - a[axis]
    if (Math.abs(delta) < EPS) {
      if (a[axis] <= low || a[axis] >= high) return false
    } else {
      const t1 = (low - a[axis]) / delta
      const t2 = (high - a[axis]) / delta
      start = Math.max(start, Math.min(t1, t2))
      end = Math.min(end, Math.max(t1, t2))
      if (start > end) return false
    }
  }
  return start <= end && end > EPS && start < 1 - EPS
}

function segmentTouchesNonEndpointNode(a, b, nodes, sourceId, targetId) {
  return nodes
    .filter((node) => node.id !== sourceId && node.id !== targetId)
    .some((node) => entersRectangle(a, b, node, 1))
}

function assertRouteAvoidsNonEndpointNodes(result, nodes, edge) {
  assert.equal(result.ok, true, result.reason)
  assert.ok(result.points.length >= 2)
  for (let i = 1; i < result.points.length; i++) {
    assert.ok(Number.isFinite(result.points[i].x) && Number.isFinite(result.points[i].y))
    assert.ok(router.dist(result.points[i - 1], result.points[i]) > EPS)
    assert.equal(
      segmentTouchesNonEndpointNode(
        result.points[i - 1],
        result.points[i],
        nodes,
        edge.source,
        edge.target
      ),
      false,
      `segment ${i - 1}->${i} enters a non-endpoint node`
    )
    for (const node of nodes) {
      assert.equal(
        entersRectangle(result.points[i - 1], result.points[i], node),
        false,
        `segment ${i - 1}->${i} enters node ${node.id}, including an endpoint node`
      )
    }
  }
}

function assertNoRetracedTurn(points) {
  for (let i = 1; i < points.length - 1; i++) {
    const a = points[i - 1], b = points[i], c = points[i + 1]
    const dx = b.x - a.x, dy = b.y - a.y
    const ex = c.x - b.x, ey = c.y - b.y
    assert.equal(Math.abs(dx * ey - dy * ex) < EPS && dx * ex + dy * ey < -EPS,
      false, `turn ${i} retraces its incoming segment and leaves a visible spur`)
  }
}

test('nearby ports do not overshoot a corner and retrace into the target arrow', () => {
  const nodes = [
    { id: 'source', x: 270, y: 448, w: 132, h: 66 },
    { id: 'target', x: 82, y: 518, w: 132, h: 66 }
  ]
  const edge = { source: 'source', target: 'target',
    fixedSource: { side: 'left', fraction: 0.68 },
    fixedTarget: { side: 'top', fraction: 0.6 } }
  const result = router.routeEdge(edge, nodes, [], { stub: 28 })
  assertRouteAvoidsNonEndpointNodes(result, nodes, edge)
  assertNoRetracedTurn(result.points)
  const [before, tip] = result.points.slice(-2)
  assert.ok(before.y < tip.y, 'the target arrow must approach its top port from above')
})

test('a source port stub does not immediately reverse and leave a projecting line', () => {
  const nodes = [
    { id: 'source', x: 82, y: 518, w: 132, h: 66 },
    { id: 'target', x: 270, y: 448, w: 132, h: 66 }
  ]
  const edge = { source: 'source', target: 'target',
    fixedSource: { side: 'top', fraction: 0.6 },
    fixedTarget: { side: 'left', fraction: 0.68 } }
  const result = router.routeEdge(edge, nodes, [], { stub: 28 })
  assertRouteAvoidsNonEndpointNodes(result, nodes, edge)
  assertNoRetracedTurn(result.points)
  assert.ok(result.points[1].y < result.points[0].y, 'the source must leave its top port upwards')
})

test('the captured 13-edge user layout separates intermediate collinear wires', () => {
  const graph = JSON.parse(fs.readFileSync(path.join(__dirname, '../evidence/verification/overlap-fixture.json'), 'utf8'))
  const before = copyNodes(graph.nodes)
  const routes = []
  for (const edge of graph.edges) {
    const fraction = id => {
      const siblings = graph.edges.filter(e => e.source === id || e.target === id)
      return 0.2 + 0.6 * (siblings.indexOf(edge) + 1) / (siblings.length + 1)
    }
    const result = router.routeEdge(edge, graph.nodes, routes, {
      margin: 14, stub: 28, bendCost: 40, crossingCost: 220, overlapCost: 3, edgeSpacing: 12,
      sourceFraction: fraction(edge.source), targetFraction: fraction(edge.target)
    })
    assertRouteAvoidsNonEndpointNodes(result, graph.nodes, edge)
    assertNoRetracedTurn(result.points)
    for (const prior of routes) {
      for (let i = 1; i < result.points.length; i++) {
        for (let j = 1; j < prior.length; j++) {
          const a = result.points[i - 1], b = result.points[i], c = prior[j - 1], d = prior[j]
          if (Math.abs(a.x - b.x) < EPS && Math.abs(c.x - d.x) < EPS && Math.abs(a.x - c.x) < EPS)
            assert.ok(Math.min(Math.max(a.y, b.y), Math.max(c.y, d.y)) - Math.max(Math.min(a.y, b.y), Math.min(c.y, d.y)) <= EPS)
          if (Math.abs(a.y - b.y) < EPS && Math.abs(c.y - d.y) < EPS && Math.abs(a.y - c.y) < EPS)
            assert.ok(Math.min(Math.max(a.x, b.x), Math.max(c.x, d.x)) - Math.max(Math.min(a.x, b.x), Math.min(c.x, d.x)) <= EPS)
        }
      }
    }
    routes.push(result.points)
  }
  assert.equal(routes.length, 13)
  assert.deepEqual(graph.nodes, before)
})

test('routes around an obstacle and leaves endpoint ports without entering non-endpoint nodes', () => {
  const nodes = copyNodes(baseNodes)
  const before = copyNodes(nodes)
  const edge = { source: 'source', target: 'target' }
  const result = router.routeEdge(edge, nodes)

  assertRouteAvoidsNonEndpointNodes(result, nodes, edge)
  assert.deepEqual(nodes, before, 'routing must not mutate node coordinates')
})

test('left/right and top/bottom side constraints choose the requested port sides', () => {
  const nodes = copyNodes(baseNodes)
  const edge = { source: 'source', target: 'target' }

  const leftRight = router.routeEdge(edge, nodes, [], { sides: 'lr' })
  assert.equal(leftRight.ok, true, leftRight.reason)
  assert.ok(['left', 'right'].includes(leftRight.sourcePort.side))
  assert.ok(['left', 'right'].includes(leftRight.targetPort.side))
  assertRouteAvoidsNonEndpointNodes(leftRight, nodes, edge)

  const topBottom = router.routeEdge(edge, nodes, [], { sides: 'tb' })
  assert.equal(topBottom.ok, true, topBottom.reason)
  assert.ok(['top', 'bottom'].includes(topBottom.sourcePort.side))
  assert.ok(['top', 'bottom'].includes(topBottom.targetPort.side))
  assertRouteAvoidsNonEndpointNodes(topBottom, nodes, edge)
})

test('fixed source and target ports remain fixed, including their fractions', () => {
  const nodes = copyNodes(baseNodes)
  const edge = {
    source: 'source',
    target: 'target',
    fixedSource: { side: 'bottom', fraction: 0.2 },
    fixedTarget: { side: 'top', fraction: 0.8 }
  }
  const result = router.routeEdge(edge, nodes, [], { sides: 'any' })

  assert.equal(result.ok, true, result.reason)
  assert.equal(result.sourcePort.side, 'bottom')
  assert.equal(result.targetPort.side, 'top')
  assert.equal(result.sourcePort.fraction, 0.2)
  assert.equal(result.targetPort.fraction, 0.8)
  assertRouteAvoidsNonEndpointNodes(result, nodes, edge)
})

test('self-loop produces a non-degenerate loop route', () => {
  const nodes = copyNodes(baseNodes)
  const edge = { source: 'source', target: 'source' }
  const result = router.routeEdge(edge, nodes)

  assert.equal(result.ok, true, result.reason)
  assert.ok(result.points.length >= 4, 'self-loop should contain a visible detour')
  assert.ok(
    result.points.some((point, index) => index > 0 && router.dist(point, result.points[0]) > EPS),
    'self-loop should not collapse to a single point'
  )
  assertRouteAvoidsNonEndpointNodes(result, nodes, edge)
})

test('an impossible waypoint inside an obstacle fails cleanly', () => {
  const nodes = copyNodes(baseNodes)
  const result = router.routeEdge(
    { source: 'source', target: 'target', waypoints: [{ x: 465, y: 300 }] },
    nodes,
    [],
    { preserve: true }
  )

  assert.equal(result.ok, false)
  assert.match(result.reason, /No valid path|waypoint/i)
})

test('preserve mode keeps each waypoint in the returned route', () => {
  const nodes = copyNodes(baseNodes)
  const waypoints = [
    { x: 300, y: 90 },
    { x: 650, y: 540 }
  ]
  const edge = { source: 'source', target: 'target', waypoints }
  const result = router.routeEdge(edge, nodes, [], { preserve: true })

  assert.equal(result.ok, true, result.reason)
  for (const waypoint of waypoints) {
    assert.ok(
      routeContains(result.points, waypoint),
      `preserved waypoint ${JSON.stringify(waypoint)} is missing`
    )
  }
  assertRouteAvoidsNonEndpointNodes(result, nodes, edge)
})

test('chamfered orthogonal route introduces diagonal segments without entering nodes', () => {
  const nodes = copyNodes(baseNodes)
  const edge = { source: 'source', target: 'target' }
  const route = router.routeEdge(edge, nodes)
  assert.equal(route.ok, true, route.reason)

  const chamfered = router.chamfer(route.points, nodes, 18)
  assert.ok(chamfered.length >= route.points.length)
  let hasDiagonal = false
  for (let i = 1; i < chamfered.length; i++) {
    const a = chamfered[i - 1]
    const b = chamfered[i]
    if (Math.abs(a.x - b.x) > EPS && Math.abs(a.y - b.y) > EPS) hasDiagonal = true
    assert.equal(
      segmentTouchesNonEndpointNode(a, b, nodes, edge.source, edge.target),
      false,
      `chamfer segment ${i - 1}->${i} enters a non-endpoint node`
    )
  }
  assert.equal(hasDiagonal, true, 'chamfer should contain at least one diagonal segment')
  assertRouteAvoidsNonEndpointNodes({ ok: true, points: chamfered }, nodes, edge)
})

function routeContains(points, point) {
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1]
    const b = points[i]
    const cross = (point.x - a.x) * (b.y - a.y) - (point.y - a.y) * (b.x - a.x)
    if (Math.abs(cross) < EPS &&
      point.x >= Math.min(a.x, b.x) - EPS && point.x <= Math.max(a.x, b.x) + EPS &&
      point.y >= Math.min(a.y, b.y) - EPS && point.y <= Math.max(a.y, b.y) + EPS) return true
  }
  return false
}

test('collinear preserved waypoint remains on the routed path even if its vertex is simplified', () => {
  const nodes = [
    { id: 'source', x: 100, y: 200, w: 80, h: 60 },
    { id: 'target', x: 760, y: 200, w: 80, h: 60 }
  ]
  const waypoint = { x: 400, y: 230 }
  const result = router.routeEdge(
    { source: 'source', target: 'target', waypoints: [waypoint] }, nodes, [], { preserve: true }
  )
  assert.equal(result.ok, true, result.reason)
  assert.equal(routeContains(result.points, waypoint), true)
})

test('a blocked fixed port fails instead of crossing the adjacent node', () => {
  const nodes = [
    { id: 'source', x: 100, y: 200, w: 80, h: 60 },
    { id: 'blocker', x: 185, y: 195, w: 40, h: 70 },
    { id: 'target', x: 760, y: 200, w: 80, h: 60 }
  ]
  const result = router.routeEdge(
    { source: 'source', target: 'target', fixedSource: { side: 'right', fraction: 0.5 } }, nodes
  )
  assert.equal(result.ok, false, 'the required source stub runs through blocker')
})

test('deterministic varied layouts preserve node geometry and obstacle avoidance', () => {
  let seed = 0x6012026
  const random = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
    return seed / 0x100000000
  }
  for (let layout = 0; layout < 12; layout++) {
    const nodes = [
      { id: 'source', x: 90, y: 150 + random() * 320, w: 80, h: 60 },
      { id: 'target', x: 900, y: 150 + random() * 320, w: 80, h: 60 },
      ...Array.from({ length: 3 }, (_, i) => ({
        id: `obstacle-${i}`, x: 280 + i * 180, y: 130 + random() * 270, w: 70, h: 60 + random() * 80
      }))
    ]
    const before = copyNodes(nodes)
    const edge = { source: 'source', target: 'target' }
    const result = router.routeEdge(edge, nodes, [], { sides: ['any', 'lr', 'tb'][layout % 3] })
    assertRouteAvoidsNonEndpointNodes(result, nodes, edge)
    assertNoRetracedTurn(result.points)
    const chamfered = router.chamfer(result.points, nodes, 24)
    assertRouteAvoidsNonEndpointNodes({ ok: true, points: chamfered }, nodes, edge)
    assert.deepEqual(nodes, before, `layout ${layout} must preserve all node geometry`)
  }
})
