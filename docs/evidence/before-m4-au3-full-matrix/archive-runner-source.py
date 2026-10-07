#!/usr/bin/env python3
"""Preserve the exact old AU3 seal union before current docs may change."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
OUTPUT = ROOT / 'docs/evidence/before-m4-au3-full-matrix'
SEAL = ROOT / 'docs/evidence/m4-ancestor-corridor-current-verification-sealed.json'
FINAL = ROOT / 'docs/evidence/m4-ancestor-corridor-work/acceptance/final-seal-attempt-1/final-receipt.json'
RESULT = WORK / 'archive-before-matrix-attempt-1.json'

specification = importlib.util.spec_from_file_location('au3_archive_binder_utils', WORK / 'bind_case.py')
binder = importlib.util.module_from_spec(specification)
specification.loader.exec_module(binder)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_new(path, value):
    with path.open('xb') as handle:
        handle.write(binder.encoded(value))


def copy_new(source, destination):
    raw = binder.regular(source).read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as handle:
        handle.write(raw)
    if destination.read_bytes() != raw:
        raise ValueError(f'Archive copy differs: {destination}')
    return binder.binding(destination, raw)


def file_set(directory):
    return [str(path.relative_to(directory)) for path in sorted(directory.rglob('*')) if path.is_file()]


def main():
    if OUTPUT.exists() or RESULT.exists():
        raise ValueError('Archive/result exists; preserve and use a fresh independent attempt.')
    started = now()
    OUTPUT.mkdir()
    try:
        runner_binding = copy_new(Path(__file__).absolute(), OUTPUT / 'archive-runner-source.py')
        binder_binding = copy_new(WORK / 'bind_case.py', OUTPUT / 'archive-binder-utils-source.py')
        seal_bytes = binder.regular(SEAL).read_bytes()
        final_bytes = binder.regular(FINAL).read_bytes()
        seal, final = json.loads(seal_bytes), json.loads(final_bytes)
        observed_seal = binder.binding(SEAL, seal_bytes)
        if final['seal'] != observed_seal or seal['bindingCount'] != 4233 or final['supplementalBindingCount'] != 24:
            raise ValueError('Old final receipt/seal count or bytes/hash mismatch.')
        expected, origin = {}, {}
        for label, records in (('old-seal-4233', seal['bindings']), ('old-final-readback-supplemental-24', final['supplementalBindings'])):
            for record in records:
                path = record['path']
                if not isinstance(path, str) or Path(path).is_absolute() or '..' in Path(path).parts:
                    raise ValueError('Archive source is not a safe actual project-relative path.')
                if path in expected and expected[path] != record:
                    raise ValueError('Duplicate archive source has incompatible binding.')
                expected[path] = record
                origin.setdefault(path, []).append(label)
        for path, raw, label in ((SEAL, seal_bytes, 'old-seal-itself'), (FINAL, final_bytes, 'old-final-readback-itself')):
            key = binder.relative(path)
            record = binder.binding(path, raw)
            if key in expected and expected[key] != record:
                raise ValueError('Seal/final source is already listed with incompatible bytes.')
            expected[key] = record
            origin.setdefault(key, []).append(label)
        if len(expected) != 4259:
            raise ValueError('Require exact seal4233 + supplemental24 + seal + final union4259.')
        source_before = []
        for name in sorted(expected):
            path = binder.regular(ROOT / name)
            if not path.resolve().is_relative_to(ROOT):
                raise ValueError('Actual archive source escapes formal project.')
            actual = binder.binding(path, path.read_bytes())
            if actual != expected[name]:
                raise ValueError(f'Old sealed source bytes/hash changed: {name}')
            source_before.append(actual)
        before_list_raw = binder.encoded(source_before)
        write_new(OUTPUT / 'source-before.json', source_before)
        mapping, content = [], OUTPUT / 'files'
        content.mkdir()
        print('4259 actual source bindings exact; copying complete union.', flush=True)
        for index, name in enumerate(sorted(expected)):
            archived = copy_new(ROOT / name, content / name)
            wanted = expected[name]
            if archived['bytes'] != wanted['bytes'] or archived['sha256'] != wanted['sha256']:
                raise ValueError(f'Source changed during archive copy: {name}')
            mapping.append({'sourcePath': name, 'archivePath': str((content / name).relative_to(OUTPUT)),
                            'bytes': wanted['bytes'], 'sha256': wanted['sha256'],
                            'sourceBindingOrigins': origin[name], 'byteExact': True})
            if (index + 1) % 1000 == 0:
                print(f'{index + 1} exact files copied.', flush=True)
        actual_set = file_set(content)
        if actual_set != sorted(expected):
            raise ValueError('Archive content file-set differs from exact source union.')
        source_after = [binder.binding(binder.regular(ROOT / name), (ROOT / name).read_bytes()) for name in sorted(expected)]
        if source_after != source_before:
            raise ValueError('Old sealed sources changed during archive; preserve failed attempt.')
        for row in mapping:
            raw = binder.regular(OUTPUT / row['archivePath']).read_bytes()
            if len(raw) != row['bytes'] or digest(raw) != row['sha256']:
                raise ValueError('Archive final readback differs from original union.')
        write_new(OUTPUT / 'source-after.json', source_after)
        write_new(OUTPUT / 'content-file-set.json', actual_set)
        manifest = {'schemaVersion': 1, 'protocol': 'archcanvas-exact-prior-evidence-union-archive/1',
                    'startedAt': started, 'finishedAt': now(),
                    'sourceRoot': str(ROOT), 'archiveRoot': str(OUTPUT),
                    'seal': observed_seal, 'finalReceipt': binder.binding(FINAL, final_bytes),
                    'sealBindingCount': 4233, 'supplementalBindingCount': 24,
                    'addedSelfExcludedFiles': 2, 'contentFileCount': len(mapping),
                    'contentBytes': sum(row['bytes'] for row in mapping),
                    'fileSetExact': True, 'sourceBeforeAfterExact': True,
                    'sourceBeforeListSha256': digest(before_list_raw),
                    'sourceAfterListSha256': digest(binder.encoded(source_after)),
                    'sourceFileSetSha256': digest(binder.encoded(actual_set)),
                    'mappingSha256': digest(binder.encoded(mapping)),
                    'runnerSource': runner_binding, 'binderUtilsSource': binder_binding,
                    'sourcePathsMappedWithoutFabrication': True, 'sourceFilesModified': False,
                    'currentStatusOrDocsModified': False, 'productModified': False,
                    'scope': 'Exact prior frozen-evidence byte archive. It does not certify new visual matrix, screenshot pixels, aesthetics, performance or human acceptance.',
                    'mapping': mapping}
        write_new(OUTPUT / 'manifest.json', manifest)
        expected_archive_set = sorted(['archive-runner-source.py', 'archive-binder-utils-source.py',
                                       'source-before.json', 'source-after.json', 'content-file-set.json', 'manifest.json']
                                      + ['files/' + name for name in sorted(expected)])
        if file_set(OUTPUT) != expected_archive_set:
            raise ValueError('Archive overall file-set has unexpected entries.')
        # Final source read follows manifest creation and full archive readback.
        source_final = [binder.binding(binder.regular(ROOT / name), (ROOT / name).read_bytes()) for name in sorted(expected)]
        if source_final != source_before:
            raise ValueError('Source changed at final archive readback.')
        manifest_binding = binder.binding(OUTPUT / 'manifest.json', (OUTPUT / 'manifest.json').read_bytes())
        result = {'schemaVersion': 1, 'startedAt': started, 'finishedAt': now(), 'exitCode': 0,
                  'argv': sys.argv, 'cwd': str(Path.cwd()), 'archive': str(OUTPUT),
                  'contentFileCount': len(mapping), 'contentBytes': manifest['contentBytes'],
                  'overallFileCount': len(expected_archive_set),
                  'overallBytes': sum(path.stat().st_size for path in OUTPUT.rglob('*') if path.is_file()),
                  'manifest': manifest_binding, 'mappingSha256': manifest['mappingSha256'],
                  'sourceFileSetSha256': manifest['sourceFileSetSha256'],
                  'sourceFinalListSha256': digest(binder.encoded(source_final)),
                  'all4259SourceBindingsStillExact': True, 'all4259ArchiveCopiesExact': True,
                  'sourceBeforeAfterFinalExact': True, 'archiveFileSetExact': True,
                  'sourceFilesModified': False, 'newMatrixCollectorOrAuditModified': False,
                  'currentStatusOrDocsModified': False, 'productModified': False}
        write_new(RESULT, result)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0
    except Exception as error:
        failure = {'schemaVersion': 1, 'startedAt': started, 'finishedAt': now(), 'exitCode': 1,
                   'error': str(error), 'archivePreservedForReview': str(OUTPUT),
                   'sourceFilesModified': False, 'currentStatusOrDocsModified': False}
        write_new(RESULT, failure)
        print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
