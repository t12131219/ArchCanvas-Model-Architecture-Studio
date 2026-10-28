import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {auditPreviewAuthorities} from '../scripts/audit-preview-authorities.ts';

test('production excludes retired preview implementations while retaining formal source Worker, authoring and export dependencies',()=>{
 const report=auditPreviewAuthorities(fileURLToPath(new URL('../',import.meta.url)));assert.equal(report.ok,true,JSON.stringify(report));
 for(const name of ['src/AuthoringStudio.tsx','src/sourceEditingWorker.ts','src/sourceEditingProjection.ts','src/core/scene.ts','src/core/exportScene.ts','src/core/orthogonalRouter.ts','src/core/portRouting.ts','src/core/sourceRelationRoutes.ts','src/core/memoryContinuity.ts'])assert.ok(report.reachable.includes(name),name);
});
function fixture(t:any,files:Record<string,string>){
 const root=mkdtempSync(path.join(tmpdir(),'archcanvas-authority-audit-'));t.after(()=>rmSync(root,{recursive:true,force:true}));
 for(const [name,text]of Object.entries(files)){const file=path.join(root,'src',name);mkdirSync(path.dirname(file),{recursive:true});writeFileSync(file,text);}
 return root;
}
test('authority audit follows export cycles, literal imports and Worker URL entries; renamed retired declarations fail',t=>{
 const root=fixture(t,{'main.tsx':"export * from './a.ts'; void import('./lazy.ts'); new Worker(new URL('./worker.ts', import.meta.url));",'a.ts':"export * from './b.ts';",'b.ts':"export * from './a.ts';",'lazy.ts':'export const lazy=1;','worker.ts':"import './projection.ts';",'projection.ts':'export const source=1;'});
 const report=auditPreviewAuthorities(root);assert.equal(report.ok,true);assert.equal(report.reachableModules,6);
 writeFileSync(path.join(root,'src','renamed.ts'),'export function prepareMovePreview() {}');
 const rejected=auditPreviewAuthorities(root);assert.equal(rejected.ok,false);assert.deepEqual(rejected.retiredDeclarations,[{file:'src/renamed.ts',name:'prepareMovePreview'}]);
});
test('unresolved dynamic imports and production links into retired test support cannot be reported as complete',t=>{
 const root=fixture(t,{'main.tsx':"const target='./opaque.ts'; void import(target); import '../tests/retired-preview/movePreview.ts';"});
 const report=auditPreviewAuthorities(root);assert.equal(report.ok,false);assert.equal(report.unresolvedDynamicImports.length,1);assert.equal(report.testOnlyImports.length,1);
});
