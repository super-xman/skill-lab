# 验证规范

## 通过的含义

最终通过 = 成品完整性 + 实际渲染 + 生成资源审计 + 真实玩法流程 + 指定硬件性能 + 已查看的视觉证据。任何缺项标记 `unverified`。自动脚本只能证实其测得的范围，不能自动认证“3A”。

`validate_game.py` 退出码：0=自动检查全部通过（视觉仍待审），2=有失败，3=存在未验证项。`finalize_review.py` 返回 0 才表示这份证据的完整验收通过。脚本报错、超时或缺少依赖不得写成通过。

## 可重复测试入口

只在 `?test=1&seed=4207&q=medium` 下暴露 `window.__GAME_TEST__`，见模板：

- `ready`：必要资源已生成、核心 shader 可用，玩家可操作；不能只表示 DOM 加载。
- `fatal`：启动失败原因或 null。
- `setScene(id)`：选择约定视角并重置确定性状态。默认 overview/materials/combat/interior；固定种子、质量、内部尺寸、模拟时刻、曝光收敛、敌人和粒子负载。正式基准时不能冻结渲染或只显示背景。
- `metrics()`：返回上一完整帧的只读指标，字段见模板；不要同步读 GPU 像素。`frame` 必须随真正提交的帧递增；`dynamicResolution=false` 才可作固定画质性能验收。
- `audit()`：独立检查生成物，返回 `checks` 数组。每项必须有 id、status、具体 evidence。
- `snapshot()`：提供可用于真实操作前后对比的只读状态。

测试工具不能直接改成胜利再声称通关。测试夹具可以定位玩家、构建确定性敌人场景，但命中、伤害、目标和胜负必须经实际游戏路径执行。

## 五项生成资源审计

`audit()` 必须覆盖以下固定 id；不存在某种资源时说明项目设计以及检查替代物，不得仅填 `passed`：

1. `geometry`：扫描实际生成几何的 position/normal/index，检查有限值、索引越界、退化三角形比例、法线长度、包围盒尺度及地面接触。记录扫描对象/顶点数量与异常数量；抽样时写明覆盖率。
2. `materials`：记录每套贴图尺寸、格式、颜色空间与估算字节；检查采样范围/NaN/无效法线。对约定平铺资源测相对内部差异的边界跳变；ORM 通道语义需正确。图集的 mip 串色还需近远景图检查。允许在测试模式一次性离屏 readback，不得把此耗时混入运行性能样本。
3. `audio`：生成所有必需音频，检查有限值、峰值 ≤ 1、预期有声段 RMS 不接近零、首尾包络、采样数/时长和总字节。峰值正常不证明音色合适；仍需播放或试听代表样本。
4. `determinism`：相同种子及参数生成两遍，对实际几何/CPU 纹理/音频数据摘要进行比较；改变种子验证期望变化。GPU 浮点结果跨设备用容差与结构指标，不要求跨 GPU 逐像素相同。动态特效检查固定模拟时刻。
5. `navigation`：出生点、任务点、撤离点、敌人生成点位于有效区域，必经路径可达；角色半径能通过窄门，不允许导航穿越碰撞墙。记录实际测试路径及失败点。

这些审计需针对项目实现。模板没有预先写出虚假的成功结果。可扩展更多检查，但不要漏掉五项。

`scripts/audit_resources.mjs` 提供实际 BufferGeometry 全顶点/索引扫描、AudioBuffer 峰值/RMS/有限值检查，以及实际 TypedArray 的重复生成 SHA-256 比较。它不检查世界空间物体接触，不理解材质语义，也不证明音色好听；需用项目检查和截图/试听补足。传入所有必需资产，不能只挑一个正常对象。

## 真实玩法测试

创建项目级 Python 文件并传入 `--scenario-script`。接口：

```python
def run(page):
    # 用 page.keyboard / page.mouse / page.get_by_role 等执行真实操作。
    # 独立比较 snapshot() 观测结果，不是调用返回常量的“自测通过”。
    before = page.evaluate('window.__GAME_TEST__.snapshot()')
    page.keyboard.down('w')
    page.wait_for_timeout(500)
    page.keyboard.up('w')
    after = page.evaluate('window.__GAME_TEST__.snapshot()')
    # …测试墙体、攻击、任务、胜负等；这里不提供伪造的断言。
    return {'checks': [
        # {'id': 'movement_collision', 'status': 'passed',
        #  'evidence': {'before': ..., 'after': ..., 'wallBoundary': ...}}
    ]}
```

