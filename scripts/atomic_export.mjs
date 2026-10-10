import { lstat, mkdir, mkdtemp, writeFile, readFile, rename, rm } from 'node:fs/promises';
import { dirname, basename, join } from 'node:path';

/** Stage the whole pair before replacing either destination. An ordinary
 * commit failure restores both prior files. No power-loss atomicity claim. */
export async function commitExportPair(path, artifact, receipt) {
  const lock = `${path}.export-lock`;
  await mkdir(lock); // Exclusive; another export never interleaves this pair.
  try { return await commit(path, artifact, receipt); }
  finally { await rm(lock, { recursive: true }); }
}

async function commit(path, artifact, receipt) {
  const targets = [path, `${path}.receipt.json`];
  const previous = [];
  for (const target of targets) {
    let stat;
    try { stat = await lstat(target); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (stat && (!stat.isFile() || stat.isSymbolicLink())) throw new Error(`Export destination must be a regular file: ${target}`);
    previous.push(stat ? await readFile(target) : null);
  }
  const staged = await mkdtemp(join(dirname(path), `.${basename(path)}-stage-`));
  const committed = [];
  let retainBackups = false;
  try {
    for (let i = 0; i < targets.length; i++) {
      await writeFile(join(staged, `new-${i}`), i === 0 ? artifact : `${JSON.stringify(receipt, null, 2)}\n`, { flag: 'wx' });
      if (previous[i] !== null) await writeFile(join(staged, `old-${i}`), previous[i], { flag: 'wx' });
    }
    try {
      for (let i = 0; i < targets.length; i++) { await rename(join(staged, `new-${i}`), targets[i]); committed.push(i); }
    } catch (error) {
      try {
        for (const i of committed.reverse()) {
          if (previous[i] === null) await rm(targets[i]); else await rename(join(staged, `old-${i}`), targets[i]);
        }
      } catch (restoreError) {
        retainBackups = true;
        throw new Error(`Export recovery failed; prior files remain in ${staged}: ${restoreError.message}`, { cause: error });
      }
      throw error;
    }
  } finally { if (!retainBackups) await rm(staged, { recursive: true, force: true }); }
}
