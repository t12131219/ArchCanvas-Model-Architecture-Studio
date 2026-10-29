# Third-party notices

## TFB read-only validation evidence (2026-10-29)

The unknown-module view validation artifacts contain source text and source
excerpts from the local TFB benchmark. Its MIT license (Copyright 2024 Huawei
Technologies Co., Ltd) is retained at
`docs/evidence/agent-unknown-views-20261029/tfb/TFB-LICENSE.txt`.
These are validation evidence, not a new executable runtime dependency.
The follow-up CPU validation executes an exact copied ChebyKAN source only in
the formal isolated runtime; the original TFB directory remains read-only.

The 2026-10-29 native import integration change skips legacy full-frontier
construction when the native Summary Worker already owns the graph. Source
verification and native graph acceptance are retained. The vendored
flow optimizer also receives a transaction validation fix: complete proposed
fanout trees must preserve distinct physical operand slots before acceptance.
An unchanged MIT-licensed ChebyKAN source fixture and its license are retained
under `fixtures/agent_views` for independent regression. This change adapts the
already authorized vendored editor, not the failed Temp runtime.

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

The multiformat document reader originally used the source-identical `generic-semantic.js`.
The 2026-10-29 Studio adaptation (native-semantic/22) attaches verified,
expression-only callable/receiver inspection subtrees to the original opaque
call's source details. These syntax cards and arrows do not appear on the
computation canvas or expansion tree. Structural inspection remains available;
any non-syntax incident dependency vetoes attachment. Canonical nodes, edges,
operand bindings and unknown status remain unchanged and fully accounted for.
The earlier renderer 21 explanation wrapper is superseded by this policy.
Source cuts also place predecessor-free, nonmutable resource reads near their
first consumers and use a larger bounded routing grid and graph-size-based
routing budget. These are generic policies without model/project name checks
or source execution. Prior affected layouts migrate with provenance preserved.
Current hashes are in the integration manifest; the native manifest retains
the original migration baseline. Checks are recorded in
`docs/evidence/inspection-connections-20261029/`.
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

## Monaco source workbench (2026-10-29)

Monaco Editor 0.57.0 is loaded locally on demand for Python editing. It includes VSCode editing components, not a Python language server. DOMPurify is fixed to 3.4.17; all versions are locked in studio/package-lock.json.

### monaco-editor

```text
The MIT License (MIT)

Copyright (c) 2016 - present Microsoft Corporation

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
```

### marked

```text
# License information

## Contribution License Agreement

If you contribute code to this project, you are implicitly allowing your code
to be distributed under the MIT license. You are also implicitly verifying that
all code is your original work. `</legalese>`

## Marked

Copyright (c) 2018+, MarkedJS (https://github.com/markedjs/)
Copyright (c) 2011-2018, Christopher Jeffrey (https://github.com/chjj/)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

## Markdown

Copyright © 2004, John Gruber
http://daringfireball.net/
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
* Neither the name “Markdown” nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

This software is provided by the copyright holders and contributors “as is” and any express or implied warranties, including, but not limited to, the implied warranties of merchantability and fitness for a particular purpose are disclaimed. In no event shall the copyright owner or contributors be liable for any direct, indirect, incidental, special, exemplary, or consequential damages (including, but not limited to, procurement of substitute goods or services; loss of use, data, or profits; or business interruption) however caused and on any theory of liability, whether in contract, strict liability, or tort (including negligence or otherwise) arising in any way out of the use of this software, even if advised of the possibility of such damage.
```

### dompurify

```text
Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```

The executable reconstruction audit adds unchanged original Summary_Merge fixtures models.py (SHA256 380ba612d236f58d41cd54531a58d296d2f9522da8be3cea50ae6d4567d32834) and design_compositions.py (SHA256 d3c3b9539576faf36288b82bb5ff45b80f8a356eeeb49a7f3f45a49ec633e7e2) under tests/fixtures/executable_rebuild. They test the already migrated catalog models using only local copies and the formal runtime, without a runtime dependency on the prototype checkout.
