
import {readFile,writeFile} from 'node:fs/promises';
const {createDocument,applyVisualBatch,buildScene,renderSvg}=await import(process.argv[2]);
const output=process.argv[3];
const facts=(scene)=>new Map(scene.nodes.map(n=>[n.id,{x:n.x,y:n.y,width:n.width,height:n.height}]));
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const reports=[];
for(const fixture of ['transformer','mlp','residual_cnn']) {
  const a=JSON.parse(await readFile(`${output}/${fixture}.architecture.json`,'utf8'));
  const by=new Map(a.nodes.map(n=>[n.id,n]));
  const depth=(node)=>{let n=node,d=0;while(n.parentId){d++;n=by.get(n.parentId)}return d};
  let d=createDocument(a),base=buildScene(d);
  const pin=base.nodes.find(n=>!n.children && n.category==='output') ?? base.nodes.find(n=>n.category==='output');
  const pinNode=base.nodes.find(n=>n.id===pin?.id);
  const initialPin=pinNode && {x:pinNode.x,y:pinNode.y};
  let pinnedDocument=pinNode?applyVisualBatch(d,[{type:'pin',ids:[pinNode.id],pinned:true}]):d;
  // A representative full frontier at each available authored containment depth.
  // A shallow model is not advertised as having three recovered hierarchy levels.
  const maxDepth=Math.max(...a.nodes.filter(n=>n.children.length).map(depth));
  const continuity=[];
  for(let level=0;level<=Math.min(3,maxDepth);level++) {
    if(level>0)for(const n of a.nodes.filter(n=>n.children.length && depth(n)===level)) {
      const before=buildScene(d),anchor=before.nodes.find(v=>v.id===n.id);
      d=applyVisualBatch(d,[{type:'expand',id:n.id,expanded:true}]);
      pinnedDocument=applyVisualBatch(pinnedDocument,[{type:'expand',id:n.id,expanded:true}]);
      const after=buildScene(d),current=after.nodes.find(v=>v.id===n.id),pinned=buildScene(pinnedDocument).nodes.find(v=>v.id===pinNode?.id);
      continuity.push({operatedId:n.id,level,anchorBefore:{x:anchor?.x,y:anchor?.y},anchorAfter:{x:current?.x,y:current?.y},
        anchorUnchanged:anchor?.x===current?.x&&anchor?.y===current?.y,
        pinUnchanged:!initialPin||(pinned?.x===initialPin.x&&pinned?.y===initialPin.y)});
    }
    for(const preset of ['paper','monochrome'])for(const widthMm of [85,180]) {
      const current=applyVisualBatch(d,[{type:'page',page:{preset,widthMm}}]);
      const scene=buildScene(current),name=`${fixture}-level${level}-${preset}-${widthMm}`;
      await writeFile(`${output}/${name}.canvas.json`,JSON.stringify(current));
      await writeFile(`${output}/${name}.scene.json`,JSON.stringify(scene));
      await writeFile(`${output}/${name}.svg`,renderSvg(scene));
      const represented=scene.edges.flatMap(e=>e.canonicalEdgeIds).concat(scene.hiddenEdges);
      const edgeCoverage=same([...represented].sort(),a.edges.map(e=>e.id).sort());
      const endpointChecks=scene.edges.map(e=>{
        const source=scene.nodes.find(n=>n.id===e.sourceId),target=scene.nodes.find(n=>n.id===e.targetId);
        const sp=source.ports.find(p=>p.canonicalEdgeIds.includes(e.id)&&p.direction==='out');
        const tp=target.ports.find(p=>p.canonicalEdgeIds.includes(e.id)&&p.direction==='in');
        const tokens=[...e.path.matchAll(/([MVH])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?/g)];
        let x=0,y=0;const points=[];
        for(const [,op,first,second]of tokens){if(op==='M'){x=+first;y=+second}else if(op==='V')y=+first;else x=+first;points.push({x,y})}
        // Scene routes round coordinates to 0.1 model units, SVG to 0.01.
        const close=(p,q)=>p&&q&&Math.abs(p.x-q.x)<=.051&&Math.abs(p.y-q.y)<=.051;
        return {id:e.id,passed:!!sp&&!!tp&&close(points[0],sp)&&close(points.at(-1),tp)};
      });
      const glyphMeaning=scene.nodes.every(n=>!!n.glyph&&!!n.label)&&scene.edges.filter(e=>e.role==='mask').every(e=>e.dashed);
      const overlap=(p,q)=>p.x<q.x+q.width&&p.x+p.width>q.x&&p.y<q.y+q.height&&p.y+p.height>q.y;
      const siblingOverlaps=scene.nodes.flatMap((node,i)=>scene.nodes.slice(i+1).filter(other=>node.parentId===other.parentId&&overlap(node,other)).map(other=>[node.id,other.id]));
      reports.push({name,fixture,level,preset,widthMm,sceneWidth:scene.bounds.width,sceneHeight:scene.bounds.height,
        sourceDigest:scene.sourceDigest,irDigest:scene.irDigest,edgeCoverage,endpointChecks,
        monochromeMeaningViaLabelsGlyphsAndMaskDashes:glyphMeaning,siblingOverlaps,visibleNodes:scene.nodes.length,visibleEdges:scene.edges.length});
    }
  }
  // Restore the complete base frontier. Geometry recovery is separate from visual undo.
  for(const n of [...a.nodes].reverse().filter(n=>n.children.length&&d.expandedIds.includes(n.id)&&depth(n)>0))
    d=applyVisualBatch(d,[{type:'expand',id:n.id,expanded:false}]);
  const restored=buildScene(d),restore=facts(restored),original=facts(base);
  const geometryRestored=[...original].every(([id,b])=>same(restore.get(id),b));
  await writeFile(`${output}/${fixture}-continuity.json`,JSON.stringify({maxAuthoredContainerDepth:maxDepth,continuity,
    anchorAndPinPassed:continuity.every(c=>c.anchorUnchanged&&c.pinUnchanged),baseGeometryRestored:geometryRestored,
    pinnedConflictDiagnostics:buildScene(pinnedDocument).diagnostics.filter(d=>d.message.includes('overlaps expanded'))},null,2));
}
await writeFile(`${output}/scene-audit.json`,JSON.stringify(reports,null,2));
