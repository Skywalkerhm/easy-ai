# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] / 开发中

### Added
- Initial release of Easy AI Shell
- Zero-dependency AI terminal agent framework
- ReAct (Reasoning + Acting) agent loop implementation
- Workspace sandbox with permission control
- AutoReview local memory mechanism
- SessionCompactor for context compression
- Support for multiple LLM providers (Ark, DashScope, MiniMax, etc.)
- MCP (Model Context Protocol) client support

### Features
- `allow/deny/ask` three-level permission rules
- Interactive authorization for sensitive operations
- Auto-compression of conversation history
- Local memory storage in `.easy_ai/memory/`
- Multi-turn execution until task completion

### Documentation
- Bilingual README (Chinese/English)
- Apache 2.0 license with custom additional terms
- CONTRIBUTING.md guidelines
- CODE_OF_CONDUCT.md

### Technical
- Pure Python standard library implementation
- OpenAI-Compatible API interface
- Windows/PowerShell compatible

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
