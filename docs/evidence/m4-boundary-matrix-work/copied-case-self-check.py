#!/usr/bin/env python3
"""Synthetic copied-envelope safety checks, no browser evidence."""
from __future__ import annotations
import copy
import importlib.util
import json
import tempfile
from pathlib import Path

WORK=Path(__file__).resolve().parent
specification=importlib.util.spec_from_file_location('copied_case',WORK/'package-copied-case.py')
adapter=importlib.util.module_from_spec(specification)
specification.loader.exec_module(adapter)
workflow=adapter.workflow
formal=adapter.formal


def reject(label,call,contains):
    try:call()
    except (ValueError,OSError) as error:
        assert contains in str(error),(label,str(error))
        return {'check':label,'passed':True,'observedError':str(error)}
    raise AssertionError(label+': expected rejection')


def main():
    spec=formal.verified_spec(workflow.MATRIX)
    variant=next(v for v in spec['variants'] if v['variantId']=='mlp-level0-paper-180')
    document=json.loads(Path(variant['canvasFile']).read_bytes())
    scene=Path(variant['svgFile']).read_bytes()
    result=[]
    freeze=adapter.guarded()
    with tempfile.TemporaryDirectory(prefix='archcanvas-synthetic-copied-envelope-') as name:
        temporary=Path(name)
        adapter.WORK=temporary/'work';adapter.WORK.mkdir()
        workflow.STORE=temporary/'service/documents';workflow.STORE.mkdir(parents=True)
        artifact=workflow.STORE.parent/'exports'/('a'*32);artifact.mkdir(parents=True)
        binding={'documentId':document['id'],'revision':document['revision'],
                 'sourceDigest':variant['sourceDigest'],'irDigest':variant['irDigest']}
        (artifact/'document.json').write_bytes(formal.encode(document))
        (artifact/'figure.svg').write_bytes(scene)
        (artifact/'figure.svg.receipt.json').write_bytes(formal.encode({'format':'svg',**binding,
            'widthMm':180,'exportScope':{'kind':'document'},'outputDigest':formal.sha(scene),'bytes':len(scene)}))
        copied=temporary/'actual-document-store.json'
        copied_bytes=formal.encode({'revision':1,'document':document});copied.write_bytes(copied_bytes)
        source=workflow.STORE/(document['id']+'.json')
        copy_facts={'observedSourcePath':str(source),'snapshotPath':str(copied),
                    'copiedAt':'2026-10-05T00:00:00Z','sha256':formal.sha(copied_bytes),'bytes':len(copied_bytes)}
        sidecar=Path(str(copied)+'.receipt.json');sidecar.write_bytes(formal.encode(copy_facts))
        raw={'caseId':'synthetic-copied-only','variantId':variant['variantId'],'state':'baseline',
             'capturedAt':'2026-10-05T00:00:00Z','studioUrl':workflow.ORIGIN+'/',
             'documentBinding':binding,'pageSpec':{'preset':'paper','widthMm':180},'expandedIds':document['expandedIds'],
             'environment':{'userAgent':'SYNTHETIC-NOT-A-BROWSER','browserVersion':None,
                 'viewport':{'width':1280,'height':720},'devicePixelRatio':1,'hardware':None,'fontEvidence':[]},
             'camera':{'transform':'SYNTHETIC','sceneScreenBounds':{'x':1,'y':2,'width':3,'height':4}},
             'loadedBuildAssets':[{'path':v['path'],'url':workflow.ORIGIN+'/'+v['path']}
                 for v in spec['buildFiles'] if v['path'].endswith(('.js','.css'))],
             'actualExport':{'observedUrl':workflow.ORIGIN+'/api/exports/'+('a'*32)+'/figure.svg'},
             'actualStoredEnvelope':copy_facts,'captureScope':'studio-viewport','limitations':['SYNTHETIC: no native image claim.']}
        raw_path=temporary/'raw.json';raw_bytes=formal.encode(raw);raw_path.write_bytes(raw_bytes)
        scene_path=temporary/'synthetic.svg';scene_path.write_bytes(scene)
        screenshot=temporary/'synthetic.jpg';screenshot.write_bytes(b'\xff\xd8\xffSYNTHETIC-INVALID-IMAGE-ONLY')
        # No live saved file exists. Success is direct evidence it was not reread.
        assert not source.exists()
        bound=adapter.package(raw_path,scene_path,screenshot,copied)
        assert bound['liveStoreReread'] is False
        assert raw_path.read_bytes()==raw_bytes and copied.read_bytes()==copied_bytes
        result.append({'check':'packages-exact-copy-even-when-live-store-file-is-absent','passed':True})
        result.append(reject('refuses-output-replacement',lambda:adapter.package(raw_path,scene_path,screenshot,copied),'already exists'))
        modified=copy.deepcopy(raw);modified['caseId']='synthetic-sidecar-mismatch';modified['actualStoredEnvelope']['copiedAt']='2026-10-05T00:00:01Z'
        raw_path.write_bytes(formal.encode(modified))
        result.append(reject('rejects-raw-sidecar-fact-mismatch',lambda:adapter.package(raw_path,scene_path,screenshot,copied),'must equal'))
        modified=copy.deepcopy(raw);modified['caseId']='synthetic-wrong-hash';modified['actualStoredEnvelope']['sha256']='0'*64
        raw_path.write_bytes(formal.encode(modified));sidecar.write_bytes(formal.encode(modified['actualStoredEnvelope']))
        result.append(reject('rejects-copied-byte-hash-mismatch',lambda:adapter.package(raw_path,scene_path,screenshot,copied),'exact saved bytes'))
        modified=copy.deepcopy(raw);modified['caseId']='synthetic-wrong-source';modified['actualStoredEnvelope']['observedSourcePath']=str(source.parent/'other.json')
        raw_path.write_bytes(formal.encode(modified));sidecar.write_bytes(formal.encode(modified['actualStoredEnvelope']))
        result.append(reject('rejects-different-source-document-path',lambda:adapter.package(raw_path,scene_path,screenshot,copied),'exact known store'))
        modified=copy.deepcopy(raw);modified['caseId']='synthetic-wrong-snapshot';modified['actualStoredEnvelope']['snapshotPath']=str(temporary/'other-copy.json')
        raw_path.write_bytes(formal.encode(modified));sidecar.write_bytes(formal.encode(modified['actualStoredEnvelope']))
        result.append(reject('rejects-different-snapshot-path',lambda:adapter.package(raw_path,scene_path,screenshot,copied),'exact supplied saved copy'))
        modified=copy.deepcopy(raw);modified['caseId']='synthetic-no-timezone';modified['actualStoredEnvelope']['copiedAt']='2026-10-05T00:00:00'
        raw_path.write_bytes(formal.encode(modified));sidecar.write_bytes(formal.encode(modified['actualStoredEnvelope']))
        result.append(reject('rejects-copied-time-without-timezone',lambda:adapter.package(raw_path,scene_path,screenshot,copied),'actual ISO timestamp'))
        modified=copy.deepcopy(raw);modified['caseId']='synthetic-missing-export';modified['actualExport']['observedUrl']=workflow.ORIGIN+'/api/exports/'+('b'*32)+'/figure.svg'
        raw_path.write_bytes(formal.encode(modified));sidecar.write_bytes(formal.encode(modified['actualStoredEnvelope']))
        result.append(reject('rejects-missing-exact-export-without-search',lambda:adapter.package(raw_path,scene_path,screenshot,copied),'Missing actual input'))
        assert not (adapter.WORK/'cases/synthetic-missing-export').exists()
        altered=copy.deepcopy(document);altered['title']='SYNTHETIC DIFF'
        (artifact/'document.json').write_bytes(formal.encode(altered))
        modified=copy.deepcopy(raw);modified['caseId']='synthetic-export-canvas-diff'
        raw_path.write_bytes(formal.encode(modified));sidecar.write_bytes(formal.encode(modified['actualStoredEnvelope']))
        result.append(reject('rejects-full-export-canvas-diff',lambda:adapter.package(raw_path,scene_path,screenshot,copied),'No fallback attempted'))
        assert not (adapter.WORK/'cases/synthetic-export-canvas-diff').exists()
        formal.recheck(freeze)
    print(json.dumps({'schemaVersion':1,'protocol':'archcanvas-boundary-copied-case-self-check/1',
        'scope':'Synthetic local bytes in removed /tmp tree; no genuine screenshot/image or browser evidence.',
        'checksPassed':len(result),'realBrowserCaptured':False,'humanAcceptanceCertified':False,'checks':result},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
