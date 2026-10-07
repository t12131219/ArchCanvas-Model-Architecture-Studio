# M5 project-local Skill installation

`scripts/m5_host_install.py` installs a complete ArchCanvas Skill into one
explicit project workspace. It accepts an independently unpacked and verified
local release directory, such as the directory produced by:

```bash
python scripts/m5_beta_bundle.py verify \
  --bundle .archcanvas/releases/archcanvas-0.1.0-beta.1.tar.gz \
  --extract-to /tmp/archcanvas-beta-release
```

The caller must select both a host and a project workspace. The installer does
not inspect or modify a home directory, a global Skill directory, an existing
Skill directory, or a host configuration:

```bash
python scripts/m5_host_install.py install \
  --release-dir /tmp/archcanvas-beta-release \
  --host codex --workspace /path/to/project

python scripts/m5_host_install.py install \
  --release-dir /tmp/archcanvas-beta-release \
  --host claude-code --prefix /path/to/project

python scripts/m5_host_install.py install \
  --release-dir /tmp/archcanvas-beta-release \
  --host deepseek-harness --workspace /path/to/project
```

The project-local discovery paths are `.agents/skills/archcanvas` for Codex,
`.claude/skills/archcanvas` for Claude Code, and
`.dsh/skills/archcanvas` for the official DeepSeek Harness. `--prefix` is an
explicit workspace alias; exactly one of `--workspace` and `--prefix` is
required.

Installation first verifies the release inventory, hashes, release schema and
artifact bindings. It then copies into an exclusive staging directory and
renames the completed Skill into place. A pre-existing target, symlink,
directory/file collision, malformed release, or validation failure leaves the
user's files intact. The installed directory contains `archcanvas-install.json`
with the release digest, version, host, complete file inventory and a portable
runtime binding. Verify it after moving the entire directory with:

```bash
python scripts/m5_host_install.py verify \
  --skill-directory /path/to/project/.agents/skills/archcanvas
```

The runtime is copied under `runtime/release`; the generated
`scripts/archcanvas_runtime.py` resolves that directory relative to itself and
sets `-B`-equivalent bytecode protection. It can run static analysis after the
Skill directory is moved:

```bash
python -I -B /path/to/project/.agents/skills/archcanvas/scripts/archcanvas_runtime.py \
  capabilities
```

The embedded release excludes its original `skills/archcanvas` subtree because
the host Skill is copied beside it. This avoids recursive host discovery of a
second same-named Skill. The contract records this exclusion and verifies the
filtered runtime manifest against the remaining release inventory. The source
release is verified in full before this exclusion is applied.

Links in copied Skill Markdown that previously climbed into the development
checkout are rewritten to files under `runtime/release`. A historical document
that is not distributed gets a local note under `resources/unavailable`; it is
never resolved through the original checkout. The release itself remains byte
bound and is safe to move with the Skill.

`serve` requires an explicit `--data-dir` outside the installed Skill so
documents and runtime state cannot contaminate the immutable embedded release:

```bash
python -I -B /path/to/project/.agents/skills/archcanvas/scripts/archcanvas_runtime.py \
  serve --data-dir /tmp/archcanvas-host-data --port 8765
```

This stage proves project-local package compatibility, portable resources and
runtime provenance. It does not claim that Codex, Claude Code or DeepSeek
Harness has loaded the Skill, nor does it certify a full host workflow. Host
E2E remains recorded as `not-tested` until the respective client is actually
run and its loaded Skill path, CLI lifecycle and Studio actions are captured.

## Recoverable project-local uninstall and restoration

`scripts/m5_host_uninstall.py` removes a verified install from the selected
host's discovery path by moving the entire Skill into a private archive under
that workspace's `.archcanvas/host-skill-archives`. It retains all installed
bytes and leaves external Studio data directories intact. It does not stop a
running Studio process. Stop that process before changing its installation.

Preview the exact installation first and use its `installationSha256` in the
uninstall command:

```bash
python scripts/m5_host_uninstall.py preview \
  --host codex --workspace /path/to/project

python scripts/m5_host_uninstall.py uninstall \
  --host codex --workspace /path/to/project \
  --expected-installation-sha256 ACTUAL_DIGEST_FROM_PREVIEW
```

The uninstall command re-verifies the complete install and rejects a stale
digest, changed files, user-added files, unknown same-named directories, and
symlink paths. It prints the actual `archiveDirectory` and writes an
`archive.json` that binds the archived inventory. An interruption after the
move leaves every byte in a `quarantined-needs-review` archive instead of
silently accepting or deleting changed content.

Restore uses the actual archive directory returned by uninstall:

```bash
python scripts/m5_host_uninstall.py restore \
  --host codex --workspace /path/to/project \
  --archive-directory ACTUAL_ARCHIVE_DIRECTORY
```

The archive must be one direct child of the selected workspace's archive root.
Restoration verifies the archived installation and receipt, rejects additional
archive files and changed content, and uses an atomic operation that cannot
replace even an empty same-named directory created after validation. The whole
workspace and its archive can be moved together before restoration; original
absolute paths in the receipt remain audit metadata.

This lifecycle operation has been verified on Linux using
`renameat2(RENAME_NOREPLACE)`. Windows uses its non-replacing rename contract
but has not been exercised here. Other platforms or filesystems without an
equivalent atomic operation fail closed and retain the installation.

To install another verified release, archive the current install, then run the
existing installer into the now-empty discovery path. To restore the earlier
install, first archive the replacement and restore the earlier archive. The
command never overwrites an active same-named Skill. The current evidence
tests this replacement lifecycle with the frozen beta.1; a different-version
upgrade still needs a separately verified next release and its own evidence.

The implementation and test evidence are in
[m5-host-uninstall-v1](evidence/m5-host-uninstall-v1/receipt.json). They extend
the working tree's lifecycle tools and do not modify or re-certify beta.1.
