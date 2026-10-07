# Repeat outline 前归档独立复核

归档2916个文件逐一哈希相符：旧ChSseal的2915个绑定完整映射到归档路径，另含原始seal本身。归档manifest与原seal的给定SHA256均相符，归档files目录没有额外未列文件。

当前matrix raw 454个文件、collected 352个文件全部与旧seal绑定字节相等，且两个目录没有额外未绑定文件。归档、manifest、原seal与当前matrix输入在复核结束时均重哈希不变。

产品源码、dist与历史文档允许继续修改，其原版本仅在归档中核验；未要求当前版本不变。未重看图像、未运行产品suite、未修改任何旧文档/status/matrixseal/raw/collected。结论限于本地字节与路径映射一致性。
