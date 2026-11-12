# skill-lab

用于沉淀、验证和迭代 AI Agent Skills 的技能库。

每个 skill 单独放在 `skills/<skill-name>/` 中，包含 `SKILL.md`、参考资料、模板以及必要的脚本。复制完整目录即可保留引用关系，方便在不同项目中复用。

## 当前收录

| Skill | 版本 | 用途 |
| --- | --- | --- |
| [light-aaa-web-game](skills/light-aaa-web-game/) | 1 | 按玩法生成轻量高画质 Web 游戏，使用程序化资产、单 HTML 和零额外网络请求，按核心操作和真实场景验收。 |

## 安装与使用

先克隆本仓库：

```bash
git clone https://github.com/super-xman/skill-lab.git
cd skill-lab
```

将需要的 **完整 skill 目录** 复制到目标项目的技能目录。以下路径是示例，具体以客户端配置为准。

Codex 项目级安装：

```bash
mkdir -p /path/to/project/.agents/skills
cp -R skills/light-aaa-web-game /path/to/project/.agents/skills/
```

Claude Code 项目级安装：

```bash
mkdir -p /path/to/project/.claude/skills
cp -R skills/light-aaa-web-game /path/to/project/.claude/skills/
```

重新加载客户端的技能后，明确调用 skill，例如：

> 使用 light-aaa-web-game，制作一款海岛滑翔竞速游戏，玩家穿过风门完成计时，并能再次挑战。严格遵循 skill 的设计、实现、体验迭代和验收流程，交付单 HTML、源码与验收报告，并如实标注未验证项。

## 验证

当前 skill 的验证器要求 Python 3.10+；资源审计自测使用 Node.js 20+。

```bash
cd skills/light-aaa-web-game
python -m pip install -r scripts/requirements.txt
python scripts/self_test.py
python scripts/self_test_v2.py
node scripts/self_test_resources.mjs
```

浏览器网络反例与游戏验收方法见 [skill 使用说明](skills/light-aaa-web-game/README.md)。验证器自身测试通过不代表生成的游戏已经通过画质或性能验收。

## 添加其他 skill

1. 新建 `skills/<skill-name>/` 并提供 `SKILL.md`。
2. 明确适用场景、输入、执行流程、交付物和验收标准。
3. 将参考资料、模板和脚本随 skill 一起保存，使用相对路径引用。
4. 更新上方技能目录，并保留版本变更与实际验证记录。
