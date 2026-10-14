"""Independent SVG checks for the deliberately small source glyph vocabulary."""
import ast,math,xml.etree.ElementTree as ET
from source_glyphs import classify,VERSION

def tag(e):return e.tag.rsplit('}',1)[-1]
def check(ok,message):
    if not ok:raise ValueError('source glyph: '+message)
def close(a,b):return len(a)==len(b) and all(abs(float(x)-float(y))<1e-6 for x,y in zip(a,b))

def outline(element,presentation=None):
    shapes=[c for c in element if tag(c) in ('rect','circle')]
    check(len(shapes)==1,'one body outline required: '+str(element.get('data-node-id')))
    shape=shapes[0]
    if tag(shape)=='circle':
        check(presentation and presentation['kind']=='binary-circle','circle has no source contract')
        cx,cy,r=[float(shape.get(k,'nan')) for k in ('cx','cy','r')]
        return shape,[cx-r,cy-r,2*r,2*r],r
    return shape,[float(shape.get(k,'nan')) for k in ('x','y','width','height')],float(shape.get('rx',0))

def validate_presentations(svg,layout,evidence,ir):
    nodes={n['id']:n for n in ir['nodes']}
    elements={e.get('data-node-id'):e for e in svg.iter() if e.get('data-node-id')}
    count=0
    for box in layout['boxes']:
        c=box.get('presentation')
        if not c:continue
        count+=1;identity=box['id'];node=nodes[identity];e=elements.get(identity)
        request=None
        if c.get('source_expression'):request={'expression':c['source_expression'],'operation':c['operation']}
        expected=classify(node,ir,evidence,request)
        check(expected is not None,'ineligible IR value/operator '+identity)
        check(all(c.get(k)==v for k,v in expected.items()),'contract differs from source '+identity)
        check(c['schema']==VERSION and e is not None and e.get('data-glyph-kind')==c['kind'],'missing owned glyph '+identity)
        shape,bbox,radius=outline(e,c)
        check(close(bbox,box['bbox']) and abs(radius-box['radius'])<1e-6,'body geometry '+identity)
        w,h=(32,32) if c['kind']=='binary-circle' else (72,32)
        sx,sy,sw,sh=c['slot_bbox']
        check(close(bbox,[sx+(sw-w)/2,sy+(sh-h)/2,w,h]),'body left its measured slot '+identity)
        check(shape.get('fill')==box['style']['fill'] and shape.get('stroke')==box['style']['stroke'] and
              abs(float(shape.get('stroke-width'))-box['style']['stroke_width'])<1e-6,'body style '+identity)
        if c['kind']=='binary-circle':
            check(tag(shape)=='circle' and shape.get('fill')=='white','arithmetic outline '+identity)
            symbols=[v for v in e if v.get('data-glyph-symbol')]
            check(len(symbols)==1 and symbols[0].get('data-glyph-symbol')==c['operation'] and ''.join(symbols[0].itertext())==('+' if c['operation']=='add' else '×'),'wrong arithmetic symbol '+identity)
            inputs=[r for r in layout['routes'] if r.get('dst') and r['dst'].rsplit(':',1)[0]==identity]
            check(len(inputs)==2 and len({tuple(r['points'][-1]) for r in inputs})==2,'two independent arithmetic inputs '+identity)
        else:
            check(tag(shape)=='rect' and radius==0,'tensor outline '+identity)
            lines=[v for v in e if tag(v)=='line']
            check(len(lines)==7,'symbolic tensor grid '+identity)
            x,y,w,h=bbox
            expected_lines=[[x+i*w/6,y,x+i*w/6,y+h] for i in range(1,6)]+[[x,y+i*h/3,x+w,y+i*h/3] for i in (1,2)]
            check(all(close([float(v.get(k,'nan')) for k in ('x1','y1','x2','y2')],expected) for v,expected in zip(lines,expected_lines)),'tensor cells '+identity)
        texts=[v for v in e if tag(v)=='text' and not v.get('data-glyph-symbol')]
        check(len(texts)==len(c['label_boxes']),'caption ownership '+identity)
        actual=''.join(''.join(v.itertext()) for v in texts)
        compact=lambda s:''.join(s.split())
        check(compact(node['label']) in compact(actual) and compact(node.get('shape','')) in compact(actual),'caption content '+identity)
        for text,record in zip(texts,c['label_boxes']):
            check(compact(''.join(text.itertext()))==compact(record['text'].replace(' | ','')),'caption text '+identity)
            tx,ty,size=[float(text.get(k,'nan')) for k in ('x','y','font-size')]
            check(math.isfinite(tx+ty+size),'caption coordinates '+identity)
            bx,by,bw,bh=record['bbox']
            if box.get('parent'):
                parent=next(b for b in layout['boxes'] if b['id']==box['parent']);px,py,pw,ph=parent['bbox']
                check(px<=bx and py<=by and bx+bw<=px+pw and by+bh<=py+ph,'caption crosses its owning scope '+identity)
            anchor=text.get('text-anchor','start');expected_x=bx+bw if anchor=='end' else bx+bw/2 if anchor=='middle' else bx
            check(abs(tx-expected_x)<1e-6 and abs(ty-size-by)<1e-6,'caption bounds '+identity)
        x,y,w,h=bbox;points={'in':[x+w/2,y+h],'out':[x+w/2,y],'left':[x,y+h/2],'right':[x+w,y+h/2]}
        for name,p in layout['ports'][identity].items():
            side=c['port_sides'].get(name)
            check(side in points and close(p,points[side]),'port is detached from actual outline '+identity+':'+name)
            field=layout.get('port_fields',{}).get(identity,{}).get(name)
            if field:check(field['side']==side,'port normal differs '+identity+':'+name)
    return count
