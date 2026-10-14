// Resumeable source/geometry/routing audit for every independently opened branch.
const fs=require('fs'),p=require('path'),b=p.resolve(__dirname,'../..'),dir=__dirname;require(b+'/yworks_edge_router_lab/router.js');const E=require(b+'/yworks_edge_router_lab/graph-engine.js'),F=require(b+'/yworks_edge_router_lab/recursive-graph.js'),C=globalThis.SummaryConstraints,cs=JSON.parse(fs.readFileSync(b+'/data/catalog.json')).cases;
const shard=+(process.env.RECURSIVE_SHARD||0),shards=+(process.env.RECURSIVE_SHARDS||8),start=Date.now(),output=dir+'/branch-results-'+shard+'.jsonl',resumed=fs.existsSync(dir+'/branches-resume.json')?JSON.parse(fs.readFileSync(dir+'/branches-resume.json')):[],prior=fs.existsSync(output)?fs.readFileSync(output,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse):[],saved=new Map([...resumed,...prior].map(r=>[r.id+':'+r.module,r])),done=[];let index=0;
for(const c of cs.filter(c=>!c.historical&&c.views.some(v=>v.json))){
 const sources=Object.fromEntries(c.views.filter(v=>v.json).map(v=>[v.key,C.initialize(JSON.parse(fs.readFileSync(p.join(b,v.json))))])),doc=F.create(sources);
 for(const id of F.containers(doc.authority).filter(id=>!doc.authority.mandatory.includes(id))){
  if(index++%shards!==shard)continue;const key=c.id+':'+id;if(saved.has(key)){done.push(saved.get(key));continue;}
  const d=E.clone(doc);let n=d.authority.detail.nodes.find(n=>n.id===id);while(n){if(!d.state.open.includes(n.id))d.state.open.push(n.id);n=d.authority.detail.nodes.find(v=>v.id===n.parent);}
  const g=F.build(d),t=Date.now();console.log('checking',c.title,id);const out=F.route(g,{margin:6,stub:28,crossingCost:450,edgeSpacing:12}),checked=E.validateView(g),r={id:c.id,title:c.title,module:id,failed:out.failed,source:checked.source,layout:checked.layout,errors:checked.edges.filter(([,v])=>!v.ok).map(([id,v])=>[id,v.violations]),ms:Date.now()-t};
  done.push(r);fs.appendFileSync(output,JSON.stringify(r)+'\n');if(out.failed||!r.source.ok||!r.layout.ok||r.errors.length)console.log('failure',JSON.stringify(r));
 }
}
const report={states:done.length,shard,shards,elapsedMs:Date.now()-start,failures:done.filter(r=>r.failed||!r.source.ok||!r.layout.ok||r.errors.length)};fs.writeFileSync(dir+'/branch-check-final-'+shard+'.json',JSON.stringify(report,null,2));console.log('FINISHED',report.states,'failures',report.failures.length,report.elapsedMs);if(report.failures.length)process.exitCode=1;
