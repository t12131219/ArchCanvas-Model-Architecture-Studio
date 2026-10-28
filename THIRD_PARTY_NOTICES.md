# Third-party notices

The built Studio includes React, React DOM and Scheduler. Versions are fixed by `studio/package-lock.json`; the notices below are copied from the installed package LICENSE files. Python publication/runtime dependencies are optional, installed separately from their lock files and are not bundled here.

## Summary_Merge preview migration (2026-10-14)

The 2026-10-28 authoring extension uses the already vendored, byte-identical
`semantic_studio/authoring-model.js` and copies
`data/semantic/authoring-presets.json` from Summary_Merge unchanged. Studio's
`studio-authoring.js` and retained panel adapter are separate integration code.
Source hashes, current validation and remaining authoring scope are recorded in
`docs/summary-authoring-manifest-20261028.json` and
`docs/summary-authoring-integration-20261028.md`.


At the user's explicit request, this source tree includes the recursive preview editor, router, model catalog, source snapshots and evidence copied from the separate local source `prototype/Summary_Merge`. The runtime copy is `studio/public/preview` (copied into `studio/dist/preview` by Vite); the standard-library AST adapter is adapted into `src/archcanvas_preview`. This source is distinct from the rejected `ArchCanvas_Model Architecture Studio_Temp` project. The formal build and server do not import or serve the original prototype directory.

The baseline inventory [vendor-manifest.json](studio/dist/preview/vendor-manifest.json), also kept at `studio/public/preview/vendor-manifest.json` in the development tree, records each original relative path, byte count and SHA256: 7,355 copied files and 519,531,592 bytes, containing 115 current and 115 historical cases. Its SHA256 at migration was `95bce258c86021443752da6daad661696594c62a2eb04496f338e59c1b1af9bd`. Integration changes to the copied editor, bridge and presentation code are formal Studio changes; the baseline manifest records the copied source and does not claim later modified files remain byte-identical.

The original `source_adapter/analyze.py` SHA256 was `4203423099ebe24d81a0d512e932d26ae3b172f8d7dce8f1d155c17fa4978650`; the original and retained `source_adapter/registry.json` SHA256 is `5e5a34d04886f1a0450428a0715abc3dc4a14caa3ff1d9669e7948f245f1dbb3`. The adapted package uses its own installed registry resource and has no runtime path into `prototype`.

Model-source snapshots retain their source-specific license/notice files, original headers and evidence alongside the relevant sources. Those assets include third-party model examples and libraries; this migration does not relicense them or assert that every file shares the Studio license. See their retained `LICENSE`, `COPYING` and `NOTICE` files under `studio/public/preview/snapshots`, and the individual source/evidence paths in the inventory. No commercial yFiles runtime is introduced: the vendored browser routing implementation is local JavaScript. The migration's new validation scope and limits are recorded in [preview-migration.md](docs/preview-migration.md).

Preset Python sources are also organized under `studio/public/preview/sources/packages` with their declared licenses copied into each package, and Notebook code-cell derivatives under `sources/notebooks`. Python text and line positions are preserved; filenames may be normalized for static module resolution. Original paths, content hashes and licenses remain recorded in `data/source-packages.json`, `data/catalog-sources.json` and `data/notebook-conversions.json`. The Notebook derivatives retain the original code headers and do not introduce a new license. Original materials and evidence remain in `snapshots`; the new source audit is documented in [preview-sources.md](docs/preview-sources.md).

The 2026-10-28 extension also copies the 21 Python modules from Summary_Merge's
`semantic_adapter` into `src/archcanvas_summary_semantic`. Static analysis is
connected through `archcanvas_preview/semantic_bridge.py`; optional runtime and
probe code is retained but is not called by preview analysis. Original and
adapted hashes and the adaptation reasons are recorded in
`docs/summary-semantic-manifest-20261028.json`. This package resolves inside the
formal distribution and has no runtime dependency on the prototype checkout.

