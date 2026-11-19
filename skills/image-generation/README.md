# Image Generation Skills · 生图技能

本分类存放图像生成、图生图与插画风格相关的 Agent Skills。每个子目录均可独立安装。当前两种复古旅行海报风格都**只靠文字规范**，不需要额外风格参考图。

| Skill | 画面风格 | 天空笔触 | 适合用户 |
| --- | --- | --- | --- |
| [`vintage-travel-gouache-painterly`](vintage-travel-gouache-painterly/) | 明显油画式颜料扫涂、不透明水粉与复古海报 | 可见的有节奏涂抹 | 喜欢更强烈手绘肌理、云朵和山石更有运动感 |
| [`vintage-travel-gouache-refined`](vintage-travel-gouache-refined/) | 精致哑光水粉、清晰复古商业插画 | 近乎平滑，只有低对比微颗粒 | 喜欢天空安静、笔触因材质分区、整体更克制 |

## 示例图
两种风格的海滨与荒漠实际输出均分别嵌入各自的 README，见上述目录链接。所有示例图仅用于**展示与比较**，在执行 Skill 时**不可自动加载为风格参考图**。

## 共通原则
- 保留目标图的核心主体、人物/建筑特征、重要姿态和场景关系。
- 默认允许 L1 适度扩景；用户要求原样保留则使用 L0；明确授权自由发挥时使用 L2。
- 默认沿用目标图画幅，多张目标图分别生成，除非用户要求拼贴。
- 不引入无依据标题、Logo、巨型太阳、邮轮、灯塔或其他不相关主题物。
- 生成质量取决于具体图像模型；两套 Skill 只规定提示词与验收流程。

## Codex 项目级安装

```bash
cp -R skills/image-generation/vintage-travel-gouache-painterly /path/to/project/.agents/skills/
cp -R skills/image-generation/vintage-travel-gouache-refined /path/to/project/.agents/skills/
```

例如：“使用 `vintage-travel-gouache-painterly` 转绘这张照片，保留主体并适度扩景”；或“使用 `vintage-travel-gouache-refined`，让天空保持平滑轻薄”。
