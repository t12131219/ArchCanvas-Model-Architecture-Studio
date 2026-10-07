import { createFixedWindowObserver, measuredSurfaceCoverage } from '/__m4_controls/observer.mjs';

const byId = id => document.getElementById(id);
const surfaceKind = document.body.dataset.measurementSurface;
let context = null, observer = null, controlClicks = 0;
const controls = ['label', 'mode', 'viewport-profile', 'operation', 'targets', 'start'];
const setRunning = running => {
  document.body.dataset.running = String(running);
  for (const id of controls) byId(id).disabled = running;
  byId('cancel').disabled = !running;
};
const setSize = () => { byId('measured-surface').style.height = `${Number(byId('viewport-profile').value)}px`; };
byId('viewport-profile').addEventListener('change', setSize);
setSize();
if (surfaceKind === 'control') {
  byId('control-target').addEventListener('click', event => {
    // This is the minimal control behavior, not injected product input.
    if (!event.isTrusted) return;
    controlClicks++;
    byId('control-target').textContent = `原生点击目标 · ${controlClicks}`;
    byId('control-target').style.background = controlClicks % 2 ? '#deeee6' : '#dcebf6';
  });
}
try {
  const response = await fetch('/__m4_controls/context.json', { cache: 'no-store' });
  if (!response.ok) throw new Error(`context HTTP ${response.status}`);
  context = await response.json();
  byId('status').textContent = '就绪；先检查完整可见区域与匹配配置';
} catch (error) {
  byId('status').textContent = `上下文未就绪：${String(error)}`;
  byId('start').disabled = true;
}

byId('start').addEventListener('click', () => {
  if (!context || observer) return;
  const surface = byId('measured-surface');
  const coverage = measuredSurfaceCoverage(window, surface);
  if (!coverage.fullyInsideTopViewport) {
    byId('status').textContent = `未开始：测量区域 ${coverage.rect.width}×${coverage.rect.height} 未完整可见；请恢复顶端并选匹配视口`;
    return;
  }
  try {
    const measuredWindow = surfaceKind === 'studio' ? surface.contentWindow : window;
    observer = createFixedWindowObserver(measuredWindow, {
      topWindow: window, surface, surfaceKind, context,
      mode: byId('mode').value, label: byId('label').value,
      operation: byId('operation').value,
      targetIds: byId('targets').value.split(',').map(value => value.trim()).filter(Boolean),
      onPhase(phase) {
        byId('status').textContent = phase === 'warmup' ? '预热 2 秒；将焦点放回测量区域'
          : phase === 'capture' ? '正在采集 20 秒；原生操作须在前 10 秒内完成'
            : '采集已截止；固定等待 2 秒 delivery drain';
      },
      onComplete(receipt) {
        // Large cloning/serialization and controller updates occur after disconnection.
        byId('receipt').value = JSON.stringify(receipt, null, 2);
        byId('status').textContent = `${receipt.status}；${receipt.frames.length} rAF 记录，${receipt.inputs.length} 原生事件；原始收据已保留`;
        observer = null;
        setRunning(false);
      }
    });
    byId('receipt').value = '';
    setRunning(true);
    observer.start();
  } catch (error) {
    byId('status').textContent = `未开始：${String(error)}`;
    observer = null;
    setRunning(false);
  }
});
byId('cancel').addEventListener('click', () => observer?.cancel('native-controller-cancel'));
