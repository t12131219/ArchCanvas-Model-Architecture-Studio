import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from '/home/fzg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs';
const browser=await chromium.launch({headless:true,executablePath:'/home/fzg/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[],checks=[];
page.on('pageerror',e=>errors.push(e.message));
try {
  await page.goto('http://127.0.0.1:8891');
  await page.waitForFunction(()=>document.querySelector('select[aria-label="示例模型"]')&&!document.querySelector('select[aria-label="示例模型"]').disabled);
  await page.getByRole('combobox',{name:'示例模型',exact:true}).selectOption('mlp');
  await page.waitForFunction(()=>document.querySelector('.project-breadcrumb')?.textContent.includes('MLP'));
  const frame=page.frame({url:/preview\/yworks_edge_router_lab\/index.html/});
  await frame.waitForFunction(()=>document.querySelector('#graph')?.getAttribute('data-source-constraint-valid')==='true');
  await page.waitForTimeout(2200);
  const baseEdges=await frame.locator('[data-edge-id]').count();
  const nodes=frame.locator('[data-node-id] .node-hit');
  const endpoints=await nodes.evaluateAll(es=>es.slice(0,2).map(e=>e.closest('[data-node-id]').getAttribute('data-node-id')));
  await frame.locator('[data-tool="connect"]').click();
  await nodes.nth(0).click({position:{x:8,y:8}});
  await nodes.nth(1).click({position:{x:8,y:8}});
  const draft=frame.locator('[data-edge-id][data-draft="true"]');
  await draft.waitFor();
  const id=await draft.getAttribute('data-edge-id');
  assert.equal(await frame.locator('[data-edge-id]').count(),baseEdges+1);
  assert.equal(await draft.getAttribute('data-source'),endpoints[0]);
  assert.equal(await draft.getAttribute('data-target'),endpoints[1]);
  await page.getByRole('heading',{name:'视觉草稿连接',exact:true}).waitFor();
  await page.getByLabel('视觉连接颜色',{exact:true}).waitFor();
  checks.push('native connect tool creates a draft edge and selects its formal properties');
  await page.getByLabel('视觉连接颜色',{exact:true}).fill('#c32f52');
  try {await frame.waitForFunction(id=>document.querySelector(`[data-edge-id="${id}"] .wire-path`)?.getAttribute('stroke')==='#c32f52',id,{timeout:6000});} catch(error) {console.log('STYLE FAILURE',await page.locator('body').innerText().then(t=>t.slice(-3000)),await draft.evaluate(e=>e.outerHTML));throw error;}
  checks.push('formal edge color property renders on the draft edge');
  await page.getByLabel('视觉连接宽度',{exact:true}).fill('4.2');
  await frame.waitForFunction(id=>document.querySelector(`[data-edge-id="${id}"] .wire-path`)?.getAttribute('stroke-width')==='4.2',id);
  checks.push('formal edge width property renders on the draft edge');
  await page.getByRole('checkbox',{name:'使用虚线',exact:true}).click();
  await frame.waitForFunction(id=>document.querySelector(`[data-edge-id="${id}"] .wire-path`)?.getAttribute('stroke-dasharray')==='7 5',id);
  await page.waitForFunction(()=>Array.from(document.querySelectorAll('label.check-field')).find(e=>e.textContent.includes('使用虚线'))?.querySelector('input')?.checked);
  checks.push('formal dashed property renders on the draft edge');
  for(let i=0;i<4;i++){
    await page.getByRole('button',{name:'撤销 Ctrl+Z',exact:true}).click();
    await page.waitForTimeout(450);
  }
  await draft.waitFor({state:'detached'});
  assert.equal(await frame.locator('[data-edge-id]').count(),baseEdges);
  checks.push('formal toolbar undo restores properties then removes the draft edge');
  await page.getByRole('button',{name:'重做 Ctrl+Shift+Z',exact:true}).click();
  await draft.waitFor();
  checks.push('formal toolbar redo restores the draft edge');
  assert.deepEqual(errors,[]);
  const report={ok:true,checks,baseEdges,id,endpoints,errors};
  await fs.writeFile('/tmp/archcanvas-draft-edge-smoke.json',JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));
} finally {await browser.close();}
