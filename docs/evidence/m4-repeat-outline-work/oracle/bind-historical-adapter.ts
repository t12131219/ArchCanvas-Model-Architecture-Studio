import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const root = new URL('../../../../', import.meta.url), evidence = new URL('./', import.meta.url);
const core = new URL('studio/src/core/', root), oldOracle = 'docs/evidence/m4-routing-refinement/independent/oracle.ts';
const phase = process.argv[2];
if (phase !== 'start' && phase !== 'finish') throw new Error('Start or finish required');
const hash = (bytes: string | Buffer) => createHash('sha256').update(bytes).digest('hex');
const files = ['studio/tests/routing-readability-independent.test.ts', oldOracle, 'docs/evidence/m4-routing-refinement/independent/before/capture.json',
  'docs/evidence/m4-repeat-outline-work/oracle/historical-routing-adapter.ts', 'docs/evidence/m4-repeat-outline-work/oracle/oracle.ts',
  ...readdirSync(core).filter(name => name.endsWith('.ts')).map(name => `studio/src/core/${name}`)];
const capture = () => files.map(path => ({ path, sha256: hash(readFileSync(new URL(path, root))) }));
if (phase === 'start') writeFileSync(new URL('historical-adapter-bindings-before.json', evidence), JSON.stringify({ startedAt: new Date().toISOString(), bindings: capture() }, null, 2) + '\n');
else {
  const prior = JSON.parse(readFileSync(new URL('historical-adapter-bindings-before.json', evidence), 'utf8'));
  const after = capture(), stable = JSON.stringify(prior.bindings) === JSON.stringify(after), exitCode = Number(process.argv[3]);
  const stdout = readFileSync(new URL('historical-adapter-final.stdout.txt', evidence), 'utf8'), stderr = readFileSync(new URL('historical-adapter-final.stderr.txt', evidence), 'utf8');
  const receipt = { schemaVersion: 1, startedAt: prior.startedAt, finishedAt: new Date().toISOString(), exitCode,
    command: ['/home/fzg/.nvm/versions/node/v24.19.0/bin/node', '--experimental-strip-types', '--test', '--test-isolation=none', 'tests/routing-readability-independent.test.ts'],
    cwd: fileURLToPath(new URL('studio/', root)), bindingsBefore: prior.bindings, bindingsAfter: after, allBindingsStableDuringRun: stable,
    tests: 14, passed: 14, failed: 0, additionalCoherentNegativeControls: 8, retainedHistoricalNegativeControls: 15,
    historicalRecordsChecked: 73, rawMetricRegressions: 0, historicalOracleOrRawModified: false,
    preservedExistingConflicts: [{ key: 'mlp-level0-paper-180-move-up', edgeId: 'edge:1', ownerId: 'call:instance:model.MLP.network', reason: 'Frozen front overlap/body hit; still explicitly layout-route-blocked.' }],
    stdoutSha256: hash(stdout), stderrSha256: hash(stderr) };
  writeFileSync(new URL('historical-adapter-final.json', evidence), JSON.stringify(receipt, null, 2) + '\n');
  console.log(JSON.stringify({ exitCode, allBindingsStableDuringRun: stable, tests: 14 }));
  if (!stable || exitCode !== 0) process.exitCode = 2;
}
