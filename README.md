# ArchCanvas

ArchCanvas is a source-grounded model architecture studio. The current rewrite baseline provides the protocol boundary, a short agent skill, deterministic Python source discovery, an Exact Architecture IR, and structured validation receipts.

This repository is intentionally rebuilding from the source-truth boundary outward. The interactive Studio and source transactions are not claimed as available until their quality gates exist.

## Quick start

```bash
python -m pip install -e .[dev]
archcanvas doctor --json
archcanvas analyze \
  --project fixtures/tier_a/transformer \
  --entry model:Transformer \
  --task inference \
  --mode eval \
  --out build/transformer \
  --json
archcanvas validate build/transformer/architecture.json --json
```

`analyze` never imports the target project. It reads Python source, records file digests and source spans, and emits unresolved facts whenever the static subset cannot prove a claim.

## Current support

| Capability | Status |
| --- | --- |
| Doctor and environment receipt | Available |
| Python entrypoint discovery | Available |
| Static module/call recovery | Transformer L3 subset |
| Evidence ledger and Exact IR | Available |
| Semantic validation | Available |
| Publication compiler / Studio | Planned |
| Runtime tracing | Planned, opt-in only |
| Source transactions | Planned, never direct-write |

See [PRODUCT.md](PRODUCT.md), [DESIGN.md](DESIGN.md), and [docs/contracts/protocols.md](docs/contracts/protocols.md).
