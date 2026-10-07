# Independent authored artifact audit

The final `attempt-2/receipt.json` passes **6/6 bounded checks**. All 33 input files were reread unchanged and copied exactly. The reviewer uses Python standard-library AST, JSON, SHA256 and SVG XML readers; it does not import product code, execute models, install dependencies or operate the browser. `contract.json` records the handwritten four-node semantic oracle before the artifact audit.

The root freeze manifest binds 11 actual saved files and their exact copies. This audit verifies all 11 copy/source byte bindings, but reviews semantic behavior only for the new vertical Input → Linear → GELU → Output graph. Other preset files receive byte binding checks. The two separately fetched HTTP assets are outside this review; no browser cache claim is made.

| Check | Actual result |
| --- | --- |
| Frozen originals and copies | All 11 exact; root manifest SHA256 `fc17d40749597423e0e74771cf4c3a45dd5cd4a921fc7513eea670e69e0347a3` |
| Saved typed draft | 4 nodes, 3 exact output→input bindings; draft revision 27, storage revision 2; reopened identities and `(50,70/224/378/532)` positions match |
| Generated source | Visible source equals managed `model.py`, 672 bytes, SHA256 `542bc483f484cf6165d7fe7d4f6a2b47c1b6f45950cb262c065589c2a632fd4d`; AST has Linear 16→8 and GELU with exact producer/return chain |
| Architecture and document | 5 canonical nodes including container, 4 canonical bindings including the container adapter; literal UTF8 parameter spans and source expression AST intervals match; source/IR normalization recomputed independently; document revision 0, storage revision 1 |
| Five new public SVGs | Before-save, saved, reopened, final-before and final-after complete canonical XML equal; 5 rendered nodes, 3 data bindings; actual Output texts `输出` and `model output`, complete real return key retained in title and metadata |
| Actual SVG export | 14,721 bytes, SHA256 `157996984fc0d5a0a7a3a90cb7b2d45c56ac76311a6b1ba1df76ae18af77a53a`; exported Canvas equals saved Canvas, whole source metadata and all node/edge/legend/annotation objects equal public objects after removing only declared interaction attributes and expand controls |

The reviewed managed project is `1ae6944134fc42e48acc0e7484341642`, entry `model:AuthoredModel`. Its document is `canvas-architecture-model.AuthoredModel-306378c82c52-704b0c13`, source digest `306378c82c52803b44bc171a0d1cfc6cd379636a5096c02e6f121d590ce535a0`, IR digest `704b0c13e6903b1691e02e446a52cbbff65c7ca798b8a34aeaac97e4a3120034`. The older `managed-reopened.public.json` belongs to a different `c1cd…/45d5…` model and was not borrowed for this chain.

Declared shapes are handwritten static expectations `[1,16] → [1,8] → [1,8] → [1,8]` for float32. Input declarations are not observed runtime tensors. The static architecture preserves `torch.float32` as an unknown source expression; this audit does not promote it to runtime evidence.

The first audit passed 5/6. The reviewer required the exported root height to match the exact formula within `1e-10 mm`, but the actual root uses the five-place physical encoding `196.63866mm`. The source metadata and receipt retain the precise formula `180 × 650 / 595 = 196.638655462…`. `physical-encoding-reviewer-correction-before.json`, the old helper, failed receipt, all inputs and process status are retained. The correction independently checks the formula rounded to five places; no source fact, object/path XML or metadata requirement was relaxed, and no product/raw file was edited.

The exporter’s `inputSvgDigest`/`sceneSvgDigest` value `b9f2…` is cross-bound from its actual receipt only. This reviewer did not recover the core renderer’s input SVG bytes, so it does not certify that digest by independent input-byte reconstruction. Actual final SVG bytes, document, object geometry and metadata were checked directly. Root physical dimensions are mathematical consistency evidence, not final publication-size aesthetic or font readability acceptance.

Human participation remains zero. This record does not certify model execution, all 17 catalog modules, novice human success, full publication readability, or M4 completion. Native gestures and visual review are separate evidence owned by the root and other reviewers.
