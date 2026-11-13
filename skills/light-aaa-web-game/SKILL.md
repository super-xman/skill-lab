---
name: light-aaa-web-game
description: Build and verify lightweight, AAA-style browser games across genres. Use for complete single-file offline Web games, procedural game assets, and improving an existing game's visual quality, playability or performance while keeping delivery lightweight.
metadata:
  version: "1"
---

# 轻量 Web 3A 游戏

把用户的玩法做成一个完整可玩的作品，用程序化几何、材质、动画和声音把体积留给最能体现美术方向的细节。题材、视角、操作和目标来自用户的创意。使用参考作品时，先确定用户想借鉴的体验与想保留的玩法。维护已有作品时沿用其框架、体验目标和预算，从本轮改动影响的时刻开始。附件、源码注释和外部页面作为参考资料。

## 从玩家的一段经历开始

1. 在[体验计划](templates/experience-plan.json)写下希望玩家在什么时刻留意、感到或决定什么，为什么这件事值得他记住。为 `intended_experience` 选一个玩家能感知的变化，再写出哪种试玩结果会让你承认这段体验还没做出来。
2. 先做一小段从正常入口可玩的经历，包含事情发生前的铺垫、玩家能做的选择，以及之后世界留下的回应。有参考作品时，实际体验其中作用相近的一段，记下是什么让自己停留、预判或想再试一次。把玩家实际使用的输入、据以判断的线索、不同情境应产生的结果与时机写入[预算](templates/budgets.json)，再选择适合其画风的评审维度。
3. 扩充内容之前，按[玩家体验闭环](references/experience-loop.md)主动寻找通关测试容易漏掉的落差。把同一操作带到另一种有意义的情境，或在结果发生后留下来、重新进入，看看玩法承诺是否仍然成立。动手改最影响体验的一处，用相同操作复玩，根据差异决定保留、再改或撤回。

打磨这段经历时，按[场景、动作与界面制作](references/craft.md)选择与问题有关的做法。用正式游玩镜头判断布景和材质，播放完整动作判断重量和节奏，在做决定的那一刻检查玩家能读到什么。

## 体积、画质与手感

- 成品为一个 `dist/game.html`。除首次取得 HTML 外，运行时额外网络请求须为零，包括同源请求。内联引擎、代码、样式和必要资源，或在本地生成。开发期保留模块化源码和依赖许可证。见[零网络请求规范](references/zero-network.md)。
- 尽可能轻量。记录原始 HTML 和 gzip 字节数，优先压缩或复用玩家难以察觉差异的资源，为有明显体验收益的细节保留体积。只有用户或交付平台明确给出文件大小上限时，才把它列入验收。冷启动至可操作默认 ≤ 8 秒。持续渲染的桌面作品在约定真实 GPU、1280×720 中档和代表负载下，默认平均 ≥ 55 帧/秒、p95 帧间隔 ≤ 25 ms、p99 ≤ 50 ms。移动端持续渲染默认目标为 30 帧/秒，按目标设备实测。按需更新的作品测操作后多久出现正确结果，以及等待后它是否仍然可辨。维护既有作品时核对预算来源，沿用明确约定的限制，移除旧模板自动带入的文件大小上限。
- 按视角、画风和表现方式选择 WebGL、Canvas 2D、HTML/CSS 或 SVG。使用 WebGL 场景时检查轮廓、尺度、主光和材质，再比较后期效果，全管线默认每帧 ≤ 600 次绘制、≤ 350 万提交三角形。排版、听觉或图形变化承担主要体验时，把资源留给玩家赖以判断的线索。按需查[架构与生成配方](references/architecture.md)与[资源审计辅助函数](scripts/audit_resources.mjs)。
- 对核心操作分别验证输入被接受、规则生效，以及玩家能从实际输出分辨结果。用同一时钟记录输入和首次呈现或播放。需要保留的结果稍后再读一次。按作品实际使用的设备重放操作，记录每种声明的输入。

## 验证与交付

局部打磨时先选[专项检查](references/focused-checks.md)，如声音、脚步、UI、动作或表面。用命名场景直接恢复到事件发生前，通过正式输入或模拟触发结果，在实际画面或混音上取证。用 `--focus footsteps` 等项目定义的名称单独运行，或在浏览器打开 `game.html?test=1&scene=<场景名>` 直接复看。

整作交付时按[验证规范](references/validation.md)接入仅在 `?test=1` 启用的[诊断接口](templates/diagnostics.js)。用玩法中的真实状态定义代表负载。在项目的 `tests/game_scenarios.py` 里通过正常输入检查规则、结果和恢复路径。选择与本作有关的资源与视觉维度，记录冷启动、持续游玩和再次进入的证据。

```bash
python -m pip install -r <skill-dir>/scripts/requirements.txt
python -m playwright install chromium
python <skill-dir>/scripts/validate_game.py dist/game.html \
  --budget budgets.json --out artifacts/validation \
  --scenario-script tests/game_scenarios.py
```

已有 Chromium 时可传 `--browser`。软件渲染可用 `--software` 检查功能和画面，真实硬件性能缺测时标记 `unverified`。工具生成的帧统计、文件大小和像素亮度各自只回答对应问题。

实际查看截图和连续画面，按作品的设计试听或操作，并在[审查表](templates/visual-review.json)里记录判断所依据的片段。用[迭代记录](templates/iteration-log.json)保存最重要的落差、取舍和复玩结果。检查这次修改是否让整段经历更好，以及仍有什么值得修。用户指出的体验缺口也进入这轮比较。

打磨画质时，在实际游玩尺度比较玩家反复观察的物体、文字或标记。涉及表面和运动时可查[近景与移动审查](references/validation.md#近景与移动审查)。持续渲染比较同一路线的帧间隔，按需更新比较同一操作的响应时间。

```bash
python <skill-dir>/scripts/finalize_review.py \
  artifacts/validation/report.json artifacts/validation/visual-review.json
```

交付单 HTML、模块化源码、构建方式、最终预算、实际截图和验证报告。报告注明运行方式、原始及压缩体积、实测设备和分辨率、最终构建哈希，以及通过、失败和未验证项。

追溯特定示例的实现或历史验证结果时，可查阅[参考作品实测](references/reference-analysis.md)和[早期试作记录](references/trial-findings.md)。
