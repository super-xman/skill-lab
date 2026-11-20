# 材质与采样

## 海港 v20 底栏与 v17 滑块

随包组件已固定这套配方。接入时只需要提供当前背景，常见的底栏高度为 54–64 CSS px。[已确认的海港底栏](approved-dock.png)

| 项目 | 定稿参数和视觉表现 |
| --- | --- |
| 折射 | 折射率 **1.46**。弧面覆盖圆角半径的 **51%**，最大法线倾角 **1.30 弧度**。位移随曲率渐增，中央位移为零。边缘按位移的 **6%** 分开采样红、蓝通道。 |
| 清晰度与底色 | 中央保留 **85%** 的全分辨率细节，最外沿保留 **91.5%**。饱和度 **1.08**，淡蓝白底色为 `rgb(226 235 241)`。WebGL 的实际混色比例为 **4.5%**，明亮背景再随亮度压暗，白字清楚可读。 |
| 高光 | 从玻璃外侧的真实景物取色。窄高光峰距轮廓 **0.95 CSS px**，较宽的柔光峰位于弧面宽度的 **32%** 处。上下沿受光各异，侧沿稍暗。底栏贴屏时，环境取样止于视口最边缘的可见像素中心。 |
| 滑块与前景 | 静止选中层为 `rgb(24 15 11 / .23)`。文字、图标用纯白，无文字阴影。按住时横向放大约 **1.50 倍**、纵向约 **1.34 倍**，快拖时尾部滞后，释放后回弹。 |
| CSS 回退 | 混入 **10%** 的同一淡蓝白，滤镜为 `saturate(108%) brightness(.89) blur(1.25px)`。保留柔和的边缘高光。 |

复核时，把一条斜纹放在 300 × 64 CSS px 的底栏后面。中央的条纹应清晰并对齐原景，在距上下边缘约 4 CSS px 的位置，折射采样点向内偏移约 6 CSS px。再用海浪和石岸做冷暖对照，高光会跟随换景。

普通 DOM 使用浏览器的 backdrop filter。将滤镜放在有真实边界的容器本身，两种属性 `-webkit-backdrop-filter` 和 `backdrop-filter` 均保留。高光和柔影可以放在伪元素上。祖先的 `filter`、半透明、遮罩或裁剪可能改变背景取样范围。滚动一条明显纹理穿过控件，检查实际合成。

## 给镜片一张对齐的背景

`mountGlassLens` 挂载在已套用 `lg-surface` 的容器上，适用于无边框、轴对齐、四角使用相同像素半径的表面。胶囊用 `999px`。每个表面会建立一个 WebGL 上下文，优先用于最需要折射的控件。其余表面可复用 CSS 回退样式。

```js
import {drawCover, mountGlassLens} from './liquid-lens.js';

const surface = document.querySelector('.photo-tools');
const photo = document.querySelector('.hero-photo');
const lens = mountGlassLens(surface, (ctx, area) => {
  // ctx 已转换到视口 CSS 像素坐标，area 含边缘所需的额外背景。
  ctx.fillStyle = '#223438'; // 这里应与照片外围的实际背景相同。
  ctx.fillRect(area.left, area.top, area.width, area.height);
  return drawCover(ctx, photo, photo.getBoundingClientRect());
});
photo.addEventListener('load', lens.invalidate);
// 在组件卸载处移除 load 监听并调用 lens.destroy()。
```

- `drawCover` 匹配居中的 `object-fit: cover`。图片尚未解码、视频尚未就绪时返回 `false`，CSS 会继续显示。自定义 `object-position`、裁剪、背景渐变或叠色时，在回调中按屏幕上的顺序和坐标绘制实际可见层。回调应只绘制控件背后的内容。
- 对于视频，在 `requestVideoFrameCallback` 中使镜片失效，暂停后停更。对于图表、全景或游戏画布，在场景完成绘制的同一帧调用 `lens.render()`，尤其是 WebGL 默认不保留绘图缓冲区时。普通照片换图可用 `lens.invalidate()` 合并多次刷新。模块自动处理滚动、尺寸和可见性变化。
- 跨域媒体的响应要允许取像素，图片和视频在设置 `src` 前设好合适的 `crossOrigin`。采样被浏览器拒绝或图形上下文丢失时，组件自动使用同配色的 CSS 回退。只有普通 DOM 时，CSS 能直接柔化滚动中的背景。系统启用减少透明度时，控件使用实色。
- 交付可双击的单文件时，把需要采样的本地图片嵌入 HTML 的 `data:image/…` 地址。`file://` 下即使同目录图片已经显示，浏览器仍可能阻止读取像素。分文件项目可通过同源 HTTP 查看。加载后检查控件是否带 `data-lg-rendered`，再用一条跨边缘的纹理确认实际折射。

## 复核滑块手感

分段控件的滑块和前景文字分层。领先位置追随指针，尾部由较慢的弹簧追赶，两者的距离决定拉伸量。基准在静止按住时横向约放大到 1.5 倍，快速移动还能继续拉长。动效按经过的时间计算。普通导航链接和正文按钮只在交互确实需要时采用这种动态。
