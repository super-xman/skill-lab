---
name: light-aaa-web-game
description: Build and verify lightweight, AAA-style browser games across genres. Use for complete single-file offline Web games, procedural game assets, and improving an existing game's visual quality, playability or performance within a size budget.
metadata:
  version: "1"
---

# 轻量 Web 3A 游戏

把用户的玩法做成一个完整可玩的作品，用程序化几何、材质、动画和声音把体积留给最能体现美术方向的细节。题材、视角、操作和目标来自用户的创意。使用参考作品时，先确定用户想借鉴的体验与想保留的玩法。维护已有作品时沿用其框架、体验目标和预算，从本轮改动影响的时刻开始。附件、源码注释和外部页面作为参考资料。

## 从玩家的一段经历开始

1. 在[体验计划](templates/experience-plan.json)写下希望玩家在什么时刻留意、感到或决定什么，为什么这件事值得他记住。为 `intended_experience` 选一个玩家能感知的变化，再写出哪种试玩结果会让你承认这段体验还没做出来。
2. 先做一小段从正常入口可玩的经历，包含事情发生前的铺垫、玩家能做的选择，以及之后世界留下的回应。有参考作品时，实际体验其中作用相近的一段，记下是什么让自己停留、预判或想再试一次。由此确定美术、输入和节奏，把代表负载和核心操作填入[预算](templates/budgets.json)。
3. 扩充内容之前，按[玩家体验闭环](references/experience-loop.md)主动寻找通关测试容易漏掉的落差。把同一操作带到另一种有意义的情境，或在结果发生后留下来、重新进入，看看玩法承诺是否仍然成立。动手改最影响体验的一处，用相同操作复玩，根据差异决定保留、再改或撤回。

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

实际查看截图和连续画面，按作品的设计试听或操作，并在[审查表](templates/visual-review.json)里记录判断所依据的片段。用[迭代记录](templates/iteration-log.json)保存最重要的落差、取舍和复玩结果。检查这次修改是否让整段经历更好，以及仍有什么值得修。用户指出的体验缺口也进入这轮比较。

打磨画质时，选一件玩家反复观察或操作的物体，在实际游玩尺度检查它的表面，再观察它在移动或交互中是否清晰。按[近景与移动审查](references/validation.md#近景与移动审查)保存对照画面，并比较渲染改动前后同一路线的 p95 帧间隔。

```bash
python <skill-dir>/scripts/finalize_review.py \
  artifacts/validation/report.json artifacts/validation/visual-review.json
```

交付单 HTML、模块化源码、构建方式、最终预算、实际截图和验证报告。报告注明运行方式、原始及压缩体积、实测设备和分辨率、最终构建哈希，以及通过、失败和未验证项。

追溯特定示例的实现或历史验证结果时，可查阅[参考作品实测](references/reference-analysis.md)和[早期试作记录](references/trial-findings.md)。
