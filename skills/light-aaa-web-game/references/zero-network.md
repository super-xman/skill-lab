# 一个 HTML，运行时零额外请求

## 硬边界

交付游戏只有 `game.html` 一个必要文件。HTTP 首次获取入口文档允许 1 次；此后启动、菜单、开火、换弹、死亡、重开、画质切换、任务完成和持续运行期间，额外网络请求必须为 0。独立 file:// 运行应没有 HTTP(S) 请求，但必须实测浏览器是否允许打开。

同源请求也算请求，404/被拦截/缓存命中仍暴露依赖或尝试。不能允许后再忽略“无关埋点”；不能靠 Service Worker、localStorage 资源缓存、先在线加载再断网或浏览器已有字体包掩盖缺失资源。

开发 npm 安装与测试工具的通讯不属于游戏运行流量。系统字体不触发下载。data:、本地 Blob、程序生成纹理/几何/声音可以使用；它们内部代码继续发请求则失败。base64 不保证小体积，优先生成规则。

## 构建约束

- 内联 Three.js/其他必要库、JS/CSS、shader、Worker/WASM 字节；不要复制参考游戏的私有实现。保留许可证。
- 不保留动态 chunk、远程 `import()`、CSS `@import`、字体 URL、贴图/音频 URL、sourceMappingURL、manifest、预加载/预连接提示、广告和分析代码。
- 使用 `<link rel="icon" href="data:,">`，避免浏览器自动请求 favicon。响应式使用内联样式，不依赖另一套图片文件。
- 构建器用替换回调插入 JS，避免 `$&` 等替换字符串语义损坏代码。对最终 HTML 中实际嵌入的脚本做语法检查并打开成品；不能只测试开发服务器。
- 目录里的源码、Skill、测试证据不属于成品运行依赖，单独打包，不能通过旁边的文件补齐游戏。

可在 HTML 开头加 CSP 作为纵深防护，按实际自包含资源验证后使用：

```html
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' blob:; style-src 'unsafe-inline'; img-src data: blob:; media-src data: blob:; font-src data:; connect-src 'none'; worker-src blob:; base-uri 'none'; form-action 'none'">
<link rel="icon" href="data:,">
```

CSP 不是零请求证据：代码尝试请求但被 CSP 拦住，验收仍失败。若某 API/本地资源需要调整策略，只能放行必要的本地类型，不能直接加 `https:` 或 `*`。

## 验证过程

1. 只把最终 HTML 放入干净目录。静态扫描资源引用、CSS、SVG、link 提示；静态扫描无法穷尽动态 JavaScript。
2. 新浏览器上下文、空存储、禁用缓存、禁止 Service Worker。网络审计只放行主 frame 的第一次精确入口请求，同 URL 子 frame 和再次获取也不豁免。
3. 从 context 捕获请求（含新窗口/Worker），额外使用 Chromium CDP 捕获 favicon 等；拦截 HTTP、WebSocket，记录 fetch/XHR/sendBeacon/EventSource/Worker/SW/WebTransport/WebRTC 的尝试。缺少必要拦截能力标为未验证。
4. 审计贯穿真实交互和持续测试。冷启动的三个上下文各安装 `NetworkAudit`，不能只监控第一个。后台 worker 中的请求通过 context 网络事件检查。
5. 在全部非入口请求被阻断的状态完成玩法。即使画面正常，只要发现一次额外尝试仍失败。零请求观测仅对已覆盖路径成立，报告要列出未覆盖路径。

`network_audit.py` 与验证器默认集成；报告包括 requests、blockedRequests、apiAttempts、websockets 和 CDP 额外记录。重复记录用于定位来源，不代表多次实际传输。不能把拦截器当作对恶意代码的完备网络沙箱；它是对本项目代码的测试工具。

托管站点可能带 ChatGPT 登录、平台外壳或注入脚本。独立 HTML 的零请求结论不能直接推广到整个托管页面。若用户要求线上地址也零额外请求，必须审计该地址；外壳产生额外请求就如实判不满足，另提供独立 HTML。
