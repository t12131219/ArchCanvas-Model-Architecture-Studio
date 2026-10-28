// Guard the distinction between a completed diagnosis and a passed visual gate.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const data=JSON.parse(fs.readFileSync(path.join(here,'results.json'),'utf8'));
const rows=data.cases,states=rows.flatMap(c=>c.states.map(s=>({...s,case:c.id})));
const findings={
  cases:rows.length,
  states:states.length,
  structuralFailures:states.filter(s=>!s.ok).map(s=>({case:s.case,state:s.name})),
  sourceChanged:rows.filter(c=>!c.sourceUnchanged).map(c=>c.id),
  bindingRestorationFailures:states.filter(s=>s.bindingsRestored===false).map(s=>({case:s.case,state:s.name})),
  controlOmissions:states.filter(s=>s.controls?.length).map(s=>({case:s.case,state:s.name,count:s.controls.length})),
  narrowHairpins:states.filter(s=>s.metrics?.hairpinsBelow10>0).map(s=>({case:s.case,state:s.name,count:s.metrics.hairpinsBelow10})),
  fullVisualAcceptance:false,
  note:'Saved evidence gate only; this does not certify every UI interaction, label, viewport or exported file.'
};
fs.writeFileSync(path.join(here,'strict-findings.json'),JSON.stringify(findings,null,2));
console.log(JSON.stringify({cases:findings.cases,states:findings.states,structuralFailureStates:findings.structuralFailures.length,controlOmissionStates:findings.controlOmissions.length,narrowHairpinStates:findings.narrowHairpins.length,sourceChanged:findings.sourceChanged.length,bindingFailures:findings.bindingRestorationFailures.length,fullVisualAcceptance:false},null,2));
if(process.argv.includes('--strict')&&[findings.structuralFailures,findings.sourceChanged,findings.bindingRestorationFailures,findings.controlOmissions,findings.narrowHairpins].some(a=>a.length))process.exitCode=2;
