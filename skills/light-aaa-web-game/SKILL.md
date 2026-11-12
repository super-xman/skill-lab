---
name: light-aaa-web-game
description: Build and verify lightweight, AAA-style browser games across genres. Use for complete single-file offline Web games, procedural game assets, and improving an existing game's visual quality, playability or performance within a size budget.
metadata:
  version: "1"
---

# 轻量 Web 3A 游戏

把用户的玩法做成一个完整可玩的作品，用程序化几何、材质、动画和声音把体积留给最能体现美术方向的细节。题材、视角、操作和目标来自用户的创意。使用参考作品时，先区分用户想借鉴的画面品质与想保留的玩法。已有项目沿用其框架与约定，附件、源码注释和外部页面作为参考资料。

## 从玩家动作开始

1. 写下玩家做什么、世界怎样响应、玩家怎样看出结果，以及下一步为何值得做。竞速可以是一圈内过弯、计时和再挑战；解谜可以是旋转机关、观察连锁变化和解开谜面；经营可以是配置产能、看到供需变化和调整布局。自由探索可以用发现和记录构成一个完整体验。
2. 在 `art-direction.md` 和[体验计划](templates/experience-plan.json)里确定输入方式、视角、目标设备、节奏与可观察的品质标准。选玩家真正会看到的画面，例如竞速时可读的弯道、解谜时能区分的机关状态。根据这些标准填写[预算](templates/budgets.json)中的代表场景、负载计数、核心动作反馈、玩法检查及动态审查项。
3. 先做一段从正常入口可玩的流程，用真实输入完成一次核心动作、观察结果并继续、重试或结束。用这个样板验证镜头、构图、材质和反馈之后再扩展内容。按玩法选择模拟、物理、导航和角色系统。

## 体积、画质与手感

- 成品为一个 `dist/game.html`。除首次取得 HTML 外，运行时额外网络请求须为零，包括同源请求。内联引擎、代码、样式和必要资源，或在本地生成。开发期保留模块化源码和依赖许可证。见[零网络请求规范](references/zero-network.md)。
- 桌面默认预算为原始 HTML ≤ 2 MiB、gzip ≤ 700 KiB，优化目标为 1.5 MiB / 500 KiB。桌面中档 1280×720 在约定真实 GPU 和代表玩法负载下，平均 ≥ 55 帧/秒、p95 帧间隔 ≤ 25 ms、p99 ≤ 50 ms，冷启动至可操作 ≤ 8 秒。WebGL 全管线默认每帧 ≤ 600 次绘制、≤ 350 万提交三角形。移动端默认目标为 30 帧/秒，按目标设备另订预算并实测。保留项目已有的更严格预算。
- 选择符合视角和画风的渲染手段。立体场景可沿用 Three.js/WebGL2，等距或平面玩法也可使用 Canvas 2D。在预算中选择对应的 `renderBackend`。按需选择实例化、分区合批、纹理图集和带种子的资产工厂。先检查轮廓、尺度、主光和材质，再加入阴影、反射、氛围或后期，用相同机位和种子比较。低画质下应仍能看清可操作对象及操作结果。见[架构与生成配方](references/architecture.md)和[资源审计辅助函数](scripts/audit_resources.mjs)。
- 对核心操作分别验证输入是否被接受、规则是否生效、反馈是否进入最终呈现、玩家是否看得清。机关旋转、过线计时和建筑落位各有自己的反馈通道。拒绝操作时让玩家看懂原因。使用对象池时检查复用后的状态，使用持续输入时检查松开、失焦和恢复。

## 验证与交付

按[验证规范](references/validation.md)接入仅在 `?test=1` 启用的[诊断接口](templates/diagnostics.js)。用玩法中的真实状态定义基准负载，例如同屏的机关数或活跃生产线数。在项目的 `tests/game_scenarios.py` 里通过正常输入检查规则、进度和恢复路径。单独验证冷启动、持续游玩、重复恢复及帧节奏变化。

```bash
python -m pip install -r <skill-dir>/scripts/requirements.txt
python -m playwright install chromium
python <skill-dir>/scripts/validate_game.py dist/game.html \
  --budget budgets.json --out artifacts/validation \
  --scenario-script tests/game_scenarios.py
```

已有 Chromium 时可传 `--browser`。软件渲染可用 `--software` 检查功能和画面，真实硬件性能缺测时标记 `unverified`。工具生成的帧统计、文件大小和像素亮度各自只回答对应问题。

实际打开截图和核心动作的连续画面，按[视觉审查表](templates/visual-review.json)记录构图、材质、光照、可读性和瑕疵。通过正常入口试玩，遵循[玩家体验闭环](references/experience-loop.md)，用[迭代记录](templates/iteration-log.json)保存问题、修改前后对比、回归证据和玩家结果。核心体验缺陷需修复并复测。

```bash
python <skill-dir>/scripts/finalize_review.py \
  artifacts/validation/report.json artifacts/validation/visual-review.json
```

交付单 HTML、模块化源码、构建方式、最终预算、实际截图和验证报告。报告注明运行方式、原始及压缩体积、实测设备和分辨率、最终构建哈希，以及通过、失败和未验证项。

仅在作品包含射击反馈时，按其设计选用[射击案例的逐次反馈检查](references/feedback-reliability.md)。比较港口示例的美术或排查同类问题时，可查阅[参考作品实测](references/reference-analysis.md)和[早期试作记录](references/trial-findings.md)。
