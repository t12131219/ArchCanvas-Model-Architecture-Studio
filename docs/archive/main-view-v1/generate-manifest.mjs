import { createHash } from "node:crypto";
import { readdir, readFile, stat, writeFile } from "node:fs/promises";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const archiveRoot = dirname(fileURLToPath(import.meta.url));
const sourceRoot = resolve(archiveRoot, "source");
const archivedCommit = "45a887fabebf767965235e8f6996369c2b5555ff";

async function walk(root) {
  const paths = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = resolve(root, entry.name);
    if (entry.isDirectory()) paths.push(...await walk(path));
    else if (entry.isFile()) paths.push(path);
  }
  return paths.sort();
}

async function digest(path) {
  return createHash("sha256").update(await readFile(path)).digest("hex");
}

const sourceFiles = await walk(sourceRoot);
const files = [];
for (const archivedPath of sourceFiles) {
  const archivePath = relative(archiveRoot, archivedPath);
  const originalPath = relative(sourceRoot, archivedPath);
  files.push({
    original_path: originalPath,
    archive_path: archivePath,
    bytes: (await stat(archivedPath)).size,
    sha256: await digest(archivedPath),
  });
}

await writeFile(resolve(archiveRoot, "MANIFEST.json"), `${JSON.stringify({
  schema_version: "1.0",
  archive: "main-view-v1",
  git_commit: archivedCommit,
  files,
}, null, 2)}\n`);

const checksumFiles = (await walk(archiveRoot)).filter((path) => (
  !path.endsWith("SHA256SUMS")
));
const lines = [];
for (const path of checksumFiles) {
  lines.push(`${await digest(path)}  ${relative(archiveRoot, path)}`);
}
await writeFile(resolve(archiveRoot, "SHA256SUMS"), `${lines.join("\n")}\n`);
