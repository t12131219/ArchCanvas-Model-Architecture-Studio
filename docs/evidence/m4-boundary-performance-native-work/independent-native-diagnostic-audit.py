#!/usr/bin/env python3
"""Independent, read-only arithmetic audit of the native observer receipt."""
from __future__ import annotations
import argparse, hashlib, json, math, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def p95(values):
    return sorted(values)[math.ceil(len(values) * .95) - 1] if values else None

def audit(raw_path: Path, validator_stdout: Path, validator_stderr: Path, validator_exit: int):
    raw_bytes = raw_path.read_bytes()
    report = json.loads(raw_bytes)
    assert report['schemaVersion'] == 2 and report['protocol'] == 'archcanvas-input-observation/2'
    assert report['measurement']['runtimeAccess'] == 'DOM-only'
    assert report['measurement']['latency'] == 'matched-discrete-event-timing-only'
    assert report['measurement']['continuousInput'] == 'observed-geometry-proxy-not-paint'
    assert report['measurement']['frames'] == 'raf-callback-cadence-not-presented-frames'
    assert report['environment']['viewport'] == {'width': 1280, 'height': 720, 'devicePixelRatio': 1}
    assert report['environment']['isIframe'] is True
    assert report['harness']['productInputsDispatched'] is False
    assert report['harness']['productHiddenStateRead'] is False
    assert report['harness']['humanParticipants'] == 0
    assert report['buffers'] and all(v['dropped'] == 0 for v in report['buffers'].values())
    events = report['events']; timing = report['eventTiming']
    event_map = {e['id']: e for e in events}
    assert len(event_map) == len(events)
    discrete = {'pointerdown', 'pointerup', 'click', 'keydown', 'keyup'}
    inputs = [e for e in events if e['trusted'] and e['type'] in discrete and e['target']['token']]
    candidates, reverse = {}, {}
    for e in inputs:
        indexes = [i for i, n in enumerate(timing)
                   if n['interactionId'] > 0 and n['name'] == e['type']
                   and n['targetToken'] == e['target']['token']
                   and abs(n['startAt'] - e['eventAt']) <= 8]
        candidates[e['id']] = indexes
        for i in indexes: reverse.setdefault(i, []).append(e['id'])
    matched = []
    for e in inputs:
        indexes = candidates[e['id']]
        if len(indexes) == 1 and len(reverse[indexes[0]]) == 1:
            n = timing[indexes[0]]
            matched.append({'inputId': e['id'], 'trialId': e['trialId'], 'nativeEntryIndex': indexes[0],
                            'interactionId': n['interactionId'], 'durationMs': n['durationMs']})
    matched_trial = [m for m in matched if m['trialId'] is not None]
    interactions = {}
    for m in matched_trial:
        interactions[m['interactionId']] = max(m['durationMs'], interactions.get(m['interactionId'], 0))
    frames = report['frames']; intervals = [b['at'] - a['at'] for a, b in zip(frames, frames[1:])]
    idle = [b['at'] - a['at'] for a, b in zip(frames, frames[1:]) if a['trialId'] is None and b['trialId'] is None]
    trials = []
    for t in report['trials']:
        trial_inputs = [e for e in events if e['trialId'] == t['id']]
        no_input = t['status'] == 'no-input'
        # Successful committed operations are represented by the raw trial's public
        # geometry/DOM facts and the checked validator output; this arithmetic audit
        # deliberately does not infer paint or hidden history.
        if no_input:
            success = False
        else:
            before, after = t['before'], t['after']
            success = (after['documentId'] == before['documentId'] and
                       after['sourceDigest'] == before['sourceDigest'] and
                       after['irDigest'] == before['irDigest'] and
                       (t['spec']['operation'] in ('toggle', 'drag', 'undo', 'redo') and after['revision'] == before['revision'] + 1 or
                        t['spec']['operation'] == 'pan' and after['revision'] == before['revision']))
        trials.append({'id': t['id'], 'operation': t['spec']['operation'], 'status': t['status'],
                       'rawInputCount': len(trial_inputs), 'successFromRawBinding': success})
    source_bindings = []
    for rel in ['scripts/m4_input_observer.mjs', 'scripts/validate_input_observation.mjs']:
        path = ROOT / rel; data = path.read_bytes(); source_bindings.append({'path': rel, 'sha256': sha(data), 'bytes': len(data)})
    return {
        'schemaVersion': 1, 'protocol': 'archcanvas-independent-native-diagnostic-audit/1',
        'auditedAt': datetime.now(timezone.utc).isoformat(), 'auditCompleted': True,
        'raw': {'path': str(raw_path.relative_to(ROOT)), 'sha256': sha(raw_bytes), 'bytes': len(raw_bytes)},
        'observerValidator': source_bindings,
        'validatorProcess': {'command': 'node scripts/validate_input_observation.mjs product-raw.json',
            'exitCode': validator_exit, 'stdoutPath': str(validator_stdout.relative_to(ROOT)),
            'stdoutSha256': sha(validator_stdout.read_bytes()), 'stdoutBytes': validator_stdout.stat().st_size,
            'stderrPath': str(validator_stderr.relative_to(ROOT)), 'stderrSha256': sha(validator_stderr.read_bytes()),
            'stderrBytes': validator_stderr.stat().st_size, 'validatorStatus': 'passed' if validator_exit == 0 else 'failed'},
        'bidirectionalUniqueMatching': {'eligibleTrustedDiscreteInputs': len(inputs),
            'matchedUniqueInputs': len(matched), 'matchedTrialInputs': len(matched_trial),
            'matchedInteractions': len(interactions), 'interactionMaxDurationsMs': sorted(interactions.values()),
            'interactionP95Ms': p95(list(interactions.values())),
            'algorithm': 'full candidate graph; input and entry must each have exactly one candidate',
            'matchesOnlyDiscreteEventTiming': True},
        'frameCadence': {'callbackCount': len(frames), 'intervalCount': len(intervals),
            'intervalP95Ms': p95(intervals), 'maxIntervalMs': max(intervals) if intervals else None,
            'fps': (len(frames)-1)*1000/(frames[-1]['at']-frames[0]['at']) if len(frames)>1 else None,
            'idleIntervalCount': len(idle), 'idleIntervalP95Ms': p95(idle),
            'idleFps': len(idle)*1000/sum(idle) if idle and sum(idle)>0 else None,
            'rAFCallbacksAreNotPresentedFrames': True},
        'trialRequests': {'requested': len(trials), 'successfulCommittedBindings': sum(t['successFromRawBinding'] for t in trials),
            'noInput': sum(t['status'] == 'no-input' for t in trials), 'trials': trials},
        'environment': report['environment'], 'harness': report['harness'],
        'errors': report['errors'], 'buffers': report['buffers'],
        'humanCertified': False, 'presentedPaintCertified': False,
        'limitations': ['Raw is a same-origin iframe DOM/Event Timing observation; it does not certify native presented paint or FPS.',
            'The 2000 ms matched interaction p95 is a four-interaction matched subset, not overall INP or a publication threshold.',
            'The approximately 2 FPS values are rAF callback cadence over this observation; they are not presented-frame FPS and have no unique CPU cause.',
            'Agent-operated trusted automation is not a human participant; no researcher acceptance is inferred.',
            'Unknown hardware, browser version and resolved font bytes remain unknown.']}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--raw', type=Path, required=True); ap.add_argument('--validator-stdout', type=Path, required=True); ap.add_argument('--validator-stderr', type=Path, required=True); ap.add_argument('--validator-exit', type=int, required=True); ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args(); out = a.output.resolve(); assert out.is_relative_to(WORK) and not out.exists()
    result = audit(a.raw.resolve(), a.validator_stdout.resolve(), a.validator_stderr.resolve(), a.validator_exit)
    with out.open('x', encoding='utf-8') as f: json.dump(result, f, ensure_ascii=False, indent=2); f.write('\n')
    print(json.dumps({'output': str(out), 'sha256': sha(out.read_bytes()), 'rawSha256': result['raw']['sha256'], 'interactionP95Ms': result['bidirectionalUniqueMatching']['interactionP95Ms'], 'rAFfps': result['frameCadence']['fps']}))
if __name__ == '__main__': main()
