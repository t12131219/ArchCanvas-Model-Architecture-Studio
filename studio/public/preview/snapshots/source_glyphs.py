"""Small source-grounded presentation vocabulary: tensor grids and binary circles.

The semantic IR is authoritative. A presentation contract never adds a tensor,
edge, parameter sharing claim, or arithmetic meaning to an opaque module.
"""
from __future__ import annotations
import ast,copy,html,itertools,json,math,re,sys,textwrap,xml.etree.ElementTree as ET
from pathlib import Path
SVG='http://www.w3.org/2000/svg'
ET.register_namespace('',SVG)
VERSION='source-glyph-presentation/1'


def source_expression(node,evidence,expression):
    try:expected=ast.dump(ast.parse(expression,mode='eval').body,include_attributes=False)
    except SyntaxError:return False
    return any(expected==ast.dump(a,include_attributes=False) for s in node.get('source',[]) for a in ast.walk(ast.parse(textwrap.dedent(evidence['symbols'][s]['snippet']))))


def classify(node,ir,evidence,request=None):
    if node.get('mode') or not node.get('source_evidence'):return None
    op=node.get('operation',node.get('kind'));authority='typed IR operation'
    if request:
        expression=request['expression'];op=request['operation']
        if not source_expression(node,evidence,expression):raise ValueError('Unproven glyph expression: '+node['id'])
        root=ast.parse(expression,mode='eval').body
        if not isinstance(root,ast.BinOp) or type(root.op)!={'add':ast.Add,'multiply':ast.Mult}.get(op):raise ValueError('Wrong glyph operator: '+node['id'])
        authority='adapter expression matched to frozen source AST'
    if op in ('add','multiply','elementwise_multiply'):
        expression=node.get('expression')
        if expression:
            try:root=ast.parse(expression,mode='eval').body
            except SyntaxError:return None
            wanted=ast.Add if op=='add' else ast.Mult
            if not (isinstance(root,ast.BinOp) and isinstance(root.op,wanted) or isinstance(root,ast.Call) and isinstance(root.func,ast.Attribute) and root.func.attr in (('add',) if op=='add' else ('mul','multiply'))):return None
        incoming=[e for e in ir['edges'] if e['dst']==node['id'] and e['role'] not in ('shape_dependency','output_binding')]
        if len(incoming)!=2:return None
        operation='add' if op=='add' else 'multiply'
        return dict(schema=VERSION,kind='binary-circle',operation=operation,symbol='+' if operation=='add' else '×',
                    authority=authority,source_expression=request['expression'] if request else None,
                    source_evidence=node['source_evidence'],semantic_node=node['id'],silhouette='circle')
    kind=node.get('kind');shape=node.get('shape','').strip()
    if node.get('output_tuple') or node.get('chunk_order') or node.get('ordered_output_scales') or node.get('semantic_mode'):return None
    simple=re.fullmatch(r'(?:[A-Za-z_][\w ]*:\s*)?(?:\[[\w ,=]+\]|[A-Za-z0-9_]+(?:\s*,\s*[A-Za-z0-9_]+)+)',shape)
    value=kind in ('input','output','parameter') or kind=='tensor' and node.get('state_role')
    if value and simple:
        return dict(schema=VERSION,kind='tensor-grid',operation=None,authority='typed IR value and explicit tensor shape',
                    source_evidence=node['source_evidence'],semantic_node=node['id'],silhouette='rectangle',
                    grid='symbolic 3 by 6 cells; not numerical dimensions or runtime values')
    return None


def wrapped(text,width,size):
    return [line for raw in str(text).splitlines() for line in (textwrap.wrap(raw,max(4,int(width/(size*.62))),break_long_words=True,break_on_hyphens=False) or [''])]


def text_element(x,y,lines,size,anchor='start',bold=False):
    e=ET.Element('{'+SVG+'}text',dict(x=str(x),y=str(y),**{'font-family':'DejaVu Sans,Arial,sans-serif','font-size':str(size),'font-weight':'700' if bold else '400','text-anchor':anchor,'fill':'#172336'}))
    for i,line in enumerate(lines):ET.SubElement(e,'{'+SVG+'}tspan',dict(x=str(x),dy=str(0 if i==0 else size*1.18))).text=line
    w=max(map(len,lines),default=0)*size*.62
    return e,dict(text=' | '.join(lines),bbox=[x-w if anchor=='end' else x-w/2 if anchor=='middle' else x,y-size,w,size*1.18*len(lines)])


