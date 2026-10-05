#!/usr/bin/env python3
"""Package an already copied current case; never reread the live store.

The actual browser operator copied the saved envelope at capture time and
declared its exact source/snapshot/time/hash in raw JSON and a sidecar. This
adapter verifies those bytes against the exact observed export artifact and
the frozen formal matrix. It does not control/request a browser or grant
native provenance, image, publication, performance or human acceptance.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path

WORK = Path(__file__).resolve().parent
specification = importlib.util.spec_from_file_location('frozen_boundary_workflow', WORK / 'capture_workflow.py')
workflow = importlib.util.module_from_spec(specification)
specification.loader.exec_module(workflow)
formal = workflow.formal
GUARD = WORK / 'copied-case-guard.json'


def guarded() -> list[tuple[Path, bytes]]:
    guard_input = formal.frozen(GUARD)
    guard = formal.decoded(guard_input[1], 'copied-case wrapper guard')
    inputs = [guard_input]
    for item in guard['frozenInputs']:
        frozen_input = formal.frozen(Path(item['path']))
        if formal.binding(*frozen_input) != item:
            raise ValueError(f'Frozen copied-case preparation input changed: {item["path"]}')
        inputs.append(frozen_input)
    inputs.extend(workflow.guarded())
    formal.recheck(inputs)
    return inputs


def package(raw_path: Path, scene_path: Path, screenshot_path: Path, saved_envelope: Path) -> dict:
    inputs = guarded()
    actual_inputs = [formal.frozen(path) for path in
                     (raw_path, scene_path, screenshot_path, saved_envelope,
                      Path(str(saved_envelope) + '.receipt.json'))]
    inputs.extend(actual_inputs)
    raw = formal.decoded(actual_inputs[0][1], 'actual raw capture observation')
    case = raw.get('caseId')
    if not isinstance(case, str) or not formal.SAFE_CASE.fullmatch(case):
        raise ValueError('The current raw observation requires a safe caseId.')
    if raw.get('studioUrl') != workflow.ORIGIN + '/':
        raise ValueError('Current matrix observations must use the isolated 8906 origin.')
    snapshot_observation = formal.obj(raw.get('actualStoredEnvelope'), 'actual already-copied envelope observation')
    sidecar = formal.decoded(actual_inputs[4][1], 'actual already-copied envelope sidecar')
    if sidecar != snapshot_observation:
        raise ValueError('Raw snapshot facts must equal the exact copied-envelope sidecar.')
    if (snapshot_observation.get('sha256') != formal.sha(actual_inputs[3][1])
            or type(snapshot_observation.get('bytes')) is not int
            or snapshot_observation['bytes'] != len(actual_inputs[3][1])):
        raise ValueError('The copied envelope sidecar must bind the exact saved bytes.')
    envelope = formal.decoded(actual_inputs[3][1], 'actual saved-envelope copy')
    document = formal.obj(envelope.get('document'), 'actual saved Canvas')
    binding = formal.obj(raw.get('documentBinding'), 'actual DOM document binding')
    document_id = binding.get('documentId')
    if not isinstance(document_id, str) or not formal.SAFE_DOCUMENT.fullmatch(document_id):
        raise ValueError('The current DOM document identity must name the exact copied envelope.')
    if document.get('id') != document_id or document.get('revision') != binding.get('revision'):
        raise ValueError('Copied saved Canvas identity/revision differs from the actual DOM.')
    source = workflow.STORE / (document_id + '.json')
    if (not isinstance(snapshot_observation.get('observedSourcePath'), str)
            or Path(snapshot_observation['observedSourcePath']).absolute() != source.absolute()
            or not isinstance(snapshot_observation.get('snapshotPath'), str)
            or Path(snapshot_observation['snapshotPath']).absolute() != actual_inputs[3][0]):
        raise ValueError('Snapshot facts must name the exact known store/document and exact supplied saved copy.')
    formal.timezone_timestamp(snapshot_observation.get('copiedAt'), 'actual file copiedAt')
    output = WORK / 'cases' / case
    if output.exists():
        raise ValueError('Case output already exists; preserve it and use a fresh case.')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.copied-boundary-case-', dir=output.parent))
    try:
        result = formal.prepare_case(workflow.MATRIX, workflow.STORE, actual_inputs[0][0],
                                     actual_inputs[1][0], actual_inputs[2][0],
                                     temporary / 'prepared', actual_inputs[3][0])
        wrapper_receipt = {'schemaVersion':1, 'protocol':'archcanvas-boundary-copied-case-package/1',
                           'caseId':case, 'createdAt':workflow.now(),
                           'inputBindings':[formal.binding(*item) for item in inputs],
                           'actualStoredEnvelope':snapshot_observation,
                           'fullSavedAndExportCanvasEquality':True,
                           'liveStoreReread':False, 'replacementExportSearch':'not-attempted',
                           'browserOperationExecuted':False, 'exportRequestExecuted':False,
                           'humanAcceptanceCertified':False,
                           'scope':'Already copied operator snapshot and exact export local-byte consistency only.'}
        workflow.emit(temporary / 'prepared' / 'package-copied-case-receipt.json', formal.encode(wrapper_receipt))
        formal.recheck(inputs)
        if output.exists():
            raise ValueError('Case output appeared during validation; refusing replacement.')
        (temporary / 'prepared').rename(output)
        temporary.rmdir()
        return {'caseId':case, 'caseDirectory':str(output),
                'fullSavedAndExportCanvasEquality':True, 'liveStoreReread':False,
                'matrixSpecDigest':result['matrixSpecDigest'],
                'helperReceipt':formal.binding(*formal.frozen(output / 'case-helper.json')),
                'wrapperReceipt':formal.binding(*formal.frozen(output / 'package-copied-case-receipt.json')),
                'humanAcceptanceCertified':False}
    except Exception:
        shutil.rmtree(temporary)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,required=True)
    parser.add_argument('--browser-scene',type=Path,required=True)
    parser.add_argument('--screenshot',type=Path,required=True)
    parser.add_argument('--saved-envelope',type=Path,required=True)
    args = parser.parse_args()
    try:
        result = package(args.raw,args.browser_scene,args.screenshot,args.saved_envelope)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (OSError,ValueError,TypeError,KeyError) as error:
        parser.exit(1,str(error)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