The same extension vendors 29 pure semantic projection modules from
`semantic_studio` and the original `flow-optimizer.js`, `source-runtime.js` and
`generic-semantic.js` into `studio/public/preview`. The 32 source-identical files
and their hashes are listed in `docs/summary-native-view-manifest-20261028.json`.
The Studio wrapper, panel and native dispatch are recorded separately as
integration changes. No original semantic HTML, sidebar or legacy renderer is
loaded as a second Studio canvas.
The shared router and graph engine also incorporate Summary's bounded native
search and physical-port candidate options, with adaptations and original
hashes recorded in the same native manifest. Studio's existing endpoint,
ordered-waypoint and canonical binding guards remain in effect.

The multiformat document reader is the same unmodified `generic-semantic.js`.
`studio-documents.js`, the imported-document provenance contract and retained
Studio import/panel wiring are local integration code, documented in
`docs/summary-documents-integration-20261028.md`. No second semantic renderer or
original standalone authoring UI is introduced.

## react 19.3.0

MIT License

Copyright (c) Meta Platforms, Inc. and affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## react-dom 19.3.0

MIT License

Copyright (c) Meta Platforms, Inc. and affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## scheduler 0.28.0

MIT License

Copyright (c) Meta Platforms, Inc. and affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

The 2026-10-28 source-module extension calls the previously vendored Summary
`authoring.compile_module` unchanged in a bounded formal Python process. The
original `AuthoringModel.replaceModule`, `recipe` and `restoreConnection` now
drive retained Studio inspector controls. No original standalone server or
authoring renderer is embedded. Current source, adaptation and independent
verification are recorded in `docs/summary-source-authoring-integration-20261028.md`
and `docs/summary-source-authoring-manifest-20261028.json`.

The local assembly extension invokes Summary's unchanged `authoring.certify_assembly`
and `contracts.recognize_contracts` in the formal bounded static process. The
new bridge, strict derived-result binding and retained Studio folding panel are
formal adaptations documented in `docs/summary-local-assembly-integration-20261028.md`
and `docs/summary-local-assembly-manifest-20261028.json`.

2026-10-28 D0 接管适配：Studio 宿主退出旧 formal preview Scene/指针/相机职责，保留面板并委托 Summary 的原生端口、布线与手势。Summary 副本的 app/bridge 新增统一 cancel-gesture 与 pan camera rollback；来源、改动前副本及当前验证见 `docs/summary-preview-retirement-integration-20261028.md`。32 个已登记原版原生 JS 模块未改动。

2026-10-28 generic catalog: copied Summary_Merge's original 43 IR files, one semantic presentation profile and catalog JSON byte-for-byte under the authorized migration. The generated Studio index and inspector adapt loading and enforce current resource limits; source paths remain provenance. File hashes: `docs/summary-catalog-assets-manifest-20261028.json`. This does not certify archived runtime observations or authorize source commits.

2026-10-28 evidence-view adaptation: retained Studio folding controls now select Summary's native source/runtime/merged state and archived run index. The bridge validates transitions and preserves exact latent object identity across modes. The 32 original native JS modules remain unchanged; no prototype executor is enabled. Adaptation, limits and independent evidence: `docs/summary-evidence-views-integration-20261028.md`.

2026-10-28 compact-state adaptation: Studio navigation rows reference exact IDs in the already-carried canonical IR; native session snapshots share recursively frozen evidence through Summary's unchanged cloneGeometry. Formal host adaptation and independent comparisons are recorded in `docs/summary-compact-state-integration-20261028.md`. All 32 original native modules remain byte-identical.


## 原生测量驱动局部细化（2026-10-28）

Summary 的原版 adaptive-frontier/5 现由 studio-adaptive.js 接到唯一原生画布；候选比较使用实际图元文字、精确操作数绑定和成功的物理路径。Studio 保留右侧折叠面板，增加开关、策略、采用/拒绝回执和手动收起入口。保存有效请求与开启前基线；关闭恢复原请求，重开独立校验已保存布局。详细范围、来源及验证见 `docs/summary-adaptive-view-integration-20261028.md`。新 CPU、大图完整压力与 D1 仍未完成。
