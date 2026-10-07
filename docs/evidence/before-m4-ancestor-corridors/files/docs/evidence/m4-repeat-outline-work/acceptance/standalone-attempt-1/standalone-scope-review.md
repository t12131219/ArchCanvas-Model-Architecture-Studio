# 当前正式独立发行检查

未修改的 scripts/check_independence.py --build 实际完成 9 项检查，exit0：正式模块出处、能力声明、5 个样例静态分析、复制源码不变、独立 Studio 构建。使用正式 .venv/bin/python（解析到正式工程所用 /home/fzg/anaconda3/bin/python），运行时隔离为 -I -S 且只添加独立副本 src。Node 为 24.19.0。

/tmp 初始可用 3,804,884,992 字节；完整 RELEASE_ITEMS 估算分配 1,280,204,800 字节，依赖 72,306,688 字节，另留 536,870,912 字节余量，因此无需缩减复制。正式源文件与 654 个已安装依赖文件前后哈希相等。实际 report 原样复制保存，副本为 /tmp/archcanvas-independent-kp5avi3z/release。

首次 reviewer wrapper 在调用正式 check 前根路径计算错误；失败说明及空输出保留，retry1 成功使用原正式脚本。构建用已安装项目本地 npm 依赖的副本，未进行 clean install、模型执行、产品 suite 或像素/人工验收。
