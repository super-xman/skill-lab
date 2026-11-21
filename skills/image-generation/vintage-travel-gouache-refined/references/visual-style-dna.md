# 纯文字视觉风格 DNA（不依赖参考图片）

## 不是“厚涂越多越像”

用户偏好的视觉来源可以用下列组合描述：

- **Mid-century painted travel poster / 复古旅行宣传画**：20 世纪中期欧美观光商业海报的优雅构图、浪漫怀旧气息，明快但克制。
- **Refined editorial illustration / 精致商业编辑插画**：主体形状可读、建筑结构准确、有控制的细节层次，不是稚拙卡通。
- **Opaque matte gouache / 不透明哑光水粉**：有覆盖感的颜色层、平整的大色面、轻柔的画笔边缘。
- **Selective local brushwork / 局部笔触**沿着浪脊、枝叶或岩石转折变化，表现材质和形体。
- **Fine print-like pigment grain / 细微印刷式颜料颗粒**：只有放大时才容易看到，不应像旧纸破损、涂鸦噪点。
- **Warm-cool color balance / 柔和冷暖对比**：暖金光与灰蓝阴影，色彩有年代感，不荧光不过饱和。

## 造型语法

1. **轮廓明确**：人物、船体、建筑、山体、植物有简洁但准确的外形。
2. **块面分层**：光影靠少量精确的色块表达，不靠摄影级渐变、复杂材料反射或过量轮廓线。
3. **细节集中**：视觉焦点清晰，近景或主角精致；远景则简化，用空气透视增强层次。
4. **装饰性节奏**：云形、波浪、山脊、棕榈树、街道光影可以有优雅韵律，但不机械重复。
5. **复古广告插画感**：有轻度理想化的光线和色彩，但与目标照片地理、天气、季节相容。
6. **干净表面**：图像整体应整洁，不脏、不粗、不满是划痕；“画得出来”不等于“每笔都很粗”。

## 禁止全局主标签

以下说法容易让生成器把整幅画变成粗重油画，**不要作为主风格正面指令**：

- `heavy oil painting`, `thick impasto everywhere`, `heavy palette knife texture`, `Van Gogh brush strokes`, `expressionist paint`, `rough canvas scratch marks`, `intense canvas grain`。

与其写“强烈油画厚涂”，不如写：

> **Refined mid-century travel poster painted in opaque matte gouache, with crisp illustrative forms, subtle print-like grain and brushwork shaped by each material.**

## 风格与内容的边界

邮轮、灯塔、海滨房屋、棕榈树和巨型太阳只是某张作品中的景物，**均非本风格的必要元素**。在荒漠、雪山、城市、人物、雨夜等任何题材里依然应能复现相同的“造型、光色、哑光水粉和局部笔触”语言。