必测 id：

| id | 要验证的事实 |
|---|---|
| movement_collision | 走/转向/跳跃按设计工作，墙体不能穿透，重力不把角色卡死 |
| primary_action_hit_and_occlusion | 攻击有消耗与命中反馈，遮挡阻止伤害；非射击游戏定义同等核心动作 |
| enemy_response | 检测、移动、攻击、受击、死亡状态真实改变 |
| objective_progression | 目标按规则完成，不可跳过，进度 UI 同步 |
| win_and_restart | 从实际最后一步进入胜利，重开清空状态 |
| loss_and_restart | 经实际伤害进入失败，重开恢复控制 |
| pause_resume | 暂停期间模拟停止，恢复不跳时、不粘键 |
| audio_unlock_and_feedback | 用户手势解锁 AudioContext，实际事件触发相应声音 |
| quality_fallback | 低画质和关闭重效果仍可玩，分辨率变化不破坏 UI/准星 |

加测鼠标锁定与释放、触屏（在范围内时）、resize、失焦、连续重开 5 次的对象/内存增长。机械化 smoke test 不替代完整试玩。非 FPS 项目可以在计划阶段显式改写 requiredGameplayChecks，但必须覆盖同等完整闭环。

当前验收标准将以下项目列为必测，不能只用上表九项宣称完整通过：

| id | 额外验收事实 |
|---|---|
| primary_action_visual_feedback | 真实开火后的枪口焰/弹道/命中反馈在最终画面可见；区别已提交与可见 |
| sustained_fire_and_pool_reuse | 长按/松开、空弹与换弹正确；超过特效池容量 3 倍后无反馈丢失或旧状态 |
| input_lifecycle | 鼠标锁定、Esc、失焦、恢复、resize 不粘键、不继续自动射击 |
| restart_stress | 连续 5 次重开后第一枪可用；任务、音频、输入、资源计数正常 |
| cold_start_repetition | 3 个独立干净上下文使用同一 HTML，均能开始且零额外网络请求 |
| sustained_play | 至少 300 秒真实墙钟时间运行，其中至少 60 秒移动/战斗，无错误和资源持续增长 |

旧项目只返回九项时，其旧检查仍有效，新检查保留未验证。不要补常量 passed。

`run(page, artifacts_dir)` 可额外返回 feedback、stability、captures，见 [反馈规范](feedback-reliability.md)。反馈审计由原始事件/主画面提交记录计算，不接受游戏直接返回“反馈全部可见”。stability 的原始字段如下（数字都须实测；示意不代表结果）：

```text
coldStarts: [{contextId, artifactSha256, readyFrame, runtimeErrors, extraNetworkRequests}]
warmedBaseline: {geometries, textures, materials, audioNodes, listeners, activeEffects}
restarts: [{state, shotsBefore, shotsAfter, settledResources:{...同 baseline}}]
soak: {wallSeconds, combatSeconds, renderedFrames, runtimeErrors, extraNetworkRequests}
frameCapsTested: [真实执行过的帧节奏]
effectPoolCapacity: 实际容量
poolReuseAcceptedShots: 实际连续复用测试中的有效开火数
```

冷启动由测试驱动创建新浏览器上下文，每个都安装 NetworkAudit；contextId 由驱动分配，不能由游戏自报三个字符串。持续测试时间由驱动用单调墙钟记录，不能拿被钳制/加速的 simTime 代替。资源在完成预热和瞬态效果退出后计数，所有重开都与同一基线比较。JS 堆受 GC 影响只能辅助观察，不用一次堆快照判泄漏；material/listener/audio 的数量需要实际注册表。

用户体验评审使用正常入口和自然任务路径。测试夹具、传送和无敌只能用于定位问题，不能证明首次引导和完整流程体验。按 [体验闭环](experience-loop.md) 保留问题、假设、前后证据、回归和下一轮建议。

## 自动浏览器验证

