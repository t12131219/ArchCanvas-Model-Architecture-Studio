#!/usr/bin/env python3
"""Audit full product SVG observations, save/reopen store and source bindings."""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, tempfile, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]; WORK = Path(__file__).resolve().parent
SVG = '{http://www.w3.org/2000/svg}'

def sha(b): return hashlib.sha256(b).hexdigest()
def xml_value(raw, strip_revision=False):
    root = ET.fromstring(raw)
    assert root.tag == SVG + 'svg'
    if strip_revision:
        root.attrib['data-revision'] = '0'
        metas = root.findall(SVG + 'metadata'); assert len(metas) == 1
        value = json.loads(metas[0].text); assert type(value['revision']) is int
        metas[0].text = re.sub(r'("revision"\s*:\s*)\d+(?=\s*[,}])', r'\g<1>0', metas[0].text)
    def node(e): return [e.tag, sorted(e.attrib.items()), e.text or '', e.tail or '', [node(c) for c in e]]
    return node(root)
def read_json(path): return json.loads(path.read_bytes())

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=Path); a=ap.parse_args(); out=a.output.resolve(); assert out.is_relative_to(WORK) and not out.exists()
    raw_path=WORK/'product-raw.json'; raw=read_json(raw_path); trials={t['id']:t for t in raw['trials']}
    # Full untruncated public SVG strings are retained inside product-raw trial snapshots.
    t4=trials['trial-4']; t5=trials['trial-5']; t6=trials['trial-6']
    before=t4['before']['svgMarkup'].encode(); committed=t4['after']['svgMarkup'].encode(); undo=t5['after']['svgMarkup'].encode(); redo=t6['after']['svgMarkup'].encode()
    assert not any(x.endswith(b'[Truncated]') for x in (before,committed,undo,redo))
    assert xml_value(before,True) == xml_value(undo,True), 'undo scene changed beyond root revisions'
    assert xml_value(committed,True) == xml_value(redo,True), 'redo scene changed beyond root revisions'
    revisions=[t4['before']['revision'],t4['after']['revision'],t5['after']['revision'],t6['after']['revision']]; assert revisions==[2,3,4,5]
    # Save/reopen files collected through the native channel are capped at 200011 bytes;
    # retain that fact and use the complete reopened document-store Canvas below.
    capped=[]
    for name in ('drag-round2-dom','undo-dom','redo-dom','saved-dom','reopened-dom'):
        data=read_json(WORK/(name+'.json')); svg=data['svg']; capped.append({'name':name,'bytes':len(svg),'truncated':svg.endswith('[Truncated]')})
    store=read_json(WORK/'actual-document-store.json'); doc=store['document']; assert doc['revision']==5 and store['revision']>=0
    assert doc['id']==t6['after']['documentId']; assert doc['architecture']['sourceDigest']==t6['after']['sourceDigest']; assert doc['architecture']['irDigest']==t6['after']['irDigest']
    assert doc['expandedIds']==t6['after']['expandedIds']
    # Rebuild the full interactive SVG from the complete reopened Canvas using the frozen formal core.
    with tempfile.TemporaryDirectory(prefix='archcanvas-native-dom-') as temp:
        temp=Path(temp); inp=temp/'input.json'; expected=temp/'expected'; inp.write_text(json.dumps([{'document':doc}],ensure_ascii=False))
        proc=subprocess.run(['node',str(ROOT/'scripts/browser_visual_core.mjs'),str(inp),str(expected)],cwd=ROOT,capture_output=True,text=True,timeout=60)
        assert proc.returncode==0,proc.stderr
        rebuilt=(expected/'0.interactive.svg').read_bytes(); facts=read_json(expected/'facts.json')[0]
    assert xml_value(rebuilt)==xml_value(redo), 'complete store Canvas formal core differs from final DOM scene'
    sources=[]
    for src in doc['architecture']['sources']:
        matches=[path for path in (ROOT/'fixtures').glob('*/'+src['path']) if path.is_file() and sha(path.read_bytes())==src['digest']]
        assert len(matches)==1, (src['path'], src['digest'], [str(path) for path in matches])
        path=matches[0]; data=path.read_bytes(); assert data==src['content'].encode()
        sources.append({'path':str(path.relative_to(ROOT)),'sha256':sha(data),'bytes':len(data)})
    result={'schemaVersion':1,'protocol':'archcanvas-independent-native-dom-audit/1','auditedAt':datetime.now(timezone.utc).isoformat(),'auditCompleted':True,
      'rawProduct':{'path':str(raw_path.relative_to(ROOT)),'sha256':sha(raw_path.read_bytes()),'bytes':raw_path.stat().st_size},
      'visualRevisionSequence':revisions,'undoFullXmlExceptTwoRevisionValues':True,'redoFullXmlExceptTwoRevisionValues':True,
      'saveReopenFullDomScope':'complete reopened Canvas store reconstructed by frozen formal core; direct native reopened-dom SVG text is truncated at 200011 bytes',
      'saveReopenStoreCanvasReconstructsFinalDom':True,'store':{'path':str((WORK/'actual-document-store.json').relative_to(ROOT)),'sha256':sha((WORK/'actual-document-store.json').read_bytes()),'bytes':(WORK/'actual-document-store.json').stat().st_size,'documentRevision':doc['revision'],'storeRevision':store['revision']},
      'rebuildFacts':facts,'cappedNativeDomObservations':capped,'sourceBindings':sources,'sourceDigest':t6['after']['sourceDigest'],'irDigest':t6['after']['irDigest'],
      'limitations':['The complete raw trial SVG strings support undo/redo semantic equality; direct saved/reopened native DOM files are capped strings and are not claimed byte-complete.','Store Canvas reconstruction verifies full saved state and final DOM through the frozen formal core, not native screenshot pixels or presented paint.','No model executed; source bytes are checked against the stored architecture evidence.']}
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'output':str(out),'sha256':sha(out.read_bytes()),'storeReconstructs':True}))
if __name__=='__main__':main()
