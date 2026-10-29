import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

test('preview locale messages translate chrome and accessibility while retaining opaque source labels and subtitle bounds',async()=>{
 const english=JSON.parse(readFileSync(new URL('../src/locales/en.json',import.meta.url),'utf8'));
 const callbacks:Record<string,(event:any)=>void>={};
 const element=(attributes:Record<string,string>,textContent='')=>({
  attributes,textContent,isConnected:true,
  getAttribute(name:string){return this.attributes[name]??null;},
  setAttribute(name:string,value:unknown){this.attributes[name]=String(value);},
  removeAttribute(name:string){delete this.attributes[name];},
 });
 const title=element({},'我的 Encoder'),module=element({},'CustomPair');
 const subtitle=element({'data-ui-message':'源码语义 · 可逆语义图 · 可继续展开至源码细节','data-ui-width':'640'},'源码语义 · 可逆语义图 · 可继续展开至源码细节');
 const toggle=element({'aria-label':'展开 我的 Encoder'});
 const node=element({'aria-label':'节点 custom:id 我的 Encoder','data-node-id':'custom:id'});
 const edge=element({'aria-label':'边 e a 到 b','data-edge-id':'e','data-source':'a','data-target':'b'});
 const document={documentElement:{lang:''},body:{querySelectorAll:()=>[]},querySelectorAll:(selector:string)=>{
  if(selector==='[data-ui-message]')return [subtitle];
  if(selector==='[data-node-id][aria-label]')return [node];
  if(selector==='[data-edge-id][aria-label]')return [edge];
  if(selector==='.expansion-control')return [toggle];
  return [];
 }};
 const root:any={location:{origin:'http://localhost'},addEventListener:(name:string,fn:any)=>callbacks[name]=fn};root.parent={};
 const context=vm.createContext({window:root,document,localStorage:{getItem:()=>null},MutationObserver:class{observe(){}disconnect(){}},fetch:async()=>({ok:true,json:async()=>english})});
 vm.runInContext(readFileSync(new URL('../public/preview/yworks_edge_router_lab/studio-locale.js',import.meta.url),'utf8'),context);
 await new Promise(resolve=>setImmediate(resolve));
 const message=(locale:string,origin='http://localhost')=>callbacks.message({source:root.parent,origin,data:{type:'archcanvas:ui-locale',locale}});
 message('en','http://untrusted.invalid');assert.equal(document.documentElement.lang,'zh-CN');
 message('en');
 assert.equal(document.documentElement.lang,'en');
 assert.equal(subtitle.textContent,'Source semantics · Reversible graph · Expand for source detail');
 assert.equal(subtitle.getAttribute('textLength'),'640');
 assert.equal(toggle.getAttribute('aria-label'),'Expand 我的 Encoder');
 assert.equal(node.getAttribute('aria-label'),'Node custom:id 我的 Encoder');
 assert.equal(edge.getAttribute('aria-label'),'Edge e from a to b');
 assert.equal(root.ArchCanvasUILocale.node('custom:id','我的 Encoder'),'Node custom:id 我的 Encoder');
 assert.equal(root.ArchCanvasUILocale.edge('e','中文 ID','b'),'Edge e from 中文 ID to b');
 assert.equal(title.textContent,'我的 Encoder');assert.equal(module.textContent,'CustomPair');
 message('zh-CN');
 assert.equal(subtitle.textContent,'源码语义 · 可逆语义图 · 可继续展开至源码细节');
 assert.equal(subtitle.getAttribute('textLength'),null);
 assert.equal(toggle.getAttribute('aria-label'),'展开 我的 Encoder');
 assert.equal(node.getAttribute('aria-label'),'节点 custom:id 我的 Encoder');
 assert.equal(edge.getAttribute('aria-label'),'边 e a 到 b');
});
