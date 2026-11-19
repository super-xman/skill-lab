# 复古旅行海报厚涂风 Skill

这是以你提供的《海边度假》参考插画为视觉依据制作的可复用 Agent Skill。它旨在把其他图片变成**复古旅行海报 × 不透明水粉 × 轻度手绘厚涂**风，**默认允许适度扩展背景和场景细节**，但不复制原参考图里的邮轮、灯塔、落日等具体内容。

## 文件结构

```text
vintage-travel-gouache-reference/
├── SKILL.md                          # 核心指令与触发规则
├── assets/
│   └── style-reference.webp          # 高清 WebP 参考图（2048×731，优化仓库体积）
├── references/
│   ├── style-guide.md               # 风格 DNA 和近似色板
│   └── prompt-templates.md          # 中文/英文提示词与验收标准
└── examples/
    └── example-requests.md         # 常见使用场景
```

## 在 Codex 中使用

将 ZIP **解压后**的整个 `vintage-travel-gouache-reference` 文件夹放到：

- **个人级**（所有项目）：`~/.agents/skills/vintage-travel-gouache-reference/`
- **项目级**（当前项目）：`项目目录/.agents/skills/vintage-travel-gouache-reference/`

打开新的 Codex 会话后，直接说：

> 使用 `vintage-travel-gouache-reference` Skill，把我上传的图片转换成复古旅行海报厚涂风。保留原图主体、姿态和关键特征，允许适度扩展背景、增添合理环境细节和优化取景，但不要照搬参考图的具体元素。

**注意：** Skill 是工作流与提示词，不自带绘图模型。真正出图依赖你使用的应用/Agent 是否具备图像生成或编辑工具。若应用无法把 Skill 内的参考图片传给绘图模型，请在那次绘图请求里额外附上 `assets/style-reference.webp`。

## 快速复用

- 查看核心规则：`SKILL.md`
- 查看风格色板和光影：`references/style-guide.md`
- 复制长提示词或英文提示词：`references/prompt-templates.md`

## 设计原则

1. **主体保真、背景可扩展**：目标图片的核心主体、关键姿态和指定颜色优先，允许适当补景、延展画面并提升空间层次。
2. **变画风**：复刻的是绘画方法——不透明水粉、手绘厚涂、复古冷暖关系与哑光纸张颗粒。
3. **拒绝场景照搬**：不把邮轮、灯塔、巨大太阳、海湾、建筑等参考图元素当作固定模板；新增环境元素必须符合目标主题。
4. **扩展强度可控**：默认 1 级适度扩展；用户要求原样不动时 0 级严格复刻；明确授权自由创作时 2 级扩展。

版本：1.1（2026-11-19；增加适度内容扩展）。
