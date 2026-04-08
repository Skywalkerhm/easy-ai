# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] / 开发中

### Added
- **企业级 AI Agent 特性**：集成生产级 AI Agent 框架的核心功能
- **ProviderRegistry**：11个主流 LLM Provider 支持（OpenAI、Anthropic、通义千问、DeepSeek、智谱清言等）
- **ToolRegistry**：动态工具注册机制，8个内置工具（文件操作、代码执行、网页抓取等）
- **SessionStore**：SQLite 会话存储 + FTS5 全文搜索
- **ErrorClassifier**：智能错误分类与故障转移（retry/compress/fallback/abort）
- **ContextReferenceParser**：上下文引用解析（@file/@git/@url）
- **CodeSandbox**：安全代码执行沙箱
- **BrowserTool**：简化版网页抓取工具
- **ProcessRegistry**：后台进程管理
- **自动故障转移**：API 失败时自动切换备用模型
- **多工具集分类**：core（核心）、web（网络）等工具集
- **AGI成长系统**：仿生人类成长模式的五层架构（DNA/Soul/State/Consolidation/Inference）
- **自主成长能力**：通过用户交互实现渐进式发展
- **夜间整合机制**：模拟人类睡眠时的记忆整理过程
- **个性化适配**：基于用户交互模式的自适应响应
- **AGI配置系统**：支持通过agi_config.json进行详细配置

### Enhanced
- **配置系统**：支持自定义 Provider 和 MCP 服务器配置
- **环境变量支持**：所有 Provider 支持环境变量配置 API Key
- **错误处理**：更细粒度的错误分类和恢复策略
- **会话管理**：完整的会话持久化和搜索功能

### Features
- `allow/deny/ask` three-level permission rules
- Interactive authorization for sensitive operations
- Auto-compression of conversation history
- Local memory storage in `.easy_ai/memory/`
- Multi-turn execution until task completion
- Full-text search across conversation history
- Background process management
- Context reference parsing and resolution

### Documentation
- 更新 README.md：新增企业级特性说明
- 扩展配置文档：详细的 Provider 和环境变量说明
- 丰富使用场景：开发者、运维、数据分析、团队协作等场景

### Technical
- Pure Python standard library implementation
- OpenAI-Compatible API interface
- Windows/PowerShell compatible
- SQLite FTS5 full-text search integration
- Dynamic tool registration system
- Multi-provider failover mechanism

---

## Version History | 版本历史

| Version | Date | Description |
|---------|------|-------------|
| 0.1.0 | 2026-04-08 | Initial release / 初始版本 |

---

## Migration Notes | 迁移说明

### From v0.x to future versions
- Configuration structure may change between minor versions
- Please backup your `.easy_ai/` directory before upgrading

### 從 v0.x 升級說明
- 配置結構在 minor 版本間可能會有變化
- 升級前請備份 `.easy_ai/` 目錄

---

*This changelog follows the Keep a Changelog format.*
*此變更日誌遵循 Keep a Changelog 格式。*
