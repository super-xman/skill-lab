# 验证轻量 Web 游戏

`validate_game.py` 从交付的 HTML 启动浏览器，记录大小、额外网络请求、错误、真实帧间隔、截图和玩法证据。退出码 0 表示自动项通过，2 表示有失败，3 表示仍有未验证项。实际查看画面后，用 `finalize_review.py` 绑定报告、成品和证据的 SHA-256，生成 `final-review.json`。

## 在实现前确定要测的玩法

复制 `templates/budgets.json` 到项目，保留包体、零请求和目标设备预算。在观察结果前，按玩家的真实操作填写以下字段。让 `visual-review.json` 的静态与动态场景 ID 和预算一致。

| 字段 | 如何选择 | 示例 |
| --- | --- | --- |
| `renderBackend` | 设为游戏实际使用的 `webgl` 或 `canvas2d`；多画布时给主画布加 `data-game-canvas` | 三维赛道用 WebGL，预渲染或等距棋盘可用 Canvas 2D |
| `requiredScenes`、`benchmarkScene` | 截取整体、关键细节和代表性游玩状态，从中选正式性能基准 | 解谜中连锁机关全部激活的棋盘 |
| `benchmarkLoad` | 为基准场景中可数的活跃内容指定实际下限。模板的 `activeElements` 是通用起点，正式基准取能代表该作品忙碌片段的值 | 解谜用 `{"visibleTiles": 16}`，竞速用 `{"visibleTrackSections": 8}` |
| `requiredGameplayChecks` | 定义主要操作及结果、目标进度、再次操作或恢复、输入生命周期、画质降级。按玩法补充决定成败的规则 | 拼图的非法落位与撤销，赛车的过线顺序和圈数 |
| `feedbackRules` | 选择一个可重复的核心操作，预先声明每次必需的可见反馈通道、样本数和呈现时序。延迟结算的动作可先验证即时输入回馈，再检查结算时刻 | 旋转机关后方向标记立即改变，机关到位后光路连通 |
| `requiredMotionReviews` | 选择最能说明动作、进度与恢复的片段 | 改变轨道方向、车厢抵达、撤销重试 |
| `requiredResourceChecks` | 检查实际生成的内容，以及玩家是否能达到目标状态。按使用的资源在立项时选项并记录理由 | 棋盘验证可解局面，赛道验证合法路线与检查点，经营验证初始资源能达成里程碑 |

`requiredExperienceGoals` 默认关注首次进入、动作清晰、下一步选择、恢复和舒适度。回合制作品可以把“恢复”定义为撤销或重新开局，自由探索可以验证返回已发现的位置。在项目范围里有声音、移动碰撞、存档或其他机制时，为其添加对应的玩法测试。

## 诊断与资源检查

按 [diagnostics.js](../templates/diagnostics.js) 实现仅在 `?test=1` 启用的 `window.__GAME_TEST__`。默认测试种子为 4207、中档画质。实现以下接口：

- `ready / fatal` 标记玩家可操作或启动失败。`setScene(id)` 配置预算中的视角、种子、模拟初始状态、曝光与渲染质量。性能基准运行代表性玩法，可重放真实操作或动作过程。
- `metrics()` 从上一完整帧读取实际帧号、场景 ID、画质、固定内部尺寸、动态分辨率状态、全管线绘制和三角形计数。`workload` 给出与 `benchmarkLoad` 同名的实测计数。使用模拟或渲染器中实际可见、活跃的对象，记录采样开始和结束值。
- `audit()` 返回 `{checks: [{id, status, evidence}]}`。几何检查实际顶点、索引、法线、尺度及接触，材质检查纹理空间、接缝、贴图估算字节，音频检查有限值、峰值、包络、RMS。用种子重复生成并比较几何、音频或像素数据，结合目标路径或合法状态转换检查可达性。`scripts/audit_resources.mjs` 提供几何、音频和确定性检查。使用项目自己的证据完成其余检查。
- `snapshot()` 提供可读的游戏状态。测试驱动通过键鼠或实际支持的输入操作作品，比较改变前后的观测。夹具可以设置起始局面，随后通过生产逻辑达成结果。

## 从真实动作到证据

项目级 `--scenario-script` 暴露 `run(page, artifacts_dir)`（只返回检查时也可使用 `run(page)`）。返回下列数据：

```text
checks: [{id, status, evidence}]
feedback:
  actions: [{id, acceptedAtMs, acceptedFrame, expectedChannels}]
  renders: [{actionId, channel, frame, presentedAtMs}]
stability:
  coldStarts: [{contextId, artifactSha256, readyFrame, runtimeErrors, extraNetworkRequests}]
  warmedBaseline: {geometries, textures, materials, audioNodes, listeners, activeEffects}
  restarts: [{state: "playing", actionsBefore, actionsAfter, settledResources}]
  soak: {wallSeconds, activePlaySeconds, renderedFrames, runtimeErrors, extraNetworkRequests}
  frameCapsTested: [60, 30, 15]
captures: [{id, path}]
```