验证器启动隔离的本地 HTTP 服务和浏览器上下文，拦截除入口 HTML 外的网络请求，禁用 service worker。记录所有尝试；网络请求被阻断但程序凑巧仍显示画面，也不能称自包含通过。

使用系统 Chromium 可传 `--browser`。`--software` 显式启用 SwiftShader，仅用于诊断。`--adapter reference` 支持本次附件的 `__G/__ready/__fatal` 接口；其只验证启动、截图、网络、静态体积，不假装拥有完整玩法与审计覆盖。

截图的标准差、亮度范围、黑白像素比例仅辅助发现空白/曝光问题。纯色截图判失败；亮度或熵正常不代表美术达标。

采样先切到 benchmarkScene，预热，再以 requestAnimationFrame 的真实间隔采样。报告平均、p50/p95/p99、样本数量，记录 GPU、浏览器、输出/内部尺寸、质量、敌人/特效负载。rAF 是浏览器端到端节奏，不是纯 GPU 执行时间；需要定位 GPU 瓶颈时另用 timer query，并处理 disjoint。

没有真实 GPU、缺少负载标识、动态分辨率未固定、未切到基准场景或样本不足，不得宣称达到指定画质帧率。只在背景菜单跑到 60 FPS 无效。CPU 软件光栅化结果不能外推用户电脑性能。

默认战斗负载下限为 3 个敌人、1 个活动特效，内部宽高至少达到输出的 80%，真实渲染帧增量至少为采样 rAF 数量的 90%。可在立项时按游戏类型调整这些预算并记录原因。GPU 标识无法识别时也保留未验证，不能仅凭 WebGL 上下文存在就认定硬件加速。

默认预算是一次桌面配置。交付支持更多平台时，对每个平台保留独立配置、报告和截图。正式交付要求至少 3 次独立冷启动、一个 60 秒移动/战斗过程、一个 5 分钟持续运行；默认 10 秒性能采样用于迭代，不能代替稳定性测试。软件 GPU 不免除逻辑/反馈/网络检查，但真实硬件性能缺测始终保持未验证。

## 视觉审查

打开全部必需视角的实际截图，记录文件哈希。评价每个视角的五维分数，1=明显失败、2=多处问题、3=基本可用但粗糙、4=符合约定目标、5=超过目标。默认每维至少 4；不得平均掉某一维的明显失败。

- composition：层次、尺度、焦点、轮廓，是否符合 art-direction。
- materials：金属/油漆/橡胶可区分，近景精度、湿润梯度、平铺与接缝。
- lighting：曝光、阴影、反射、冷暖与暗部层次；无大面积非设计性过曝/死黑。
- readability：敌人/目标/路径/HUD 在运动、逆光、特效中可辨。
- artifactFree：无明显穿插、浮空、z-fighting、错法线、反射错位、字形缺失。

危及可玩性、黑屏、明显生成错误等写入 criticalDefects，存在即不通过。每个视角需具体描述看到的证据，例如“枪身与橡胶握把高光宽度有明显区别”，不能只写“很真实”。静态截图不能证明动画稳定或手感，另以玩法测试和视频/试玩检查。

在相同相机/种子/时间下做消融对比；要求 reference 的构图、光照与材质特征吻合，而不是盲目像素相似。用户参考是不同题材时，用视觉原则而不复制所有港口元素。

## 证据闭环

报告绑定成品 SHA-256，视觉审查绑定报告与截图 SHA-256。最终器同时复核磁盘上成品与截图未改变。任何实质改动后重跑受影响检查；不能拿旧截图验收新 HTML。

最终器只是检查审查完整性和阈值，不能证明审查者诚实或自动理解图片。始终实际查看图片。最终文件 `final-review.json` 与源报告分开，保留原始证据。

最终器还要求四类动态画面的实际审查，以及首次进入、动作清晰、导航、恢复、舒适五类体验观察。`visual-review.json` 的 experience 段记录评审来源、正常入口试玩、具体观察及文件哈希；将 `iteration-log.json` 的全部已知问题（包括未关闭项）复制到 experience.issues，不得只挑已解决问题。P0/P1 未关闭直接失败；关闭问题必须绑定当前构建、修改前/后和回归证据。缺少过程证据就不能完成闭环。
