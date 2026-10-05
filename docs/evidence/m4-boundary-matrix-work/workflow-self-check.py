#!/usr/bin/env python3
"""Synthetic local-byte tests; never browser capture or acceptance evidence."""
from __future__ import annotations
import base64
import copy
import importlib.util
import json
import tempfile
from pathlib import Path

WORK = Path(__file__).resolve().parent
specification = importlib.util.spec_from_file_location('boundary_workflow', WORK / 'capture_workflow.py')
workflow = importlib.util.module_from_spec(specification)
specification.loader.exec_module(workflow)
formal = workflow.formal


def expect(label, action, message):
    try:
        action()
    except (ValueError, FileExistsError) as error:
        assert message in str(error), (label,str(error))
        return {'check':label,'passed':True,'observedError':str(error)}
    raise AssertionError(label + ': expected rejection')


def main():
    matrix = workflow.MATRIX
    matrix_spec = formal.verified_spec(matrix)
    variant = next(v for v in matrix_spec['variants'] if v['variantId']=='mlp-level0-paper-180')
    canvas = json.loads(Path(variant['canvasFile']).read_bytes())
    scene = Path(variant['svgFile']).read_bytes()
    results=[]
    with tempfile.TemporaryDirectory(prefix='archcanvas-synthetic-boundary-workflow-') as name:
        directory=Path(name)
        workflow.HERE=directory/'work'
        workflow.HERE.mkdir()
        workflow.STORE=directory/'service/documents'
        workflow.STORE.mkdir(parents=True)
        # The guard still references genuine frozen inputs; outputs are only tmp.
        workflow.GUARD=WORK/'preparation-guard.json'
        artifact=workflow.STORE.parent/'exports'/('a'*32)
        artifact.mkdir(parents=True)
        envelope=formal.encode({'revision':1,'document':canvas})
        (workflow.STORE/(canvas['id']+'.json')).write_bytes(envelope)
        binding={'documentId':canvas['id'],'revision':canvas['revision'],
                 'sourceDigest':variant['sourceDigest'],'irDigest':variant['irDigest']}
        (artifact/'document.json').write_bytes(formal.encode(canvas))
        (artifact/'figure.svg').write_bytes(scene)
        (artifact/'figure.svg.receipt.json').write_bytes(formal.encode({
            'format':'svg',**binding,'widthMm':180,'exportScope':{'kind':'document'},
            'outputDigest':formal.sha(scene),'bytes':len(scene)}))
        raw={'caseId':'synthetic-only','variantId':variant['variantId'],'state':'baseline',
             'capturedAt':'2026-10-05T00:00:00Z','studioUrl':workflow.ORIGIN+'/',
             'documentBinding':binding,'pageSpec':{'preset':'paper','widthMm':180},
             'expandedIds':canvas['expandedIds'],
             'environment':{'userAgent':'SYNTHETIC-NOT-A-BROWSER','browserVersion':None,
                'viewport':{'width':1280,'height':720},'devicePixelRatio':1,'hardware':None,'fontEvidence':[]},
             'camera':{'transform':'SYNTHETIC','sceneScreenBounds':{'x':1,'y':2,'width':3,'height':4}},
             'loadedBuildAssets':[{'path':v['path'],'url':workflow.ORIGIN+'/'+v['path']}
                for v in matrix_spec['buildFiles'] if v['path'].endswith(('.js','.css'))],
             'actualExport':{'observedUrl':workflow.ORIGIN+'/api/exports/'+('a'*32)+'/figure.svg'},
             'captureScope':'studio-viewport','limitations':['SYNTHETIC: no native browser or screenshot claim.']}
        raw_path=directory/'synthetic-raw.json'
        raw_bytes=formal.encode(raw)
        raw_path.write_bytes(raw_bytes)
        scene_path=directory/'synthetic.svg'; scene_path.write_bytes(scene)
        image_path=directory/'synthetic.jpg'
        # Only a byte/type guard is exercised; this is deliberately invalid image data.
        fake_image=b'\xff\xd8\xffSYNTHETIC-NOT-AN-IMAGE\xff\xd9'
        image_path.write_bytes(fake_image)
        frozen=workflow.guarded()
        assert len(frozen)==103
        results.append({'check':'genuine-final-freeze-103-inputs','passed':True})
        bound=workflow.bind_observation(raw_path)
        assert raw_path.read_bytes()==raw_bytes
        observation=workflow.HERE/'bound-observations/synthetic-only'
        assert (observation/'actual-document-store.json').read_bytes()==envelope
        results.append({'check':'exclusive-bound-copy-preserves-original-raw-and-envelope','passed':True})
        results.append(expect('bound-copy-refuses-replacement',lambda:workflow.bind_observation(raw_path),'already exists'))
        # New live Canvas does not invalidate the earlier explicitly copied bytes.
        newer=copy.deepcopy(canvas); newer['revision']+=1
        (workflow.STORE/(canvas['id']+'.json')).write_bytes(formal.encode({'revision':2,'document':newer}))
        packaged=workflow.package_case('synthetic-only',scene_path,image_path)
        case=workflow.HERE/'cases/synthetic-only'
        assert packaged['fullSavedAndExportCanvasEquality'] is True
        assert (case/'actual-document-store.json').read_bytes()==envelope
        results.append({'check':'frozen-snapshot-survives-later-live-save-without-fallback','passed':True})
        results.append(expect('case-refuses-replacement',lambda:workflow.package_case('synthetic-only',scene_path,image_path),'already exists'))
        results.append(expect('index-refuses-unstamped-case',lambda:workflow.index_cases(workflow.HERE/'captures-001.json'),'Missing actual input'))
        originals={p:p.read_bytes() for p in (case/'screen-receipt.json',case/'screen-receipt-unstamped.json')}
        workflow.stamp_case('synthetic-only')
        assert all(path.read_bytes()==value for path,value in originals.items())
        results.append({'check':'stamp-writes-new-file-and-preserves-both-original-receipts','passed':True})
        results.append(expect('stamp-refuses-replacement',lambda:workflow.stamp_case('synthetic-only'),'File exists'))
        indexed=workflow.index_cases(workflow.HERE/'captures-001.json')
        assert indexed['captures']==1 and indexed['baselines']==1
        captures=json.loads((workflow.HERE/'captures-001.json').read_bytes())
        assert captures['captures'][0]['screenReceipt'].endswith('screen-receipt-stamped.json')
        results.append({'check':'index-binds-separate-stamped-receipt-inside-root','passed':True})
        results.append(expect('index-refuses-replacement',lambda:workflow.index_cases(workflow.HERE/'captures-001.json'),'already exists'))
        results.append(expect('index-refuses-input-root-escape',lambda:workflow.index_cases(workflow.HERE/'nested/captures-002.json'),'directly in this work'))
        stamped=json.loads((case/workflow.STAMPED).read_bytes())
        stamped['environment']['devicePixelRatio']=2
        (case/workflow.STAMPED).write_bytes(formal.encode(stamped))
        results.append(expect('index-refuses-changed-observation',lambda:workflow.index_cases(workflow.HERE/'captures-002.json'),'facts changed'))
        stamped['environment']['devicePixelRatio']=1
        (case/workflow.STAMPED).write_bytes(formal.encode(stamped))
        (case/'canvas.json').write_bytes(b'{}')
        results.append(expect('index-refuses-changed-copied-canvas',lambda:workflow.index_cases(workflow.HERE/'captures-002.json'),'input changed'))
        # Exact ID mismatch is checked against the copied envelope, no export search.
        broken=copy.deepcopy(raw); broken['caseId']='synthetic-stale-export'; broken['documentBinding']['revision']=newer['revision']
        broken_path=directory/'stale-raw.json'; broken_path.write_bytes(formal.encode(broken))
        workflow.bind_observation(broken_path)
        results.append(expect('stale-current-export-is-rejected-without-replacement',
            lambda:workflow.package_case('synthetic-stale-export',scene_path,image_path),'No fallback attempted'))
        assert not (workflow.HERE/'cases/synthetic-stale-export').exists()
        encoded=directory/'synthetic-base64.txt'; encoded.write_bytes(base64.b64encode(fake_image))
        output=directory/'synthetic-decoded.jpg'
        workflow.save_jpeg(encoded,output)
        assert output.read_bytes()==fake_image
        results.append({'check':'base64-decodes-exact-bytes-without-reencoding','passed':True})
        results.append(expect('base64-copy-refuses-replacement',lambda:workflow.save_jpeg(encoded,output),'already exists'))
        encoded.write_text(base64.b64encode(b'not-jpeg').decode())
        results.append(expect('base64-copy-rejects-non-jpeg',lambda:workflow.save_jpeg(encoded,directory/'invalid.jpg'),'complete exact JPEG'))
        formal.recheck(frozen)
    print(json.dumps({'schemaVersion':1,'protocol':'archcanvas-boundary-workflow-self-check/1',
        'scope':'Synthetic local bytes in a removed /tmp directory; no real browser cases or native image decoding claim.',
        'realBrowserCaptured':False,'humanAcceptanceCertified':False,
        'checksPassed':len(results),'checks':results},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
