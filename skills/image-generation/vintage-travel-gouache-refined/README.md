# Vintage Travel Gouache · Refined（精致轻纹理）

以**精致的20世纪中期商业旅行海报与哑光不透明水粉**为核心。用清晰的轮廓和冷暖色块组织画面。海浪、山石和树冠使用贴合结构的短笔触，建筑通过准确的透视和光影塑形。

**不需要风格参考图。** 仅上传要改绘的**目标照片**；纯文字原创时不需要任何图片。下面展示的是已生成的创作案例，**仅用于 README 展示，Skill 不会自动加载它们作为风格参考**。

## 实际创作示例

| 海滨酒店 | 荒漠落日 |
| :---: | :---: |
| ![Refined 海滨酒店](examples/seaside.webp) | ![Refined 荒漠落日](examples/desert.webp) |

## 安装与调用

将本文件夹完整复制到 `~/.agents/skills/vintage-travel-gouache-refined/` 或项目 `.agents/skills/vintage-travel-gouache-refined/`，并在支持图像生成/编辑的 Agent 中明确调用：

> 使用 `vintage-travel-gouache-refined` 把这张照片改绘成精致复古旅行海报水粉插画。保留主体，允许适度扩景，用哑光色块表现光影，让笔触贴合水纹、石块和枝叶。

## 主要文件

- [SKILL.md](SKILL.md) 说明工作流程与风格定位
- [分区域笔触](references/region-texture-map.md) 说明云、水面、岩石和建筑的画法
- [视觉风格 DNA](references/visual-style-dna.md)：形体和插画气质
- [配色与光照](references/palette-and-lighting.md)：适应地点和时段
- [提示词](references/prompt-templates.md) 提供中英模板及分题材示例
- [质量检查](references/comparison-and-qa.md)：验收与修复
- [调用示例](examples/example-requests.md)：常见场景

> Skill 提供工作流程与提示词，不内置绘图模型；生成效果受具体模型与随机性影响。
