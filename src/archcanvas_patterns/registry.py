from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from archcanvas_core.models import (
    PatternDistribution,
    PatternPackLoad,
    PatternPackManifest,
    VisualTemplateManifest,
)

BUILTIN_ROOT = Path(__file__).resolve().parent / "builtin"
VISUAL_TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "archcanvas_publication" / "templates"


def manifest_digest(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("pack_digest", None)
    canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_manifest(
    path: Path,
    distribution: PatternDistribution,
    *,
    locked_digest: str | None,
) -> tuple[PatternPackManifest, PatternPackLoad]:
    resolved = path.resolve()
    if resolved.name != "pattern.json" or not resolved.is_file():
        raise ValueError(f"pattern pack must resolve to a pattern.json file: {path}")
    if (resolved.parent / "matcher.py").exists():
        raise ValueError("executable Pattern Pack matchers are not permitted in this stage")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Pattern Pack manifest is not an object: {resolved}")
    digest = manifest_digest(payload)
    if payload.get("pack_digest") != digest:
        raise ValueError(f"Pattern Pack digest is stale: {resolved}")
    payload["distribution"] = distribution.value
    manifest = PatternPackManifest.model_validate(payload)
    if distribution is PatternDistribution.WORKSPACE:
        if locked_digest is None:
            raise ValueError(f"workspace Pattern Pack {manifest.pack_id} requires an explicit digest lock")
        if locked_digest != digest:
            raise ValueError(f"workspace Pattern Pack digest lock mismatch for {manifest.pack_id}")
    return manifest, PatternPackLoad(
        pack_id=manifest.pack_id,
        version=manifest.version,
        digest=digest,
        distribution=distribution,
        source=str(resolved),
        locked=distribution is PatternDistribution.BUILTIN or locked_digest == digest,
    )


@dataclass(frozen=True)
class PatternRegistry:
    manifests: list[PatternPackManifest]
    loads: list[PatternPackLoad]
    templates: dict[str, VisualTemplateManifest] = field(default_factory=dict)


def _load_visual_templates() -> dict[str, VisualTemplateManifest]:
    templates: dict[str, VisualTemplateManifest] = {}
    for path in sorted(VISUAL_TEMPLATE_ROOT.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError(f"visual template manifest is not an object: {path}")
        template = VisualTemplateManifest.model_validate(payload)
        if template.template_id in templates:
            raise ValueError(f"duplicate visual template id: {template.template_id}")
        templates[template.template_id] = template
    return templates


def _lock_map(values: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values or []:
        pack_id, separator, digest = value.partition("=")
        if not separator or len(digest) != 64:
            raise ValueError("pattern locks use PACK_ID=SHA256")
        result[pack_id] = digest
    return result


def load_registry(
    *,
    workspace_paths: list[Path] | None = None,
    workspace_locks: list[str] | None = None,
    candidate_paths: list[Path] | None = None,
) -> PatternRegistry:
    manifests: list[PatternPackManifest] = []
    loads: list[PatternPackLoad] = []
    locks = _lock_map(workspace_locks)
    sources: list[tuple[Path, PatternDistribution, str | None]] = []
    sources.extend(
        (path, PatternDistribution.BUILTIN, None)
        for path in sorted(BUILTIN_ROOT.glob("*/pattern.json"))
    )
    for directory in workspace_paths or []:
        path = (directory / "pattern.json") if directory.is_dir() else directory
        raw = json.loads(path.resolve().read_text(encoding="utf-8"))
        pack_id = raw.get("pack_id") if isinstance(raw, dict) else None
        sources.append((path, PatternDistribution.WORKSPACE, locks.get(str(pack_id))))
    for directory in candidate_paths or []:
        path = (directory / "pattern.json") if directory.is_dir() else directory
        sources.append((path, PatternDistribution.SESSION_CANDIDATE, None))
    seen: set[str] = set()
    for path, distribution, lock in sources:
        manifest, loaded = _read_manifest(path, distribution, locked_digest=lock)
        if manifest.pack_id in seen:
            raise ValueError(f"duplicate Pattern Pack id: {manifest.pack_id}")
        seen.add(manifest.pack_id)
        manifests.append(manifest)
        loads.append(loaded)
    unused = sorted(set(locks) - {item.pack_id for item in manifests})
    if unused:
        raise ValueError("pattern locks do not match an enabled workspace pack: " + ", ".join(unused))
    templates = _load_visual_templates()
    for manifest in manifests:
        for rule in manifest.template_rules:
            template = templates.get(rule.template_id)
            if template is None:
                raise ValueError(
                    f"Pattern Pack {manifest.pack_id} references missing visual template "
                    f"{rule.template_id}"
                )
            if not set(manifest.supported_ir_versions) & set(template.supported_ir_versions):
                raise ValueError(
                    f"Pattern Pack {manifest.pack_id} and visual template {rule.template_id} "
                    "have no shared IR version"
                )
    return PatternRegistry(manifests=manifests, loads=loads, templates=templates)
