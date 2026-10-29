import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import ts from 'typescript';
import { getLocale, setLocale, subscribeLocale, t, uiMessage } from '../src/i18n.ts';
import { modelName } from '../src/modelName.ts';
const english=JSON.parse(readFileSync(new URL('../src/locales/en.json',import.meta.url),'utf8'));

test('UI language switches preserve opaque model/module names and interpolation values',()=>{
 let updates=0;const unsubscribe=subscribeLocale(()=>updates++);
 try {
  const data={title:'自定义 Encoder',module:'PositionwiseFeedForward',source:'class 中文名称: pass',args:{width:16}};
  const original=JSON.stringify(data);
  setLocale('en');assert.equal(getLocale(),'en');assert.equal(t('编辑'),'Edit');
  assert.equal(t('当前：{0}',{0:data.module}),'Current: PositionwiseFeedForward');
  assert.equal(t('当前：{0}',{0:data.title}),'Current: 自定义 Encoder');
  assert.equal(uiMessage('Error: 源码路径重复：model.py'),'Error: Duplicate source path: model.py');
  assert.equal(t('PositionwiseFeedForward'),'PositionwiseFeedForward');
  setLocale('unsupported');assert.equal(getLocale(),'en');
  setLocale('zh-CN');assert.equal(t('编辑'),'编辑');
  assert.equal(JSON.stringify(data),original);assert.equal(updates,2);
 }finally{unsubscribe();setLocale('zh-CN');}
});
test('all explicitly marked UI literals have English entries with identical placeholders',()=>{
 const missing=new Set<string>();
 for(const file of readdirSync(new URL('../src/',import.meta.url)).filter(f=>f.endsWith('.tsx'))){
  const source=readFileSync(new URL('../src/'+file,import.meta.url),'utf8'),ast=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
  function visit(n:ts.Node){if(ts.isCallExpression(n)&&n.expression.getText(ast)==='t'&&n.arguments[0]&&ts.isStringLiteral(n.arguments[0])){const key=n.arguments[0].text;if(!Object.hasOwn(english,key))missing.add(key);}ts.forEachChild(n,visit);}visit(ast);
 }
 assert.deepEqual([...missing],[]);
 for(const [key,value]of Object.entries(english))assert.deepEqual([...key.matchAll(/\{\d+\}/g)].map(m=>m[0]).sort(),[...(value as string).matchAll(/\{\d+\}/g)].map(m=>m[0]).sort(),key);
 assert.equal(readFileSync(new URL('../public/preview/ui-en.json',import.meta.url),'utf8'),readFileSync(new URL('../src/locales/en.json',import.meta.url),'utf8'));
});
test('model naming rejects invalid content, trims boundaries and never translates user names',()=>{
 assert.equal(modelName('  VisionEncoder  '),'VisionEncoder');
 assert.equal(modelName('我的模型'),'我的模型');
 for(const value of ['', '  ', 'x'.repeat(241),'A\nB','A\u007fB'])assert.throws(()=>modelName(value));
 assert.equal(modelName('x'.repeat(240)).length,240);
});

test('preview interaction notices have English entries, including conditional and parameterized feedback',()=>{
 const source=readFileSync(new URL('../public/preview/yworks_edge_router_lab/app.js',import.meta.url),'utf8');
 const ast=ts.createSourceFile('app.js',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS),missing=new Set<string>();
 function notice(node:ts.Node){
  if(ts.isConditionalExpression(node)){notice(node.whenTrue);notice(node.whenFalse);return;}
  const key=ts.isStringLiteral(node)||ts.isNoSubstitutionTemplateLiteral(node)?node.text:ts.isTemplateExpression(node)?node.head.text+node.templateSpans.map((span,index)=>`{${index}}`+span.literal.text).join(''):null;
  if(key&&/[\u3400-\u9fff]/.test(key)&&!Object.hasOwn(english,key))missing.add(key);
 }
 function visit(node:ts.Node){if(ts.isCallExpression(node)&&node.expression.getText(ast)==='toast'&&node.arguments[0])notice(node.arguments[0]);ts.forEachChild(node,visit);}
 visit(ast);assert.deepEqual([...missing],[]);
 try{setLocale('en');assert.equal(uiMessage('展开状态与局部布局已保存；可继续选择内部模块。'),'Expansion and local layout saved. You can select internal modules.');assert.equal(uiMessage('已导入 我的模型；文档证据未绑定 Python 源码，模型未执行。'),'Imported 我的模型; document evidence is not bound to Python source. The model was not executed.');}finally{setLocale('zh-CN');}
});
