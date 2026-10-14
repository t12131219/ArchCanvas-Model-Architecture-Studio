"""Shared measured, hierarchical bottom-to-top SVG layout for explicit adapters."""
from __future__ import annotations
import html
import heapq
import hashlib
import json
import math
import re
import textwrap
from pathlib import Path
from theme import PALETTE as COLORS, INK, FONT, TEXT, SECONDARY, TYPE, FILL_WIDTH, node_style, manifest

GAP=24
PAD=32
HEAD=74
TAIL=26
MIN_TERMINAL=18


def wrapped(text, width, size=20, break_hyphens=False):
    # Deliberately conservative, deterministic estimation; export inspection remains required.
    chars=max(4,int(width/(size*.62)))
    return [line for raw in str(text).splitlines() for line in (textwrap.wrap(raw,chars,break_long_words=True,break_on_hyphens=break_hyphens) or [''])]


def visible_tree(node, level, root=False, overrides=None):
    out={k:v for k,v in node.items() if k!='items'}
    if node.get('items') and (root or level>=(overrides or {}).get(node['id'],node.get('expand',1))):
        out['items']=[visible_tree(n,level,overrides=overrides) for n in node['items'] if not n.get('fold_inline')]
    return out


def measure(node, level, min_width=0):
    children=node.get('items',[])
    if not children:
        width=max(min_width,node.get('width',330))
        label=wrapped(node['label'],width-48,TYPE['operator'])
        shape=wrapped(node.get('shape',''),width-40,TYPE['shape']) if node.get('shape') else []
        details=[]
        if level and node.get('mode'):
            details=[line for d in node.get('detail',[])[:1] for line in wrapped(d,width-48,TYPE['detail'])][:2]
        # Evidence badges are part of measurement and have their own final row.
        height=18+len(label)*24+len(shape)*19+len(details)*17+20
        node['_label'],node['_shape'],node['_details']=label,shape,details
        node['_size']=(width,max(68,height))
    else:
        sizes=[measure(n,level) for n in children]
        if node['mode']=='chain':
            width=max(min_width,max(w for w,h in sizes)+PAD*2)
            sizes=[measure(child,level,width-PAD*2) if child['id'] in FILL_WIDTH and cw<width-PAD*2 else (cw,ch)
                   for child,(cw,ch) in zip(children,sizes)]
            height=TAIL+sum(h for w,h in sizes)+GAP*(len(sizes)-1)
        else:
            width=max(min_width,sum(w for w,h in sizes)+PAD*2+48*(len(sizes)-1))
            height=TAIL+48+max(h for w,h in sizes)
        title_size=node_style(node,True)['title_size']
        left=wrapped(node['label'],width*.42,title_size,break_hyphens=True)
        right=wrapped(node.get('shape',''),width*.36,TYPE['shape'])
        node['_head']=max(HEAD,math.ceil(30+max((len(left)-1)*title_size*TYPE['line_height'],
                                              (len(right)-1)*TYPE['shape']*TYPE['line_height'])+35))
        height+=node['_head']
        node['_size']=(width,height)
    return node['_size']


