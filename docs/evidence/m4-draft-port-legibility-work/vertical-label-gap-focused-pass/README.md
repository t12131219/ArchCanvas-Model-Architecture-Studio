# 纵向邻卡文字间隙修复的独立 focused 检查

Bf83实际从零Concat纵向模型将输入B与Concat隔开28world。在18的56%缩放公开geometry里，上游output右边缘x366，下游Concat.a label起点x360.666667，名义文字的水平范围交叠5.333333；配合两张相邻卡片的外置基线，在名义一em高度下有交叠。本次只将纵向output offset从x−12改为x−22，使右边缘x356，与a起点保留4.666667world水平间隙；纵向input仍x+12，横向全部offset/anchors、dot与peer hit、catalog/backend/schema/参数/保存position不变。

新独立测试在当前17种真实catalog的每个outlet与每个inlet组合、四种zoom .15/.53/1/3下检查28world邻卡文字框不相交。对output/input/left/right/a/b的固定字母advance手写，不以产品textWidth作为oracle；所有dot仍有完整hit、inletpeerhit不变，输出label水平范围由hit覆盖，外置text也在同一可点击port group上。测试明确保留旧x−12/max16.2字号的output→Concat.a交叠反例，不抹去产生修复的失败条件。

实际7文件focused64/64，exit0，原工具chunk为4b9ebd；完整stdout在会话工具输出，本目录不声称另有完整stdout副本。12份实际源码/测试/catalog输入及SHA保存在manifest，结束读回12/12不变。修复前2份src/test与17/18public5份文件保存在 `../before-vertical-label-gap-fix/manifest.json`。主Agent另做完整Studio/strict/build与修复后browser。

名义字体bbox不等同浏览器真实字体塑形或审美；即使某些低zoom框分离，也不宣称低zoom字号可读、动态新端口数、任意相邻布局、出版尺寸、人类易用性或性能通过。此前Bf83四向移动/相机/保存和首portgeometry63/63证据保持原版本历史，不能作为新labelrenderer的currentpixel认证。M4partial，M5not_started，真人0。
