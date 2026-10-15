/* Persisted interaction-mode contract shared by the editor and its tests. */
(function(root) {
  'use strict';
  const key = 'summary-merge:interaction-mode';
  const normalize = value => value === 'realtime' ? 'realtime' : 'compat';
  const label = value => normalize(value) === 'realtime' ? '实时模式' : '兼容模式';
  const description = value => normalize(value) === 'realtime'
    ? '拖动中同步更新箭头、端点和连线路径。'
    : '拖动时轻量预览，松开后后台完成完整约束校验。';
  const api = {key, normalize, label, description};
  root.SummaryInteractionMode = api;
  if(typeof module !== 'undefined' && module.exports)module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
