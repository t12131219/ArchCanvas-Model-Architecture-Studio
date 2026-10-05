# 隔离服务目录：已核对正式源码

此文件更正 `service-layout-note.md` 中误写的模块名称 `archcanvas_service.server`；原说明与原 receipt 保留。实际正式源码是 `src/archcanvas_cli/server.py`。

该源码第 183 行将 `data_dir` 直接传给 `DocumentStore`，第 184 行以 store 根的父目录构建 Workspace。因此矩阵服务使用 `--data-dir /tmp/archcanvas-m4-boundary-matrix/documents`，保存文件为 `/tmp/archcanvas-m4-boundary-matrix/documents/<documentId>.json`，导出为 `/tmp/archcanvas-m4-boundary-matrix/exports/<artifactId>/`。

最初按工作区根 `/tmp/archcanvas-m4-boundary-matrix` 启动会使 store 直接位于该根，exports 位于共享 `/tmp/exports`。root 已明确将初次真实原始材料保留到 excluded 路径，并停止初始服务、采用正确隔离路径重新启动。辅助工具没有修改 guard，没有搜索替代 store 或 export；第一例失败不会获得矩阵覆盖。

本文确认参数与目录合同；新服务实际启动、当前在线状态和后续浏览器行为应以 root 保存的服务日志与真实 CUA 原始记录为证据。
