# Third-party provenance

The Python baseline depends on Pydantic, jsonschema, and LibCST under their respective upstream
licenses. The Stage 4 frontend depends on React, React DOM, Lucide React, TypeScript, and Vite; exact
versions, integrity hashes, transitive packages, and declared licenses are locked in
`studio/package-lock.json`. The production Studio bundle contains no external network resources.

Stage 5 optionally uses the environment-provided PyTorch runtime to collect explicitly authorized
module-boundary shape and dtype evidence. PyTorch is declared in the `runtime` optional dependency
group and is not imported by static analysis. Runtime receipts record the exact Torch version,
CUDA build, CUDA availability, and selected device instead of inferring accelerator support from a
CUDA-tagged package version.

`fixtures/tier_a/autoformer/` contains four unmodified source files from THUML Autoformer revision `51c7d416ae120b805fd5beef2f4ccf7de496a6ff`, used only as a deterministic static-analysis fixture. The upstream project is MIT licensed; the preserved license and archive/member SHA-256 values are stored beside the fixture.

`fixtures/tier_a/itransformer/` contains three unmodified source files from THUML iTransformer revision `c2426e68ca13f74aaec08045c5c724d8ad328124`, used only as a deterministic static-analysis fixture. The upstream project is MIT licensed; the preserved license and archive/member SHA-256 values are stored beside the fixture.

`fixtures/tier_a/patchtst/` contains four unmodified source files from PatchTST revision `bb0bc6058ddc421c02e8afe77e7e8db99f913957`, used only as a deterministic static-analysis fixture. The supplied archive has no repository-root license file, so the fixture records `NOASSERTION` and does not infer a license from bundled comparison projects.

`fixtures/tier_a/timemixer/` contains three unmodified source files from TimeMixer revision `e24610583b36fdd8c76cc17a8df4e65759a5f460`, used only as a deterministic static-analysis fixture. The upstream project is Apache-2.0 licensed; the preserved license and archive/member SHA-256 values are stored beside the fixture.
