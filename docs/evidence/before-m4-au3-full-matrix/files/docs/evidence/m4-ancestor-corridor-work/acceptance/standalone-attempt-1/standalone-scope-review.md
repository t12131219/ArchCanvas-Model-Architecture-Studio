# Formal standalone check

The unmodified formal `scripts/check_independence.py --project <formal-root>
--build` completed all nine actual checks with exit 0: package provenance,
capability declaration, five static fixture analyses, copied source bytes
unchanged, and standalone Studio build. Its `--help` API was inspected and
stdout/stderr/argv retained in `run-1`. The Python subprocesses use `-I -S` and
only add the standalone formal `src`; origins of all five packages resolve under
`/tmp/archcanvas-independent-kidh2k3_/release/src`. The formal `.venv/bin/python`
resolves to `/home/fzg/anaconda3/bin/python3.11`; Node is 24.19.0.

The complete release copy includes all declared RELEASE_ITEMS, including full
historical docs. The actual copied source manifest has 28,523 entries. The
initial complete release estimate was 1,447,460,864 allocated bytes, plus copied
installed dependencies and 512 MiB build/report headroom; `/tmp` had sufficient
space. No release item, source, or check was removed to reduce the scope.

All 209 declared active source/test/check/helper inputs and all 654 installed
dependency files have exact before/after byte and SHA bindings. The five
installed dependency symlink targets remain within each dependency tree, and
copied dependency bytes/symlink targets match the originals. Actual standalone
source-manifest entries and static analysis output hashes were read back.

`run-1/actual-independence-report.json` is an exact byte copy of the actual
standalone report (6,401,364 bytes, SHA256
7818271e965d9650ee1305a20754ba8a219e3d776f438a2df0552c4996b25cfa).
`run-1/process.json` binds argv, tools, source/dependency receipts, stdout/stderr
and actual/copy report (5,098 bytes, SHA256
5dc54f5d8e7b9182a633e8678d6035cceea9dc039aef730c1104986fecb01d04).
`standalone-scope-review.json` records the independent exact readback.

The build reuses already installed formal project-local dependencies by copying
them. This is source/build independence evidence, not a clean install. No user
model was executed, no prototype runtime was imported, no new dependency was
installed, and no product suite, browser, human or pixel acceptance was run here.
