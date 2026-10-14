import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from '/home/fzg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs';
const browser=await chromium.launch({headless:true,executablePath:'/home/fzg/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1600,height:1100}});const errors=[],cases=[];page.on('pageerror',e=>errors.push(e.message));
try{
await page.goto('http://127.0.0.1:8891');await page.waitForFunction(()=>document.querySelector('select[aria-label="示例模型"]')&&!document.querySelector('select[aria-label="示例模型"]').disabled);const frame=page.frame({url:/preview\/yworks_edge_router_lab\/index.html/});
const catalog=await page.evaluate(()=>fetch('/preview/data/catalog.json').then(r=>r.json()));
for(const target of [{title:'resnet',collection:'model_zoo_programmatic_guide'},{title:'Transformer',collection:'transformer_programmatic_guide'},{title:'autoformer',collection:'timeseries_programmatic_guide'},{id:'routing-lab'}]){
 const item=catalog.cases.find(c=>target.id?c.id===target.id:c.title===target.title&&c.collection===target.collection&&!c.historical);
 console.log('open',item.title,await page.locator('summary').allTextContents());if(!await page.locator('.workspace-menu').getAttribute('open'))await page.locator('.workspace-menu summary').click();console.log('menu',await page.locator('.workspace-menu').innerText());await page.locator('.workspace-menu button').filter({hasText:/示例|模块库/}).click();await frame.locator(`button[data-case-id="${item.id}"]`).click();try{await frame.waitForFunction(title=>document.querySelector('#modelTitle')?.textContent===title,item.title,{timeout:15000});}catch(error){console.log('LOAD FAILURE',item.title,await frame.locator('#modelTitle').innerText(),await frame.locator('#toast').innerText(),await page.locator('.project-breadcrumb').innerText());throw error;}await frame.locator('.library .studio-drawer-close').click();await page.locator('.workspace-menu').evaluate(e=>e.open=false);
 await page.waitForTimeout(3500);
 const breadcrumb=await page.locator('.project-breadcrumb').innerText(),heading=await frame.locator('#modelTitle').innerText(),failure=await page.locator('.notice.error,.error-notice,.failure').allTextContents();
 assert.ok(breadcrumb.toLowerCase().includes(item.title.toLowerCase()),`breadcrumb mismatch ${item.title}: ${breadcrumb}`);assert.equal(heading,item.title);
 const candidates=frame.locator('[data-node-id] .node-hit');if(await candidates.count())await candidates.nth(Math.min(1,(await candidates.count())-1)).click({position:{x:8,y:8}});else await frame.locator('[data-node-id] .frame-hit').first().click({force:true});await page.waitForTimeout(300);
 const objectText=await page.locator('.inspector').innerText();
 cases.push({title:item.title,breadcrumb,objectPanel:objectText.slice(0,220),failure});
 if(item.id==='routing-lab'){
  const editor=page.getByRole('button',{name:'编辑',exact:true});await editor.click();await page.waitForTimeout(500);const body=await page.locator('body').innerText();assert.ok(body.includes('没有模型源码')||body.includes('没有可编辑')||body.includes('教学')||body.includes('路由实验'));assert.equal(await page.locator('.prototype-preview').isVisible(),true);
 }
}
await page.getByRole('combobox',{name:'示例模型',exact:true}).selectOption('mlp');await page.waitForFunction(()=>document.querySelector('.project-breadcrumb')?.textContent.includes('MLP'));await page.waitForTimeout(2200);assert.match(await frame.locator('#modelTitle').innerText(),/MLP/);assert.deepEqual(errors,[]);await fs.writeFile('/tmp/archcanvas-catalog-smoke.json',JSON.stringify({ok:true,cases,errors},null,2)+'\n');console.log(JSON.stringify({ok:true,cases,errors}));
}finally{await browser.close();}
