#!/usr/bin/env python3
"""Read-only archive resolver; no receipt or evidence rewriting."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[3]
ARCHIVE=Path(__file__).resolve().parent
EXPECTED='7fecf8b0ba1e5befec1d43613f0c115f1fd84d0503460f6d59118bacd22e7533'


def frozen(path):
    current=path
    while current!=current.parent:
        assert not current.is_symlink(),str(path)
        current=current.parent
    value=path.read_bytes()
    return value,hashlib.sha256(value).hexdigest()


def main():
    inputs=[]
    receipt_raw,receipt_sha=frozen(ARCHIVE/'source-receipt.json');assert receipt_sha==EXPECTED
    live_raw,live_sha=frozen(ROOT/'docs/evidence/m4-boundary-final-verification.json');assert live_raw==receipt_raw
    source=json.loads(receipt_raw);assert source['bindingCount']==len(source['bindings'])==3644
    manifest_raw,_=frozen(ARCHIVE/'manifest.json');resolution_raw,_=frozen(ARCHIVE/'historical-resolution.json')
    manifest=json.loads(manifest_raw);resolution=json.loads(resolution_raw)
    inputs.extend([(ARCHIVE/'source-receipt.json',receipt_raw),(ROOT/'docs/evidence/m4-boundary-final-verification.json',live_raw),(ARCHIVE/'manifest.json',manifest_raw),(ARCHIVE/'historical-resolution.json',resolution_raw)])
    seen=set()
    for item in manifest['files']:
        path=ROOT/item['archivePath'];raw,digest=frozen(path)
        assert digest==item['sha256']and len(raw)==item['bytes']
        assert item['originalPath']not in seen;seen.add(item['originalPath']);inputs.append((path,raw))
    assert len(seen)==20
    bindings=resolution['bindings'];assert len(bindings)==3644 and len({v['bindingPath']for v in bindings})==3644
    archived=0
    for item in bindings:
        assert source['bindings'][item['bindingPath']]==item['sha256']
        path=ROOT/item['resolvedPath'];raw,digest=frozen(path)
        assert digest==item['sha256']and len(raw)==item['bytes'],item['bindingPath']
        inputs.append((path,raw));archived+=item['resolvedPath']!=item['bindingPath']
    for path,raw in inputs:assert frozen(path)[0]==raw,str(path)
    print(json.dumps({'schemaVersion':1,'protocol':'archcanvas-boundary-final-matrix-archive-verification/1','sourceReceiptSha256':receipt_sha,'sourceBindings':3644,'resolvedBindings':len(bindings),'archivedBindings':archived,'retainedBindings':len(bindings)-archived,'snapshots':len(seen),'readOnly':True,'allExactBytesResolved':True,'humanAcceptanceCertified':False},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
