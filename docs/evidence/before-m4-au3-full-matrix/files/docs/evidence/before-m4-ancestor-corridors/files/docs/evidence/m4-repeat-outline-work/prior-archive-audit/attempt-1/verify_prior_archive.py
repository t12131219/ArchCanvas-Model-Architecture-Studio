"""Bounded independent prior archive and immutable matrix-byte review; no product imports."""
from pathlib import Path
from collections import Counter
import datetime
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
ARCHIVE = ROOT / "docs/evidence/before-m4-repeat-outline"
MANIFEST = ARCHIVE / "manifest.json"
SEAL_PATH = "docs/evidence/m4-chs-browser-matrix-current-verification-sealed.json"
ARCHIVED_SEAL = ARCHIVE / "files" / SEAL_PATH
EXPECTED_MANIFEST_SHA = "a0ae1bd0d2b21589a4986acc992c13c3f6cde0659a0c94c770f37fd5be299e70"
EXPECTED_SEAL_SHA = "332f9b84a085efa95ef0cb09fdfd152bbbef072fc97c5268f355191a597a4581"
CURRENT_PREFIXES = {
    "matrixRaw": "docs/evidence/m4-chs-browser-matrix-work/raw/",
    "matrixCollected": "docs/evidence/browser-visual-matrix-chs-current/",
}


def bind(path):
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


manifest_start = bind(MANIFEST)
archived_seal_start = bind(ARCHIVED_SEAL)
assert manifest_start["sha256"] == EXPECTED_MANIFEST_SHA
assert archived_seal_start["sha256"] == EXPECTED_SEAL_SHA
manifest = json.loads(MANIFEST.read_text())
seal = json.loads(ARCHIVED_SEAL.read_text())
assert manifest["previousSeal"] == SEAL_PATH and manifest["previousSealSha256"] == EXPECTED_SEAL_SHA
assert manifest["bindingCount"] == len(manifest["bindings"]) == 2916
assert seal["bindingCount"] == len(seal["bindings"]) == 2915
seal_bindings = {binding["path"]: binding for binding in seal["bindings"]}
archive_bindings = {binding["path"]: binding for binding in manifest["bindings"]}
assert len(seal_bindings) == 2915 and len(archive_bindings) == 2916
assert set(archive_bindings) == set(seal_bindings) | {SEAL_PATH}
archive_start = []
for relative, binding in archive_bindings.items():
    assert not Path(relative).is_absolute() and ".." not in Path(relative).parts
    expected_archive_path = "docs/evidence/before-m4-repeat-outline/files/" + relative
    assert binding["archivePath"] == expected_archive_path
    actual = ROOT / binding["archivePath"]
    assert actual.resolve().is_relative_to((ARCHIVE / "files").resolve()) and not actual.is_symlink()
    archived = bind(actual)
    assert (archived["bytes"], archived["sha256"]) == (binding["bytes"], binding["sha256"])
    if relative in seal_bindings:
        assert {key: binding[key] for key in ["path", "bytes", "sha256"]} == seal_bindings[relative]
    else:
        assert relative == SEAL_PATH and archived == archived_seal_start
    archive_start.append({"originalPath": relative, "archivePath": binding["archivePath"], **archived, "sealMappingExact": relative in seal_bindings, "additionalOriginalSeal": relative == SEAL_PATH})
actual_archived_files = {str(path.relative_to(ROOT)) for path in (ARCHIVE / "files").rglob("*") if path.is_file()}
assert actual_archived_files == {binding["archivePath"] for binding in manifest["bindings"]}

# Current product, dist, source and historical docs may now change. Their prior
# versions are checked above only in archive, never compared to current files.
current_start = []
for relative, expected in seal_bindings.items():
    kinds = [kind for kind, prefix in CURRENT_PREFIXES.items() if relative.startswith(prefix)]
    if not kinds:
        continue
    assert len(kinds) == 1
    actual = ROOT / relative
    assert actual.is_file() and not actual.is_symlink()
    current = bind(actual)
    assert (current["bytes"], current["sha256"]) == (expected["bytes"], expected["sha256"])
    current_start.append({"kind": kinds[0], "relativePath": relative, **current, "unchangedAgainstSeal": True})
