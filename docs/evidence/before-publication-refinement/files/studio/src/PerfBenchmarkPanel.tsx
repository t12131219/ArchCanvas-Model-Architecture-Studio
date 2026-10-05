import { useEffect, useRef, useState } from 'react';
import { runStudioBenchmark } from './perfBenchmark';
import { NativePerformanceSession } from './nativePerformance';

export function PerfBenchmarkPanel() {
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState('');
  const [result, setResult] = useState('');
  const [error, setError] = useState('');
  const [nativeRunning, setNativeRunning] = useState(false);
  const [nativeCount, setNativeCount] = useState(0);
  const [nativeResult, setNativeResult] = useState('');
  const nativeSession = useRef<NativePerformanceSession | null>(null);
  useEffect(() => () => nativeSession.current?.dispose(), []);
  if (new URLSearchParams(location.search).get('benchmark') !== '1') return null;
  async function run() {
    setRunning(true); setResult(''); setError(''); setProgress('正在采样 2 秒空闲帧基线…');
    try {
      const report = await runStudioBenchmark({ frameMs: 2000, sampleCount: 20, onProgress: (completed, total) => setProgress(`${completed} / ${total} 组展开与收起`) });
      setResult(JSON.stringify(report, null, 2)); setProgress('已完成 20 组真实浏览器场景采样');
    } catch (failure) { setError(String(failure)); setProgress('采样未完成'); }
    finally { setRunning(false); }
  }
  function startNative() {
    setError(''); setNativeResult(''); setNativeCount(0);
    try { nativeSession.current = new NativePerformanceSession(setNativeCount); setNativeRunning(true); }
    catch (failure) { setError(String(failure)); }
  }
  function stopNative() {
    if (!nativeSession.current) return;
    setNativeResult(JSON.stringify(nativeSession.current.stop(), null, 2));
    nativeSession.current = null; setNativeRunning(false);
  }
  return <aside style={{ position: 'fixed', left: 244, bottom: 32, width: 340, maxHeight: '45vh', zIndex: 30, background: '#fff', border: '1px solid #b8ccc6', borderRadius: 8, padding: 12, boxShadow: '0 4px 20px #0002', overflow: 'auto' }} aria-label="Studio 性能验收">
    <strong>Studio 性能验收</strong>
    <p style={{ fontSize: 10, lineHeight: 1.6 }}>先测 2 秒空闲帧，再采样 20 次非根容器展开与收起。同步 handler、两帧绘制代理与 Event Timing 分别记录。</p>
    <button disabled={running || nativeRunning} onClick={() => void run()}>{running ? '正在采样…' : '运行 20 组性能采样'}</button>
    <output style={{ display: 'block', marginTop: 8 }}>{progress}</output>
    {error && <p role="alert">{error}</p>}
    {result && <><textarea aria-label="性能采样 JSON" value={result} readOnly style={{ width: '100%', height: 150, marginTop: 8, font: '9px monospace' }} /><a href={`data:application/json;charset=utf-8,${encodeURIComponent(result)}`} download="m4-studio-performance.json">下载性能收据</a></>}
    <hr /><strong>原生输入与空间采样</strong>
    <p style={{ fontSize: 10, lineHeight: 1.6 }}>开始后，直接点击层级或画布的展开/收起控件，每次等待画面稳定；结束前再等待两帧。可先固定一个无关可见对象。浏览器 Event Timing 提供事件到下一次绘制的耗时；缺失条目保留为空。屏幕锚点与画布固定位置分别记录。</p>
    <button disabled={running} onClick={nativeRunning ? stopNative : startNative}>{nativeRunning ? '结束原生输入采样' : '开始原生输入采样'}</button>
    <output style={{ display: 'block', marginTop: 8 }}>{nativeRunning ? `正在记录：${nativeCount} 次展开/收起` : nativeResult ? '记录已生成；仍需固定环境与独立复核' : ''}</output>
    {nativeResult && <><textarea aria-label="原生性能 JSON" value={nativeResult} readOnly style={{ width: '100%', height: 150, marginTop: 8, font: '9px monospace' }} /><a href={`data:application/json;charset=utf-8,${encodeURIComponent(nativeResult)}`} download="m4-native-performance.json">下载原生采样收据</a></>}
  </aside>;
}
