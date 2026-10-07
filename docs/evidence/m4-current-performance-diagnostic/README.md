# 当前构建浏览器性能诊断

正式构建 `index-thbum3BQ.js` / `index-QPVAzYp6.css` 在真实 in-app 浏览器的 `?benchmark=1` 页面完成 20 组展开/收起（40 trials）。原始收据与实际完成截图保存在本目录；validator 退出 0 只证明字段一致。展开 p95 约 990 ms、收起 p95 约 990 ms、rAF cadence 约 1.67 FPS，空闲基线约 1.34 FPS。结果继续不符合性能目标。

这不是原生 input-to-presented-paint 认证；使用普通控件的合成点击及两帧代理，当前没有 compositor trace。没有参与者或模型执行。浏览器/调度与产品耗时的因果仍待固定环境进一步定位。
