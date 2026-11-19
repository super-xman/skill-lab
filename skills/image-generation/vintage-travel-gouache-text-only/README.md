# 复古旅行海报水粉插画 Skill · v2.0

`vintage-travel-gouache-text-only` 是为将照片、人物和文字场景转换成**精致、哑光、不透明水粉质感的复古旅行海报插画**而写的可复用 Agent Skill。

## 这次更新了什么

- **真正不依赖风格参考图片**：v2.0 包内不含风格图，调用时只需你的目标照片与 Skill 中的文字规范。
- **天空纹理修正**：大面积天空必须轻薄、近乎平滑，只有极弱颜料微颗粒，**不得出现厚重斜向笔痕、油画刀纹或粗糙刮擦**。
- **分区笔触**：海水、山石、树冠可以比天空更具有手绘感；建筑和人物保持精致轮廓。
- **更像复古商业插画**：弱化泛印象派油画倾向，强化准确形体、清晰结构、哑光色块与柔和光色。
- **保持适度内容扩展**：仍然允许合理补景，但不能用云朵填满原本清朗的天空，也不能添加无关场景或改变主体。
- **不强制“黄金日落滤镜”**：尊重原片的时段、天气与主体固有色。

## 文件结构

```text
vintage-travel-gouache-text-only/
├── SKILL.md
├── README.md
├── CHANGELOG.md
├── references/
│   ├── visual-style-dna.md
│   ├── region-texture-map.md
│   ├── palette-and-lighting.md
│   ├── prompt-templates.md
│   └── comparison-and-qa.md
└── examples/
    └── example-requests.md
```

**注意：没有 `assets/style-reference.webp`，这正是 v2.0 的设计。** 如果在使用此 Skill 时仍向生成模型附带其他旧参考图，就不再是“纯文字规范”的测试了。

## 安装与使用

把 ZIP 解压后完整的 `vintage-travel-gouache-text-only` 文件夹放到支持 Agent Skills 的工具所识别的 skills 目录，例如个人级 `~/.agents/skills/vintage-travel-gouache-text-only/` 或项目级 `.agents/skills/vintage-travel-gouache-text-only/`（具体以工具的安装要求为准）。新建会话后调用。

直接说：

> 使用 `vintage-travel-gouache-text-only` v2.0，只凭文字风格规范把这张照片改成复古旅行水粉插画。保留主体，适度扩展背景；天空平滑、轻薄、只有极微弱颜料颗粒，海水和地面可以有较明显但精致的短笔触。不要使用风格参考图。

## 注意事项

Skill 是生成提示词和质量控制的工作流，不是图像模型本身，最终效果仍受具体图像生成工具与随机性影响。推荐先用相同原图、相同画幅分别测试 v1.1 与 v2.0，尤其比较天空质感和商业插画精致度。若天空仍过重，使用 `references/prompt-templates.md` 的局部纠偏模板 F。
