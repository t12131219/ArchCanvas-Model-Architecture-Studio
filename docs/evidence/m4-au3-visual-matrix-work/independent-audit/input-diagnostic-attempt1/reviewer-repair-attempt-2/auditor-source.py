"""Independent read-only au3 diagnostic review; does not run the validator/product."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import traceback
import ast
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
WORK = OUT.parent.parent / 'input-diagnostic'
NS = '{http://www.w3.org/2000/svg}'
CACHE = {}


def read(path):
    path = Path(path).absolute()
    raw = path.read_bytes()
    assert path not in CACHE or CACHE[path] == raw, f'Input changed: {path}'
    CACHE[path] = raw
    return raw


def load(path):
    return json.loads(read(path))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def binding(path, raw):
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(raw), 'sha256': sha(raw)}


def verify(record):
    raw = read(ROOT / record['path'])
    assert len(raw) == record['bytes'] and sha(raw) == record['sha256'], record['path']
    return raw


def p95(values):
    return sorted(values)[math.ceil(len(values) * .95) - 1] if values else None


def cadence(frames):
    intervals = [b['at'] - a['at'] for a, b in zip(frames, frames[1:])]
    return {'frames': len(frames), 'intervalP95Ms': p95(intervals),
            'maxIntervalMs': max(intervals) if intervals else None,
            'fps': (len(frames) - 1) * 1000 / (frames[-1]['at'] - frames[0]['at']) if intervals else None}


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9), (a, b)


def without_revision(svg):
    return re.sub(r'("revision":)\d+', r'\g<1>REV',
                  re.sub(r'data-revision="\d+"', 'data-revision="REV"', svg))


def geometry(g):
    svg = ET.fromstring(g['svgMarkup'])
    metadata = json.loads(svg.find(NS + 'metadata').text)
    assert metadata['documentId'] == g['documentId'] and metadata['revision'] == g['revision']
    assert metadata['sourceDigest'] == g['sourceDigest'] and metadata['irDigest'] == g['irDigest']
    bodies = {}
    for element in svg.iter():
        if element.get('data-canonical-id'):
            rectangles = [child for child in element if child.tag == NS + 'rect']
            assert rectangles
            bodies[element.get('data-node-id')] = {k: float(rectangles[-1].get(k)) for k in ('x','y','width','height')}
    assert sorted(bodies) == sorted(g['visibleIds'])
    assert sorted(bodies) == sorted(node['sceneNodeId'] for node in metadata['renderedNodes'])
    for identity, obj in g['objects'].items():
        if obj is None:
            continue
        assert obj['canvas'] == bodies[identity]
        rect, matrix = obj['canvas'], obj['screenMatrix']
        corners = [(rect['x'],rect['y']), (rect['x']+rect['width'],rect['y']),
                   (rect['x'],rect['y']+rect['height']), (rect['x']+rect['width'],rect['y']+rect['height'])]
        transformed = [(matrix['a']*x+matrix['c']*y+matrix['e'], matrix['b']*x+matrix['d']*y+matrix['f']) for x,y in corners]
        expected = {'x': min(x for x,y in transformed), 'y': min(y for x,y in transformed),
                    'width': max(x for x,y in transformed)-min(x for x,y in transformed),
                    'height': max(y for x,y in transformed)-min(y for x,y in transformed)}
        for key in expected:
            assert abs(expected[key]-obj['screen'][key]) < .001
        s,v = obj['screen'],g['viewport']
        intersects = s['x']+s['width'] > v['x'] and s['x'] < v['x']+v['width'] and s['y']+s['height'] > v['y'] and s['y'] < v['y']+v['height']
        assert intersects == obj['intersectsViewport']
    return bodies


def audit():
    raw_path = WORK / 'full-observer-raw-chunked.json'
    raw = read(raw_path)
    r = json.loads(raw)
    output = load(WORK / 'validation-attempt-1/stdout.json')
    command = load(WORK / 'validation-attempt-1/command-receipt.json')
    assert command['exitCode'] == 0 and command['cwd'] == str(ROOT) and command['inputBytesUnchanged'] is True
    for record in command['inputs'] + command['outputs']:
        verify(record)
    assert read(WORK / 'validation-attempt-1/stderr.log') == b''
    assert command['argv'][1] == str(ROOT / 'scripts/validate_input_observation.mjs')
    assert command['argv'][2] == str(raw_path)
    assert output['status'] == 'validated-engineering-observation'
    assert r['protocol'] == 'archcanvas-input-observation/2' and r['schemaVersion'] == 2
    assert r['measurement']['runtimeAccess'] == 'DOM-only'
    assert r['measurement']['continuousInput'] == 'observed-geometry-proxy-not-paint'
    assert r['measurement']['frames'] == 'raf-callback-cadence-not-presented-frames'
    assert r['harness']['productInputsDispatched'] is False and r['harness']['productHiddenStateRead'] is False
    assert r['harness']['humanParticipants'] == 0
    assert r['context']['formalStudioUnmodified'] is True
    for record in r['context']['productionAssets'] + r['context']['probeSources']:
        verify(record)
    assert r['environment']['scripts'] == ['http://127.0.0.1:33057/assets/index-au3IB_0Q.js']
    assert r['environment']['url'] == 'http://127.0.0.1:33057/'
    assert r['environment']['topUrl'] == 'http://127.0.0.1:33057/__m4/' and r['environment']['isIframe'] is True
    assert r['environment']['viewport'] == {'width':1280,'height':720,'devicePixelRatio':1}
    assert r['environment']['fonts'] == {'status':'loaded','loadedFaces':[]}
    assert r['environment']['supported']['eventTimingObserved'] and r['environment']['supported']['longTasksObserved']
    chunks = load(WORK / 'raw-read-chunked.receipt.json')
    length_utf16 = len(raw.decode().encode('utf-16-le')) // 2
    assert chunks['bytes'] == len(raw) and chunks['sha256'] == sha(raw)
    assert chunks['publicTextLength'] == chunks['receivedTextLength'] == length_utf16 == 9177272
    assert chunks['chunks'] == math.ceil(length_utf16/chunks['chunkSize']) == 92
    assert chunks['source'] == 'readonly public textarea value' and chunks['wholeReadFailurePreserved'] is True
    truncated = read(WORK / 'full-observer-raw.json')
    failure = load(WORK / 'raw-read-truncation-attempt-1.json')
    assert len(truncated.decode().encode('utf-16-le')) // 2 == failure['receivedStringLength'] == 200011
    try:
        json.loads(truncated)
        raise AssertionError('Expected preserved transport truncation failure')
    except json.JSONDecodeError:
        pass
    assert failure['observedTextLength'] == length_utf16
    for name, buffer in r['buffers'].items():
        values = r
        for component in name.split('.'):
            values = values[component]
        assert buffer['dropped'] == 0 and len(values) <= buffer['limit']
    assert r['errors'] == [] and output['completeBuffers'] and output['dropped'] == [] and output['errors'] == []
    # Build both sides of the candidate graph from all trusted discrete inputs,
    # including unassigned inputs. Only assigned trials enter the eligible denominator.
    types = {'pointerdown','pointerup','click','keydown','keyup'}
    possible = [event for event in r['events'] if event['trusted'] and event['type'] in types and event['target']['token']]
    candidates, entry_inputs = {}, {}
    for event in possible:
        indices = [i for i,entry in enumerate(r['eventTiming']) if entry['interactionId'] > 0 and entry['name'] == event['type'] and
                   entry['targetToken'] == event['target']['token'] and abs(entry['startAt']-event['eventAt']) <= 8]
        candidates[event['id']] = indices
        for index in indices:
            entry_inputs.setdefault(index,[]).append(event['id'])
    matches = []
    for event in possible:
        if not event['trialId']:
            continue
        indices = candidates[event['id']]
        index = indices[0] if len(indices)==1 and len(entry_inputs[indices[0]])==1 else None
        entry = r['eventTiming'][index] if index is not None else None
        matches.append({'inputId':event['id'],'trialId':event['trialId'],'nativeEntryIndex':index,
                        'nativeDurationMs':entry['durationMs'] if entry else None,
                        'interactionId':entry['interactionId'] if entry else None,
                        'inputCandidateCount':len(indices),
                        'candidateEntryInputCounts':[{'nativeEntryIndex':i,'inputs':len(entry_inputs[i])} for i in indices],
                        'missingReason':None if entry else 'ambiguous' if indices else 'unavailable-below-threshold-detached-or-truncated'})
    assert matches == output['latency']['matches']
    interactions = {}
    for match in matches:
        if match['interactionId'] is not None:
            interactions[match['interactionId']] = max(match['nativeDurationMs'], interactions.get(match['interactionId'],0))
    assert len(matches) == output['latency']['eligibleDiscreteInputs'] == 14
    assert sum(m['nativeEntryIndex'] is not None for m in matches) == output['latency']['matchedDiscreteInputs'] == 10
    assert len(interactions) == output['latency']['matchedInteractions'] == 4
    assert p95(list(interactions.values())) == output['latency']['matchedInteractionP95Ms'] == 3000
    frame_stats = cadence(r['frames'])
    for key in frame_stats:
        close(frame_stats[key], output['frameCadence'][key])
    idle = [b['at']-a['at'] for a,b in zip(r['frames'],r['frames'][1:]) if a['trialId'] is None and b['trialId'] is None]
    assert len(idle) == output['idleCadence']['intervals'] == 314
    close(p95(idle),output['idleCadence']['intervalP95Ms'])
    close(len(idle)*1000/sum(idle),output['idleCadence']['fps'])
    for category, values in r['overhead'].items():
        stats = output['observerSelfCost'][category]
        assert stats['samples'] == len(values)
        close(stats['p95Ms'],p95([v['durationMs'] for v in values]))
        close(stats['maxMs'],max(v['durationMs'] for v in values))
    trials = r['trials']
    assert len(trials) == len(output['trials']) == 6
    assert [t['spec']['operation'] for t in trials] == ['toggle','toggle','pan','drag','undo','redo']
    events = {event['id']:event for event in r['events']}
    first = trials[0]
    assert first['status'] == 'no-input' and first['before'] is None
    assert not [e for e in r['events'] if e['trialId']==first['id']]
    assert not [f for f in r['frames'] if f['trialId']==first['id']]
    assert first['after']['objects'][first['spec']['targetIds'][0]] is None
    assert first['spec']['targetIds'][0] not in first['after']['visibleIds']
    assert not output['trials'][0]['observed'] and not output['trials'][0]['operationSucceeded']
    geometry(r['bindingAtStart'])
    before_bodies, after_bodies = {}, {}
    source_raw = read(ROOT / 'fixtures/stress_300/model.py')
    source_text = source_raw.decode()
    aggregate = json.dumps([{'path':'model.py','digest':sha(source_raw)}],sort_keys=True,separators=(',',':')).encode()
    assert sha(aggregate) == r['bindingAtStart']['sourceDigest']
    source_tree = ast.parse(source_text)
    source_segments = {(node.lineno,node.end_lineno,ast.get_source_segment(source_text,node))
                       for node in ast.walk(source_tree) if hasattr(node,'lineno') and hasattr(node,'end_lineno')}
    source_metadata = json.loads(ET.fromstring(r['bindingAtStart']['svgMarkup']).find(NS+'metadata').text)
    assert len(source_metadata['sourceFacts'])==304
    for fact in source_metadata['sourceFacts']:
        loc=fact['source']
        assert loc['path']=='model.py' and (loc['line'],loc['endLine'],loc['expression']) in source_segments
    for index,t in enumerate(trials[1:],1):
        assert t['status'] == 'finished' and output['trials'][index]['operationSucceeded']
        before, after = t['before'],t['after']
        before_bodies[t['id']],after_bodies[t['id']] = geometry(before),geometry(after)
        assert before['documentId'] == after['documentId'] == r['bindingAtStart']['documentId']
        assert before['sourceDigest'] == after['sourceDigest'] == r['bindingAtStart']['sourceDigest']
        assert before['irDigest'] == after['irDigest'] == r['bindingAtStart']['irDigest']
        selected_events = [e for e in r['events'] if e['trialId']==t['id']]
        assert t['firstEventId']==selected_events[0]['id'] and t['lastEventId']==selected_events[-1]['id']
        assert all(e['trusted'] and t['armedAt']<=e['capturedAt']<=t['finishedAt'] for e in selected_events)
        delta = after['revision']-before['revision']
        assert delta == (0 if t['spec']['operation']=='pan' else 1)
        assert delta == output['trials'][index]['revisionDelta']
        start = events[t['firstEventId']]
        downs = [e for e in selected_events if e['type']=='pointerdown']
        ups = [e for e in selected_events if e['type']=='pointerup' and e['pointerId']==downs[0]['pointerId']]
        assert len(downs)==len(ups)==1
        # Release/control-focus events after the pointer-up are outside the
        # held interval. They remain observed, rather than causing a false
        # cancellation or being erased from the evidence.
        held=selected_events[:selected_events.index(ups[0])]
        assert not any(e['type'] in ['pointercancel','blur'] for e in held)
        assert not any(e['type']=='lostpointercapture' and e['pointerId']==downs[0]['pointerId'] for e in held)
        if t['spec']['operation']=='toggle':
            target=t['spec']['targetIds'][0]
            assert start['target']['kind']=='toggle' and start['target']['nodeId']==target
            assert target not in before['expandedIds'] and target in after['expandedIds']
            assert len(before['visibleIds'])==4 and len(after['visibleIds'])==304
            assert before['camera']==after['camera']
        elif t['spec']['operation']=='pan':
            target=start['target']
            assert target['inCanvas'] and not target['editingTarget'] and not target['canvasControl']
            assert target['canvasTool']=='pan' and target['handToolPressed'] is True
            assert before['svgMarkup']==after['svgMarkup'] and before['visibleIds']==after['visibleIds']
            assert before['expandedIds']==after['expandedIds'] and before['selectionMarkup']==after['selectionMarkup']
            expected=before['camera']['matrix'].copy()
            for scalar,coordinate in [('e','x'),('f','y')]:
                expected[scalar] += (ups[0][coordinate]-ups[0]['viewport'][coordinate])-(downs[0][coordinate]-downs[0]['viewport'][coordinate])
            assert expected==after['camera']['matrix']==output['trials'][index]['panTerminal']['expectedCamera']
        else:
            target=t['spec']['targetIds'][0]
            assert before['camera']==after['camera'] and before['visibleIds']==after['visibleIds'] and before['expandedIds']==after['expandedIds']
            moved=[after['objects'][target]['canvas'][k]-before['objects'][target]['canvas'][k] for k in ('x','y')]
            assert moved==([-32,0] if t['spec']['operation']=='undo' else [32,0])
            assert all(before_bodies[t['id']][identity]==after_bodies[t['id']][identity] for identity in before_bodies[t['id']] if identity!=target)
            if t['spec']['operation']=='drag':
                assert start['target']['nodeId']==target and start['target']['kind']=='node' and start['target']['canvasTool']=='select'
                s=before['objects'][target]['screen']
                assert s['x']<start['x']<s['x']+s['width'] and s['y']<start['y']<s['y']+s['height']
                assert math.floor((ups[0]['x']-downs[0]['x'])/before['camera']['matrix']['a']/4+.5)*4==32
            else:
                assert start['target']['action']==t['spec']['operation']
    assert without_revision(trials[3]['before']['svgMarkup'])==without_revision(trials[4]['after']['svgMarkup'])
    assert without_revision(trials[3]['after']['svgMarkup'])==without_revision(trials[5]['after']['svgMarkup'])
    # Bind every new diagnostic artifact and retain failed transport material;
    # file hashes do not upgrade root capture provenance to human/native-paint proof.
    for path in sorted(WORK.rglob('*')):
        if path.is_file():
            read(path)
    return {'commandReceiptExact':True,'validatorExitCode':0,'validatorRerunByAuditor':False,
            'rawBytes':len(raw),'rawSha256':sha(raw),'chunkedPublicUtf16LengthExact':length_utf16,
            'preservedTruncatedRead':{'bytes':len(truncated),'utf16Length':200011,'jsonParseFailed':True,'countedAsSuccess':False},
            'contextAssetsAndProbeSourcesExact':len(r['context']['productionAssets'])+len(r['context']['probeSources']),
            'sourceFixtureBinding':binding(ROOT/'fixtures/stress_300/model.py',source_raw),
            'sourceDigestRecomputed':sha(aggregate),'sourceFactAstExpressionBindingsChecked':304,
            'newEnvironmentObservedForThisHarnessOnly':r['environment'],
            'oldMatrixEnvironmentReceiptsRewritten':False,'fontsResolvedFacesCertified':False,
            'allBufferDroppedCountsZero':True,'matchingGraphTrustedDiscreteInputs':len(possible),
            'assignedEligibleInputs':14,'matchedInputs':10,'unmatchedAssignedInputs':4,
            'interactionMaxDurations':interactions,'interactionNearestRankP95Ms':3000,
            'matcherUsesAllInputsForTwoSidedUniqueCandidates':True,'frameCadence':frame_stats,
            'idleCadence':output['idleCadence'],'selfCostStatisticsRecomputed':True,
            'trials':6,'successfulTrials':5,'wrongTargetNoInputNotCountedSuccess':True,
            'expandedRenderedMembership':304,'allRenderedNodesInsideViewportCertified':False,
            'panTerminalCameraAndPublicSvgContinuityMatched':True,
            'dragUndoRedoWorldDeltas':[[32,0],[-32,0],[32,0]],
            'undoRedoWholeSvgExactExceptRevision':True,'unrelatedBodiesUnchanged':True,
            'observerRecordedTrustedEvents':True,'independentNativeOsProvenanceCertified':False,
            'humanParticipants':0,'presentedPaintCertified':False,'completePageInpCertified':False,
            'performanceThresholdPassed':False,'causeOfSlowCadenceIdentified':False,
            'scope':'Only new artifacts/context, independent numerical denominator/matching/p95/rAF and committed public geometry/history review. No validator/product/model/build/browser execution; rAF is callback cadence and continuous observations are noncausal DOM proxies.'}


def main():
    source=read(Path(__file__))
    result={'protocol':'archcanvas-au3-independent-input-diagnostic-review/1',
            'startedAt':datetime.now(timezone.utc).isoformat(),'testsRun':False,'validatorRun':False,
            'modelsRun':False,'buildRun':False,'browserOperated':False,
            'auditorSource':binding(Path(__file__).absolute(),source)}
    try:
        result['diagnostic']=audit()
        result['status']='passed-with-stated-scope'
    except Exception as error:
        result['status']='audit-failed';result['error']=str(error);result['traceback']=traceback.format_exc()
    before=[binding(path,raw) for path,raw in sorted(CACHE.items())]
    after=[binding(path,path.read_bytes()) for path in sorted(CACHE)]
    result.update({'inputsBefore':before,'inputsAfter':after,'inputsUnchanged':before==after,
                   'finishedAt':datetime.now(timezone.utc).isoformat()})
    if before!=after:result['status']='audit-failed-input-changed'
    raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
    destination=OUT/'reviewer-repair-attempt-2'
    destination.mkdir()
    (destination/'auditor-source.py').open('xb').write(source)
    (destination/'report.json').open('xb').write(raw)
    print(json.dumps({'report':binding(destination/'report.json',raw),'status':result['status'],
                      'inputs':len(CACHE),'unchanged':before==after,'error':result.get('error')},ensure_ascii=False))
    return 0 if result['status']=='passed-with-stated-scope' else 1


if __name__=='__main__':
    raise SystemExit(main())
