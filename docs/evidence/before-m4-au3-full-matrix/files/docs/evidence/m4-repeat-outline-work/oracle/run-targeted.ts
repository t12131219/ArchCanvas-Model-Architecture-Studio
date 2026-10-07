import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = new URL('../../../../', import.meta.url), evidence = new URL('./', import.meta.url);
const node = '/home/fzg/.nvm/versions/node/v24.19.0/bin/node';
const hash = (value: string | Buffer) => createHash('sha256').update(value).digest('hex');
const testPath = new URL('studio/tests/repeat-outline-independent.test.ts', root);
// Bind before/after phases around a direct harness exec. Nested Node child
// spawning is unavailable in this sandbox, so the harness owns test execution.
const phase = process.argv[2], mode = process.argv[3];
if (phase !== 'start' && phase !== 'finish') throw new Error('Specify start or finish');
if (mode !== 'sealed-ChS' && mode !== 'current') throw new Error('Specify sealed-ChS or current');
const core = mode === 'sealed-ChS' ? new URL('docs/evidence/before-m4-repeat-outline/files/studio/src/core/', root) : new URL('studio/src/core/', root);
const bindings = () => readdirSync(core).filter(name => name.endsWith('.ts')).sort().map(name => {
  const bytes = readFileSync(new URL(name, core)); return { path: fileURLToPath(new URL(name, core)), bytes: bytes.length, sha256: hash(bytes) };
});
const tests = () => ({ testSha256: hash(readFileSync(testPath)), oracleSha256: hash(readFileSync(new URL('oracle.ts', evidence))), fixturesSha256: hash(readFileSync(new URL('fixtures.ts', evidence))) });
if (phase === 'start') {
  writeFileSync(new URL(`${mode}.run-bindings-before.json`, evidence), JSON.stringify({ mode, startedAt: new Date().toISOString(), sourceBindings: bindings(), ...tests() }, null, 2) + '\n');
} else {
  const prior = JSON.parse(readFileSync(new URL(`${mode}.run-bindings-before.json`, evidence), 'utf8'));
  const sourceAfter = bindings(), stable = JSON.stringify(prior.sourceBindings) === JSON.stringify(sourceAfter), testBindings = tests();
  const exitCode = Number(process.argv[4]);
  if (!Number.isInteger(exitCode)) throw new Error('Pass the actual direct harness exit code');
  const stdout = readFileSync(new URL(`${mode}.stdout.txt`, evidence), 'utf8'), stderr = readFileSync(new URL(`${mode}.stderr.txt`, evidence), 'utf8');
  const stableTests = Object.entries(testBindings).every(([key, value]) => prior[key] === value);
  const report = { schemaVersion: 1, mode, startedAt: prior.startedAt, finishedAt: new Date().toISOString(), command: [node, '--experimental-strip-types', '--test', '--test-isolation=none', 'tests/repeat-outline-independent.test.ts'],
    cwd: fileURLToPath(new URL('studio/', root)), exitCode, sourceBindingsBefore: prior.sourceBindings, sourceBindingsAfter: sourceAfter, stableSourceDuringRun: stable,
    ...testBindings, stableTestsDuringRun: stableTests, stdoutSha256: hash(stdout), stderrSha256: hash(stderr),
    expectedExit: mode === 'sealed-ChS' ? 'nonzero: actual regression controls must reject archived formal ChS' : 'zero: current formal implementation must pass' };
  writeFileSync(new URL(`${mode}.json`, evidence), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ mode, exitCode, stableSourceDuringRun: stable, stableTestsDuringRun: stableTests, stdoutPath: `${mode}.stdout.txt` }));
  if (!stable || !stableTests || (mode === 'current' ? exitCode !== 0 : exitCode === 0)) process.exitCode = 2;
}