def body(contract,box,node,evidence):
    sx,sy,sw,sh=contract['slot_bbox'];x,y,w,h=box['bbox'];cx=x+w/2;cy=y+h/2;ink=box['style']['stroke']
    g=ET.Element('{'+SVG+'}g',{'data-node-id':node['id'],'data-visual-role':box['style']['role'],'data-glyph-kind':contract['kind']})
    labels=[]
    if contract['kind']=='binary-circle':
        ET.SubElement(g,'{'+SVG+'}circle',dict(cx=str(cx),cy=str(cy),r=str(w/2),fill='white',stroke=ink,**{'stroke-width':'2','data-glyph-outline':'circle'}))
        e,_=text_element(cx,cy+7,[contract['symbol']],22,'middle');e.set('data-glyph-symbol',contract['operation']);g.append(e)
        tx=cx+28;tw=max(70,sw/2-38);size=14
        label=wrapped(node['label'],tw,size);shape=wrapped(node.get('shape',''),tw,11)
        while len(label)*size*1.18+len(shape)*13+13>sh-8 and size>12:
            size-=1;label=wrapped(node['label'],tw,size)
        # Leave the horizontal input corridor through the centre unobstructed.
        # A caption is part of its operator, not part of the incoming wire.
        yy=cy-14-(len(label)-1)*size*1.18
        e,b=text_element(tx,yy,label,size);g.append(e);labels.append(b)
        yy=cy+26
        if shape:
            e,b=text_element(tx,yy,shape,11);g.append(e);labels.append(b);yy+=len(shape)*13+3
        badge=','.join(node['source_evidence'][:2])
        e,b=text_element(tx,max(yy,sy+sh-3),[badge],9);g.append(e);labels.append(b)
    else:
        ET.SubElement(g,'{'+SVG+'}rect',dict(x=str(x),y=str(y),width=str(w),height=str(h),rx='0',fill=box['style']['fill'],stroke=ink,**{'stroke-width':'1.4','data-glyph-outline':'rectangle'}))
        for i in range(1,6):ET.SubElement(g,'{'+SVG+'}line',dict(x1=str(x+i*w/6),x2=str(x+i*w/6),y1=str(y),y2=str(y+h),stroke=ink,**{'stroke-width':'.6'}))
        for i in (1,2):ET.SubElement(g,'{'+SVG+'}line',dict(x1=str(x),x2=str(x+w),y1=str(y+i*h/3),y2=str(y+i*h/3),stroke=ink,**{'stroke-width':'.6'}))
        tw=max(70,sw/2-46)
        for caption,tx,anchor,bold in [(node['label'],x-10,'end',True),(node.get('shape',''),x+w+10,'start',False)]:
            lines=wrapped(caption,tw,14)
            if lines:
                e,b=text_element(tx,cy+5-(len(lines)-1)*8,lines,14,anchor,bold);g.append(e);labels.append(b)
        e,b=text_element(x+w+10,sy+sh-3,[','.join(node['source_evidence'][:2])],9);g.append(e);labels.append(b)
    contract['label_boxes']=labels
    return g


