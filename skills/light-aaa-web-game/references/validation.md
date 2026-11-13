# 验证轻量 Web 游戏

`validate_game.py` 从交付的 HTML 启动浏览器，记录大小、额外网络请求、错误、真实帧间隔、截图和玩法证据。退出码 0 表示自动项通过，2 表示有失败，3 表示仍有未验证项。实际查看画面后，用 `finalize_review.py` 绑定报告、成品和证据的 SHA-256，生成 `final-review.json`。

检查某个声音、界面或动作时，按[专项检查与场景直达](focused-checks.md)配置 `--focus`。每个用例可以直接进入自己的准备状态，输出独立的专项报告。交付流程使用不带该参数的完整命令。

## 在实现前确定要测的玩法

从玩家用什么线索做决定开始。选一个能暴露问题的操作，写下要对照的情境、每种情境的预期结果、玩家应该何时察觉，以及该结果应保留多久。然后填写 [budgets.json](../templates/budgets.json)。模板展示了一种连续渲染的桌面配置，项目按创作意图替换其中的输入、条件、通道和审美维度。在观察结果前确定这些约定。

| 字段 | 对本作做的选择 |
| --- | --- |
| `device` | 设置 `inputMethods`、`isMobile`、`deviceScaleFactor` 及外层 `viewport`。标准驱动记录实际发生的 `mouse`、`keyboard`、`pen` 或 `touch` 输入。触屏场景用 `tap()` 走完核心操作。其他输入方式在 `requiredGameplayChecks` 中声明 `input_<名称>`，由场景驱动在适用设备上取证。多个目标设备各跑一份配置。 |
| `renderBackend` | 可选 `webgl`、`canvas2d`、`dom` 或 `svg`。多个画布用 `data-game-canvas` 标记主画布，HTML 或独立 SVG 作品可用 `data-game-root` 标记实际游玩区域。 |
| `renderMode` | 持续模拟或动画用 `continuous` 测帧节奏。输入、事件才触发重绘的作品用 `on-demand` 测输入至结果的时间和结果是否保持。按需作品仍可评审转场动画。 |
| `requiredScenes`、`benchmarkScene`、`benchmarkLoad` | 选能看出本作体验的场面，声明一种能在代表场面实际计数的负载。例如可见的选项数、活跃车辆数或播放声部数。 |
| `requiredGameplayChecks`、`requiredResourceChecks` | 为决定玩法成败的规则选择检查，资源项只列本作实际采用的内容。音频缓冲的峰值和 RMS 可用于发现削波或静音。 |
| `visualDimensions`、`requiredMotionReviews` | 为这款作品选评分维度，例如排版节奏、轮廓辨认或逆光下的材质。静态截图的 `scores` 与维度名一致。需要评判运动时列出对应片段，离散互动可用操作前后两幅画面。纯听觉核心可把动态列表留空，完全通过声音表达的作品也可将视觉维度留空。 |
| `requiredExperienceGoals` | 用 `intended_experience` 记录希望玩家记住的经历和会让它落空的反例。仍妨碍某个已声明目标的问题在审查表中填 `blocksGoal`。 |

## 从操作到玩家实际收到的结果

`feedbackRules.channels` 按作品命名，每个通道声明取证来源 `source`、按情境索引的 `expected` 和允许响应的 `maxDelayMs`。持续状态可加 `holdMs`，数值测量可加绝对误差 `tolerance`。预期和实测值使用文本、数值或布尔值。一个核心动作可以同时有听觉和视觉通道，工具只核对声明了该动作情境的通道。每个情境至少实际触发一次，总样本达到项目的 `minAcceptedActions`。

例如辨音作品可以声明下列通道。两次输入都亮起按钮时，真正决定答案的差异仍需从送入播放链路的信号独立取得。

```json
{"tone": {"source": "audio", "expected": {"first": 320, "second": 640},
          "tolerance": 8, "maxDelayMs": 180}}
```

项目的 `--scenario-script` 提供 `run(page, artifacts_dir)` 或 `run(page)`，从游戏正常处理的输入取得动作 ID、情境和时间。由另一处读取实际输出。棋盘可以读取合成像素或可见标记，叙事作品可以读取屏幕上的文本，辨音可以测播放信号的音高。取证使用同一单调时钟。即将替换持久状态时，先在约定停留时间后重新读取。保存原始观测，相关录音、画面或回放也可以作为体验审查证据。

