import { createInputObserver } from '/__continuous/observer.mjs';
const $ = id => document.getElementById(id);
const ids = value => value.split(/[,\n]/).map(v => v.trim()).filter(Boolean);
let observer = null, context = null;
const journal = [];
function panel(shown) {
  $('controls').hidden = !shown; $('show').setAttribute('aria-expanded', String(shown));
  journal.push({ atOuter: performance.now(), shown, outerViewport: { width:innerWidth,height:innerHeight,dpr:devicePixelRatio } });
}
$('show').addEventListener('click', () => panel($('controls').hidden));
$('hide').addEventListener('click', () => panel(false));
function guard(action) { try { action(); } catch(e) { $('status').textContent = String(e); } }
try { context = await (await fetch('/__continuous/context.json')).json(); $('status').textContent = '冻结构建已绑定；请先在产品中载入 Dense 300'; }
catch(e) { $('status').textContent = String(e); $('start').disabled = true; }
$('start').addEventListener('click', () => guard(() => {
  observer = createInputObserver($('studio').contentWindow, { mode:$('mode').value, drainMs:2000, onProgress: p => { $('denominator').textContent = `原生 retained ${p.inputs} · rAF ${p.frames} · trials ${p.trials}`; } });
  observer.start({label:$('label').value}); $('receipt').value=''; $('download').hidden=true;
  $('start').disabled=true; $('mode').disabled=true; $('stop').disabled=false; $('arm').disabled=$('mode').value!=='full';
  $('status').textContent='会话中：外页控件不计为产品原生输入'; panel(false);
}));
$('arm').addEventListener('click', () => guard(() => {
  const pins=JSON.parse($('studio').contentDocument.querySelector('.publication-scene')?.dataset.pinnedIds ?? '[]');
  const trial=observer.arm({operation:$('operation').value,targetIds:ids($('targets').value),anchorIds:ids($('anchors').value),pinnedIds:pins});
  $('arm').disabled=true; $('finish').disabled=false; $('status').textContent=`准备 ${trial}，执行普通原生操作`;panel(false);
}));
$('finish').addEventListener('click', () => guard(() => {
  const trial=observer.finishTrial(); $('arm').disabled=false; $('finish').disabled=true;
  $('status').textContent=`${trial.id} ${trial.status}；可准备下一操作`;
}));
$('stop').addEventListener('click', async () => {
  if (!observer) return;
  $('stop').disabled=true; $('arm').disabled=true; $('finish').disabled=true;
  $('status').textContent='产品输入 capture 已结束；固定 2000 ms 交付等待中';
  try {
    const receipt=await observer.stop(); observer=null;receipt.context=context;
    receipt.responsiveHarness={outerViewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},frameViewport:{width:$('studio').clientWidth,height:$('studio').clientHeight},panelJournal:journal.slice(),controlsOverlay:true,smallToggleRect:JSON.parse(JSON.stringify($('show').getBoundingClientRect().toJSON())),productInputsDispatched:false,productHiddenStateRead:false,humanParticipants:0};
    const value=JSON.stringify(receipt,null,2);$('receipt').value=value;
    $('download').href='data:application/json;charset=utf-8,'+encodeURIComponent(value);$('download').download='m4-readable300-continuous.json';$('download').hidden=false;
    $('start').disabled=false; $('mode').disabled=false;$('status').textContent=`已结束：observed ${receipt.inputDenominator.observed}, retained ${receipt.inputDenominator.retained}, dropped ${receipt.inputDenominator.dropped}, failed ${receipt.inputDenominator.failed}；仅工程代理证据`;
  } catch(e) { $('status').textContent=String(e); }
});
