# light-aaa-web-game

用程序化资产制作完整可玩的轻量 Web 游戏。玩法、视角、关键反馈和代表场景按作品设定，开发与交付流程见 [SKILL.md](SKILL.md)。

本版的重点是玩家体验闭环：先定义玩家目标和参考品质锚点，再做可玩样板；依据实际试玩/用户反馈建立问题、假设、失败回归、最小修改、前后对比与回归证据。核心问题未关闭不能验收。单 HTML、运行时零额外网络请求是硬约束。

Skill 发布版本为 `1`。新项目使用第 3 版验收预算和诊断模板。验证器也支持第 2 版项目已有的预算与场景脚本。

## 使用

将整个目录放入支持 Agent Skills 的客户端所读取的技能目录，保持 `SKILL.md` 位于目录根部。常见项目级位置为 Codex 的 `.agents/skills/light-aaa-web-game/` 或 Claude Code 的 `.claude/skills/light-aaa-web-game/`；具体以客户端配置为准。重新加载客户端技能后使用，生成本文件不意味着其他设备已自动安装。

示例提示：

> 使用 light-aaa-web-game，做一个等距视角的光路解谜游戏。让玩家旋转棱镜、观察折射，并能撤销重试。单 HTML 离线运行，体积不超过 2 MiB。先完成玩法闭环，再做程序化素材和高画质，最后运行验证、检查实际截图，报告已通过与未验证项。

建议完整调用：

> 使用 light-aaa-web-game，以我给的 Demo 为品质参考。先从新玩家的目标、操作反馈和失败恢复定义 experience-plan，并做一段达到参考品质的可玩样板。成品只有一个 HTML，除入口文档外不得有任何网络请求。每轮从玩家角度提出 2–3 条具体优化建议，在授权范围内实施并复测；用 iteration-log 保存问题、假设、修改前后和回归证据。P0/P1、动态反馈、视觉或数值门槛不通过就继续有针对性地迭代；缺测如实标记。请用连续画面验证核心操作的反馈。

## 文件

- `SKILL.md`：触发条件、开发流程、验收与交付要求。
- `references/`：架构、验证规范、参考作品实测分析。
- `templates/`：预算、游戏诊断接口、人工/模型视觉审查表。
- `scripts/validate_game.py`：静态大小、自包含、隔离浏览器运行、截图、帧时间、接口审计、项目玩法测试。
- `scripts/finalize_review.py`：核对成品/报告/截图哈希、分数和全部验收状态。
- `scripts/audit_resources.mjs`：实际几何/音频/确定性审计辅助函数；项目仍需补齐材质、导航及视觉语义检查。
- `scripts/self_test.py`：验证器自身的正反例回归测试。
- `references/experience-loop.md`：玩家目标、样板品质、问题分级、每轮建议、迭代与收敛。
- `references/feedback-reliability.md`：射击反馈的事件/渲染/可见性、对象池、低帧率和动态证据。
- `references/zero-network.md`：单 HTML、同源也计入零请求、动态网络监测与托管外壳边界。
- `scripts/network_audit.py`：全浏览器上下文网络和请求尝试审计。
- `scripts/feedback_audit.py`：逐次有效动作的反馈提交关联与缺失率计算。
- `scripts/stability_audit.py`：冷启动、持续运行、重开和资源增长数据的验收。
- `scripts/experience_audit.py`：玩家评审与问题关闭证据检查。
- `scripts/self_test_v2.py`、`scripts/self_test_network.py`：旧版预算兼容回归及 Chromium 网络反例。

## 验证器

Python 3.10+，依赖见 `scripts/requirements.txt`；资源审计辅助函数用于浏览器 ES module 或 Node.js 20+。

```bash
python -m pip install -r scripts/requirements.txt
python -m playwright install chromium
python scripts/self_test.py
python scripts/self_test_v2.py
python scripts/self_test_network.py --browser /path/to/chromium
node scripts/self_test_resources.mjs
python scripts/validate_game.py /path/to/game.html --out /path/to/evidence
```

没有标准诊断接口的 HTML 会因缺失证据而未验证/失败。对于本次参考作品，可加 `--adapter reference`；这不会伪造完整覆盖。

单文件默认硬预算为 2 MiB 原始、700 KiB gzip；性能默认桌面 1280×720 中档，设计目标 60 FPS。预算是目标，不是未经测试的保证。低帧率、黑屏、效果不符都要修复；软件渲染环境只用于诊断，不用于硬件性能承诺。

最终验收须实际打开截图。不要直接把模板的 0 改成高分；填写可见证据。视觉评分是审查记录，不是客观的“3A 检测算法”。

发布前的早期内部版本曾用于制作并测试 BREAKWATER 港口 FPS。30 项自动检查通过，9 项玩法交互通过，真实硬件性能未验证；视觉完成度低于参考 Demo，最终视觉验收未通过。具体问题及后续实现约束见 `references/trial-findings.md`，这次实作证明了轻量与可玩路线，但尚未证明 Skill 能稳定产出参考级画质。

上面的游戏结果属于早期验收标准，不能自动视为通过当前标准。当前规范与验收器根据画质差距和用户报告的偶发射击反馈问题修订；测试器反例通过不等于游戏已修复。旧游戏缺少新的动态/稳定性/体验证据时仍为未验证。用户已报告的核心问题保持开放直到复现、修复和复测完成。

已有项目可以继续使用第 2 版预算。采用新格式时按作品声明代表负载、核心动作与反馈通道，同步更新接口与场景脚本。字段和证据示例见[验证规范](references/validation.md)。
