# Easy AI Shell
## 轻量级本地 AI 终端代理框架（Lite 版）| Zero-Dependency Terminal AI Agent

> 🔥 **注意**：当前开源版本为 **Lite 轻量版**，已集成仿生人类成长模式的AGI架构。完整版将包含更多企业级特性（如高级插件、多模态支持等），敬请期待！

> 🔥 **Note**: This is the **Lite version** with core features and integrated AGI Growth System based on biologically-inspired human growth model. The full version with more enterprise features (advanced plugins, multimodal support, etc.) is coming soon!

[![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green?logo=apache)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/Zero-Dependencies-orange)]()
[![ReAct Agent](https://img.shields.io/badge/ReAct-Agent-purple)]()
[![AGI Growth](https://img.shields.io/badge/AGI-Growth-blueviolet)]()
[![Workspace Sandbox](https://img.shields.io/badge/Workspace-Sandbox-red)]()

> 马上有人工智能团队出品 | 一个**零依赖、简约即美**的本地 AI 终端代理，具备仿生人类成长能力，让 AI 真正帮你干活而不是只给一段代码。

> A **zero-dependency, simple-is-beautiful** local AI terminal agent with biologically-inspired growth capabilities that actually gets work done, not just gives you code.

**搜索关键词**：AI CLI、terminal AI、local AI agent、ReAct Agent、上下文压缩、session compactor、AI 终端代理、workspace sandbox、Lite 轻量版、AGI成长、仿生人类成长

**Keywords**: AI CLI, terminal AI, local AI agent, ReAct Agent, context compression, session compactor, AI terminal agent, workspace sandbox, Lite version, AGI growth, biologically-inspired growth

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

### 🪶 简约之美 · 零依赖 | Simple is Beautiful · Zero Dependencies

【中文】
- 仅依赖 Python 标准库
- HTTP 请求用原生 `urllib` 实现
- **下载一个 `.py` 文件就能跑**，无需 `pip install`，无需虚拟环境
- **第一性原理**：保留调度需要的关键主体，简约即美
- 适合追求轻量化的开发者

【English】
- Only depends on Python standard library
- HTTP requests implemented with native `urllib`
- **Run with just one .py file**, no `pip install`, no virtual environment
- **First Principles**: Retain only the essential components for scheduling, simple is beautiful
- Perfect for developers who value lightweight tools

---

### 🔌 多厂商支持 · 智能切换 | Multi-Provider Support · Smart Switching

【中文】
- **11个主流 LLM Provider**：OpenAI、Anthropic、通义千问、DeepSeek、智谱清言等
- **自动故障转移**：API 失败时自动切换备用模型
- **智能错误分类**：区分限流、认证、上下文溢出等错误类型
- **统一接口**：一套代码支持所有 OpenAI-Compatible API

【English】
- **11 mainstream LLM Providers**: OpenAI, Anthropic, Qwen, DeepSeek, Zhipu, etc.
- **Automatic failover**: Switch to backup models when API fails
- **Smart error classification**: Distinguish rate limit, auth, context overflow errors
- **Unified interface**: One codebase supports all OpenAI-Compatible APIs

---

### 🛠️ 动态工具系统 · 可扩展 | Dynamic Tool System · Extensible

【中文】
- **工具注册机制**：动态注册、模块化管理
- **8个内置工具**：文件操作、代码执行、网页抓取、进程管理等
- **工具集分类**：core（核心）、web（网络）等工具集
- **易于扩展**：遵循接口即可添加新工具
- **轻量级核心**：嵌套不同外壳可在不同场景适用

【English】
- **Tool registry mechanism**: Dynamic registration, modular management
- **8 built-in tools**: File operations, code execution, web scraping, process management
- **Toolset classification**: core, web and other toolsets
- **Easy to extend**: Add new tools by following the interface
- **Lightweight core**: Nest different shells for different scenarios

---

### 💾 SQLite 记忆系统 · 全文搜索 | SQLite Memory System · Full-Text Search

【中文】
- **会话持久化**：所有对话保存到 SQLite 数据库
- **FTS5 全文搜索**：快速搜索历史对话内容
- **会话管理**：列出、搜索、管理多个会话
- **本地存储**：数据完全在本地，隐私安全

【English】
- **Session persistence**: All conversations saved to SQLite database
- **FTS5 full-text search**: Fast search through historical conversations
- **Session management**: List, search, manage multiple sessions
- **Local storage**: Data completely local, privacy secure

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

### 🧬 AGI 成长系统 · 仿生人类成长 | AGI Growth System · Biologically-Inspired Growth

【中文】
- **五层架构**：DNA层（先天参数）、Soul层（长时记忆）、State层（实时状态）、Consolidation层（离线整合）、Inference层（在线决策）
- **自主成长**：通过用户交互不断学习和进化
- **夜间整合**：模拟人类睡眠时的大脑整理过程
- **个性化适配**：根据用户偏好调整响应策略
- **渐进式发展**：持续优化响应策略和知识权重

【English】
- **Five-layer architecture**: DNA (innate parameters), Soul (long-term memory), State (real-time context), Consolidation (offline processing), Inference (online decision-making)
- **Autonomous growth**: Continuously learns and evolves through user interactions
- **Nightly consolidation**: Simulates brain organization during human sleep
- **Personalized adaptation**: Adjusts response strategies based on user preferences
- **Progressive development**: Continuously optimizes response strategies and knowledge weights

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

### 🎯 上下文引用 · 精准定位 | Context References · Precise Targeting

【中文】
- **@file:路径** - 引用文件内容
- **@git:staged** - 引用 Git 暂存区
- **@url:链接** - 引用网页内容
- **智能解析**：自动识别并加载引用内容

【English】
- **@file:path** - Reference file content
- **@git:staged** - Reference Git staging area
- **@url:link** - Reference web page content
- **Smart parsing**: Automatically recognize and load referenced content

---

### 🤖 开放性学习框架 | Open Learning Framework

【中文】
- **开放性学习**：会去学习各个项目的优势，但基于第一性原理
- **克制选择**：只保留那些为了让它更好用而需要保留的功能
- **少即是多**：easy-ai-shell 的目标是理解用户的需求
- **社区共建**：欢迎大家一起把它变得更好

【English】
- **Open Learning**: Learns from advantages of various projects, but based on first principles
- **Restraint Selection**: Only retain features that are needed to make it more useful
- **Less is More**: Easy-ai-shell's goal is to understand user needs
- **Community Driven**: Welcome everyone to make it better together

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

### 1. 基础配置 | Basic Configuration

复制配置示例 / Copy config example:
```bash
copy config.example.json config.json
```

修改 `config.json` / Modify `config.json`:
```json
{
  "llm": {
    "provider": "ark",
    "model": "ark-code-latest",
    "api_key": "your-api-key",
    "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  "shell": {
    "ai_mode": true,
    "max_context_turns": 20,
    "show_tool_calls": true,
    "workspace": null,
    "context_rounds": 3
  },
  "memory": {
    "autoMemoryEnabled": true,
    "autoReviewEnabled": true,
    "minHours": 24,
    "minSessions": 1,
    "memoryDir": ".easy_ai/memory"
  },
  "permission": {
    "mode": "workspace-write",
    "allow_rules": ["bash(git:*)", "read_file(*.md)"],
    "deny_rules": ["bash(rm -rf:*)", "bash(sudo:*)"],
    "ask_rules": ["bash(ssh:*)", "write_file(*.env)"],
    "bash_workspace_policy": "trust-workspace"
  }
}
```

### 2. AGI 成长系统配置 | AGI Growth System Configuration

创建AGI配置文件 / Create AGI configuration:
```bash
copy agi_config.example.json agi_config.json
```

AGI配置允许您自定义五层架构的行为 / AGI configuration allows customization of the five-layer architecture:
```json
{
  "agi_growth": {
    "enabled": true,
    "debug_mode": false,
    "log_level": "INFO",
    "dna_layer": {
      "initial_config": {
        "capabilities": {
          "creativity": 0.7,
          "logical_reasoning": 0.8,
          "empathy": 0.6
        },
        "personality": {
          "openness": 0.8,
          "conscientiousness": 0.7
        }
      }
    },
    "consolidation_layer": {
      "daily_time": "02:00",
      "compression_enabled": true
    },
    "nightly_scheduler": {
      "enabled": true,
      "integration_time": "02:00"
    }
  }
}
```

### 2. 支持的 Provider | Supported Providers

| Provider | 中文名 | 环境变量 | 示例模型 |
|----------|--------|----------|----------|
| openai | OpenAI | `OPENAI_API_KEY` | gpt-4o, gpt-4o-mini |
| anthropic | Anthropic | `ANTHROPIC_API_KEY` | claude-3-5-sonnet |
| deepseek | DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat |
| zhipu | 智谱清言 | `ZHIPU_API_KEY` | glm-4 |
| ark | 字节跳动 | `ARK_API_KEY` | ark-code-latest |
| dashscope | 阿里云 | `DASHSCOPE_API_KEY` | qwen3.5-plus |
| minimax | MiniMax | `MINIMAX_API_KEY` | abab6.5s-chat |
| custom | 自定义 | - | llama3, mistral |

### 3. 高级配置 | Advanced Configuration

#### 自定义 Provider | Custom Provider
```json
{
  "_providers": {
    "my-provider": {
      "base_url": "https://my-api.com/v1",
      "models": ["my-model-v1", "my-model-v2"]
    }
  }
}
```

### 4. 环境变量 | Environment Variables

也可以通过环境变量配置 API Key：
```bash
# OpenAI
set OPENAI_API_KEY=your-key

# Anthropic
set ANTHROPIC_API_KEY=your-key

# DeepSeek
set DEEPSEEK_API_KEY=your-key

# 智谱清言
set ZHIPU_API_KEY=your-key

# 字节跳动
set ARK_API_KEY=your-key

# 阿里云
set DASHSCOPE_API_KEY=your-key

# MiniMax
set MINIMAX_API_KEY=your-key
```

---

## 🏗️ 架构与模块 | Architecture & Modules

| 模块 / Module | 功能 / Function | 亮点 / Highlights |
|------|------|------|
| **ProviderRegistry** | 多厂商 LLM 支持 / Multi-provider LLM | 11个 Provider + 故障转移 / 11 providers + failover |
| **ToolRegistry** | 工具注册与调度 / Tool registry & dispatch | 动态注册 + 8个内置工具 / Dynamic registration + 8 built-in tools |
| **SessionStore** | SQLite 会话存储 / SQLite session storage | FTS5 全文搜索 + 会话持久化 / FTS5 search + persistence |
| **ErrorClassifier** | 错误分类与恢复 / Error classification & recovery | 4种策略：retry/compress/fallback/abort / 4 strategies |
| **ContextReferenceParser** | 上下文引用解析 / Context reference parsing | 支持 @file/@git/@url 引用 / Support @file/@git/@url refs |
| **CodeSandbox** | 代码执行沙箱 / Code execution sandbox | 安全 Python 执行 + 超时控制 / Safe Python exec + timeout |
| **BrowserTool** | 网页抓取工具 / Web scraping tool | 简化版 HTTP 访问 / Simplified HTTP access |
| **ProcessRegistry** | 后台进程管理 / Background process management | spawn/poll/kill 后台任务 / Background task management |
| **PermissionSystem** | 权限规则引擎 / Permission engine | allow/deny/ask + 交互式授权 / interactive auth |
| **Workspace Sandbox** | 工作区沙盒 / Workspace sandbox | 越界访问自动触发授权 / Auto-trigger auth for out-of-bounds |
| **AgentLoop** | ReAct 执行循环 / ReAct loop | 多步迭代直到完成 / Multi-step iteration until done |
| **QueryEngine** | 智能路由 / Smart routing | 命令/工具/AI 自动路由 / Auto-route commands/tools/AI |
| **SessionCompactor** | 会话压缩 / Session compression | 省 token、降低上下文长度 / Save tokens, reduce context |
| **AutoReview** | 记忆整理 / Memory organization | 越用越懂你 / Gets better with use |

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

### 🛠️ 开发者场景 | Developer Scenarios
- **代码重构**：多步执行直到重构完成，不只是给代码片段
- **调试助手**：分析错误日志、定位问题、提供修复方案
- **单元测试**：自动生成测试用例、运行测试、修复失败用例
- **文档生成**：读取代码结构、生成 API 文档、README 更新

### 🔧 运维场景 | DevOps Scenarios
- **批量文件操作**：安全的多文件处理、备份、迁移
- **日志分析**：解析日志文件、提取关键信息、生成报告
- **自动化脚本**：编写、测试、部署自动化脚本
- **系统监控**：检查系统状态、发送告警、自动恢复

### 📊 数据分析场景 | Data Analysis Scenarios
- **数据清洗**：读取 CSV/JSON、清理异常值、格式转换
- **数据转换**：ETL 流程、格式标准化、数据聚合
- **报表生成**：分析数据、生成图表、导出报告
- **可视化**：使用 Python 库生成图表、仪表板

### 👥 团队协作场景 | Team Collaboration Scenarios
- **代码审查**：自动检查代码规范、安全漏洞、性能问题
- **知识管理**：整理团队文档、沉淀最佳实践、快速检索
- **工作流自动化**：CI/CD 流程、发布管理、回滚机制
- **共享记忆**：团队共享上下文、避免重复沟通

### 🤖 开放性学习框架 | Open Learning Framework
- **专业分工**：基于第一性原理，保留核心调度功能
- **可扩展性**：用户可以根据需要添加插件和功能
- **轻量级核心**：嵌套不同外壳可在不同场景适用
- **社区驱动**：欢迎大家一起把它变得更好

### 🎯 特殊场景 | Special Scenarios
- **学习助手**：解释复杂概念、提供示例代码、答疑解惑
- **迁移工具**：代码语言转换、框架升级、API 迁移
- **安全审计**：检查安全漏洞、扫描依赖、生成安全报告
- **性能优化**：分析性能瓶颈、提供优化建议、实施改进

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