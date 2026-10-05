# 本轮隔离服务目录的实际语义

`archcanvas_service.server` 的 `serve --data-dir` 参数直接给 DocumentStore 根，exports 在该根的父目录下。因此正式矩阵服务必须使用 `--data-dir /tmp/archcanvas-m4-boundary-matrix/documents`，对应保存文件 `/tmp/archcanvas-m4-boundary-matrix/documents/<documentId>.json` 与导出目录 `/tmp/archcanvas-m4-boundary-matrix/exports/<artifactId>/`。

最初 root 按预期工作区根 `/tmp/archcanvas-m4-boundary-matrix` 启动服务；该次实际 store 直接位于它而非 `documents/`，导致 exports 根是共享 `/tmp/exports`。第一例真实 raw 与封装失败记录保留在独立 excluded 路径，不计正式矩阵。封装工具坚持声明路径并拒绝缺失输入，没有寻找其他保存文件/导出文件；现有 frozen workflow 和 preparation guard 不修改。

root 停止初始服务并在同一 8906 端口按正确隔离布局重新启动。新的服务启动日志、实际生命周期和后续 browser 原始记录才证明该服务实际可用；本文不单独声称服务已经启动或仍在线。
