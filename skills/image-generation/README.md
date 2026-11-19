# Image Generation Skills · 生图技能

存放图像生成、风格迁移与图生图相关的 Agent Skills。每个目录是一套可以单独复制安装的 Skill；其 `SKILL.md` 的 `name` 字段全局区分。

| Skill | 版本 | 风格来源 | 适用情况 |
| --- | --- | --- | --- |
| [`vintage-travel-gouache-reference`](vintage-travel-gouache-reference/) | v1.1 | **附带参考图** `assets/style-reference.webp` + 文字规范 | 更注重与原始《海边度假》海报画风一致的用户 |
| [`vintage-travel-gouache-text-only`](vintage-travel-gouache-text-only/) | v2.0 | **仅文字规范，不依赖任何风格参考图** | 需要独立复用、天空轻薄哑光、分区域控制笔触的用户 |

## 使用建议

- 两版并列保存，不是升级覆盖关系；可同时安装，明确使用各自的 `name` 调用。
- **参考图版**更容易对齐原始画风，但可能让天空笔触偏重，适用时可手动补充“天空平滑，减少方向性笔痕”。
- **纯文字版**强调精致复古商业插画，禁止天空普遍厚涂，默认允许适度扩充合理背景。
- 两版都优先保留用户提供图片的主体、构图关系和指定细节；不允许机械复制参考图中的邮轮、灯塔和巨大太阳。
- 有多张目标图时应分别出图，除非用户明确要求拼贴或组图。

## 安装到 Agent / Codex 项目

任选一个完整目录复制到项目 `.agents/skills/`，例如：

```bash
cp -R skills/image-generation/vintage-travel-gouache-text-only /path/to/project/.agents/skills/
```

使用时明确指定 Skill 的名称：

> 使用 `vintage-travel-gouache-text-only`，把这张照片改绘成精致的复古旅行海报水粉插画，保留主体，适度扩景，天空平滑、颗粒轻微。

生成图像需要可用的图像生成/编辑工具；Skill 本身是工作流与风格规范，不含生图模型。