class Scene:
    def __init__(self,width,height,evidence,ir,level):
        self.width,self.height,self.evidence,self.ir,self.level=width,height,evidence,ir,level
        self.nodes={n['id']:n for n in ir['nodes']}
        self.svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
          '<defs><marker id="arrow" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L9,4 L0,8 Z" fill="#263348"/></marker></defs>',
          '<rect width="100%" height="100%" fill="white"/>']
        binding=dict(model=ir['model'],source_archive_sha256=evidence['archive_sha256'],
                     semantic_ir_sha256=hashlib.sha256(json.dumps(ir,sort_keys=True).encode()).hexdigest(),view=level)
        self.svg.append('<metadata id="source-binding">'+html.escape(json.dumps(binding))+'</metadata>')
        self.svg.append('<metadata id="diagram-style">'+html.escape(json.dumps(manifest()))+'</metadata>')
        self.boxes=[];self.routes=[];self.ports={};self.texts=[]
    def text(self,x,y,lines,size=20,bold=False,anchor='middle',color=TEXT):
        if isinstance(lines,str):lines=lines.splitlines()
        self.svg.append(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="{anchor}" fill="{color}">')
        for i,line in enumerate(lines):
            self.svg.append(f'<tspan x="{x}" dy="{0 if i==0 else size*TYPE["line_height"]}">{html.escape(line)}</tspan>')
        self.svg.append('</text>')
        if lines:
            widths=[len(line)*size*.62 for line in lines]
            w=max(widths)
            xx=x-w/2 if anchor=='middle' else x if anchor=='start' else x-w
            self.texts.append(dict(text=' | '.join(lines),bbox=[xx,y-size,w,size*TYPE['line_height']*len(lines)]))
    def rect(self,node,x,y,w,h,parent,expanded=False):
        title='; '.join(f"{self.evidence['symbols'][s]['path']}:{self.evidence['symbols'][s]['start']} {self.evidence['symbols'][s]['symbol']}" for s in node['source'])
        title+='; parameter='+str(node.get('param_identity',node.get('parameter',node.get('parameter_scope','not asserted'))))
        title+='; '+' | '.join(node.get('detail',[]))
        style=node_style(node,expanded)
        self.svg.append(f'<g data-node-id="{html.escape(node["id"])}" data-visual-role="{style["role"]}"><title>{html.escape(title)}</title><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{style["radius"]}" fill="{style["fill"]}" stroke="{style["stroke"]}" stroke-width="{style["stroke_width"]}"/></g>')
        self.boxes.append(dict(id=node['id'],parent=parent,bbox=[x,y,w,h],radius=style['radius'],
                              expanded=expanded,source=node['source'],style=style))
        self.ports[node['id']]={'in':[x+w/2,y+h],'out':[x+w/2,y], 'left':[x,y+h/2],'right':[x+w,y+h/2]}
    def line(self,points,src,dst,role='tensor',dashed=False,arrow=True):
        clean=[]
        for point in points:
            point=list(point)
            if clean and point==clean[-1]:continue
            if len(clean)>1:
                a,b=clean[-2:]
                u=(b[0]-a[0],b[1]-a[1]);v=(point[0]-b[0],point[1]-b[1])
                if abs(u[0]*v[1]-u[1]*v[0])<1e-7 and u[0]*v[0]+u[1]*v[1]>0:clean.pop()
            clean.append(point)
        if len(clean)<2:return
        rid=f'route-{len(self.routes)+1:04d}'
        color='#536477' if dashed else INK
        d='M '+' L '.join(f'{x},{y}' for x,y in clean)
        self.svg.append(f'<path data-route-id="{rid}" d="{d}" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"'+(' stroke-dasharray="7 5"' if dashed else '')+(' marker-end="url(#arrow)"' if arrow else '')+'/>')
        self.routes.append(dict(id=rid,points=clean,src=src,dst=dst,role=role,arrow=arrow))
    def badge(self,node,x,y,w):
        ids=[self.evidence['symbols'][s]['evidence_id'] for s in node['source']]
        self.text(x+w-13,y,','.join(ids),TYPE['evidence'],anchor='end',color='#526170')
    def draw(self,node,x,y,parent=None):
        w,h=node['_size'];cx=x+w/2
        children=node.get('items',[])
        self.rect(node,x,y,w,h,parent,bool(children))
        if not children:
            yy=y+27
            self.text(cx,yy,node['_label'],TYPE['operator'],bool(node.get('mode')))
            yy+=24*len(node['_label'])
            if node['_shape']:
                self.text(cx,yy,node['_shape'],TYPE['shape'],color=SECONDARY);yy+=19*len(node['_shape'])
            if node['_details']:self.text(cx,yy,node['_details'],TYPE['detail'],color=SECONDARY)
            self.badge(node,x,y+h-10,w)
            return
        # Titles and shape occupy side blocks, leaving the center boundary corridor clear.
        title_size=node_style(node,True)['title_size']
        self.text(x+17,y+30,wrapped(node['label'],w*.42,title_size,break_hyphens=True),title_size,True,anchor='start')
        if node.get('shape'):
            self.text(x+w-17,y+30,wrapped(node['shape'],w*.36,TYPE['shape']),TYPE['shape'],anchor='end',color=SECONDARY)
        head=node['_head']
        self.badge(node,x,y+head-12,w)
        if node['mode']=='chain':
            cursor=y+h-TAIL
            for child in children:
                cw,ch=child['_size'];cursor-=ch
                self.draw(child,x+(w-cw)/2,cursor,node['id'])
                cursor-=GAP
            first,last=children[0]['id'],children[-1]['id']
            self.line([self.ports[node['id']]['in'],self.ports[first]['in']],node['id']+':in',first+':in','boundary')
            for a,b in zip(children,children[1:]):
                self.line([self.ports[a['id']]['out'],self.ports[b['id']]['in']],a['id']+':out',b['id']+':in',node.get('flow_role','tensor'))
            self.line([self.ports[last]['out'],self.ports[node['id']]['out']],last+':out',node['id']+':out','boundary')
            if node.get('residual') or node.get('retained_input'):
                source=self.ports[node['id']]['in'];destination=self.ports[last]['left']
                lane=x+14
                # Start below the first child and approach the Add from a clear left corridor.
                self.line([source,[cx,source[1]-18],[lane,source[1]-18],[lane,destination[1]],destination],node['id']+':in',last+':left','residual' if node.get('residual') else 'retained_input')
        else:
            bottom=y+h-TAIL
            bus_bottom=bottom-18
            bus_top=y+head-18
            xx=x+PAD
            for child in children:
                cw,ch=child['_size']
                self.draw(child,xx,bottom-48-ch,node['id']);xx+=cw+48
            # Each fork and collection is drawn once. No arithmetic is implied by a bus.
            centers=[self.ports[c['id']]['in'][0] for c in children]
            self.line([self.ports[node['id']]['in'],[cx,bus_bottom]],node['id']+':in',None,'boundary',arrow=False)
            self.line([[min(centers),bus_bottom],[max(centers),bus_bottom]],None,None,'fork',arrow=False)
            for child in children:
                pp=self.ports[child['id']]['in']
                self.line([[pp[0],bus_bottom],pp],None,child['id']+':in','fork')
                out=self.ports[child['id']]['out']
                self.line([out,[out[0],bus_top]],child['id']+':out',None,'tuple_collection',arrow=False)
            self.line([[min(centers),bus_top],[max(centers),bus_top]],None,None,'tuple_collection',arrow=False)
            self.line([[cx,bus_top],self.ports[node['id']]['out']],None,node['id']+':out','boundary')
    def write(self,path):
        Path(path).write_text('\n'.join(self.svg+['</svg>']),encoding='utf-8')
    def layout(self):
        return dict(canvas=[self.width,self.height],view=self.level,boxes=self.boxes,ports=self.ports,
                    routes=self.routes,texts=self.texts,minimum_terminal=MIN_TERMINAL,
                    visual_style=manifest(),
                    computation_direction='bottom-to-top; typed auxiliary edges may cross lanes',
                    measurement='conservative text-width estimate, recursive intrinsic height; inspected rendered export')


def nearest_visible(identity,parents,ports):
    while identity not in ports:
        identity=parents.get(identity)
        if identity is None:return None
    return identity


def route_auxiliary(scene,a,b,source_side,destination_side,source_id,destination_id):
    """Orthogonal A* over obstacle-derived coordinates, with mandatory 24px stubs."""
    start=[a[0]+(-24 if source_side=='left' else 24),a[1]]
    end=[b[0]+(-24 if destination_side=='left' else 24),b[1]]
    frames=scene.boxes
    frame_index={n['id']:n for n in frames}
    ancestors=set()
    for endpoint in (source_id,destination_id):
        while endpoint in frame_index:
            ancestors.add(endpoint);endpoint=frame_index[endpoint]['parent']
    leaves=[n for n in frames if not n['expanded'] or n['id'] not in ancestors]
    # Header/shape text is an obstacle too; leaf bodies already include leaf text.
    texts=[dict(bbox=[x-3,y-3,w+6,h+6]) for t in scene.texts for x,y,w,h in [t['bbox']]]
    xs={start[0],end[0],18,scene.width-18}
    ys={start[1],end[1],88,scene.height-260}
    for box in frames:
        x,y,w,h=box['bbox']
        xs.update((x-18,x+w+18));ys.update((y-18,y+h+18))
    xs=sorted(v for v in xs if 0<v<scene.width)
    ys=sorted(v for v in ys if 80<v<scene.height-250)
    if start[0] not in xs or start[1] not in ys or end[0] not in xs or end[1] not in ys:
        raise ValueError('Auxiliary route endpoints outside routing region')
    s=(xs.index(start[0]),ys.index(start[1]));t=(xs.index(end[0]),ys.index(end[1]))
    blocked_cache={}
    def allowed(p,q):
        key=tuple(sorted((p,q)))
        if key in blocked_cache:return blocked_cache[key]
        aa=(xs[p[0]],ys[p[1]]);bb=(xs[q[0]],ys[q[1]])
        okay=not any(intersects_segment(aa,bb,n) for n in leaves+texts)
        if okay:
            for frame in frames:
                x,y,w,h=frame['bbox'];rr=frame['radius']
                hit=0
                if aa[1]==bb[1] and (aa[1]==y or aa[1]==y+h):hit=min(max(aa[0],bb[0]),x+w-rr)-max(min(aa[0],bb[0]),x+rr)
                if aa[0]==bb[0] and (aa[0]==x or aa[0]==x+w):hit=min(max(aa[1],bb[1]),y+h-rr)-max(min(aa[1],bb[1]),y+rr)
                if hit>.01:okay=False;break
        blocked_cache[key]=okay
        return okay
    heuristic=lambda p:abs(xs[p[0]]-end[0])+abs(ys[p[1]]-end[1])
    initial=(s[0],s[1],0)
    heap=[(heuristic(s),0,initial)];cost={initial:0};previous={};finish=None
    while heap:
        estimate,g,state=heapq.heappop(heap)
        if g!=cost[state]:continue
        ix,iy,direction=state
        if (ix,iy)==t:finish=state;break
        for dx,dy,newdir in ((-1,0,0),(1,0,0),(0,-1,1),(0,1,1)):
            nx,ny=ix+dx,iy+dy
            if not(0<=nx<len(xs) and 0<=ny<len(ys)):continue
            if not allowed((ix,iy),(nx,ny)):continue
            length=abs(xs[nx]-xs[ix])+abs(ys[ny]-ys[iy])
            ng=g+length+(18 if direction!=newdir else 0)+(length*.2 if dy>0 else 0)
            nxt=(nx,ny,newdir)
            if ng<cost.get(nxt,float('inf')):
                cost[nxt]=ng;previous[nxt]=state
                heapq.heappush(heap,(ng+heuristic((nx,ny)),ng,nxt))
    if finish is None:raise ValueError('No obstacle-free auxiliary route')
    points=[];cur=finish
    while True:
        points.append([xs[cur[0]],ys[cur[1]]])
        if cur==initial:break
        cur=previous[cur]
    return [a]+list(reversed(points))+[b]


def render(model,evidence,ir,level,path):
    overrides=model.get('view_overrides',{}).get(str(level),{})
    tree=visible_tree(model['tree'],level,True,overrides)
    w,h=measure(tree,level)
    aux=[visible_tree(n,level) for n in model.get('aux_inputs',[])]
    edge_count=len(model.get('extra_edges',[]))
    side=(420 if aux else 230)+edge_count*12
    width=max(1200,w+side*2)
    height=h+380
    scene=Scene(width,height,evidence,ir,level)
    scene.text(width/2,37,model['name']+'  |  '+['Architecture overview','Module structure','Operators & tensor flow'][level],TYPE['title'],True)
    scene.text(width/2,65,'Long-term forecasting  /  '+model.get('profile_label','reviewed source profile')+'  /  read bottom to top',TYPE['subtitle'],color=SECONDARY)
    x=(width-w)/2;y=98
    scene.draw(tree,x,y)
    parents={n['id']:n['parent'] for n in ir['nodes']}
    ir_index={n['id']:n for n in ir['nodes']}
    def destination_left(dst,role):
        if role in ('statistics','normalization','scores','memory'):return True
        child=dst
        while parents.get(child):
            parent=parents[child]
            if parent in scene.ports and ir_index[parent].get('mode')=='parallel':
                return scene.ports[dst]['in'][0]<scene.ports[parent]['in'][0]
            child=parent
        return role=='covariate'
    occupied={True:[],False:[]}
    aux_sides={}
    for node in aux:
        targets=[e['dst'] for e in model.get('extra_edges',[]) if e['src']==node['id']]
        dst=nearest_visible(targets[0],parents,scene.ports) if targets else tree['id']
        aw,ah=measure(node,level)
        left=destination_left(dst,'covariate');aux_sides[node['id']]=left
        preferred=min(scene.height-275-ah,max(135,scene.ports[dst]['left'][1]+50))
        candidates=[preferred]+[preferred+direction*step*(ah+24) for step in range(1,len(aux)+2) for direction in (1,-1)]
        yy=next((v for v in candidates if v>=100 and v+ah<=scene.height-275 and
                 all(not(max(v,p[0])<min(v+ah,p[1])+24) for p in occupied[left])),None)
        if yy is None:raise ValueError('No free auxiliary input slot')
        occupied[left].append((yy,yy+ah))
        scene.draw(node,25 if left else width-25-aw,yy)
    for i,edge in enumerate(model.get('extra_edges',[])):
        src=nearest_visible(edge['src'],parents,scene.ports)
        dst=nearest_visible(edge['dst'],parents,scene.ports)
        if src is None or dst is None or src==dst:continue
        # If one endpoint is an ancestor, its typed state stays within the folded boundary.
        def is_ancestor(a,b):
            while b is not None:
                if a==b:return True
                b=parents.get(b)
            return False
        if is_ancestor(src,dst) or is_ancestor(dst,src):continue
        left=destination_left(dst,edge.get('role','tensor'))
        sp='left' if left else 'right';dp=sp
        a=scene.ports[src][sp];b=scene.ports[dst][dp]
        lane=(x-28-i*12) if left else (x+w+28+i*12)
        if src in [n['id'] for n in aux]:
            sp='right' if left else 'left';a=scene.ports[src][sp]
        points=route_auxiliary(scene,a,b,sp,dp,src,dst)
        scene.line(points,src+':'+sp,dst+':'+dp,edge.get('role','tensor'),dashed=True)
        scene.routes[-1].update(semantic_src=edge['src'],semantic_dst=edge['dst'],
                                semantic_src_port=edge.get('src_port','out'),semantic_dst_port=edge.get('dst_port','side'),
                                projected_src=src,projected_dst=dst)
        # Labels stay in the reserved gutters, away from terminal turns and modules.
        label=edge.get('label',edge.get('role',''))
        if label:
            actual=scene.routes[-1]['points']
            vertical=[(abs(q[1]-p[1]),p,q) for p,q in zip(actual,actual[1:]) if p[0]==q[0]]
            if vertical:
                _,p,q=max(vertical)
                tx=p[0]+(-7 if left else 7);ty=(p[1]+q[1])/2
                lines=wrapped(label,170,13);tw=max(map(len,lines))*13*.62
                bounds=dict(bbox=[tx-tw if left else tx,ty-13,tw,16*len(lines)])
                bx,by,bw,bh=bounds['bbox']
                collision=any(max(bx,n['bbox'][0])<min(bx+bw,n['bbox'][0]+n['bbox'][2]) and max(by,n['bbox'][1])<min(by+bh,n['bbox'][1]+n['bbox'][3]) for n in scene.boxes if not n['expanded'])
                if not collision and bx>=0 and bx+bw<=width:
                    scene.text(tx,ty,lines,13,anchor='end' if left else 'start',color='#536477')
    # Footer gives role identity without suggesting color means shared parameters.
    yy=height-245
    legend=[('embedding','Input / Embedding'),('attention','Attention'),('mixing','Mixing / FFN'),('decomposition','Decomposition'),('norm','Norm / Add'),('linear','Projection / Output')]
    start=width/2-550
    for i,(kind,label) in enumerate(legend):
        xx=start+i*185
        scene.svg.append(f'<rect x="{xx}" y="{yy}" width="16" height="16" rx="3" fill="{COLORS[kind]}" stroke="{INK}"/>')
        scene.text(xx+23,yy+13,label,TYPE['footer'],anchor='start')
    terms=[line for term in model.get('legend',[])[:3] for line in wrapped(term,width-120,TYPE['footer'])]
    scene.text(width/2,height-204,terms,TYPE['footer'],color=SECONDARY)
    scene.text(width/2,height-100,'Minor Dropout / FFN transpose steps are folded visually; all source operations remain in the semantic IR.',TYPE['footer'],color=SECONDARY)
    scene.text(width/2,height-70,'E### = source span (hover a module); dashed = named state / auxiliary input; fork-join = tuple/list, not sum.',TYPE['footer'],color=SECONDARY)
    scene.text(width/2,height-45,'Repeated colors encode operation roles. Shared weights and independent instances are recorded in semantic_ir.json.',TYPE['footer'],color=SECONDARY)
    scene.write(path)
    result=scene.layout();result['presentation_overrides']=overrides
    result['folded_inline_nodes']=[n['id'] for n in model_nodes(model['tree']) if n.get('fold_inline')]
    return result


def model_nodes(node):
    yield node
    for child in node.get('items',[]):yield from model_nodes(child)


def intersects_segment(a,b,box):
    x,y,w,h=box['bbox']
    if abs(a[0]-b[0])<1e-6:
        return x+1e-6<a[0]<x+w-1e-6 and max(min(a[1],b[1]),y+1e-6)<min(max(a[1],b[1]),y+h-1e-6)
    if abs(a[1]-b[1])<1e-6:
        return y+1e-6<a[1]<y+h-1e-6 and max(min(a[0],b[0]),x+1e-6)<min(max(a[0],b[0]),x+w-1e-6)
    return True


def validate(layout):
    errors=[];boxes=layout['boxes'];idx={n['id']:n for n in boxes}
    width,height=layout['canvas']
    def related(a,b):
        while a in idx:
            if a==b:return True
            a=idx[a]['parent']
        return False
    for b in boxes:
        x,y,w,h=b['bbox']
        if x<0 or y<0 or x+w>width or y+h>height:errors.append('outside canvas: '+b['id'])
        if b['parent'] in idx:
            px,py,pw,ph=idx[b['parent']]['bbox']
            if not(px<=x and py<=y and x+w<=px+pw and y+h<=py+ph):errors.append('containment: '+b['id'])
    for i,a in enumerate(boxes):
        for b in boxes[i+1:]:
            if a['parent']!=b['parent']:continue
            ax,ay,aw,ah=a['bbox'];bx,by,bw,bh=b['bbox']
            if max(ax,bx)<min(ax+aw,bx+bw)-.01 and max(ay,by)<min(ay+ah,by+bh)-.01:errors.append('sibling overlap: '+a['id']+' / '+b['id'])
    for route in layout['routes']:
        pts=route['points']
        if any(p[0]<0 or p[1]<0 or p[0]>width or p[1]>height for p in pts):errors.append('route outside canvas: '+route['id'])
        for endpoint,p in [('src',pts[0]),('dst',pts[-1])]:
            ref=route[endpoint]
            if ref:
                node,port=ref.rsplit(':',1)
                expected=layout['ports'].get(node,{}).get(port)
                if expected is None or any(abs(a-b)>1e-6 for a,b in zip(p,expected)):errors.append('endpoint: '+route['id'])
        if route['arrow'] and math.dist(pts[-2],pts[-1])<MIN_TERMINAL-.01:errors.append('short terminal: '+route['id'])
        for a,b in zip(pts,pts[1:]):
            if a[0]!=b[0] and a[1]!=b[1]:errors.append('non-orthogonal: '+route['id'])
            if route['role'] in ('tensor','boundary','fork','tuple_collection','seasonal','residual','retained_input') and b[1]>a[1]+.01:errors.append('downward main flow: '+route['id'])
            for frame in boxes:
                x,y,w,h=frame['bbox'];r=frame['radius']
                hit=0
                if a[1]==b[1] and (a[1]==y or a[1]==y+h):hit=min(max(a[0],b[0]),x+w-r)-max(min(a[0],b[0]),x+r)
                if a[0]==b[0] and (a[0]==x or a[0]==x+w):hit=min(max(a[1],b[1]),y+h-r)-max(min(a[1],b[1]),y+r)
                if hit>.01:errors.append('border run: '+route['id']+' / '+frame['id'])
                if not frame['expanded'] and intersects_segment(a,b,frame):
                    # A route may end at its named node's boundary, never pass through another leaf.
                    errors.append('route enters leaf: '+route['id']+' / '+frame['id'])
                if route.get('semantic_src') and frame['expanded'] and not related(route['projected_src'],frame['id']) and not related(route['projected_dst'],frame['id']) and intersects_segment(a,b,frame):
                    errors.append('side route enters unrelated group: '+route['id']+' / '+frame['id'])
    for text in layout.get('texts',[]):
        x,y,w,h=text['bbox']
        if x<-.01 or y<-.01 or x+w>width+.01 or y+h>height+.01:errors.append('text outside canvas: '+text['text'])
    return dict(passed=not errors,errors=sorted(set(errors)),box_count=len(boxes),route_count=len(layout['routes']),
                checks=['canvas bounds','child containment','sibling non-overlap','registered endpoints','terminal >=18px',
                        'orthogonal paths','upward main flow','no frame-border runs','no route through leaf interior',
                        'no side route through unrelated group','estimated text inside canvas'],
                limitations=['conservative text measurement; visual inspection required','no numerical model execution',
                             'dashed auxiliary edges may descend between lanes; semantic port roles retained separately in IR'])
