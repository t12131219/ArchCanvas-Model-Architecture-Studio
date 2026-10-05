#!/usr/bin/env python3
"""Freeze this change while resolving all prior evidence through original archives."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = ROOT / 'docs/evidence/m4-hierarchy-verification.json'
MANIFEST = HERE / 'manifest.json'
CACHE = {}

def frozen(path):
    path = path.resolve()
    if path not in CACHE:
        CACHE[path] = path.read_bytes()
    return CACHE[path]

def digest(path):
    return hashlib.sha256(frozen(path)).hexdigest()

def record(path):
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(frozen(path)), 'sha256': digest(path)}

def read(path):
    return json.loads(frozen(path))

assert not OUTPUT.exists() and not MANIFEST.exists(), 'Never overwrite a seal; choose a new evidence directory.'
archive_path = ROOT / 'docs/evidence/before-hierarchy-optimization/manifest.json'
archive = read(archive_path)
mapping = {item['originalPath']: item['archivePath'] for item in archive['files']}
for item in archive['files']:
    file = ROOT / item['archivePath']
    assert digest(file) == item['sha256'] and len(frozen(file)) == item['bytes']
previous_path = ROOT / 'docs/evidence/m4-current-native-verification.json'
previous = read(previous_path)
linked = {}
for name, expected in previous['bindings'].items():
    path = ROOT / mapping.get(name, name)
    assert digest(path) == expected, name
    linked[str(path.relative_to(ROOT))] = expected

for name in ['ui-independent-audit.json', 'react-probe-independent-audit.json', 'native-independent-audit.json']:
    audit = read(HERE / name)
    assert audit['status'].startswith('passed'), (name, audit['status'])
    inputs = audit.get('inputsAfter', audit.get('inputBindings'))
    assert isinstance(inputs, list) and inputs, name
    for item in inputs:
        path = Path(item['path'])
        path = path if path.is_absolute() else ROOT / path
        assert digest(path) == item['sha256'], (name, path)

package_root = ROOT / '.archcanvas/m4-research-trial-hierarchy-final'
package_path = package_root / 'manifest.json'
package = read(package_path)
assert package['researcherCount'] == 0 and len(package['slots']) == 5
assert len(package['implementationFiles']) == 59
for item in package['implementationFiles']:
    assert digest(ROOT / item['path']) == item['sha256']
for slot in package['slots']:
    assert slot['assignment'] == 'unassigned' and slot['participantCode'] is None
    envelope = package_root / slot['baselineEnvelope']['path']
    assert digest(envelope) == slot['baselineEnvelope']['sha256']
    assert list(envelope.parent.glob('*')) == [envelope]
    assert not (package_root / 'slots' / slot['slotId'] / 'assignment.json').exists()
    assert not (package_root / 'slots' / slot['slotId'] / 'collected').exists()

spec_path = ROOT / '.archcanvas/browser-visual-matrix-hierarchy-final/spec.json'
spec = read(spec_path)
assert spec['expectedBaselineCount'] == 36 and len(spec['frontiers']) == 9
assert read(HERE / 'renderer-candidate-parity.json')['all36CandidateSvgBytesExact']
validation = read(HERE / 'native-stress300-validation.json')
assert all(t['operationSucceeded'] for t in validation['trials']) and len(validation['trials']) == 2
assert validation['latency']['matchedInteractionP95Ms'] == 2016
assert read(HERE / 'react-probe-independent-audit.json')['summary']['rounds'] == 18

local_paths = [p for p in HERE.rglob('*') if p.is_file() and p.name not in {'service-raw.txt', 'react-service-raw.txt', 'manifest.json'} and '__pycache__' not in p.parts]
local_paths += [p for p in package_root.rglob('*') if p.is_file()]
local_paths += [spec_path, archive_path, previous_path]
local_paths += [ROOT / name for name in ['README.md', 'docs/evidence/README.md', 'docs/m4-performance.md', 'docs/m4-input-observation.md', 'docs/m4-completion.md', 'docs/capability-matrix.md', 'docs/m4-exit-audit.md', 'docs/m4-human-review-handoff.md', 'docs/m4-hierarchy-optimization.md', 'docs/evidence/m4-human-review-handoff-status.json', 'studio/src/App.tsx', 'studio/src/HierarchyTree.tsx', 'studio/tests/hierarchy-tree.test.ts', 'scripts/prepare_hierarchy_probe.mjs']]
local_paths += [p for p in (ROOT / 'scripts/m4_hierarchy_support').rglob('*') if p.is_file()]
local_paths += [p for p in (ROOT / 'studio/dist').rglob('*') if p.is_file()]
local = {str(path.relative_to(ROOT)): record(path) for path in sorted(set(local_paths))}
links = []
for path in [ROOT / n for n in local if n.endswith('.md') and ('source-inputs' not in n and '/visual-golds/' not in n)]:
    for target in re.findall(r'\]\(([^)\n]+)\)', frozen(path).decode()):
        target = target.strip().strip('<>').split('#', 1)[0]
        if not target or re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', target):
            continue
        destination = Path(target) if target.startswith('/') else path.parent / target
        assert destination.exists() or destination.resolve() in {OUTPUT, MANIFEST}, (path, target)
        links.append({'file':str(path.relative_to(ROOT)), 'target':target})

for path, before in CACHE.items():
    assert path.read_bytes() == before, path
bindings = {**linked, **{name: item['sha256'] for name, item in local.items()}}
summary = {'schemaVersion':1, 'frozenAt':datetime.now(timezone.utc).isoformat(), 'phaseStatus':'partial',
    'scope':'Hierarchy optimization, scoped regression and actual React/UI/native diagnostics; no human/publication/presented performance acceptance.',
    'formalFromScratch':True, 'oldPrototypeReuse':False,
    'productionBuild':'index-oI5sT67U.js', 'productionJsSha256':digest(ROOT / 'studio/dist/assets/index-oI5sT67U.js'),
    'previousSnapshot':record(previous_path), 'previousBindingsVerifiedThroughArchive':len(previous['bindings']), 'archiveManifest':record(archive_path),
    'studioTests':{'total':85,'passed':85,'skipped':0}, 'strictBuildPassed':True,'standaloneChecks':9,
    'react':{'rounds':18,'trustedClicks':17,'stableRounds':5,'oldStablePropertyReads':49401,'newStablePropertyReads':0,'fullDomHashesIndependentlyRecomputed':0,'audit':record(HERE / 'react-probe-independent-audit.json')},
    'ui':{'observations':12,'savedReopenedSvgByteExact':True,'visualRevision':7,'storageRevision':1,'audit':record(HERE / 'ui-independent-audit.json')},
    'native':{'requests':2,'succeeded':2,'eligibleDiscreteInputs':6,'matchedDiscreteInputs':3,'matchedInteractions':1,'matchedSubsetP95Ms':2016,'presentedContinuousPaintCertified':False,'audit':record(HERE / 'native-independent-audit.json')},
    'matrix':{'spec':record(spec_path),'preparedBaselines':36,'collectedBaselines':0,'expectedEditedModels':3,'collectedEditedModels':0,'humanAcceptanceCertified':False},
    'research':{'manifest':record(package_path),'implementationBindings':59,'pristineSlots':5,'assigned':0,'collected':0,'humans':0},
    'localLinksChecked':len(links),'localFiles':list(local.values()),'linkedFiles':linked,
    'excludedMutableLogs':['service-raw.txt','react-service-raw.txt'],'frozenLogSnapshots':['service-cutoff.txt','react-service-cutoff.txt'],
    'allFrozenInputsRecheckedAtSeal':True}
MANIFEST.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
bindings[str(MANIFEST.relative_to(ROOT))] = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
OUTPUT.write_text(json.dumps({'schemaVersion':1,'status':'partial-hierarchy-optimization-verified-experience-gates-open','summary':summary,'manifestSha256':bindings[str(MANIFEST.relative_to(ROOT))],'bindings':dict(sorted(bindings.items()))},ensure_ascii=False,indent=2)+'\n')
for name, expected in bindings.items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
print(json.dumps({'status':'sealed-partial','previousBindings':len(previous['bindings']),'bindings':len(bindings),'localFiles':len(local),'localLinksChecked':len(links),'verificationSha256':hashlib.sha256(OUTPUT.read_bytes()).hexdigest()},ensure_ascii=False))
