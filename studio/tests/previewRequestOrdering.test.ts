import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const source = readFileSync(new URL('../src/PreviewStudio.tsx', import.meta.url), 'utf8');
const methods = source.slice(source.indexOf('  function post('), source.indexOf('  useEffect(() => {'));
const compiled = ts.transpileModule(methods, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;

for (const initiallyReady of [true, false]) test(`annotation focus follows creation when bridge ready=${initiallyReady}`, async () => {
  const sent: Record<string, unknown>[] = [], errors: string[] = [];
  let handle: any, serial = 0;
  const context = vm.createContext({
    iframe: { current: { contentWindow: { postMessage(message: Record<string, unknown>) { sent.push(message); } } } },
    window: { location: { origin: 'http://localhost' } },
    ready: { current: initiallyReady }, readyWaiters: { current: new Set<() => void>() },
    commandSequence: { current: Promise.resolve() },
    pending: { current: new Map() }, callbacks: { current: { onError: (message: string) => errors.push(message) } },
    crypto: { randomUUID: () => `request-${++serial}` },
    setTimeout: () => 1, clearTimeout() {}, ref: {},
    useImperativeHandle(_ref: unknown, factory: () => unknown) { handle = factory(); },
  });
  vm.runInContext(compiled, context);
  const created = handle.visual([{ type: 'annotation', annotation: { id: 'new-note' } }]);
  handle.focus({ annotationId: 'new-note' });
  if (!initiallyReady) {
    assert.equal(sent.length, 0);
    context.ready.current = true;
    for (const done of context.readyWaiters.current) done();
  }
  await Promise.resolve(); await Promise.resolve();
  assert.deepEqual(sent.map(message => message.type), ['archcanvas:preview:visual', 'archcanvas:preview:focus']);
  assert.deepEqual(sent.map(message => message.requestId), ['request-1', 'request-2']);
  assert.equal(sent[1].annotationId, 'new-note');
  for (const pending of context.pending.current.values()) pending.resolve({});
  await created; await Promise.resolve();
  assert.deepEqual(errors, []);
});

test('fire-and-forget toolbar commands wait for the iframe handshake and retain order', async () => {
  const sent: Record<string, unknown>[] = [], errors: string[] = [];
  let handle: any, serial = 0;
  const context = vm.createContext({
    iframe: { current: { contentWindow: { postMessage(message: Record<string, unknown>) { sent.push(message); } } } },
    window: { location: { origin: 'http://localhost' } },
    ready: { current: false }, readyWaiters: { current: new Set<() => void>() },
    commandSequence: { current: Promise.resolve() }, pending: { current: new Map() },
    callbacks: { current: { onError: (message: string) => errors.push(message) } },
    crypto: { randomUUID: () => `command-${++serial}` },
    setTimeout: () => 1, clearTimeout() {}, ref: {},
    useImperativeHandle(_ref: unknown, factory: () => unknown) { handle = factory(); },
  });
  vm.runInContext(compiled, context);
  handle.command('show-routing');
  handle.command('set-frontier', { preset: 'detail' });
  await Promise.resolve();
  assert.deepEqual(sent, []);
  context.ready.current = true;
  for (const done of context.readyWaiters.current) done();
  for (let i = 0; i < 10; i += 1) await Promise.resolve();
  assert.deepEqual(sent.map((message: Record<string, unknown>) => message.type), ['archcanvas:preview:show-routing', 'archcanvas:preview:set-frontier']);
  assert.deepEqual(sent.map((message: Record<string, unknown>) => message.requestId), ['command-1', 'command-2']);
  assert.deepEqual(errors, []);
});
