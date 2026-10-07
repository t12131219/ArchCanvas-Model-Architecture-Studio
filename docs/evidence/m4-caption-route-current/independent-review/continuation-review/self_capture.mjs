import {readFileSync,writeFileSync} from 'node:fs';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url)),tag=process.argv[2];
const {createOrthogonalRouter:before}=await import(pathToFileURL(path.join(here,'../snapshots/continuation-review/attempt-1/core/orthogonalRouter.ts')));
const {createOrthogonalRouter:after}=await import(pathToFileURL(path.join(here,`../snapshots/${tag}/core/orthogonalRouter.ts`)));
const found=JSON.parse(readFileSync(path.join(here,'../../self-route-review/exploration-before.json'))).found[0];
const records=[];
for(let mask=0;mask<16;mask++){
 const nodes=found.nodes.filter((n,i)=>i<2||mask&(1<<(i-2))),requests=found.requests;
 const bytes=JSON.stringify({nodes,requests}),old=before(nodes).batch(requests),next=after(nodes).batch(requests),repeated=after(nodes).batch(requests);
 records.push({name:`self-counterexample-obstacles-mask-${mask}`,nodes,requests,old,next,immutable:bytes===JSON.stringify({nodes,requests}),deterministic:JSON.stringify(next)===JSON.stringify(repeated)});
}
writeFileSync(path.join(here,'..',tag,'self-counterexample.json'),JSON.stringify({tag,records},null,2)+'\n');
console.log(JSON.stringify({tag,cases:records.length,immutable:records.every(r=>r.immutable),deterministic:records.every(r=>r.deterministic)}));