```text
checks: [{id, status, evidence}]
feedback:
  actions: [{id: "turn-1", condition: "second", acceptedAtMs: 100}]
  observations: [{actionId: "turn-1", channel: "tone", source: "audio", atMs: 121, value: 636}]
stability:
  coldStarts: [{contextId, artifactSha256, readyMs, runtimeErrors, extraNetworkRequests}]
  warmedBaseline: {资源名: 数量}
  restarts: [{state: "playing", actionsBefore, actionsAfter, settledResources}]
  soak: {wallSeconds, activePlaySeconds, runtimeErrors, extraNetworkRequests, renderedFrames 或 acceptedActions}
  frameCapsTested: [60, 30, 15]
captures: [{id, path}]
```

从真实输入取得 `acceptedAtMs`，从实际呈现或播放取得 `atMs`。持续时间从第一次观测到正确结果起算。共享棋盘、文字或混音须在下一次会更新该通道的输入前完成取证。各动作拥有可独立测量且可重叠的输出时，可在该通道声明 `scope: "per-action"`，按动作 ID 分别追踪。已接受动作却没有对应输出、结果始终错误或响应超时会失败。缺少约定情境、停留后的复查或实际输入时保留未验证。

## 诊断、性能与评审

按 [diagnostics.js](../templates/diagnostics.js) 在 `?test=1` 下接入 `ready`、`fatal`、`setScene(id)`、`metrics()`、`audit()` 和项目的可观测状态。`metrics()` 给出实际场景 ID 和 `benchmarkLoad` 中各项的实测数量。持续渲染另给已呈现帧号、画质、内部尺寸和动态分辨率状态。WebGL 从上一次完整呈现读取全管线绘制和三角形计数。资源检查按声明的名称返回 `{checks: [{id, status, evidence}]}`。[资源辅助函数](../scripts/audit_resources.mjs) 可测几何、声音和确定性。

从干净上下文冷启动，每次安装 NetworkAudit。复玩一次真实输入，确认重开后恰好接受一次，并比较 `stabilityTargets.trackedResources` 声明的资源是否增长。用墙钟记录持续运行与实际游玩时间。持续渲染记录 `renderedFrames` 并测试所选帧节奏，按需更新记录 `acceptedActions`。使用特效池时可设置 `effectPoolReuseFactor`，记录容量和复用动作数。模板的默认时长为 300 秒，其中 60 秒实际游玩。

持续渲染在固定画质、代表负载和真实设备上预热采样，保留平均帧率与 p50/p95/p99。按需作品在代表场面检查负载，由动作观测给出每个通道的响应延迟。手机配置在桌面浏览器中模拟屏幕、像素比和触摸，报告记录实测环境。在实体手机上另行确认设备性能与手感。启动耗时属于报告所列的浏览器环境。

检查所有已声明的视觉维度及片段，在审查表填写观察和哈希。连续动作采用视频或至少三个不同关键帧，离散状态改变可用前后两个不同画面。亮度和熵保留作诊断。通过正常入口操作、观看或试听，并按[玩家体验闭环](experience-loop.md)核对最可能推翻判断的情境。最终报告绑定成品、证据和评审。零额外网络请求及体积检查见[离线规范](zero-network.md)。

## 近景与移动审查

打磨表面或运动画质时，在相应参考片段的 `acceptanceView` 里写下玩家看哪件物体、从哪里看、做什么动作。三维作品可在玩家能靠近的位置用侧光观察同一处划痕的颜色、凹凸和高光。固定视角或平面玩法用实际画面比例，观察棋子转动、棋盘滚动或状态切换时的轮廓和标记。

1. 固定种子、机位、光照、曝光、画质和输出尺寸，拍修改前后的同一细节。按需要切换底色、粗糙度或法线来定位错位，最后用合成画面验收。将可见差异写入视觉审查表对应场景的 `evidence`。
2. 用同一段玩家操作录下约五秒的连续画面。镜头固定时重放物体本身的运动或一次完整状态变化。回看细线是否闪烁、物体转动时磨损纹理是否在表面滑动、反光是否遮住状态标记，把观察到的时刻和画面写入对应的 `motionScenes`。可以复用已经录制的核心动作片段。
3. 改了渲染路径或效果时，在同一设备、浏览器、内部分辨率和代表负载下重放同一操作。持续渲染比较预热后的 p95 帧间隔，按需更新比较输入到可感知结果的延迟。记录两端的构建、毫秒数和样本数，静态环境探针等一次性开销另记冷启动。将对照数据随画面放入迭代记录的 `beforeEvidence` 和 `afterEvidence`。仅有软件渲染时，保留画面结论并将目标硬件耗时标为未验证。

## 已有项目

新项目使用第 4 版预算。第 2、3 版按原来的设备、逐帧反馈、画面评分、性能和证据字段验收。保留项目自己的预算即可复验旧成品。迁移时同步更新预算、场景驱动、观测和评审维度。需要追溯旧格式的逐发反馈时可查[港口试作案例](feedback-reliability.md)。
