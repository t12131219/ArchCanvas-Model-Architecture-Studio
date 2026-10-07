const $ = id => document.getElementById(id);
let session = null, frame = 0, timer = 0, observer = null, clicks = 0;
let context = null;
try { context = await (await fetch('/__m4/context.json')).json(); }
catch (error) { $('status').textContent = `上下文读取失败：${error}`; $('start').disabled = true; }
const append = (key, value) => {
  if (!session) return;
  if (session[key].length < 10000) session[key].push(value);
  else session.truncated[key] = true;
};
const flags = () => ({at:performance.now(), visibility:document.visibilityState, focused:document.hasFocus()});
const tick = timestamp => {
  if (!session) return;
  const begin = performance.now();
  append('frames', timestamp);
  append('rafCallbackCosts', performance.now() - begin);
  frame = requestAnimationFrame(tick);
};
const inputs = event => {
  if (!session) return;
  const begin = performance.now();
  append('inputs', {type:event.type, at:event.timeStamp, capturedAt:begin, trusted:event.isTrusted,
    targetId:event.target?.id ?? null});
  append('inputCallbackCosts', performance.now() - begin);
};
const environmentChange = () => append('environmentChanges', flags());
for (const name of ['pointerdown','pointerup','click']) document.addEventListener(name, inputs, true);
document.addEventListener('visibilitychange', environmentChange);
window.addEventListener('focus', environmentChange);
window.addEventListener('blur', environmentChange);
$('target').addEventListener('click', () => {
  clicks++;
  $('target').textContent = `可信点击目标 · ${clicks}`;
  $('target').style.background = clicks % 2 ? '#deeee6' : '#dcebf6';
});
function finish(reason) {
  if (!session) return;
  clearTimeout(timer); cancelAnimationFrame(frame);
  if (observer) { consume(observer.takeRecords()); observer.disconnect(); observer = null; }
  session.stoppedAt = performance.now(); session.stopReason = reason;
  session.endEnvironment = flags();
  $('receipt').value = JSON.stringify(session, null, 2);
  const count = session.frames.length;
  session = null;
  $('status').textContent = `已结束：${count} 个 rAF 时间戳；原始收据已显示`;
  $('stop').disabled = true; $('start').disabled = false;
}
function consume(entries) {
  const begin = performance.now();
  for (const entry of entries) append('eventTiming', {name:entry.name,startTime:entry.startTime,
    duration:entry.duration,processingStart:entry.processingStart,processingEnd:entry.processingEnd,
    interactionId:entry.interactionId ?? 0, targetId:entry.target?.id ?? null});
  append('performanceCallbackCosts', performance.now() - begin);
}
$('start').addEventListener('click', () => {
  if (session) return;
  session = {schema:'archcanvas-scheduling-control/1',context,startedAt:performance.now(),timeOrigin:performance.timeOrigin,
    capturedAt:new Date().toISOString(),userAgent:navigator.userAgent,viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},
    hardwareConcurrency:navigator.hardwareConcurrency,beginEnvironment:flags(),environmentChanges:[],
    frames:[],eventTiming:[],inputs:[],rafCallbackCosts:[],inputCallbackCosts:[],performanceCallbackCosts:[],truncated:{},
    eventTimingSupported:PerformanceObserver.supportedEntryTypes.includes('event'),durationThresholdMs:16,
    limitations:['Agent-operated simple page control, not a human task','rAF cadence is not presented frame rate',
      'Missing EventTiming entries remain unknown','Callback cost excludes browser observer delivery overhead']};
  if (session.eventTimingSupported) { observer = new PerformanceObserver(list => consume(list.getEntries())); observer.observe({type:'event',durationThreshold:16}); }
  frame = requestAnimationFrame(tick); timer = setTimeout(() => finish('timer-20-seconds'),20000);
  $('receipt').value = ''; $('start').disabled = true; $('stop').disabled = false;
  $('status').textContent = '记录中；点击目标后等待自动结束';
});
$('stop').addEventListener('click', () => finish('manual'));
