# Offline Release

Install the same skill source into `.agents/skills/archcanvas` for Codex or
`.claude/skills/archcanvas` for Claude Code. Copy mode includes the ArchCanvas Python runtime and
schemas; it still requires Python 3.11 and the dependencies reported by `doctor`. Installation and
artifact generation perform no network access.

`archcanvas bundle create architecture.json --out model.archcanvas` writes a portable directory
with redacted analysis records, L1-L4 JSON/SVG/HTML, schemas, support matrix, verification receipt,
and a digest manifest. Run `archcanvas bundle verify model.archcanvas` before handoff. Bundle
verification detects missing, extra, or modified files. A deterministic render is not a human
visual approval; the receipt keeps visual review separate.
