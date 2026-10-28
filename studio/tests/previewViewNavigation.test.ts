import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
const context = vm.createContext({});
vm.runInContext(readFileSync(new URL('../public/preview/yworks_edge_router_lab/view-navigation.js', import.meta.url), 'utf8'), context);
const N = context.ArchCanvasViewNavigation;
test('deep, wide and sparse overviews retain all bounds while module focus restores a readable scale', () => {
  for (const viewport of [{ width: 790, height: 460 }, { width: 440, height: 320 }]) {
    for (const canvas of [[1200, 7000], [7000, 1200], [1400, 1400]]) {
      const view = N.overview(canvas, viewport);
      assert.ok(view.x <= 0 && view.y <= 0);
      assert.ok(view.x + view.w >= canvas[0] && view.y + view.h >= canvas[1]);
      assert.ok(Math.abs(view.w / view.h - viewport.width / viewport.height) < 1e-9);
      const leaf = { x: 700, y: 6000, w: 230, h: 70 }, before = JSON.stringify(leaf), camera = N.readable(leaf, viewport);
      assert.equal(viewport.width / camera.w, 1);
      assert.ok(camera.x < leaf.x && camera.y < leaf.y && camera.x + camera.w > leaf.x + leaf.w && camera.y + camera.h > leaf.y + leaf.h);
      assert.equal(JSON.stringify(leaf), before);
      const frame = N.readable({ x: 40, y: 100, w: 1800, h: 6842 }, viewport);
      assert.ok(viewport.width / frame.w >= .4, 'deep container opens a readable heading/content band rather than fitting all 6842 units');
      assert.ok(frame.y <= 100 && frame.y + frame.h > 300);
    }
  }
});
test('reading a wide source frame lands on real contents rather than its empty left corner', () => {
  const frame={id:'attention',x:40,y:100,w:4200,h:8000,expanded:true};
  const leaf={id:'return',parent:'attention',x:3500,y:240,w:160,h:60,expanded:false};
  const other={id:'unrelated',parent:null,x:45,y:110,w:160,h:60,expanded:false};
  const nodes=[frame,leaf,other],before=JSON.stringify(nodes),viewport={width:526,height:575};
  const camera=N.readable(frame,viewport,nodes);
  assert.ok(camera.x<=leaf.x&&camera.x+camera.w>=leaf.x+leaf.w);
  assert.ok(camera.y<=leaf.y&&camera.y+camera.h>=leaf.y+leaf.h);
  assert.equal(JSON.stringify(nodes),before);
});
test('Studio module focus uses descendant geometry through the actual focus handler', async () => {
  const nodes=[{id:'attention',x:40,y:100,w:4200,h:8000,expanded:true},
    {id:'projection',parent:'attention',x:3500,y:240,w:160,h:60,expanded:false}];
  const before=JSON.stringify(nodes),focusContext=vm.createContext({
    graph:{nodes},busy:false,drag:null,selectedNodes:new Set(),selectedEdges:new Set(),
    selectedAnnotation:null,sourceNodes:()=>[nodes[0]],node:(id:string)=>nodes.find(n=>n.id===id),
    $:()=>({clientWidth:526,clientHeight:575}),camera:{},cameraUpdate:()=>{},render:()=>{},studioBridge:null,
    window:{ArchCanvasViewNavigation:N,ArchCanvasStudioSelection:{update:()=>new Set(['attention'])}},
  });
  const app=readFileSync(new URL('../public/preview/yworks_edge_router_lab/app.js',import.meta.url),'utf8');
  vm.runInContext(app.slice(app.indexOf('  async function studioFocus('),app.indexOf('  function selectedLayoutNodes(')),focusContext);
  await focusContext.studioFocus({nodeId:'attention'});
  const camera=focusContext.camera,leaf=nodes[1];
  assert.ok(camera.x<=leaf.x&&camera.x+camera.w>=leaf.x+leaf.w);
  assert.ok(camera.y<=leaf.y&&camera.y+camera.h>=leaf.y+leaf.h);
  assert.equal(JSON.stringify(nodes),before);
  assert.deepEqual([...focusContext.selectedNodes],['attention']);
});
