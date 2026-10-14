# Third-party notices

The built Studio includes React, React DOM and Scheduler. Versions are fixed by `studio/package-lock.json`; the notices below are copied from the installed package LICENSE files. Python publication/runtime dependencies are optional, installed separately from their lock files and are not bundled here.

## Summary_Merge preview migration (2026-10-14)

At the user's explicit request, this source tree includes the recursive preview editor, router, model catalog, source snapshots and evidence copied from the separate local source `prototype/Summary_Merge`. The runtime copy is `studio/public/preview` (copied into `studio/dist/preview` by Vite); the standard-library AST adapter is adapted into `src/archcanvas_preview`. This source is distinct from the rejected `ArchCanvas_Model Architecture Studio_Temp` project. The formal build and server do not import or serve the original prototype directory.

The baseline inventory [vendor-manifest.json](studio/dist/preview/vendor-manifest.json), also kept at `studio/public/preview/vendor-manifest.json` in the development tree, records each original relative path, byte count and SHA256: 7,355 copied files and 519,531,592 bytes, containing 115 current and 115 historical cases. Its SHA256 at migration was `95bce258c86021443752da6daad661696594c62a2eb04496f338e59c1b1af9bd`. Integration changes to the copied editor, bridge and presentation code are formal Studio changes; the baseline manifest records the copied source and does not claim later modified files remain byte-identical.

The original `source_adapter/analyze.py` SHA256 was `4203423099ebe24d81a0d512e932d26ae3b172f8d7dce8f1d155c17fa4978650`; the original and retained `source_adapter/registry.json` SHA256 is `5e5a34d04886f1a0450428a0715abc3dc4a14caa3ff1d9669e7948f245f1dbb3`. The adapted package uses its own installed registry resource and has no runtime path into `prototype`.

Model-source snapshots retain their source-specific license/notice files, original headers and evidence alongside the relevant sources. Those assets include third-party model examples and libraries; this migration does not relicense them or assert that every file shares the Studio license. See their retained `LICENSE`, `COPYING` and `NOTICE` files under `studio/public/preview/snapshots`, and the individual source/evidence paths in the inventory. No commercial yFiles runtime is introduced: the vendored browser routing implementation is local JavaScript. The migration's new validation scope and limits are recorded in [preview-migration.md](docs/preview-migration.md).

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
