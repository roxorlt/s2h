[English](#english) | [中文](#中文)

---

<a id="english"></a>

# s2h — Skill to HTML

Decompose any [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill into an interactive HTML explainer page.

**What it does**: Give s2h a SKILL.md file (local path, GitHub URL, or skills.sh link), and it produces a single-file HTML page that breaks down the skill's workflow, architecture, and security profile — readable by anyone, no prior context needed.

## Quick start

```bash
# Install
curl -fsSL https://raw.githubusercontent.com/roxorlt/s2h/main/install.sh | bash

# Run inside Claude Code
/s2h ~/.claude/skills/some-skill/SKILL.md
/s2h https://github.com/user/repo/blob/main/SKILL.md
```

## What you get

A self-contained HTML file with four sections:

| Section | What it answers |
|---------|----------------|
| **Overview** | What does this skill do? (one-liner + stats + flow diagram) |
| **Walkthrough** | How does it work? (step-by-step, filtered for reader relevance) |
| **Security Scan** | Is it safe to use? (risk level + findings + toxic flow analysis) |
| **Context** | What else is related? (companion files, upstream/downstream skills) |

## Options

```
/s2h <source> [options]

source:
  local path     ~/.claude/skills/gstack/office-hours/SKILL.md
  GitHub URL     https://github.com/user/repo/blob/main/skills/X/SKILL.md
  skills.sh      skills.sh/some-skill

options:
  --lang <code>    Output language (zh/en/ja/ko/fr/es/de/pt), auto-detected by default
  --output <path>  HTML output path, default /tmp/s2h-{name}-{timestamp}.html
  --no-security    Skip security scan (faster, not recommended)
  --version        Show version
  --help           Show help
```

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (this is a Claude Code skill)
- Python 3 (for the deterministic parser)
- Internet connection (for GitHub/skills.sh sources and Mermaid CDN)

## Example

**office-hours** — a 1717-line skill with 6 phases, branching flows, and 34 external resources:

| Source | Result |
|--------|--------|
| [SKILL.md](https://github.com/garryslist/gstack/blob/main/office-hours/SKILL.md) | [Live demo](https://roxorlt.github.io/s2h/office-hours.html) |

## License

[MIT](LICENSE)

---

<a id="中文"></a>

# s2h — 把 Skill 拆成网页

把任意 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill 拆解为一张交互式 HTML 页面，看完就懂这个 skill 怎么运转。

**干什么用的**：丢一个 SKILL.md 进来（本地路径、GitHub 链接、skills.sh 地址都行），s2h 帮你生成一份独立的 HTML，把 skill 的工作流、架构和安全状况讲清楚，不需要任何前置知识就能看懂。

## 快速上手

```bash
# 安装
curl -fsSL https://raw.githubusercontent.com/roxorlt/s2h/main/install.sh | bash

# 在 Claude Code 里运行
/s2h ~/.claude/skills/some-skill/SKILL.md
/s2h https://github.com/user/repo/blob/main/SKILL.md
```

## 产出什么

一个自包含的 HTML 文件，分四个板块：

| 板块 | 回答什么问题 |
|------|-------------|
| **概览** | 这个 skill 做什么？（一句话定位 + 关键数据 + 流程图） |
| **逐步拆解** | 怎么运转的？（按步骤讲，只保留读者需要知道的内容） |
| **安全扫描** | 用着放心吗？（风险等级 + 发现项 + 毒性数据流分析） |
| **相关信息** | 还有什么关联的？（配套文件、上下游 skill） |

## 参数

```
/s2h <来源> [选项]

来源：
  本地路径     ~/.claude/skills/gstack/office-hours/SKILL.md
  GitHub 链接  https://github.com/user/repo/blob/main/skills/X/SKILL.md
  skills.sh    skills.sh/some-skill

选项：
  --lang <代码>    输出语言（zh/en/ja/ko/fr/es/de/pt），默认自动检测
  --output <路径>  HTML 输出路径，默认 /tmp/s2h-{名称}-{时间戳}.html
  --no-security    跳过安全扫描（更快，但不推荐）
  --version        查看版本号
  --help           查看帮助
```

## 依赖

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)（这是一个 Claude Code skill）
- Python 3（跑确定性解析器）
- 网络连接（获取 GitHub/skills.sh 来源文件，加载 Mermaid CDN）

## 示例

**office-hours** — 1717 行、6 个阶段、带分支流程和 34 个外部资源的复杂 skill：

| 输入 | 产出 |
|------|------|
| [SKILL.md 原文](https://github.com/garryslist/gstack/blob/main/office-hours/SKILL.md) | [在线查看拆解结果](https://roxorlt.github.io/s2h/office-hours.html) |

## 协议

[MIT](LICENSE)
