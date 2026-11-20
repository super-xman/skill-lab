---
name: liquid-glass-ui
description: 用已定稿的海港液态玻璃生成或改造网页 UI。适用于 iOS 风格底栏、工具条、分段选择器和浮层。默认复用 v20 底栏的实时边缘折射、环境高光，以及 v17 滑块的深色选中态和拖动回弹。
---

# 液态玻璃网页 UI

直接复用海港页面确认的组合。v20 底栏中央透出清晰的背景纹理，靠近边缘的纹理自然弯折，高光随背景取色。v17 滑块在选定后呈半透明深色，按下放大，快拖拉长，松手回弹。用户只需描述页面用途，生成时沿用随包资源和固定材质，按页面需要安排内容、布局和尺寸。[已确认的底栏截图](references/approved-dock.png)

## 生成页面

- **新页面**从 `python3 "<skill-dir>/scripts/new_page.py" ./preview.html --title "页面名称"` 起步。`<skill-dir>` 是本文件所在目录。生成的单文件可双击打开，已经接好玻璃、滑块和真实背景采样。把示例的内容、操作和布局替换成用户要的页面。色样台里切换的是背景作品，工具条始终使用同一材质。
- **已有项目**把配套 CSS 和所需 JS 模块接到用户指定的区域，沿用已有组件、路由和图标。客户端挂载后绑定，卸载时调用模块返回的 `destroy()`。[组件样式](assets/liquid-glass.css) · [分段控件](assets/glass-segments.js) · [折射模块](assets/liquid-lens.js)
- 把持续可操作的导航或工具条悬浮在内容上，表单和长文使用稳定的阅读底色。为新页面安排能透过玻璃辨认的真实背景，如摄影作品、图表或渐变画布。让控件对准层次清楚的位置，白字和白色图标可以直接阅读，文字无阴影。

## 接入背景与控件

| 场景 | 实现 |
| --- | --- |
| 玻璃后面有图片、视频或画布 | 给容器加 `lg-surface`，调用 `mountGlassLens(surface, paintBackdrop)` 并传入与屏幕对齐的背景。输入实际显示的背景帧，保留其裁切、位置和叠色。画面变化时同步刷新折射。胶囊再加 `lg-pill`。[接线与定稿参数](references/material.md) |
| 玻璃后面只有普通 DOM | `lg-surface` 自带同配色的 CSS 柔化与内缘高光。此回退能透出滚动内容，真实光学折射需要可读取的背景像素。 |
| 月份、筛选、显示模式等互斥选择 | 使用同名原生 radio 和 `mountGlassSegments(group)`。业务在 `change` 中切换数据。拖动预览、松手选定、快拖拉宽、停手回弹由模块处理。 |
| 页面跳转、工具按钮、弹窗 | 分别保留链接、按钮、对话框的原生语义。可复用相同的 `lg-surface` 外观，交互和焦点仍由原组件管理。 |

```html
<div class="lg-surface lg-segments" role="radiogroup" aria-label="时间范围">
  <label class="lg-choice"><input type="radio" name="range" value="week" checked><span>本周</span></label>
  <label class="lg-choice"><input type="radio" name="range" value="month"><span>本月</span></label>
</div>
```

同页的不同 radio 组使用不同的 `name`。标签里的 `span` 可容纳用 `currentColor` 绘制的图标和文字，组上加 `lg-stack` 可改为上下排列。若已有线框与实心图标，可用实心表示选中，叠加于滑块上方。动态增删选项、通过代码修改 `checked` 后调用 `refresh()`。模块版入口可通过本地 HTTP 预览。[完整接线示例](assets/starter.html)

## 看成品时

- 换到暖色和冷色背景，玻璃应透出相应环境色。找一条穿过底栏的直线，确认它在中央清晰并维持位置，接近边缘才明显弯折。再把底栏贴近屏幕底边检查高光。上、下沿的细高光柔和过渡，侧沿略暗，选中项比周围深一层。
- 用亮处、暗处和细纹理检查字色、图标和选中态。若样子与参考图有出入，先核对使用的资源、实际背景、采样坐标和有无页面 CSS 覆盖。优先调整控件的落位来改善白字对比。
- 用窄屏实际点选、慢拖、快拖和取消操作，并用键盘切换。确认业务内容和选中态一起变化，页面仍能纵向滚动。启用减少动态效果后选择应立即到位。对增强材质，再检查关闭 GPU 后的可读性。
