# 两项修复的独立预期（实施前）

只读检查当前代码，保留baseline source bytes与SHA。当前只形成独立预期，未宣称新实现通过。

按钮缩放须保持viewport局部中心的world点；这不能保证任意偏离中心的选中目标永不出视区。单链初始化仅适用于新源码核验/精确bindings通过的新managed图；别名后的实际width决定中心，不能覆盖旧图/手动布置或从标签/边数猜单链。

反例、数值oracle、frontier缓存风险与检查清单见 [expectations.json](expectations.json)。等待root实现后再独立审查。
