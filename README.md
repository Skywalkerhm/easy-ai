# Easy AI Shell
## 轻量级本地 AI 终端代理框架（Lite 版）| Zero-Dependency Terminal AI Agent

> 🔥 **注意**：当前开源版本为 **Lite 轻量版**，仅包含核心功能。完整版将包含更多企业级特性（如高级插件、多模态支持等），敬请期待！

> 🔥 **Note**: This is the **Lite version** with core features only. The full version with more enterprise features (advanced plugins, multimodal support, etc.) is coming soon!

[![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green?logo=apache)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/Zero-Dependencies-orange)]()
[![ReAct Agent](https://img.shields.io/badge/ReAct-Agent-purple)]()
[![Workspace Sandbox](https://img.shields.io/badge/Workspace-Sandbox-red)]()

> 马上有 AI 团队出品 | 一个**零依赖、拷贝即用**的本地 AI 终端代理，让 AI 真正帮你干活而不是只给一段代码。

> A **zero-dependency, copy-and-run** local AI terminal agent that actually gets work done, not just gives you code.

**搜索关键词**：AI CLI、terminal AI、local AI agent、ReAct Agent、上下文压缩、session compactor、AI 终端代理、workspace sandbox、Lite 轻量版

**Keywords**: AI CLI, terminal AI, local AI agent, ReAct Agent, context compression, session compactor, AI terminal agent, workspace sandbox, Lite version

---

## 🎯 解决什么问题？ | What Problems Does It Solve?

| 场景 / Scenario | 传统 AI 代理 / Traditional AI Agent | Easy AI Shell |
|------|-------------|---------------|
| 你说"帮我重构这个模块" | 给一段代码就没了 | 多步执行直到真正完成 |
| You say "refactor this module" | Gives you code and stops | Executes multi-step until truly done |
| 部署环境 | 要装七八个依赖 | 下载一个文件就能跑 |
| Deployment | Needs 7-8 dependencies | Run with just one file |
| 安全担忧 | 权限过大不知道它干了什么 | 三级权限规则 + 交互式授权 |
| Security concerns | Too much permission, unaware of actions | Three-level permissions + interactive auth |
| 上下文越来越长 | token 成本爆炸，响应变慢 | 自动压缩历史，省 token |
| Growing context | Token costs explode, slower responses | Auto-compress history, save tokens |
| 每次都要解释背景 | 重复说明很麻烦 | AutoReview 记住你的习惯 |
| Explaining context every time | Repetitive and tedious | AutoReview remembers your habits |

---

## ✨ 核心特性 | Core Features

### 🪶 轻量如羽 · 零依赖 | Light as a Feather · Zero Dependencies

【中文】
- 仅依赖 Python 标准库
- HTTP 请求用原生 `urllib` 实现
- **下载一个 `.py` 文件就能跑**，无需 `pip install`，无需虚拟环境
- 适合追求轻量化的开发者

【English】
- Only depends on Python standard library
- HTTP requests implemented with native `urllib`
- **Run with just one .py file**, no `pip install`, no virtual environment
- Perfect for developers who value lightweight tools

---

### 🔒 安全放心 · Workspace 沙盒 | Secure · Workspace Sandbox

【中文】
- `allow / deny / ask` 三级权限规则
- 删除、sudo、ssh 等敏感操作必须经你确认
- 越界访问自动触发交互式授权
- **访问范围限定在 workspace 内**，保护你的代码和数据

【English】
- `allow / deny / ask` three-level permission rules
- Sensitive operations (delete, sudo, ssh) require your confirmation
- Out-of-bounds access triggers interactive authorization
- **Access limited to workspace**, protecting your code and data

---

### 🔁 智能执行 · 不只是回复一次 | Intelligent Execution · More Than Just a Reply

【中文】
- 采用业界领先的 **ReAct（Reasoning + Acting）**模式
- 理解意图 → 调用工具 → 观察结果 → 迭代优化
- **多步执行直到任务真正完成**，不是只给一段代码

【English】
- Uses industry-leading **ReAct (Reasoning + Acting)** pattern
- Understand intent → Call tools → Observe results → Iterate and optimize
- **Multi-step execution until task is truly complete**, not just a code snippet

---

### 🧠 本地记忆 · 越用越懂你 | Local Memory · Gets Better Over Time

【中文】
- AutoReview 机制自动整理使用习惯
- 沉淀至本地 `.easy_ai/memory/`
- **下次使用无需重复说明背景**，越用越顺手

【English】
- AutoReview mechanism automatically organizes usage habits
- Stored locally in `.easy_ai/memory/`
- **No need to repeat context next time**, gets more convenient with use

---

### 💰 省 token · 拒绝上下文膨胀 | Save Tokens · No Context Bloat

【中文】
- 内置 **上下文裁剪 + SessionCompactor**
- 对话过长时自动压缩历史，只保留关键信息
- **成本更低、响应更快、稳定性更强**

【English】
- Built-in **context trimming + SessionCompactor**
- Auto-compresses history when conversation gets too long, keeping only key info
- **Lower costs, faster responses, better stability**

---

### 🤖 多机器人协同 · 一台电脑跑多个助手 | Multi-Agent Collaboration

【中文】
- **一台电脑可以同时运行多个 AI 机器人**，每个机器人可以有不同的角色和技能
- 机器人之间可以**相互协作**：一个负责写代码，一个负责 Code Review，一个负责测试
- 每个机器人有独立的记忆和工作区，互不干扰，按需调用
- 适合复杂任务拆分，让专业的人做专业的事

【English】
- **Run multiple AI agents simultaneously on one computer**, each with different roles and skills
- Agents can **collaborate with each other**: one writes code, one does Code Review, one handles testing
- Each agent has independent memory and workspace, operating independently and calling on each other as needed
- Perfect for complex task decomposition — let specialists handle specialist work

---

## 🚀 安装与运行 | Installation & Usage

```bash
# 克隆后直接运行
# Run directly after cloning
python easy_ai_shell.py
```

指定工作区（推荐）：
```bash
# Specify workspace (recommended)
python easy_ai_shell.py -w /your/project
```

单次执行：
```bash
# Single execution
python easy_ai_shell.py -p "帮我解释这段代码"
python easy_ai_shell.py -p "explain this code for me"
```

---

## ⚙️ 配置 | Configuration

1. 复制配置示例 / Copy config example:
```bash
copy config.example.json config.json
```

2. 修改 `config.json` / Modify `config.json`:
```json
{
  "llm": {
    "provider": "ark",
    "model": "your-model",
    "base_url": "https://ark.cn-east-1.volces.com/api/v3",
    "api_key": "your-api-key"
  },
  "memory": {
    "autoReviewEnabled": true
  }
}
```

> 支持 **Ark / DashScope / MiniMax** 等 OpenAI-Compatible 接口
> Supports **Ark / DashScope / MiniMax** and other OpenAI-Compatible interfaces

---

## 🏗️ 架构与模块 | Architecture & Modules

| 模块 / Module | 功能 / Function | 亮点 / Highlights |
|------|------|------|
| PermissionSystem | 权限规则引擎 / Permission engine | allow/deny/ask + 交互式授权 / interactive auth |
| Workspace Sandbox | 工作区沙盒 / Workspace sandbox | 越界访问自动触发授权 / Auto-trigger auth for out-of-bounds |
| AgentLoop | ReAct 执行循环 / ReAct loop | 多步迭代直到完成 / Multi-step iteration until done |
| QueryEngine | 智能路由 / Smart routing | 命令/工具/AI 自动路由 / Auto-route commands/tools/AI |
| SessionCompactor | 会话压缩 / Session compression | 省 token、降低上下文长度 / Save tokens, reduce context |
| AutoReview | 记忆整理 / Memory organization | 越用越懂你 / Gets better with use |
| MCP Client | 外部工具集成 / External tools | 支持 MCP 协议 / Supports MCP protocol |

---

## 📖 关键命令 | Key Commands

- `workspace <dir>` - 设置沙盒根目录 / Set sandbox root directory
- `memory list` / `memory show <name>` - 查看本地记忆 / View local memory
- `autoreview` - 触发记忆整理 / Trigger memory organization
- `permissions` - 查看/设置权限模式 / View/set permission mode

---

## 🛡️ 安全模型 | Security Model

【中文】
- 权限等级：`read-only` < `workspace-write` < `danger-full-access` < `prompt` < `allow`
- 默认模式：`workspace-write`
- 敏感操作（`rm -rf`、`sudo`、`ssh`）可通过规则拒绝或强制确认

【English】
- Permission levels: `read-only` < `workspace-write` < `danger-full-access` < `prompt` < `allow`
- Default mode: `workspace-write`
- Sensitive operations (`rm -rf`, `sudo`, `ssh`) can be denied or require forced confirmation

---

## 📋 使用场景 | Use Cases

- **开发者 / Developers**：本地代码调试、重构、单元测试生成 / Local code debugging, refactoring, unit test generation
- **运维 / DevOps**：批量文件操作、日志分析、自动化脚本 / Batch file operations, log analysis, automation scripts
- **数据分析 / Data Analysis**：数据清洗、转换、报表生成 / Data cleaning, transformation, report generation
- **团队协作 / Team Collaboration**：共享工作流、团队记忆、代码审查 / Shared workflows, team memory, code review
- **多机器人协同 / Multi-Agent Workflow**：一个写代码，一个做 Code Review，一个跑测试 / One writes code, one reviews, one tests

---

## 📄 License

【中文】
基于 **Apache 2.0 + 自定义额外条款**（见 [LICENSE](LICENSE)）：
- 个人/企业内部使用：免费
- 多租户 SaaS / 白标化：需商业授权

【English】
Based on **Apache 2.0 with additional terms** (see [LICENSE](LICENSE)):
- Personal/internal business use: Free
- Multi-tenant SaaS / White-labeling: Commercial license required

---

<div align="center">

**如果对你有帮助，欢迎 ⭐ Star 支持！**
**If you find this helpful, please ⭐ Star us!**

</div>