def finalize(scene,model,path,route_fn=None):
    """Refine only eligible leaf bodies inside their existing measured slots."""
    if route_fn is None:
        # Reuse the orthogonal source router, never execute upstream model code.
        import importlib.util
        directory=Path(__file__).resolve().parent/'model_zoo_programmatic_guide'
        sys.path.append(str(directory))
        spec=importlib.util.spec_from_file_location('_source_glyph_router',directory/'layout.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        route_fn=module.route_auxiliary
    doc=ET.fromstring('\n'.join(scene.svg+['</svg>']));boxes={b['id']:b for b in scene.boxes};selected={};mapped={}
    requests=dict(model.get('glyph_bindings',{}))
    def visit(n):
        if n.get('glyph_expression'):
            expr=n['glyph_expression'];root=ast.parse(expr,mode='eval').body
            operation={ast.Add:'add',ast.Mult:'multiply'}.get(type(getattr(root,'op',None)))
            requests[n['id']]={'operation':operation,'expression':expr}
        for child in n.get('items',[]):visit(child)
    visit(model['tree'])
    for n in model.get('aux_inputs',[]):visit(n)
    for identity,box in boxes.items():
        if box['expanded']:continue
        node=scene.nodes[identity];contract=classify(node,scene.ir,scene.evidence,requests.get(identity))
        if not contract:continue
        uses={'src':set(),'dst':set()}
        for r in scene.routes:
            for end in uses:
                ref=r.get(end)
                if ref and ref.rsplit(':',1)[0]==identity:uses[end].add(ref.rsplit(':',1)[1])
        if contract['kind']=='binary-circle' and (len(uses['src'])>1 or len(uses['dst'])!=2):continue
        if contract['kind']=='tensor-grid' and any(p.split('.')[0] in ('left','right') for ps in uses.values() for p in ps):continue
        old=box['bbox'];cx=old[0]+old[2]/2;cy=old[1]+old[3]/2;w,h=(32,32) if contract['kind']=='binary-circle' else (72,32)
        contract['slot_bbox']=list(old);box['bbox']=[cx-w/2,cy-h/2,w,h];box['radius']=w/2 if contract['kind']=='binary-circle' else 0;box['presentation']=contract
        sides={'in':[cx,cy+h/2],'out':[cx,cy-h/2],'left':[cx-w/2,cy],'right':[cx+w/2,cy]}
        mapping={}
        for p in scene.ports[identity]:mapping[p]=p.split('.')[0]
        if contract['kind']=='binary-circle':
            for p in uses['src']:mapping[p]='out'
            incoming=sorted(uses['dst'])
            producers={}
            for r in scene.routes:
                if r.get('dst') and r['dst'].rsplit(':',1)[0]==identity:
                    producers[r['dst'].rsplit(':',1)[1]]=r['points'][0]
            normals={'in':(0,1),'left':(-1,0),'right':(1,0)}
            def score(assignment):
                total=0
                for p,s in zip(incoming,assignment):
                    px,py=producers[p];dx,dy=px-cx,py-cy;nx,ny=normals[s]
                    total+=abs(px-sides[s][0])+abs(py-sides[s][1])
                    total+=80*(1-(dx*nx+dy*ny)/max(1,math.hypot(dx,dy)))
                return total
            assignment=min(itertools.permutations(normals,len(incoming)),key=score)
            mapping.update(zip(incoming,assignment))
        contract['port_sides']=mapping
        if contract['kind']=='binary-circle':box['style'].update(fill='white',stroke_width=2)
        else:box['style']['stroke_width']=1.4
        for p,s in mapping.items():
            scene.ports[identity][p]=list(sides[s]);mapped[(identity,p)]=s
            if hasattr(scene,'port_fields') and p in scene.port_fields.get(identity,{}):scene.port_fields[identity][p]['side']=s
        selected[identity]=contract
    if not selected:return
    # Replace the original body and its labels as one owned SVG group.
    active=None
    for e in list(doc):
        identity=e.get('data-node-id')
        if identity:
            active=identity
            if identity in selected:
                new=body(selected[identity],boxes[identity],scene.nodes[identity],scene.evidence)
                titles=[c for c in e if c.tag.rsplit('}',1)[-1]=='title']
                for title in reversed(titles):new.insert(0,title)
                index=list(doc).index(e);doc.remove(e);doc.insert(index,new)
            continue
        if active in selected and e.tag.rsplit('}',1)[-1]=='text' and not e.get('data-edge-label-id') and not e.get('data-follow-id'):
            try:tx,ty=float(e.get('x')),float(e.get('y'))
            except (TypeError,ValueError):continue
            sx,sy,sw,sh=selected[active]['slot_bbox']
            if sx-8<=tx<=sx+sw+8 and sy-8<=ty<=sy+sh+8:doc.remove(e)
    scene.texts=[t for t in scene.texts if not any(sx-8<=t['bbox'][0]+t['bbox'][2]/2<=sx+sw+8 and sy-8<=t['bbox'][1]+t['bbox'][3]/2<=sy+sh+8 for c in selected.values() for sx,sy,sw,sh in [c['slot_bbox']])]
    scene.texts.extend(b for c in selected.values() for b in c['label_boxes'])
    old_routes=scene.routes
    def affected(r):return any(r.get(end) and r[end].rsplit(':',1)[0] in selected for end in ('src','dst'))
    # Reserve existing unaffected corridors before laying out any compact body.
    # Otherwise a new incoming wire can occupy a later edge's retained route.
    scene.routes=[r for r in old_routes if not affected(r)]
    elements={e.get('data-route-id'):e for e in doc if e.get('data-route-id')}
    for r in old_routes:
        refs=[r.get(end) for end in ('src','dst')]
        if not affected(r):continue
        if all(refs):
            (src,sp),(dst,dp)=[ref.rsplit(':',1) for ref in refs]
            a=scene.ports[src][sp];b=scene.ports[dst][dp]
            ss=mapped.get((src,sp),sp.split('.')[0]);ds=mapped.get((dst,dp),dp.split('.')[0])
            def descendant(child,parent):
                while child in boxes:
                    if child==parent:return True
                    child=boxes[child]['parent']
                return False
            reverse={'in':'out','out':'in','left':'right','right':'left'}
            if boxes[src]['expanded'] and descendant(dst,src):ss=reverse[ss]
            if boxes[dst]['expanded'] and descendant(src,dst):ds=reverse[ds]
            def clear(p,q):
                from_boxes=[n for n in boxes.values() if n['id'] not in (src,dst) and
                            (not n['expanded'] or not descendant(src,n['id']) and not descendant(dst,n['id']))]
                from_boxes += [dict(bbox=t['bbox']) for t in scene.texts]
                def hits(n):
                    x,y,w,h=n['bbox']
                    return x<p[0]<x+w and max(min(p[1],q[1]),y)<min(max(p[1],q[1]),y+h) if p[0]==q[0] else y<p[1]<y+h and max(min(p[0],q[0]),x)<min(max(p[0],q[0]),x+w)
                if any(hits(n) for n in from_boxes):return False
                wire=r.get('wire_identity',[src,'out'])
                for other in scene.routes:
                    if other.get('wire_identity')==wire:continue
                    for u,v in zip(other['points'],other['points'][1:]):
                        if p[0]==q[0]==u[0]==v[0] and min(max(p[1],q[1]),max(u[1],v[1]))>max(min(p[1],q[1]),min(u[1],v[1])):return False
                        if p[1]==q[1]==u[1]==v[1] and min(max(p[0],q[0]),max(u[0],v[0]))>max(min(p[0],q[0]),min(u[0],v[0])):return False
                return True
            if a[0]==b[0] and ss=='out' and ds=='in' and a[1]>b[1] and clear(a,b):points=[a,b]
            else:points=route_fn(scene,a,b,ss,ds,src,dst,semantic_source=tuple(r.get('wire_identity',[src,'out'])),frame_clearance=max(8,r.get('frame_clearance',0)),source_stub=24 if r.get('explicit_sides') else 16)
            clean=[]
            for p in points:
                p=list(p)
                if clean and p==clean[-1]:continue
                if len(clean)>1:
                    u,v=clean[-2:]
                    if (u[0]==v[0]==p[0] or u[1]==v[1]==p[1]) and (v[0]-u[0])*(p[0]-v[0])+(v[1]-u[1])*(p[1]-v[1])>=0:clean.pop()
                clean.append(p)
            r['points']=clean
            if r.get('explicit_sides'):r['explicit_sides']={'src':ss,'dst':ds}
            elements[r['id']].set('d','M '+' L '.join(f'{x},{y}' for x,y in clean))
        else:
            # A tuple/list bus may have a named node at only one end. Its
            # anonymous junction remains fixed; only the registered terminal
            # moves with its body. Such a bus never becomes arithmetic Add.
            points=copy.deepcopy(r['points'])
            for ref,index,adjacent in ((refs[0],0,1),(refs[1],-1,-2)):
                if not ref:continue
                identity,p=ref.rsplit(':',1)
                if identity not in selected:continue
                old=points[index];new=scene.ports[identity][p]
                if points[adjacent][0]==old[0]:points[adjacent][0]=new[0]
                else:points[adjacent][1]=new[1]
                points[index]=list(new)
            r['points']=points
            elements[r['id']].set('d','M '+' L '.join(f'{x},{y}' for x,y in points))
        scene.routes.append(r)
    scene.routes=sorted(scene.routes,key=lambda r:next(i for i,v in enumerate(old_routes) if v['id']==r['id']))
    # Captions keep canonical edge identities; their source binding is unchanged.
    scene.svg=[ET.tostring(e,encoding='unicode') for e in doc]
    scene.svg.insert(0,ET.tostring(ET.Element('{'+SVG+'}svg',doc.attrib),encoding='unicode').replace(' />','>').replace('/>','>'))
    scene.write(path)
