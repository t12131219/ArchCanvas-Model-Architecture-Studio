# M5 recoverable host Skill lifecycle

The working-tree lifecycle tool adds `preview`, `uninstall`, and `restore` to
the existing project-local installer. Uninstall removes the verified Skill
from its selected host discovery path by atomically moving all of its files
to a private archive inside the explicit project workspace. It deletes no
files and changes no external runtime data or host-global configuration.

`receipt.json` binds the implementation, tests, usage documentation and 16
retained CLI process outputs. The independent CLI exercise used an unpacked
copy of the frozen beta.1 and completed install → preview → uninstall →
restore → verify for Codex, Claude Code and DeepSeek Harness. Each installed
tree contained 227 files; all archived and restored byte inventories exactly
match their respective initial inventories. The external data fixture
remained exact and the frozen beta.1 SHA256 remained
`2c44459c195540fd3ac99a0fa7f52583090d85eae47b26fea4a64d1da85ff9ff`.
The retained workspaces are at `/tmp/archcanvas-uninstall-cli-nh8kf089`.

`tests-candidate.txt` records 12/12 independent lifecycle checks. Those tests
create a temporary current candidate with `pack(ROOT)` and require no
pre-existing `.archcanvas/releases` input, so they can run from an extracted
distribution. They cover all three project paths, exact bytes and external
data, unknown/user-added content, stale digests, tampering, existing empty or
populated targets, kernel no-replace behavior, symlinks, move failure, host
mismatch, archive replay, workspace relocation, replacement/restore and CLI
scope validation. The earlier `tests.txt` is preserved and used beta.1 as its
opaque input; these suites overlap and their counts are not additive.

This evidence exercises Linux `renameat2(RENAME_NOREPLACE)`. It does not
exercise Windows or claim a supported equivalent on other platforms. An
unsupported atomic operation fails closed. The replacement test uses the
same candidate version; a genuinely different-version upgrade requires a
separately verified next release. No model was run, no service was started,
and all three true host workflows remain `not-tested`.
