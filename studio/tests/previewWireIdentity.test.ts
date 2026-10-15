import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const directory = fileURLToPath(new URL('../public/preview/yworks_edge_router_lab/', import.meta.url));
const context = vm.createContext({});
for (const file of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js', 'source-contracts.js', 'semantic-constraints.js'])
  vm.runInContext(readFileSync(path.join(directory, file), 'utf8'), context);
const C = context.SummaryConstraints;
const producer = 'models:network.block';
const identity = (binding: any, source = producer, nodeIds = [source]) => C.wireIdentity({ id: 'fallback', source, binding }, { nodes: nodeIds.map(id => ({ id })) });

test('an explicitly named producer field has one identity across legacy boundaries and semantic records', () => {
  const bindings = [
    { src: producer + ':out' },
    { canonical_src: producer, canonical_src_port: 'out' },
    { semantic_src: producer, semantic_src_port: 'out' },
    { endpoint_binding: { canonical: { src: producer, src_port: 'out' } } },
    { wire_identity: [producer, 'out'] },
  ];
  const before = JSON.stringify(bindings);
  assert.equal(new Set(bindings.map(binding => identity(binding))).size, 1);
  assert.equal(JSON.stringify(bindings), before, 'normalizing a key must preserve the entire original source record');
});

test('different producers and full tuple or operand fields never become one shared value', () => {
  const fields = ['out', 'out[0]', 'out[1]', 'out[0].mean', 'out[0].variance', 'operand[0]', 'operand[1]'];
  const values = ['producer/a', 'producer/b'].flatMap(producer => fields.map(port => identity({ src: producer + ':' + port }, producer)));
  assert.equal(new Set(values).size, values.length);
  assert.notEqual(identity({ src: 'producer/a' }), identity({ semantic_src: 'producer/a', semantic_src_port: 'out' }),
    'a bare source identifier does not prove a default field');
  assert.equal(identity({ canonical_src: 'bare-source' }), 'bare-source');
});

test('explicit wire and canonical endpoint evidence retain precedence over rendered source spelling', () => {
  const canonical = { src: 'producer', src_port: 'tuple[1]' };
  assert.equal(identity({ src: 'rendered:right', canonical_src: 'other:out', semantic_src: 'third', endpoint_binding: { canonical } }),
    identity({ src: 'producer:tuple[1]' }, 'producer'));
  assert.equal(identity({ wire_identity: ['shared-instance/call[1]', 'result[0]'], endpoint_binding: { canonical }, src: 'rendered:left' }),
    identity({ src: 'shared-instance/call[1]:result[0]' }, 'shared-instance/call[1]'));
  assert.notEqual(identity({ wire_identity: ['shared-instance/call[0]', 'result[0]'] }),
    identity({ wire_identity: ['shared-instance/call[1]', 'result[0]'] }), 'two calls of one module remain independent producers');
});

test('opaque IDs, producer colons and full colon-containing port fields remain distinct', () => {
  assert.notEqual(identity({ canonical_src: 'call:instance:branch' }),
    identity({ canonical_src: 'call:instance', canonical_src_port: 'branch' }));
  assert.equal(identity({ canonical_src: 'call:instance:branch' }), 'call:instance:branch');
  assert.equal(identity({ src: 'unknown:port' }), 'unknown:port', 'an unknown source spelling supplies no endpoint grammar');
  assert.equal(identity({ src: producer + ':field:branch[0]' }),
    identity({ semantic_src: producer, semantic_src_port: 'field:branch[0]' }));
  assert.notEqual(identity({ src: producer + ':field:branch[0]' }),
    identity({ semantic_src: producer + ':field', semantic_src_port: 'branch[0]' }));
  assert.equal(identity({ src: producer + ':branch' }, producer, [producer, producer + ':branch']), producer + ':branch',
    'a registered complete node identifier is never split into an inferred field');
});
