# Agent completion of unknown module views

Use this when drawing an unfamiliar model leaves opaque modules, expressions, decorators or dynamic regions. The calling Codex or Claude Code Agent performs the work during the user's task. ArchCanvas does not call an LLM, watch for Agents or install Python plugins. Default handoff is static; the optional explicit CPU step below is separate from source view authority.

## Obtain the work request

From this Skill's directory, use its bound launcher (all commands below use the same launcher). Check `doctor`, then `capabilities`: require `agentViewCompletion.nativeSummaryViews`. A development checkout is not a frozen installed release.

```bash
python3 -I -B scripts/archcanvas_runtime.py adapter handoff \
  --root /absolute/model-source --entry package.model:Model \
  --output /absolute/artifacts/unknown-view-request.json
```

Supply `--config constructor.json` for the actual source configuration, and optionally `--registry /absolute/state/adapters` to inspect existing views. Place artifacts and registries outside the source root. `handoff` reads source without execution by default and never creates a registry. Explicit `--probe-spec` opts in to the isolated CPU step described below. Source corpus limits are 80 Python files / 2 MB. For a large benchmark, select one model and its local source dependencies into a separate snapshot, retaining their relative import paths and file hashes; report omitted dependencies. Never import the benchmark to discover it, and never quietly truncate a corpus.

The `archcanvas-agent-view-handoff/1` result includes exact source file hashes, constructor configuration, unresolved boundary IDs, reasons, locatable source slices, candidate local symbols, prior rule applications, budgets and `starterRules`. Inspect each requested region and its callable definition. A candidate symbol is a navigation hint, not proof that it implements the unknown call. CPU observations can help explain a region but cannot license an invented implementation or unobserved branch. Failed/unavailable probes do not prevent this view workflow.

## Optional explicit CPU step and failure recovery

When the user requests CPU assistance, add `--probe-spec /absolute/input-spec.json --runtime-interpreter /absolute/formal-venv/bin/python --dependency-lock /absolute/requirements-runtime.lock --probe-output /absolute/artifacts/probe-result.json` to `adapter handoff`. The spec uses `semantic-inputs/1`, explicit constructor, named input cases and modes; see [runtime-compatibility.md](runtime-compatibility.md). The constructor must match `--config` when supplied. Optional `--probe-timeout` is bounded by the formal runtime. Artifacts belong outside the source root.

The formal frozen Bubblewrap/seccomp profile runs first. `probe.status` distinguishes `passed`, `failed` and `unavailable`; `modelExecuted` can be null if a killed worker cannot report its state. The full receipt is saved separately. A failed/unavailable execution still yields a valid handoff and exit 0: the handoff succeeded, not the probe. Inspect its status and reason before reporting. Invalid inputs or mismatched configuration remain errors. Diagnostic receipt binding must match source bytes, entry and constructor; it grants no tensor authority.

For `failed` or `unavailable`, retain the receipt, continue with source-only requests and author verified inspection rules. Do not retry in an ordinary subprocess, install missing model dependencies automatically, remove isolation, infer a shape from the failed sample or label the model executable. Even a passed sample may leave static unknowns. HTTP handoff remains nonexecuting; an explicitly requested HTTP observation uses the separate Summary runtime job API and its configured formal environment.

## Author the view

For real Python structure that the current analyzer has not expanded, choose or adapt an object in `starterRules`, saving the rule JSON as a new artifact. `attribute-call` explains a source callable and receiver; it does not describe the internals of FFT, CUDA kernels or an external library. `list-comprehension` exposes an iterable and body, retaining source guards; its relation is rejected if the body does not read the bound iteration variable. For a different structure, use the finite AST DSL in [adapter-generation-standard.md](adapter-generation-standard.md).

Keep labels in the source's naming convention. Use actual AST paths and supported proofs. No arbitrary coordinates, HTML, Python callbacks, invented tensor ports, shapes, runtime claims, or generation contracts are accepted. Presentation aliases and explanatory notes can be added to the scaffolded instance. If implementation is absent, retain the source-backed opaque call card and explain what is unavailable. It is impossible to reconstruct every hidden computation from a black-box observation.

```bash
python3 -I -B scripts/archcanvas_runtime.py adapter rule-validate --rule /absolute/artifacts/rule.json
python3 -I -B scripts/archcanvas_runtime.py adapter scaffold \
  --root /absolute/model-source --entry package.model:Model \
  --rules /absolute/artifacts/rule.json --output /absolute/artifacts/view.json
python3 -I -B scripts/archcanvas_runtime.py adapter validate \
  --root /absolute/model-source --definition /absolute/artifacts/view.json
python3 -I -B scripts/archcanvas_runtime.py adapter register \
  --root /absolute/model-source --definition /absolute/artifacts/view.json \
  --registry /absolute/state/adapters
python3 -I -B scripts/archcanvas_runtime.py adapter preview \
  --root /absolute/model-source --entry package.model:Model \
  --registry /absolute/state/adapters --semantic-mode summary \
  --output /absolute/artifacts/preview.json
```

Use the same `--config` on scaffold and preview when handoff used it. Use `scaffold --method METHOD` for an explicit helper or decorated method that needs inspection beyond the entry callable. Confirm real matches in `sourceRuleApplications`, and inspect `ruleDiagnostics` and truncation. A valid template with no actual application does not complete a view. Test the rule on renamed files/classes/locals, and reject an unsupported relation or stale source binding.

## Deliver through the current native canvas

Open the new portable source JSON through Studio's source JSON import, or reanalyze using the same service registry at `data-dir/adapters`. HTTP offers `POST /api/adapters/handoff` with `files`, `entry`, optional `config`, and the service session header; scaffold/validate/register and preview use the same source corpus. Preview HTTP must request `semanticMode: "summary"`. A CLI registry at some other path is not automatically the running service's registry.

Verified inspection cards now appear in `ir.semantic_ir`, with `inspection_only: true`, `kind: "opaque"`, and `semantic_type: "source-inspection"`. Original computation nodes and edges are retained exactly. The `source_inspection_views` receipt binds the original IR digest and lists all added IDs. Added arrows are syntax dependencies (`kind: "source-inspection"`), with no tensor or generation authority. Source inspection does not reduce the count of unresolved computational boundaries. Card labels/notes are plain text; the current glyph contract supplies their style.

Reanalysis creates a new bundle, not a silent mutation of a saved document. Preserve the user's original layout/history and verify expand/collapse, source location, save/reopen, and export on the new document. Report which boundaries gained explanatory structure, which remain opaque, whether budgets truncated the result, and which interactions were actually verified. Do not describe a richer picture as complete parsing or equivalent Python generation.
