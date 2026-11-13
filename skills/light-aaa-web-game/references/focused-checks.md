# 专项检查与场景直达

修一个具体问题时，先选一个能让问题暴露的起始状态，然后用正式输入、物理更新、渲染和混音走过那几秒。项目自己命名组、场景和判据。只为本作要打磨的体验建立用例。

| 专项 | 场景和刺激 | 可判断的结果和证据 |
| --- | --- | --- |
| 声音与空间 | 在信号将响、环境正在播放时开始。用正常手势解锁声音；以相同位置比较安静与繁忙混音、门内和门外，按需操作静音或暂停。 | 在音量、静音和效果处理之后采集实际送往主输出的声音，比较起音、尾音、左右/频段能量、是否被环境掩蔽。记录 WAV 或可回放混音片段，并试听。原始样本、音源名称和调用次数不能证明混音可听。 |
| 脚步 | 一小段能走过的材质边界。在同速度下跨过去，再停步；如果这款作品有跑步或跳跃，另选跑步、离地和重新着地的对照。 | 标记脚与地面的接触时刻，对照实际输出的起音、间距和音色。对两种地面各取多个脚步看差异是否大于同种地面的随机变化。停步或腾空时应停止新起音，允许已发声的尾音延续。用不看画面的回放检验可辨性。 |
| UI、HUD 与输入 | 直接进入长文案、数值换位、弹层或失败重试前的状态；按目标视口用真键盘、指针或触摸作选择。 | 检查控件与关键画面的实际边界、遮挡和点中目标，检查长文本裁剪、焦点顺序及关闭后首个输入是否到达正确对象。以可见文字、真实命中和交互后产生的界面变化取证，保存问题视口截图。 |
| 动作、接触与收势 | 恢复到着地、关门或棋子归位之前，让正式模拟越过接触点，再经历停稳或中断。 | 用实时短片或带时间的帧序列看接触前、接触、变化与停稳，并对齐声画。对照速度、位移和姿态突变可发现硬切，最终姿势单帧无法判断运动连续性。 |
| 材质、痕迹与渲染 | 在两种表面前施加相同交互；在效果消散后移动视角和距离，再回看该处。 | 在游玩尺度下比较残留形状、边缘、受光及是否附着；固定种子和曝光重放移动路线，观察闪烁和锯齿。聚焦受影响区域，留一张完整画面判断大小和遮挡。 |
| 关卡与规则 | 恢复到分岔、关键选择或已保存的中间局面，分别执行两种合法选择。 | 对照玩家当时可见的线索与之后的实际结果。测试第一次发现入口、教学顺序或存档恢复时，另走真实上游入口。 |

## 约定可复现的起点

在游戏内注册固定名称的测试场景，复用[诊断模板](../templates/diagnostics.js)的 `setScene(id)`。它准备的是事件发生**前**的世界状态。选择器恢复种子、角色与相机、必要的 UI/声音状态，清除残留按键、特效和计时，等已能接收输入才完成。接触、出声、结算、像素和菜单切换都交给正式代码。驱动另外读一个能识别该场景的实际前置条件，例如角色脚下材质或当前可见的对话框。

手动打开 `game.html?test=1&scene=surface-walk&seed=4207&q=medium`，可分享或重放同一起点。普通 URL 走正常启动。模板只在显式测试开关下处理场景名，未注册名称应报错；选择器只恢复本地预设，用隔离的测试存档或内存状态。主循环的初始化就绪应独立于诊断接口，避免场景加载互相等待。旧成品已有 `setScene(id)` 且能从 `metrics().sceneId` 回读场景时，命令行会调用该接口。

## 配置与执行

在项目 `budgets.json` 增加需要的组。场景可以专供某个检查使用，无需列入整作截图库。以下名称是一个有声音和菜单的项目示例。

```json
{
  "focusedChecks": {
    "audio": [{"scene": "station-door", "checks": ["outside_inside_mix"]}],
    "footsteps": [{"scene": "surface-walk", "checks": ["surface_change", "stops_on_rest"]}],
    "ui": [{"scene": "pause-long-label", "checks": ["resume_reachable", "focus_restored"]}]
  }
}
```

同一个项目驱动保留整作的 `run(page, artifacts_dir)`，另实现 `run_focused(page, focus, scene, artifacts_dir)`。专项命令只调用后者。每组每场景用独立浏览器上下文，新开时已处于指定起点。一个用例需要连续跨区时，在同一场景内移动。脚本可以给明显不成立的前置条件报错。

```python
# 一个 UI 用例中的一项读数；选择器、名称与预期由游戏决定。
resume = page.get_by_role('button', name='继续')
resume.click()  # Playwright 检查可见、稳定且能收到点击，再走正式处理器
focused = page.evaluate('document.activeElement?.id')
page.screenshot(path=str(artifacts_dir / 'resumed.png'))
return {
    'observations': {'focus_restored': {'actual': focused, 'expected': 'playfield'}},
    'captures': ['resumed.png']
}
```

为每个已声明的检查返回独立读到的 `actual` 与事先约定的 `expected`，默认精确比较。数值上下限用 `"op": "gte"` 或 `"op": "lte"`。在读数中保留单位、原始样本或取样时间，若还缺设备或试听就写 `actual: None` 和原因。保存 WAV、PNG、视频等证据时把当前用例目录内的文件名列入 `captures`。代码测得的音色或边界差异与实际试听、观看的评价分别记录。

Web Audio 项目可令 `__GAME_TEST__.audioOutput()` 返回音量、静音与效果处理后的实际输出节点。解锁后用 [scene_probes.py](../scripts/scene_probes.py) 的 `with record_mix(page, artifacts_dir / 'walk.wav'):` 包住正常走路线与留尾音的时间。采集器逐声道读取实际 PCM，包括静音时段，保存短 WAV。测声画同步时另外对齐游戏时钟与音频时钟。扬声器、系统音量与设备实际延迟需单独试听。UI 驱动可先用 `hit_target(locator)` 读取当前视口中的控件边界和中心点命中对象，再用真点击或键盘核对操作结果。两个函数均可以直接从 `scene_probes` 导入。可运行的声音、脚步和 UI 驱动可查[专项回归样例](../scripts/self_test_scenes.py)。

```bash
python <skill-dir>/scripts/validate_game.py dist/game.html --budget budgets.json \
  --scenario-script tests/game_scenarios.py --focus footsteps --focus ui \
  --out artifacts/validation
```

工具回读实际场景 ID，并记录构建、驱动和预算哈希、用例查询参数、当前证据哈希、每项预期与实测。命令输出本次报告的路径，每次运行都有独立报告和原始证据。同一输出目录的最近一次报告也可在 `artifacts/validation/focused/focused-report.json` 查看。测值不符返回 2，缺少约定的读数返回 3，所选检查全过返回 0。最终交付按[整作验证](validation.md)另测从入口开始的完整流程。
