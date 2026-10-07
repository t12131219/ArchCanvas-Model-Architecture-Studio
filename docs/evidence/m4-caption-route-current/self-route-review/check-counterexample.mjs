import { readFileSync, writeFileSync } from 'node:fs';
import { createOrthogonalRouter as before } from './before/core/orthogonalRouter.ts';
import { createOrthogonalRouter as after } from '../../../../studio/src/core/orthogonalRouter.ts';
const found = JSON.parse(readFileSync(new URL('./exploration-before.json',import.meta.url))).found[0];
const result=[];
for(let mask=0;mask<16;mask++) {
 const nodes=found.nodes.filter((n,i)=>i<2||mask&(1<<(i-2)));
 result.push({mask,nodeIds:nodes.map(n=>n.id),before:before(nodes).batch(found.requests)[0],after:after(nodes).batch(found.requests)[0]});
}
writeFileSync(new URL('./counterexample-subsets.json',import.meta.url),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result.map(r=>({mask:r.mask,nodeIds:r.nodeIds,before:r.before.path,after:r.after.path})),null,2));
