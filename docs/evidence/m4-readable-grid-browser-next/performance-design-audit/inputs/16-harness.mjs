import { createInputObserver } from '/__m4/observer.mjs';
const $ = id => document.getElementById(id);
let observer = null, context = null;
try { context = await (await fetch('/__m4/context.json')).json(); $('status').textContent = '正式构建就绪；先在下方选择测试模型'; }
catch (error) { $('status').textContent = String(error); $('start').disabled = true; }
const ids = value => value.split(/[,\n]/).map(id => id.trim()).filter(Boolean);
function report(action) {
  try { action(); } catch (error) { $('status').textContent = `操作失败：${error}`; }
}
$('start').addEventListener('click', () => report(() => {
  const w = $('studio').contentWindow;
  observer = createInputObserver(w, {mode:$('mode').value});
  observer.start({label:$('label').value});
  $('start').disabled = true; $('mode').disabled = true; $('stop').disabled = false;
  $('arm').disabled = $('mode').value !== 'full'; $('receipt').value = '';
  $('status').textContent = `记录中：${$('mode').value}；外页按钮不计入产品输入`;
}));
$('arm').addEventListener('click', () => report(() => {
  const pins = JSON.parse($('studio').contentDocument.querySelector('.publication-scene')?.dataset.pinnedIds ?? '[]');
  const id = observer.arm({operation:$('operation').value,targetIds:ids($('targets').value),anchorIds:ids($('anchors').value),pinnedIds:pins});
  $('arm').disabled = true; $('finish').disabled = false;
  $('status').textContent = `已准备 ${id} / ${$('operation').value}；在下方执行普通操作`;
}));
$('finish').addEventListener('click', () => report(() => {
  const trial = observer.finishTrial();
  $('arm').disabled = false; $('finish').disabled = true;
  $('status').textContent = `${trial.id}：${trial.status}；可准备下一操作`;
}));
$('stop').addEventListener('click', () => report(() => {
  const receipt = observer.stop(); observer = null;
  receipt.context = context;
  receipt.harness = {outerViewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},
    declaredFrame:{width:1280,height:720},controlsHeightPx:144,source:'/__m4/',
    productInputsDispatched:false,productHiddenStateRead:false,humanParticipants:0};
  $('receipt').value = JSON.stringify(receipt,null,2);
  $('start').disabled = false; $('mode').disabled = false; $('stop').disabled = true;
  $('arm').disabled = true; $('finish').disabled = true;
  $('status').textContent = `已结束：${receipt.trials.length} 个操作；原始收据已显示`;
}));