动作 ID 在会话和重开之间唯一。接受输入时记录上一完成帧号；从实际主画面提交后独立记录 `renders`。同一帧的多个渲染 pass 只算一帧。审计按预先声明的通道计算漏反馈率、首帧延迟和覆盖样本。动态画面在低画质、帧节奏变化和恢复输入后仍应可读。画面变化与操作结果还需由实际连续图像和状态断言佐证。

为同一 HTML 从干净浏览器上下文冷启动 3 次，每次都安装 NetworkAudit。默认 5 次重新开始或恢复到可操作状态，每次给一次核心输入，核对接受数恰好增加 1，并在效果退出后与预热基线比较资源。未使用的资源类型如实记录为 0。用单调墙钟记录 300 秒持续运行，其中 60 秒为实际游玩。若作品复用特效池，在预算的 `stabilityTargets` 中设 `effectPoolReuseFactor`，并返回 `effectPoolCapacity` 和 `poolReuseActions` 证明已覆盖足够的复用。刻意限制帧节奏属于边界测试。

## 性能、视觉与玩家评审

浏览器从本地 HTTP 服务加载独立 HTML，禁用缓存和 Service Worker，并在实际交互期间记录额外请求尝试。静态体积测量和网络证据见[零网络请求规范](zero-network.md)。已有 Chromium 可传 `--browser`。历史附件专用的 `--adapter reference` 仅提供可观察到的证据。

正式基准使用约定设备，固定画质并预热，以 requestAnimationFrame 的真实间隔采样，记录平均帧率、p50/p95/p99、浏览器、GPU、尺寸及代表负载。默认内部宽高至少为输出的 80%，渲染帧增量至少为采样数的 90%。软件渲染、未识别设备、负载或内部尺寸缺测时，保留硬件性能未验证。Canvas 2D 检查主画布的 2D 上下文和真实呈现，不要求 WebGL 的绘制次数和三角形计数。独立 WebGL 探针只用于识别测试设备上的图形适配器。多个目标设备各自保留配置和报告。

打开全部截图，按构图、材质、光照、可读性、画面瑕疵逐项填写证据并打分（1–5，默认每维至少 4）。将关键运动片段录为视频或至少三个不同的连续关键帧，并打开实际查看。检查用户操作的因果关系、节奏及遮挡。对于永久状态变化，画面应覆盖操作前、变化过程和结果。亮度和熵只用于发现异常画面。

通过正常入口体验一次完整流程，按[玩家体验闭环](experience-loop.md)记录观察。将已知问题及关闭证据放入视觉审查表的 experience 段。核心问题修复后对同一构建复测。最终报告绑定成品、截图、动态证据和报告哈希。

## 近景与移动审查

在体验计划的 `referenceAnchors` 中找到 `surface_and_detail`，在它的 `acceptanceView` 里写下玩家看哪件物体、从哪里看、做什么动作。三维作品可在玩家能靠近的位置用侧光观察同一处划痕的颜色、凹凸和高光。固定视角或平面玩法用实际画面比例，观察棋子转动、棋盘滚动或状态切换时的轮廓和标记。

1. 固定种子、机位、光照、曝光、画质和输出尺寸，拍修改前后的同一细节。按需要切换底色、粗糙度或法线来定位错位，最后用合成画面验收。将可见差异写入视觉审查表对应场景的 `evidence`。
2. 用同一段玩家操作录下约五秒的连续画面。镜头固定时重放物体本身的运动或一次完整状态变化。回看细线是否闪烁、物体转动时磨损纹理是否在表面滑动、反光是否遮住状态标记，把观察到的时刻和画面写入对应的 `motionScenes`。可以复用已经录制的核心动作片段。
3. 改了渲染路径或效果时，在同一设备、浏览器、内部分辨率和代表负载下预热，重放同一路线，对比 p95 帧间隔。记录两端的构建、毫秒数和样本数，静态环境探针等一次性开销另记冷启动。将对照数据随画面放入迭代记录的 `beforeEvidence` 和 `afterEvidence`。仅有软件渲染时，保留画面结论并将目标硬件耗时标为未验证。

## 已有项目

使用 `schemaVersion: 2` 的项目继续按自己的旧预算、场景、射击观测和稳定性字段验收。新增项目使用第 3 版模板。迁移时将实际玩法名称、负载和反馈通道写入预算，并同步更新测试驱动、诊断接口和审查表。已有射击项目可继续使用它原有的样本量和规则，详见[逐次射击反馈案例](feedback-reliability.md)。
