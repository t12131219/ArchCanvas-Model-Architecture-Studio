#!/usr/bin/env python3
"""Finalize preserved copies after attempt 1 failed on sorting, without overwrite."""
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
RESULT = WORK / 'archive-before-matrix-attempt-2.json'
spec = importlib.util.spec_from_file_location('au3_archive_utils_attempt2', WORK / 'bind_case.py')
binder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binder)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_new(path, raw):
    with path.open('xb') as handle:
        handle.write(raw if isinstance(raw, bytes) else binder.encoded(raw))


def read_binding(path):
    return binder.binding(binder.regular(path), path.read_bytes())


def file_set(directory):
    return sorted(str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file())


def main():
    started = now()
    if RESULT.exists() or not OUTPUT.exists() or (OUTPUT / 'manifest.json').exists():
        raise ValueError('Finalizer output exists or preserved attempt 1 absent; no overwrite.')
    try:
        runner = Path(__file__).absolute()
        write_new(OUTPUT / 'archive-finalizer-attempt-2.py', runner.read_bytes())
        failure = WORK / 'archive-before-matrix-attempt-1.json'
        write_new(OUTPUT / 'archive-failed-attempt-1.json', failure.read_bytes())
        seal_bytes, final_bytes = SEAL.read_bytes(), FINAL.read_bytes()
        seal, final = json.loads(seal_bytes), json.loads(final_bytes)
        if final['seal'] != binder.binding(SEAL, seal_bytes):
            raise ValueError('Old final/seal byte binding changed.')
        expected, origins = {}, {}
        for label, records in (('old-seal-4233', seal['bindings']), ('old-final-readback-supplemental-24', final['supplementalBindings'])):
            for row in records:
                name = row['path']
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise ValueError('Unsafe/nonproject actual source path.')
                if name in expected and expected[name] != row:
                    raise ValueError('Incompatible duplicate source binding.')
                expected[name] = row
                origins.setdefault(name, []).append(label)
        for path, raw, label in ((SEAL, seal_bytes, 'old-seal-itself'), (FINAL, final_bytes, 'old-final-readback-itself')):
            name = binder.relative(path)
            expected[name] = binder.binding(path, raw)
            origins.setdefault(name, []).append(label)
        if len(expected) != 4259 or seal['bindingCount'] != 4233 or final['supplementalBindingCount'] != 24:
            raise ValueError('Old input union/count differs.')
        actual_set = file_set(OUTPUT / 'files')
        if actual_set != sorted(expected):
            raise ValueError('Actual copied path-set differs from source union.')
        original_before = json.loads((OUTPUT / 'source-before.json').read_bytes())
        source_before, mapping = [], []
        for name in sorted(expected):
            source = binder.regular(ROOT / name)
            if not source.resolve().is_relative_to(ROOT):
                raise ValueError('Source escapes formal project.')
            source_row = read_binding(source)
            archived = binder.regular(OUTPUT / 'files' / name)
            archived_row = read_binding(archived)
            if source_row != expected[name] or any(archived_row[k] != source_row[k] for k in ('bytes', 'sha256')):
                raise ValueError(f'Actual source or preserved copy mismatch: {name}')
            source_before.append(source_row)
            mapping.append({'sourcePath': name, 'archivePath': 'files/' + name,
                            'bytes': source_row['bytes'], 'sha256': source_row['sha256'],
                            'sourceBindingOrigins': origins[name], 'byteExact': True})
        if source_before != original_before:
            raise ValueError('Source differs from attempt 1 pre-copy inventory.')
        write_new(OUTPUT / 'source-before-attempt-2.json', source_before)
        source_after = [read_binding(ROOT / name) for name in sorted(expected)]
        if source_after != source_before:
            raise ValueError('Source changed during full attempt 2 readback.')
        write_new(OUTPUT / 'source-after.json', source_after)
        write_new(OUTPUT / 'content-file-set.json', actual_set)
        manifest = {'schemaVersion': 1, 'protocol': 'archcanvas-exact-prior-evidence-union-archive/1',
                    'startedAt': started, 'finishedAt': now(), 'attempt': 2,
                    'priorAttempt': {'receipt': read_binding(failure),
                                     'reason': 'Path object ordering differs from string path ordering. Actual copied file-set was complete; no source/copy byte failure was found.',
                                     'originalCopiesPreserved': True},
                    'sourceRoot': str(ROOT), 'archiveRoot': str(OUTPUT),
                    'seal': binder.binding(SEAL, seal_bytes), 'finalReceipt': binder.binding(FINAL, final_bytes),
                    'sealBindingCount': 4233, 'supplementalBindingCount': 24, 'addedSelfExcludedFiles': 2,
                    'contentFileCount': len(mapping), 'contentBytes': sum(r['bytes'] for r in mapping),
                    'fileSetExact': True, 'sourceBeforeAfterExact': True, 'attempt1SourceBeforeStillExact': True,
                    'sourceBeforeListSha256': digest(binder.encoded(source_before)),
                    'sourceAfterListSha256': digest(binder.encoded(source_after)),
                    'sourceFileSetSha256': digest(binder.encoded(actual_set)),
                    'mappingSha256': digest(binder.encoded(mapping)),
                    'finalizerSource': read_binding(OUTPUT / 'archive-finalizer-attempt-2.py'),
                    'originalRunnerSource': read_binding(OUTPUT / 'archive-runner-source.py'),
                    'sourcePathsMappedWithoutFabrication': True, 'sourceFilesModified': False,
                    'currentStatusOrDocsModified': False, 'productModified': False,
                    'scope': 'Exact prior frozen evidence byte archive only. No new screenshot pixel, visual, physical readability, human, or performance acceptance.',
                    'mapping': mapping}
        write_new(OUTPUT / 'manifest.json', manifest)
        expected_archive_set = sorted(['archive-runner-source.py', 'archive-binder-utils-source.py', 'source-before.json',
                                       'archive-finalizer-attempt-2.py', 'archive-failed-attempt-1.json',
                                       'source-before-attempt-2.json', 'source-after.json', 'content-file-set.json', 'manifest.json']
                                      + ['files/' + name for name in sorted(expected)])
        if file_set(OUTPUT) != expected_archive_set:
            raise ValueError('Complete archive file-set differs.')
        archive_bindings = [read_binding(OUTPUT / name) for name in expected_archive_set]
        # Final read is after all archive metadata files and the whole archive inventory.
        source_final = [read_binding(ROOT / name) for name in sorted(expected)]
        if source_final != source_before:
            raise ValueError('Source changed at final source readback.')
        result = {'schemaVersion': 1, 'startedAt': started, 'finishedAt': now(), 'exitCode': 0,
                  'argv': sys.argv, 'cwd': str(Path.cwd()), 'archive': str(OUTPUT), 'attempt': 2,
                  'contentFileCount': len(mapping), 'contentBytes': manifest['contentBytes'],
                  'overallFileCount': len(archive_bindings), 'overallBytes': sum(r['bytes'] for r in archive_bindings),
                  'manifest': read_binding(OUTPUT / 'manifest.json'),
                  'mappingSha256': manifest['mappingSha256'], 'sourceFileSetSha256': manifest['sourceFileSetSha256'],
                  'archiveFileSetSha256': digest(binder.encoded(expected_archive_set)),
                  'archiveBindingListSha256': digest(binder.encoded(archive_bindings)),
                  'sourceFinalListSha256': digest(binder.encoded(source_final)),
                  'sourceFinalStillMatchesAttempt1Before': True, 'all4259SourceBindingsStillExact': True,
                  'all4259ArchiveCopiesExact': True, 'sourceBeforeAfterFinalExact': True, 'archiveFileSetExact': True,
                  'archiveBindings': archive_bindings,
                  'sourceFilesModified': False, 'newMatrixCollectorOrAuditModified': False,
                  'currentStatusOrDocsModified': False, 'productModified': False}
        write_new(RESULT, result)
        print(json.dumps({k: v for k, v in result.items() if k != 'archiveBindings'}, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        write_new(RESULT, {'schemaVersion': 1, 'startedAt': started, 'finishedAt': now(), 'exitCode': 1,
                          'error': str(error), 'archivePreservedForReview': str(OUTPUT)})
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