assert all(any(binding["kind"] == kind for binding in current_start) for kind in CURRENT_PREFIXES)
unbound_current = {}
for kind, prefix in CURRENT_PREFIXES.items():
    files = {str(path.relative_to(ROOT)) for path in (ROOT / prefix).rglob("*") if path.is_file()}
    unbound_current[kind] = sorted(files - set(seal_bindings))
    assert not unbound_current[kind], "New unbound file in immutable raw/collected tree"
archive_end = []
for item in archive_start:
    archive_end.append({**item, **bind(ROOT / item["archivePath"])})
current_end = []
for item in current_start:
    current_end.append({**item, **bind(ROOT / item["relativePath"])})
manifest_end = bind(MANIFEST)
archived_seal_end = bind(ARCHIVED_SEAL)
assert archive_start == archive_end and current_start == current_end
assert manifest_start == manifest_end and archived_seal_start == archived_seal_end
counts = Counter(item["kind"] for item in current_start)
result = {
    "kind": "Independent complete ChS prior-archive byte and immutable matrix audit",
    "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "scope": "2915 old seal bindings plus original seal in2916file archive; current comparisons restricted to matrix raw and collected. Current product/source/dist/historical docs may change and are not required unchanged.",
    "archiveManifestStart": manifest_start,
    "archiveManifestEnd": manifest_end,
    "archivedOriginalSealStart": archived_seal_start,
    "archivedOriginalSealEnd": archived_seal_end,
    "counts": {"oldSealBindings": 2915, "archiveManifestBindings": 2916, "archivedFilesEnumerated": len(actual_archived_files), "exactOldSealToArchivedMappings": 2915, "additionalOriginalSeal": 1, "currentMatrixRaw": counts["matrixRaw"], "currentMatrixCollected": counts["matrixCollected"], "currentMatrixTotal": len(current_start)},
    "allArchivedBytesMatchManifest": True,
    "allOldSealBindingsMatchArchivedBytes": True,
    "currentRawAndCollectedMatchSealExactly": True,
    "unboundCurrentRawAndCollectedFiles": unbound_current,
    "archiveBindingsStart": archive_start,
    "archiveBindingsEnd": archive_end,
    "currentImmutableMatrixBindingsStart": current_start,
    "currentImmutableMatrixBindingsEnd": current_end,
    "allInputsUnchangedDuringAudit": True,
    "historicalSourceDocsReviewLocation": "archive only; current source/docs/product/dist not compared",
    "limits": ["Local stored bytes and oldseal→archive path consistency only; no immutable acquisition, native provenance, live runtime, semantic correctness or human acceptance certification.", "No image views, product suite, renderer imports, service actions or changes to old docs/status/seal/raw/collected.", "Product repeat-outline implementation is authorized separately; its current source/build/doc changes do not invalidate this prior archive audit."]
}
path = OUT / "prior-archive-independent-review.json"
with path.open("x") as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
md = path.with_suffix(".md")
with md.open("x") as handle:
    handle.write("# Repeat outline 前归档独立复核\n\n归档2916个文件逐一哈希相符：旧ChSseal的2915个绑定完整映射到归档路径，另含原始seal本身。归档manifest与原seal的给定SHA256均相符，归档files目录没有额外未列文件。\n\n当前matrix raw "+str(counts["matrixRaw"])+"个文件、collected "+str(counts["matrixCollected"])+"个文件全部与旧seal绑定字节相等，且两个目录没有额外未绑定文件。归档、manifest、原seal与当前matrix输入在复核结束时均重哈希不变。\n\n产品源码、dist与历史文档允许继续修改，其原版本仅在归档中核验；未要求当前版本不变。未重看图像、未运行产品suite、未修改任何旧文档/status/matrixseal/raw/collected。结论限于本地字节与路径映射一致性。\n")
for checked in [path, md, Path(__file__)]:
    print(json.dumps(bind(checked), ensure_ascii=False))
print(json.dumps(result["counts"], ensure_ascii=False))
