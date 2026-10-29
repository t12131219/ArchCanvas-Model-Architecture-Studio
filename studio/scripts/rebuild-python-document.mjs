// The same authoring model used by Studio: empty -> add every part -> restore slots.
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const context=vm.createContext({});
vm.runInContext(readFileSync(new URL('../public/preview/semantic_studio/authoring-model.js',import.meta.url),'utf8'),context);
const A=context.SemanticAuthoring, request=JSON.parse(readFileSync(0,'utf8'));
let doc;
if(request.modules){
 doc=A.empty('ComposedModel');
 const external=A.addInterface(doc,'input','x'), output=A.addInterface(doc,'output','result');
 const added=request.modules.map(module=>A.add(doc,module).roots[0]);
 const input=id=>A.ports(doc,id).inputs[0],out=id=>A.ports(doc,id).outputs[0];
 A.connect(doc,{node:external,port:'out'},input(added[0]));
 A.connect(doc,out(added[0]),input(added[1]));
 A.connect(doc,out(added[1]),{node:output,port:'in'});
 if(request.reverse){
  doc.edges=doc.edges.filter(e=>e.evidence!=='authored-dependency');
  A.connect(doc,{node:external,port:'out'},input(added[1]));
  A.connect(doc,out(added[1]),input(added[0]));
  A.connect(doc,out(added[0]),{node:output,port:'in'});
 }
}else{
 const {module,atomic}=request,plan=A.recipe(module.ir,{atomic});
 doc=A.empty(module.title);doc.recipe={parents:plan.parents,baseline:plan.baseline};
 doc.codeReference={source:module.source,entry:module.entry,constructor:module.constructor};
 for(const part of [...plan.parts].reverse())A.add(doc,part,{keepIdentity:true});
 for(const edge of plan.connections)A.restoreConnection(doc,edge);
 if(JSON.stringify(A.sourceIR(doc))!==JSON.stringify(module.ir))throw Error('rebuild did not restore exact IR');
}
A.validate(doc);
process.stdout.write(JSON.stringify(doc));
