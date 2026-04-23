#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Easy AI Shell - Lightweight Python AI Coding Assistant
支持通过 config.json 配置 LLM API，基于 Agent 循环模式实现。

Features:
- Agent Mode (自然语言 → LLM理解 → 自动调用工具 → 循环执行)
- Permission System (权限系统)
- TaskRegistry (任务管理)
- Team + Cron (团队与定时任务)
- MCP Client (MCP协议)
- LSP Client (语言服务器)
- Session Compact (会话压缩)
- Branch Lock (分支锁定)
- Stale Branch (过期分支检测)
- Plugin System (插件系统)
- AutoReview (记忆自动整理)

Usage:
    python easy_ai_shell.py              # 交互模式（AI Agent + 工具调用）
    python easy_ai_shell.py -p "prompt"  # 单次执行模式
    python easy_ai_shell.py -w <dir>     # 指定工作目录
    python easy_ai_shell.py --no-ai      # 纯命令模式（不调用 AI）
"""

import os
import sys
import json
import hashlib
import subprocess
import re
import shlex
import threading
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from uuid import uuid4
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin, quote, urlparse, parse_qs, parse_qsl, unquote, urlencode
import io
import html
import xml.etree.ElementTree as ET

# ==================== ANSI Colors ====================

class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    CYAN    = "\033[36m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    RED     = "\033[31m"
    GRAY    = "\033[90m"
    MAGENTA = "\033[35m"
    BLUE    = "\033[34m"

def colored(text: str, color: str, bold: bool = False) -> str:
    prefix = (Color.BOLD if bold else "") + color
    return f"{prefix}{text}{Color.RESET}"

def is_tty() -> bool:
    return sys.stdin.isatty()

def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def log_line(message: str) -> None:
    print(f"[{now_ts()}] {message}")


# ==================== Config ====================

DEFAULT_CONFIG = {
    "llm": {
        "provider": "openai",
        "model": "gpt-4o",
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "max_tokens": 4096,
        "temperature": 0.7,
        "system_prompt": (
            "You are a helpful AI coding assistant running in a terminal shell. "
            "When you need to use tools, output a JSON block with the tool call. "
            "Available tools: FileReadTool, FileWriteTool, BashTool, GrepTool, GlobTool, TodoWriteTool. "
            "Format: ```json\n{\"tool\": \"ToolName\", \"input\": {...}}\n```"
        ),
    },
    "_providers": {},
    "shell": {
        "ai_mode": True,
        "max_context_turns": 20,
        "show_tool_calls": True,
        "workspace": None,
        "max_agent_turns": 24,  # Agent 循环最大次数
        "non_interactive": False,
        "context_rounds": 3,
    },
    "memory": {
        "autoMemoryEnabled": True,
        "autoReviewEnabled": False,
        "consolidateOnExit": True,
        "minHours": 24,
        "minSessions": 5,
        "memoryDir": ".easy_ai/memory",
        "userMemoryPath": "~/.easy_ai_shell/memory/USER_MEMORY.md",
        "projectMemoryFile": "PROJECT_MEMORY.md",
        "topicsIndexFile": "MEMORY.md",
        "maxSessionFiles": 50,
    },
    "permission": {
        "mode": "workspace-write",  # read-only, workspace-write, danger-full-access
        "allow_rules": [],
        "deny_rules": [],
        "ask_rules": [],
        "bash_workspace_policy": "off",  # off | trust-workspace
    },
    "web": {
        "blocked_domains": [],
        "news_allowed_domains": [],
        "news_blocked_domains": [],
    },
    "mcp_servers": {},
}


def load_config(config_path: Optional[Path] = None) -> dict:
    """Load config.json, merging with defaults."""
    if config_path is None:
        # Search: current dir, then script dir
        for candidate in [Path.cwd() / "config.json", Path(__file__).parent / "config.json"]:
            if candidate.exists():
                config_path = candidate
                break

    if config_path and config_path.exists():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
            # Deep merge into defaults
            cfg = DEFAULT_CONFIG.copy()
            cfg["llm"] = {**DEFAULT_CONFIG["llm"], **raw.get("llm", {})}
            cfg["_providers"] = raw.get("_providers", DEFAULT_CONFIG.get("_providers", {})) or {}
            cfg["shell"] = {**DEFAULT_CONFIG["shell"], **raw.get("shell", {})}
            cfg["memory"] = {**DEFAULT_CONFIG["memory"], **raw.get("memory", {})}
            cfg["permission"] = {**DEFAULT_CONFIG["permission"], **raw.get("permission", {})}
            cfg["web"] = {**DEFAULT_CONFIG.get("web", {}), **raw.get("web", {})}
            cfg["mcp_servers"] = raw.get("mcp_servers", DEFAULT_CONFIG.get("mcp_servers", {})) or {}
            try:
                servers = cfg.get("mcp_servers")
                if isinstance(servers, dict):
                    for _, info in servers.items():
                        if not isinstance(info, dict):
                            continue
                        headers = info.get("headers")
                        if not isinstance(headers, dict):
                            continue
                        new_headers = {}
                        for hk, hv in headers.items():
                            if not isinstance(hk, str):
                                continue
                            if not isinstance(hv, str):
                                new_headers[hk] = hv
                                continue
                            v = hv
                            for m in re.finditer(r"\$\{([A-Z0-9_]+)\}", hv):
                                env = os.environ.get(m.group(1), "")
                                if env:
                                    v = v.replace(m.group(0), env)
                            new_headers[hk] = v
                        info["headers"] = new_headers
            except Exception:
                pass
            return cfg
        except Exception as e:
            log_line(colored(f"[Config] Failed to load config.json: {e}", Color.YELLOW))

    return DEFAULT_CONFIG.copy()


# ==================== Data Models ====================

@dataclass
class Module:
    name: str
    responsibility: str
    source_hint: str
    status: str = "active"


@dataclass
class Match:
    kind: str       # "command" | "tool"
    name: str
    source_hint: str
    score: int


@dataclass
class ExecutionResult:
    success: bool
    output: str
    error: Optional[str] = None
    special: Optional[str] = None  # "CLEAR" | "EXIT"


@dataclass
class TurnResult:
    prompt: str
    output: str
    matched_commands: tuple
    matched_tools: tuple
    stop_reason: str = "completed"
    ai_used: bool = False


@dataclass
class ToolCall:
    """Represents a tool call from LLM"""
    tool_name: str
    tool_input: dict
    raw_json: str = ""


@dataclass
class AgentStep:
    """One step in the agent loop"""
    step_num: int
    thought: str
    action: Optional[ToolCall]
    observation: str
    is_final: bool = False


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: uuid4().hex[:8])
    messages: list = field(default_factory=list)   # raw prompt strings
    history: list = field(default_factory=list)    # {"role": ..., "content": ...}
    max_turns: int = 100


# ==================== Command & Tool Registry ====================

COMMANDS: tuple = (
    Module("add-dir",   "Create a new directory",              "commands/add-dir"),
    Module("files",     "List and search files",               "commands/files"),
    Module("copy",      "Copy files or content",               "commands/copy"),
    Module("delete",    "Delete files",                        "commands/delete"),
    Module("init",      "Initialize new project",              "commands/init"),
    Module("install",   "Install dependencies",                "commands/install"),
    Module("test",      "Run tests",                           "commands/test"),
    Module("build",     "Build the project",                   "commands/build"),
    Module("run",       "Execute shell command",               "commands/run"),
    Module("commit",    "Git commit changes",                  "commands/commit"),
    Module("branch",    "Git branch operations",               "commands/branch"),
    Module("push",      "Git push to remote",                  "commands/push"),
    Module("pull",      "Git pull from remote",                "commands/pull"),
    Module("diff",      "Show git diff",                       "commands/diff"),
    Module("status",    "Show git status",                     "commands/status"),
    Module("log",       "Show git log",                        "commands/log"),
    Module("context",   "Manage context files",                "commands/context"),
    Module("memory",    "Working memory operations",           "commands/memory"),
    Module("resume",    "Resume previous session",             "commands/resume"),
    Module("review",    "Review code changes",                 "commands/review"),
    Module("plan",      "Plan task execution steps",           "commands/plan"),
    Module("advisor",   "Give suggestions and advice",         "commands/advisor"),
    Module("compact",   "Compact/summarize context",           "commands/compact"),
    Module("config",    "Configure settings",                  "commands/config"),
    Module("model",     "Manage AI model settings",            "commands/model"),
    Module("autoreview","Auto-review and consolidate memory",     "commands/autoreview"),
    Module("task",      "Task management (create/get/list/stop)", "commands/task"),
    Module("team",      "Team management (create/delete/list)", "commands/team"),
    Module("cron",      "Cron job management (create/delete/list)", "commands/cron"),
    Module("mcp",       "MCP server management",                "commands/mcp"),
    Module("lsp",       "LSP language server operations",      "commands/lsp"),
    Module("plugin",    "Plugin management (install/enable/disable)", "commands/plugin"),
    Module("lock",      "Branch lock operations",               "commands/lock"),
    Module("stale",     "Detect stale branches",               "commands/stale"),
    Module("help",      "Show available commands",             "commands/help"),
    Module("version",   "Show version information",            "commands/version"),
    Module("clear",     "Clear screen",                        "commands/clear"),
    Module("exit",      "Exit the shell",                      "commands/exit"),
    Module("quit",      "Quit the shell",                      "commands/exit"),
    Module("workspace", "Set sandbox workspace root",          "commands/workspace"),
    Module("cd",        "Alias of workspace",                  "commands/workspace"),
)

TOOLS: tuple = (
    Module("FileReadTool",    "Read file contents",            "tools/FileReadTool"),
    Module("FileWriteTool",   "Write content to file",         "tools/FileWriteTool"),
    Module("FileEditTool",    "Edit file content",             "tools/FileEditTool"),
    Module("FileSearchTool",  "Search in files",               "tools/FileSearchTool"),
    Module("GlobTool",        "Find files by pattern",         "tools/GlobTool"),
    Module("BashTool",        "Execute shell commands",        "tools/BashTool"),
    Module("GrepTool",        "Search content in files",       "tools/GrepTool"),
    Module("WebFetchTool",    "Fetch web content",             "tools/WebFetchTool"),
    Module("WebSearchTool",   "Search the web",                "tools/WebSearchTool"),
    Module("NewsSearchTool",  "Search news via RSS",           "tools/NewsSearchTool"),
    Module("TodoWriteTool",   "Manage todo list",              "tools/TodoWriteTool"),
    Module("TaskTool",        "Task management tool",          "tools/TaskTool"),
    Module("MCPTool",         "MCP tool executor",              "tools/MCPTool"),
    Module("LSPTool",         "LSP language server tool",      "tools/LSPTool"),
)

TOOL_ALIASES = {
    "read":   "FileReadTool",
    "write":  "FileWriteTool",
    "grep":   "GrepTool",
    "glob":   "GlobTool",
    "bash":   "BashTool",
    "sh":     "BashTool",
    "search": "FileSearchTool",
    "news":   "NewsSearchTool",
    "web_search": "WebSearchTool",
    "websearch": "WebSearchTool",
    "web_fetch": "WebFetchTool",
    "webfetch": "WebFetchTool",
    "task":   "TaskTool",
}

# Tool permission requirements
TOOL_PERMISSIONS = {
    "BashTool": "danger-full-access",
    "FileReadTool": "read-only",
    "FileWriteTool": "workspace-write",
    "FileEditTool": "workspace-write",
    "GlobTool": "read-only",
    "GrepTool": "read-only",
    "WebFetchTool": "read-only",
    "WebSearchTool": "read-only",
    "NewsSearchTool": "read-only",
    "TodoWriteTool": "workspace-write",
    "TaskTool": "workspace-write",
    "MCPTool": "read-only",
    "LSPTool": "read-only",
    "ExternalPathTool": "prompt",
}

# Tool descriptions for LLM
TOOL_DESCRIPTIONS = {
    "FileReadTool": {
        "name": "FileReadTool",
        "description": "Read the contents of a file from the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "The path to the file to read"}
            },
            "required": ["file_path"]
        }
    },
    "FileWriteTool": {
        "name": "FileWriteTool",
        "description": "Write content to a file, creating it if necessary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "The path to the file to write"},
                "content": {"type": "string", "description": "The content to write to the file"}
            },
            "required": ["file_path", "content"]
        }
    },
    "BashTool": {
        "name": "BashTool",
        "description": "Execute a shell command in the terminal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"}
            },
            "required": ["command"]
        }
    },
    "GrepTool": {
        "name": "GrepTool",
        "description": "Search for text patterns in files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "The search pattern"},
                "path": {"type": "string", "description": "The directory or file to search in"}
            },
            "required": ["pattern"]
        }
    },
    "GlobTool": {
        "name": "GlobTool",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "The glob pattern (e.g., *.py)"}
            },
            "required": ["pattern"]
        }
    },
    "TodoWriteTool": {
        "name": "TodoWriteTool",
        "description": "Create, update, or manage todo items.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action: create, list, complete, delete"},
                "content": {"type": "string", "description": "Todo content or task description"},
                "todo_id": {"type": "string", "description": "Todo ID for actions like complete/delete"}
            },
            "required": ["action"]
        }
    },
    "WebFetchTool": {
        "name": "WebFetchTool",
        "description": "Fetch web content from a URL (read-only).",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"}
            },
            "required": ["url"]
        }
    },
    "WebSearchTool": {
        "name": "WebSearchTool",
        "description": "Search the web for public pages and return a ranked list of results (read-only).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "description": "Max results (1-10)"},
                "allowed_domains": {"type": "array", "items": {"type": "string"}, "description": "Optional allowlist of domains"},
                "blocked_domains": {"type": "array", "items": {"type": "string"}, "description": "Optional blocklist of domains"}
            },
            "required": ["query"]
        }
    },
    "NewsSearchTool": {
        "name": "NewsSearchTool",
        "description": "Search latest news/public updates (read-only). Uses Bing HTML by default; can fallback to Google News RSS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "description": "Max results (1-20)"},
                "provider": {"type": "string", "description": "Preferred provider: bing | google_news_rss"},
                "allowed_domains": {"type": "array", "items": {"type": "string"}, "description": "Optional allowlist of domains (prefer credible news sources)"},
                "blocked_domains": {"type": "array", "items": {"type": "string"}, "description": "Optional blocklist of domains (e.g. Q&A/forums)"},
                "language": {"type": "string", "description": "Language code, e.g. zh-CN, en-US"},
                "region": {"type": "string", "description": "Region code, e.g. CN, US"},
                "ceid": {"type": "string", "description": "Google News CEID, e.g. CN:zh-Hans"}
            },
            "required": ["query"]
        }
    },
}


# ==================== Permission System ====================

class PermissionMode:
    """Permission level enum"""
    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"
    DANGER_FULL_ACCESS = "danger-full-access"
    PROMPT = "prompt"
    ALLOW = "allow"

    @staticmethod
    def from_str(s: str):
        mapping = {
            "read-only": PermissionMode.READ_ONLY,
            "workspace-write": PermissionMode.WORKSPACE_WRITE,
            "danger-full-access": PermissionMode.DANGER_FULL_ACCESS,
            "prompt": PermissionMode.PROMPT,
            "allow": PermissionMode.ALLOW,
        }
        return mapping.get(s, PermissionMode.WORKSPACE_WRITE)

    @staticmethod
    def level(mode: str) -> int:
        """Return numeric level for comparison"""
        levels = {
            PermissionMode.READ_ONLY: 0,
            PermissionMode.WORKSPACE_WRITE: 1,
            PermissionMode.DANGER_FULL_ACCESS: 2,
            PermissionMode.PROMPT: 3,
            PermissionMode.ALLOW: 4,
        }
        return levels.get(mode, 1)


class PermissionRule:
    """Permission rule for allow/deny/ask"""

    def __init__(self, raw: str):
        self.raw = raw
        self.tool_name = ""
        self.matcher_type = "any"  # any, exact, prefix
        self.matcher_value = ""
        self._parse()

    def _parse(self):
        raw = self.raw.strip()
        # Parse format: tool_name(subject) or just tool_name
        open_bracket = raw.find("(")
        close_bracket = raw.rfind(")")
        if open_bracket != -1 and close_bracket != -1 and close_bracket == len(raw) - 1:
            self.tool_name = self._normalize_tool_name(raw[:open_bracket].strip())
            content = raw[open_bracket + 1:close_bracket]
            if content == "*" or content == "":
                self.matcher_type = "any"
            elif content.endswith(":*"):
                self.matcher_type = "prefix"
                self.matcher_value = content[:-2]
            else:
                self.matcher_type = "exact"
                self.matcher_value = content
        else:
            self.tool_name = self._normalize_tool_name(raw)
            self.matcher_type = "any"

    def matches(self, tool_name: str, input_str: str) -> bool:
        if self.tool_name != self._normalize_tool_name(tool_name):
            return False

        if self.matcher_type == "any":
            return True

        # Extract subject from input
        subject = self._extract_subject(input_str)

        if self.matcher_type == "exact":
            return subject == self.matcher_value
        elif self.matcher_type == "prefix":
            return subject and subject.startswith(self.matcher_value)
        return False

    def _extract_subject(self, input_str: str) -> str:
        """Extract permission subject from tool input"""
        try:
            # Try JSON
            data = json.loads(input_str)
            if isinstance(data, dict):
                for key in ["command", "path", "file_path", "url", "pattern", "code", "content", "query"]:
                    if key in data and data[key]:
                        return str(data[key])
        except:
            pass
        return input_str.strip() if input_str.strip() else ""

    @staticmethod
    def _normalize_tool_name(name: str) -> str:
        if not isinstance(name, str):
            return ""
        key = name.strip()
        if not key:
            return ""
        k = key.lower()
        aliases = {
            "bash": "BashTool",
            "sh": "BashTool",
            "read": "FileReadTool",
            "read_file": "FileReadTool",
            "write": "FileWriteTool",
            "write_file": "FileWriteTool",
            "edit": "FileEditTool",
            "edit_file": "FileEditTool",
            "grep": "GrepTool",
            "search": "FileSearchTool",
            "glob": "GlobTool",
            "todo": "TodoWriteTool",
            "task": "TaskTool",
            "web_fetch": "WebFetchTool",
            "webfetch": "WebFetchTool",
            "web_search": "WebSearchTool",
            "websearch": "WebSearchTool",
        }
        if k in aliases:
            return aliases[k]
        for t in TOOLS:
            if t.name.lower() == k:
                return t.name
        return key


class PermissionSystem:
    """Permission system with rules engine"""

    def __init__(self, cfg: dict, workspace: Optional[Path] = None):
        self.shell_cfg = cfg.get("shell", {}) if isinstance(cfg, dict) else {}
        self.cfg = cfg.get("permission", {})
        self.active_mode = PermissionMode.from_str(self.cfg.get("mode", "workspace-write"))
        self.allow_rules = [PermissionRule(r) for r in self.cfg.get("allow_rules", [])]
        self.deny_rules = [PermissionRule(r) for r in self.cfg.get("deny_rules", [])]
        self.ask_rules = [PermissionRule(r) for r in self.cfg.get("ask_rules", [])]
        self._allow_once: set[str] = set()
        self._allow_tool_session: set[str] = set()
        self.workspace = (workspace or Path.cwd()).expanduser()
        try:
            self.workspace = self.workspace.resolve()
        except Exception:
            pass

    def set_workspace(self, workspace: Path) -> None:
        w = (workspace or Path.cwd()).expanduser()
        try:
            w = w.resolve()
        except Exception:
            pass
        self.workspace = w

    def _bash_workspace_policy(self) -> str:
        v = (self.cfg or {}).get("bash_workspace_policy", "off")
        return str(v).strip().lower()

    def _bash_command_workspace_scope(self, tool_input: str) -> Optional[bool]:
        try:
            data = json.loads(tool_input) if isinstance(tool_input, str) else {}
        except Exception:
            data = {}

        if not isinstance(data, dict):
            return None

        cmd = data.get("command")
        if not isinstance(cmd, str) or not cmd.strip():
            return None

        s = cmd.strip()
        meta = ("|", ";", "&&", "||", ">", "<", "`", "$(")
        if any(m in s for m in meta):
            return None

        try:
            parts = shlex.split(s)
        except Exception:
            return None

        if not parts:
            return None

        workspace = self.workspace
        candidates: list[str] = []

        for tok in parts[1:]:
            if tok == "--":
                continue
            if tok.startswith("-"):
                continue
            if tok.startswith("$"):
                return None
            if tok.startswith("~"):
                candidates.append(tok)
                continue
            if "=" in tok and "/" not in tok and not tok.startswith("."):
                continue
            if any(ch in tok for ch in ("/", "\\", "*", "?", "[")) or tok.startswith("."):
                candidates.append(tok)
                continue
            try:
                if (workspace / tok).exists():
                    candidates.append(tok)
            except Exception:
                pass

        for raw in candidates:
            if not isinstance(raw, str) or not raw.strip():
                continue
            token = raw.strip()
            if token.startswith("~"):
                token = str(Path(token).expanduser())
            p = Path(token)

            try:
                rp = p.expanduser().resolve() if p.is_absolute() else (workspace / p).resolve()
            except Exception:
                rp = p if p.is_absolute() else (workspace / p)

            try:
                inside = rp.is_relative_to(workspace)
            except Exception:
                inside = str(rp).lower().startswith(str(workspace).lower().rstrip("\\/") + os.sep)

            if not inside:
                return False

        return True

    def _grant_key(self, tool_name: str, tool_input: str) -> str:
        return f"{tool_name}\n{tool_input}"

    def authorize(self, tool_name: str, tool_input: str = "{}") -> tuple[bool, str]:
        """Check if tool is allowed. Returns (allowed, reason)"""

        # 1. Check deny rules first
        for rule in self.deny_rules:
            if rule.matches(tool_name, tool_input):
                return False, f"denied by rule '{rule.raw}'"

        if tool_name in self._allow_tool_session:
            return True, "allowed tool for session by user"
        key = self._grant_key(tool_name, tool_input)
        if key in self._allow_once:
            self._allow_once.remove(key)
            return True, "allowed once by user"

        # 2. Check allow rules - if matches, bypass other checks
        for rule in self.allow_rules:
            if rule.matches(tool_name, tool_input):
                return True, f"allowed by rule '{rule.raw}'"

        # 3. Check ask rules - requires user confirmation
        for rule in self.ask_rules:
            if rule.matches(tool_name, tool_input):
                return False, f"requires approval (rule '{rule.raw}')"

        if tool_name == "BashTool" and self._bash_workspace_policy() == "trust-workspace":
            scope = self._bash_command_workspace_scope(tool_input)
            if scope is True:
                return True, "bash command scoped to workspace"
            if scope is False:
                return False, "requires approval (bash command touches outside workspace)"

        # 4. Check permission mode vs tool requirement
        required = TOOL_PERMISSIONS.get(tool_name, "danger-full-access")
        required_level = PermissionMode.level(required)
        active_level = PermissionMode.level(self.active_mode)

        if active_level >= required_level:
            return True, f"mode {self.active_mode} >= required {required}"
        else:
            return False, f"requires {required}, current mode is {self.active_mode}"

    def set_mode(self, mode: str):
        """Change permission mode"""
        self.active_mode = PermissionMode.from_str(mode)

    def get_mode(self) -> str:
        return self.active_mode

    def authorize_or_prompt(self, tool_name: str, tool_input: str = "{}") -> tuple[bool, str]:
        allowed, reason = self.authorize(tool_name, tool_input)
        if allowed:
            return True, reason
        if self.shell_cfg.get("non_interactive", False):
            return False, reason
        if not is_tty():
            return False, reason
        return self._prompt_user(tool_name, tool_input, reason)

    def _prompt_user(self, tool_name: str, tool_input: str, reason: str) -> tuple[bool, str]:
        required = TOOL_PERMISSIONS.get(tool_name, "danger-full-access")
        subject = ""
        try:
            subject = PermissionRule("_")._extract_subject(tool_input)
        except Exception:
            subject = tool_input

        log_line(colored("[Permission] ", Color.YELLOW) + f"Need approval for {tool_name}")
        log_line(f"  Reason: {reason}")
        if subject:
            log_line(f"  Subject: {subject}")
        log_line(f"  Current mode: {self.active_mode}")
        log_line(f"  Required: {required}")
        log_line("  Choose: allow / a / 2 = allow tool for session | 1 = allow once | 3 = elevate mode | 4 = deny")
        try:
            choice = input("> ").strip().lower()
        except Exception:
            return False, reason

        if choice in ("allow", "a", "2"):
            self._allow_tool_session.add(tool_name)
            return True, "allowed tool for session by user"
        if choice in ("1", "once"):
            self._allow_once.add(self._grant_key(tool_name, tool_input))
            return True, "allowed once by user"
        if choice in ("3", "elevate"):
            self.set_mode(required)
            return True, f"mode elevated to {self.active_mode} by user"
        return False, reason


# ==================== Task Registry ====================

class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class Task:
    """Task data model"""

    def __init__(self, task_id: str, description: str, prompt: str = "", team: str = ""):
        self.id = task_id
        self.description = description
        self.prompt = prompt
        self.team = team
        self.status = TaskStatus.PENDING
        self.output = ""
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.process = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "team": self.team,
            "created_at": self.created_at.isoformat(),
            "output": self.output[:500] if self.output else "",
        }


class TaskRegistry:
    """In-memory task registry"""

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()

    def create(self, description: str, prompt: str = "", team: str = "") -> Task:
        task_id = f"task-{uuid4().hex[:8]}"
        task = Task(task_id, description, prompt, team)
        with self._lock:
            self.tasks[task_id] = task
        return task

    def restore(self, task_id: str, description: str, prompt: str = "", team: str = "", status: str = TaskStatus.PENDING) -> Task:
        task = Task(task_id, description, prompt, team)
        task.status = status
        with self._lock:
            self.tasks[task_id] = task
        return task

    def get(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self.tasks.get(task_id)

    def list(self, status: str = None) -> List[Task]:
        with self._lock:
            tasks = list(self.tasks.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def update(self, task_id: str, **kwargs) -> bool:
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                for key, value in kwargs.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                return True
        return False

    def stop(self, task_id: str) -> bool:
        task = self.get(task_id)
        if not task:
            return False
        if task.process:
            task.process.terminate()
        self.update(task_id, status=TaskStatus.STOPPED, completed_at=datetime.now())
        return True

    def append_output(self, task_id: str, output: str):
        task = self.get(task_id)
        if task:
            task.output += output


# ==================== Todo Registry ====================

@dataclass
class TodoItem:
    id: str
    description: str
    status: str = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class TodoRegistry:
    """In-memory todo registry scoped by task_id."""

    def __init__(self):
        self._todos_by_task: Dict[str, Dict[str, TodoItem]] = {}
        self._lock = threading.Lock()

    def create(self, task_id: str, description: str) -> TodoItem:
        todo_id = f"todo-{uuid4().hex[:8]}"
        todo = TodoItem(id=todo_id, description=description or "")
        with self._lock:
            bucket = self._todos_by_task.setdefault(task_id, {})
            bucket[todo_id] = todo
        return todo

    def restore(self, task_id: str, todo_id: str, description: str, status: str = TaskStatus.PENDING) -> TodoItem:
        todo = TodoItem(id=todo_id, description=description or "", status=status)
        if status == TaskStatus.COMPLETED:
            todo.completed_at = datetime.now()
        with self._lock:
            bucket = self._todos_by_task.setdefault(task_id, {})
            bucket[todo_id] = todo
        return todo

    def list(self, task_id: str) -> List[TodoItem]:
        with self._lock:
            bucket = self._todos_by_task.get(task_id, {})
            todos = list(bucket.values())
        return sorted(todos, key=lambda t: t.created_at, reverse=True)

    def get(self, task_id: str, todo_id: str) -> Optional[TodoItem]:
        with self._lock:
            return self._todos_by_task.get(task_id, {}).get(todo_id)

    def complete(self, task_id: str, todo_id: str) -> bool:
        with self._lock:
            todo = self._todos_by_task.get(task_id, {}).get(todo_id)
            if not todo:
                return False
            todo.status = TaskStatus.COMPLETED
            todo.completed_at = datetime.now()
            return True

    def delete(self, task_id: str, todo_id: str) -> bool:
        with self._lock:
            bucket = self._todos_by_task.get(task_id, {})
            if todo_id in bucket:
                del bucket[todo_id]
                return True
        return False

    def clear(self, task_id: str) -> None:
        with self._lock:
            self._todos_by_task.pop(task_id, None)


# ==================== Team & Cron Registry ====================

@dataclass
class Team:
    id: str
    name: str
    description: str = ""
    members: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CronJob:
    id: str
    name: str
    command: str
    schedule: str  # cron expression
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)


class TeamRegistry:
    """Team management with persistent storage"""

    def __init__(self, data_path: Path = None):
        self.teams: Dict[str, Team] = {}
        self._lock = threading.Lock()
        self._data_path = data_path or Path(".easy_ai") / "teams.json"
        self._load()
    
    def _load(self):
        """Load teams from JSON file"""
        try:
            if self._data_path.exists():
                with self._data_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    for team_data in data:
                        team = Team(
                            id=team_data["id"],
                            name=team_data["name"],
                            description=team_data.get("description", ""),
                            members=team_data.get("members", []),
                        )
                        # Convert string date to datetime
                        if "created_at" in team_data:
                            team.created_at = datetime.fromisoformat(team_data["created_at"])
                        self.teams[team.id] = team
        except Exception as e:
            # Ignore any errors when loading
            pass
    
    def _save(self):
        """Save teams to JSON file"""
        try:
            # Ensure directory exists
            self._data_path.parent.mkdir(parents=True, exist_ok=True)
            # Convert to serializable format
            data = []
            for team in self.teams.values():
                data.append({
                    "id": team.id,
                    "name": team.name,
                    "description": team.description,
                    "members": team.members,
                    "created_at": team.created_at.isoformat()
                })
            with self._data_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # Ignore any errors when saving
            pass

    def create(self, name: str, description: str = "") -> Team:
        team_id = f"team-{uuid4().hex[:8]}"
        team = Team(team_id, name, description)
        with self._lock:
            self.teams[team_id] = team
            self._save()
        return team

    def delete(self, team_id: str) -> bool:
        with self._lock:
            if team_id in self.teams:
                del self.teams[team_id]
                self._save()
                return True
            return False

    def list(self) -> List[Team]:
        with self._lock:
            return list(self.teams.values())

    def get(self, team_id: str) -> Optional[Team]:
        with self._lock:
            return self.teams.get(team_id)


class CronRegistry:
    """Cron job management with persistent storage"""

    def __init__(self, data_path: Path = None):
        self.jobs: Dict[str, CronJob] = {}
        self._lock = threading.Lock()
        self._scheduler_thread = None
        self._running = False
        self._data_path = data_path or Path(".easy_ai") / "cronjobs.json"
        self._load()
    
    def _load(self):
        """Load cron jobs from JSON file"""
        try:
            if self._data_path.exists():
                with self._data_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    for job_data in data:
                        job = CronJob(
                            id=job_data["id"],
                            name=job_data["name"],
                            command=job_data["command"],
                            schedule=job_data["schedule"],
                            enabled=job_data.get("enabled", True),
                        )
                        # Convert string dates to datetime
                        if "created_at" in job_data:
                            job.created_at = datetime.fromisoformat(job_data["created_at"])
                        if "last_run" in job_data and job_data["last_run"]:
                            job.last_run = datetime.fromisoformat(job_data["last_run"])
                        if "next_run" in job_data and job_data["next_run"]:
                            job.next_run = datetime.fromisoformat(job_data["next_run"])
                        self.jobs[job.id] = job
        except Exception as e:
            # Ignore any errors when loading
            pass
    
    def _save(self):
        """Save cron jobs to JSON file"""
        try:
            # Ensure directory exists
            self._data_path.parent.mkdir(parents=True, exist_ok=True)
            # Convert to serializable format
            data = []
            for job in self.jobs.values():
                data.append({
                    "id": job.id,
                    "name": job.name,
                    "command": job.command,
                    "schedule": job.schedule,
                    "enabled": job.enabled,
                    "last_run": job.last_run.isoformat() if job.last_run else None,
                    "next_run": job.next_run.isoformat() if job.next_run else None,
                    "created_at": job.created_at.isoformat()
                })
            with self._data_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # Ignore any errors when saving
            pass

    def create(self, name: str, command: str, schedule: str) -> CronJob:
        job_id = f"cron-{uuid4().hex[:8]}"
        job = CronJob(job_id, name, command, schedule)
        with self._lock:
            self.jobs[job_id] = job
            self._save()
        return job

    def delete(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self.jobs:
                del self.jobs[job_id]
                self._save()
                return True
            return False

    def list(self) -> List[CronJob]:
        with self._lock:
            return list(self.jobs.values())

    def enable(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self.jobs:
                self.jobs[job_id].enabled = True
                self._save()
                return True
            return False

    def disable(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self.jobs:
                self.jobs[job_id].enabled = False
                self._save()
                return True
            return False


# ==================== MCP Client ====================

class MCPClient:
    """Simplified MCP client for tool execution"""

    def __init__(self):
        self.servers: Dict[str, dict] = {}
        self.tools: Dict[str, list] = {}  # server_name -> tool list
        self._rpc_id = 0
        self._initialized: set[str] = set()

    def add_server(self, name: str, command: str, args: List[str] = None):
        self.servers[name] = {
            "command": command,
            "args": args or [],
            "status": "disconnected",
        }
        self.tools[name] = []

    def add_http_server(self, name: str, http_url: str, headers: Optional[dict] = None):
        self.servers[name] = {
            "http_url": str(http_url or "").strip(),
            "headers": headers or {},
            "status": "http",
        }
        self.tools.setdefault(name, [])

    def remove_server(self, name: str) -> bool:
        if name in self.servers:
            del self.servers[name]
            del self.tools[name]
            return True
        return False

    def list_servers(self) -> List[dict]:
        return [
            {"name": name, **info}
            for name, info in self.servers.items()
        ]

    def list_tools(self, server_name: str = None) -> List[dict]:
        if server_name:
            return self.tools.get(server_name, [])
        all_tools = []
        for name, tools in self.tools.items():
            all_tools.extend([{**t, "server": name} for t in tools])
        return all_tools

    def has_server(self, name: str) -> bool:
        return name in self.servers

    def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> str:
        """Call MCP tool over HTTP (JSON-RPC MCP protocol)."""
        if server_name not in self.servers:
            return f"MCP server '{server_name}' not found"

        info = self.servers.get(server_name) or {}
        http_url = str(info.get("http_url") or "").strip()
        if not http_url:
            return f"MCP server '{server_name}' has no http_url configured"
        headers = info.get("headers") if isinstance(info.get("headers"), dict) else {}

        try:
            self._ensure_initialized(server_name, http_url, headers)
            if not self.tools.get(server_name):
                self.tools[server_name] = self._tools_list(server_name, http_url, headers) or []
        except Exception as e:
            return f"MCP init/list failed: {e}"

        chosen = (tool_name or "").strip()
        if not chosen:
            chosen = self._choose_tool_name(self.tools.get(server_name, []))
        if not chosen:
            return "MCP server has no available tools"

        try:
            result = self._rpc(http_url, headers, "tools/call", {"name": chosen, "arguments": arguments or {}})
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f"MCP tool call failed: {e}"

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    def _rpc(self, http_url: str, headers: dict, method: str, params: dict) -> dict:
        body = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        for k, v in (headers or {}).items():
            if isinstance(k, str) and isinstance(v, str) and k.strip():
                h[k.strip()] = v
        req = Request(http_url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=h, method="POST")
        with urlopen(req, timeout=25) as resp:
            raw = resp.read(800000).decode("utf-8", errors="replace")
        data = json.loads(raw) if raw else {}
        if isinstance(data, dict) and "error" in data and data["error"]:
            raise RuntimeError(str(data["error"]))
        if isinstance(data, dict) and "result" in data:
            return data["result"]
        return data if isinstance(data, dict) else {"result": data}

    def _ensure_initialized(self, server_name: str, http_url: str, headers: dict) -> None:
        if server_name in self._initialized:
            return
        init_params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "easy-ai-shell", "version": "1.3.0"},
        }
        self._rpc(http_url, headers, "initialize", init_params)
        try:
            self._rpc(http_url, headers, "notifications/initialized", {})
        except Exception:
            pass
        self._initialized.add(server_name)

    def _tools_list(self, server_name: str, http_url: str, headers: dict) -> list:
        res = self._rpc(http_url, headers, "tools/list", {})
        tools = res.get("tools") if isinstance(res, dict) else None
        if isinstance(tools, list):
            return tools
        return []

    def _choose_tool_name(self, tools: list) -> str:
        names: list[str] = []
        for t in tools or []:
            if isinstance(t, dict) and isinstance(t.get("name"), str):
                names.append(t["name"])
        for cand in ("web_search", "search", "WebSearch", "websearch"):
            if cand in names:
                return cand
        for n in names:
            if "search" in n.lower():
                return n
        return names[0] if names else ""


# ==================== LSP Client ====================

class LSPClient:
    """Simplified LSP client for language server operations"""

    def __init__(self):
        self.servers: Dict[str, dict] = {}
        self.capabilities: Dict[str, dict] = {}

    def add_server(self, name: str, language: str, command: str):
        self.servers[name] = {
            "language": language,
            "command": command,
            "status": "stopped",
        }
        self.capabilities[name] = {
            "hover": True,
            "definition": True,
            "references": True,
            "completion": True,
            "diagnostics": True,
        }

    def remove_server(self, name: str) -> bool:
        if name in self.servers:
            del self.servers[name]
            del self.capabilities[name]
            return True
        return False

    def list_servers(self) -> List[dict]:
        return [
            {"name": name, **info}
            for name, info in self.servers.items()
        ]

    def diagnose(self, file_path: str) -> List[dict]:
        """Get diagnostics for a file (requires LSP server)"""
        return [{
            "file": file_path,
            "severity": "info",
            "message": "LSP diagnostics not available: No LSP server configured. Use 'lsp add <lang> <cmd>' to configure an LSP server."
        }]

    def hover(self, file_path: str, line: int, character: int) -> str:
        """Get hover info (requires LSP server)"""
        return f"[LSP Hover] No LSP server configured. Use 'lsp add <lang> <cmd>' to configure an LSP server.\nRequested: {file_path}:{line}:{character}"

    def definition(self, file_path: str, line: int, character: int) -> str:
        """Go to definition (requires LSP server)"""
        return f"[LSP Definition] No LSP server configured. Use 'lsp add <lang> <cmd>' to configure an LSP server.\nRequested: {file_path}:{line}:{character}"

    def references(self, file_path: str, line: int, character: int) -> List[dict]:
        """Find references (requires LSP server)"""
        return [{
            "file": file_path,
            "line": line,
            "column": character,
            "message": "LSP references not available: No LSP server configured. Use 'lsp add <lang> <cmd>' to configure an LSP server."
        }]

    def completion(self, file_path: str, line: int, character: int) -> List[dict]:
        """Get completions (requires LSP server)"""
        return [{
            "label": "LSP completion unavailable",
            "kind": "info",
            "detail": "No LSP server configured. Use 'lsp add <lang> <cmd>' to configure an LSP server."
        }]


# ==================== Branch Lock ====================

class BranchLock:
    """Branch locking mechanism"""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.lock_dir = workspace / ".easy_ai" / "locks"
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    def lock(self, branch: str, reason: str = "") -> bool:
        lock_file = self.lock_dir / f"{branch.replace('/', '_')}.lock"
        try:
            content = json.dumps({
                "branch": branch,
                "reason": reason,
                "locked_at": datetime.now().isoformat(),
                "locked_by": os.environ.get("USER", "unknown"),
            })
            lock_file.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False

    def unlock(self, branch: str) -> bool:
        lock_file = self.lock_dir / f"{branch.replace('/', '_')}.lock"
        try:
            if lock_file.exists():
                lock_file.unlink()
                return True
        except Exception:
            pass
        return False

    def is_locked(self, branch: str) -> bool:
        lock_file = self.lock_dir / f"{branch.replace('/', '_')}.lock"
        return lock_file.exists()

    def list_locks(self) -> List[dict]:
        locks = []
        try:
            for f in self.lock_dir.glob("*.lock"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    locks.append(data)
                except:
                    pass
        except Exception:
            pass
        return locks


# ==================== Stale Branch Detection ====================

class StaleBranchDetector:
    """Detect stale branches"""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def detect(self, days: int = 90, include_protected: bool = False) -> List[dict]:
        """Detect stale branches older than specified days"""
        stale = []
        protected = ["main", "master", "develop", "dev"]

        try:
            result = subprocess.run(
                ["git", "branch", "-a", "--format=%(refname:short)|%(committerdate:iso)"],
                capture_output=True, text=True, cwd=self.workspace,
                encoding="utf-8", errors="replace"
            )
            if result.returncode != 0:
                return []

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 2:
                    continue

                branch = parts[0].strip()
                date_str = parts[1].strip()

                if branch in protected and not include_protected:
                    continue

                try:
                    branch_date = datetime.fromisoformat(date_str)
                    age_days = (datetime.now() - branch_date).days
                    if age_days >= days:
                        stale.append({
                            "branch": branch,
                            "last_commit": date_str,
                            "days_since": age_days,
                        })
                except Exception:
                    pass
        except Exception:
            pass

        return sorted(stale, key=lambda x: x["days_since"], reverse=True)


# ==================== Plugin System ====================

@dataclass
class Plugin:
    id: str
    name: str
    version: str
    description: str
    enabled: bool = True
    installed_at: datetime = field(default_factory=datetime.now)


class PluginManager:
    """Plugin management system"""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.plugins_dir = workspace / ".easy_ai" / "plugins"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.plugins: Dict[str, Plugin] = {}
        self._load_plugins()

    def _load_plugins(self):
        """Load installed plugins"""
        for f in self.plugins_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                plugin = Plugin(
                    id=data.get("id", f.stem),
                    name=data.get("name", f.stem),
                    version=data.get("version", "1.0.0"),
                    description=data.get("description", ""),
                    enabled=data.get("enabled", True),
                )
                self.plugins[plugin.id] = plugin
            except Exception:
                pass

    def install(self, name: str, source: str = "", description: str = "") -> Plugin:
        """Install a plugin"""
        plugin_id = name.lower().replace(" ", "-")
        plugin = Plugin(
            id=plugin_id,
            name=name,
            version="1.0.0",
            description=description or f"Plugin: {name}",
            enabled=True,
        )
        self.plugins[plugin_id] = plugin
        self._save_plugin(plugin)
        return plugin

    def uninstall(self, plugin_id: str) -> bool:
        """Uninstall a plugin"""
        if plugin_id in self.plugins:
            del self.plugins[plugin_id]
            plugin_file = self.plugins_dir / f"{plugin_id}.json"
            if plugin_file.exists():
                plugin_file.unlink()
            return True
        return False

    def enable(self, plugin_id: str) -> bool:
        """Enable a plugin"""
        if plugin_id in self.plugins:
            self.plugins[plugin_id].enabled = True
            self._save_plugin(self.plugins[plugin_id])
            return True
        return False

    def disable(self, plugin_id: str) -> bool:
        """Disable a plugin"""
        if plugin_id in self.plugins:
            self.plugins[plugin_id].enabled = False
            self._save_plugin(self.plugins[plugin_id])
            return True
        return False

    def list(self) -> List[Plugin]:
        return list(self.plugins.values())

    def _save_plugin(self, plugin: Plugin):
        """Save plugin to disk"""
        plugin_file = self.plugins_dir / f"{plugin.id}.json"
        data = {
            "id": plugin.id,
            "name": plugin.name,
            "version": plugin.version,
            "description": plugin.description,
            "enabled": plugin.enabled,
            "installed_at": plugin.installed_at.isoformat(),
        }
        plugin_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ==================== Session Compact ====================

class SessionCompactor:
    """Session compaction and summarization"""

    def __init__(self, workspace: Path, max_turns: int = 50):
        self.workspace = workspace
        self.max_turns = max_turns
        self.compact_dir = workspace / ".easy_ai" / "compacted"
        self.compact_dir.mkdir(parents=True, exist_ok=True)

    def should_compact(self, history: list) -> bool:
        """Check if compaction is needed"""
        return len(history) > self.max_turns * 2

    def compact(self, history: list, llm_client=None) -> list:
        """Compact session history"""
        if not self.should_compact(history):
            return history

        # Save original history
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        compact_file = self.compact_dir / f"session_{timestamp}.json"
        compact_file.write_text(
            json.dumps(history, indent=2),
            encoding="utf-8"
        )

        # Create summary (simplified - real implementation would use LLM)
        summary = self._create_summary(history)

        # Return compacted history with summary
        compacted = [
            {"role": "system", "content": f"[Session compacted. Summary: {summary}]"}
        ]
        # Keep recent messages
        compacted.extend(history[-20:])

        return compacted

    def _create_summary(self, history: list) -> str:
        """Create session summary"""
        user_msgs = [h["content"] for h in history if h.get("role") == "user"]
        if len(user_msgs) <= 5:
            return "Brief session"
        return f"Session with {len(user_msgs)} user interactions"


# ==================== AutoReview - Memory Consolidation ====================

class AutoReview:
    """
    AutoReview: 后台记忆自动整理机制
    定期整合/去重/修剪记忆文件。
    """

    def __init__(self, workspace: Path, cfg: dict):
        self.workspace = workspace
        self.cfg = cfg.get("memory", {})
        self.enabled = bool(self.cfg.get("autoReviewEnabled", False))
        self.min_hours = int(self.cfg.get("minHours", 24))
        self.min_sessions = int(self.cfg.get("minSessions", 5))
        self.memory_dir = self.cfg.get("memoryDir", ".easy_ai/memory")
        self._last_consolidate = None
        self._lock_file = None

    @property
    def memory_path(self) -> Path:
        return self.workspace / self.memory_dir

    @property
    def topics_index_path(self) -> Path:
        """返回 Topics 索引文件路径（默认 MEMORY.md）。"""
        name = self.cfg.get("topicsIndexFile", "MEMORY.md")
        name = str(name or "MEMORY.md").strip() or "MEMORY.md"
        return self.memory_path / name

    # ----- 门控检查 -----

    def should_review(self) -> tuple[bool, str]:
        """五重门控检查，返回 (should_review, reason)"""
        if not self.enabled:
            return False, "disabled"

        # 1. 功能开关已在上层检查

        # 2. 时间门控
        last_time = self._get_last_consolidate_time()
        if last_time is None:
            # 首次运行，通过
            pass
        else:
            now = datetime.now()
            hours_since = (now - last_time).total_seconds() / 3600
            if hours_since < self.min_hours:
                return False, f"only {hours_since:.1f}h since last review (min {self.min_hours}h)"

        # 3. 扫描限流
        if self._scan_rate_limited():
            return False, "scan rate limited (<10min since last scan)"

        # 4. 会话门控
        new_sessions = self._count_new_sessions()
        # 首次运行或没有现有记忆时，允许通过
        if new_sessions < self.min_sessions and not self._has_existing_memory():
            pass  # 首次运行，通过
        elif new_sessions < self.min_sessions:
            return False, f"only {new_sessions} new sessions (min {self.min_sessions})"

        # 5. 锁门控
        if self._is_locked():
            return False, "another autoreview process is running"

        return True, f"ready: {new_sessions} sessions, {int((datetime.now() - last_time).total_seconds() / 3600) if last_time else 0}h since last"

    def _get_last_consolidate_time(self):
        """获取上次巩固时间"""
        lock = self.memory_path / ".consolidate-lock"
        if lock.exists():
            try:
                mtime = lock.stat().st_mtime
                return datetime.fromtimestamp(mtime)
            except Exception:
                pass
        return None

    def _scan_rate_limited(self) -> bool:
        """检查扫描限流（简化版：检查 lock 文件）"""
        lock = self.memory_path / ".consolidate-lock"
        if lock.exists():
            age = time.time() - lock.stat().st_mtime
            return age < 600  # 10分钟
        return False

    def _count_new_sessions(self) -> int:
        """统计新会话数"""
        mem_dir = self.memory_path
        if not mem_dir.exists():
            return 0
        count = 0
        try:
            last = self._get_last_consolidate_time()
            last_ts = last.timestamp() if isinstance(last, datetime) else 0.0
            for f in mem_dir.glob("session-*.md"):
                if f.stat().st_mtime > last_ts:
                    count += 1
        except Exception:
            pass
        return count

    def _has_existing_memory(self) -> bool:
        """检查是否存在现有记忆文件"""
        mem_dir = self.memory_path
        if not mem_dir.exists():
            return False
        return any(mem_dir.glob("session-*.md"))

    def _is_locked(self) -> bool:
        """检查是否被锁"""
        lock = self.memory_path / ".consolidate-lock"
        if lock.exists():
            age = time.time() - lock.stat().st_mtime
            # 锁超过1小时视为过期
            if age > 3600:
                return False
            return True
        return False

    # ----- 锁管理 -----

    def acquire_lock(self) -> bool:
        """获取锁"""
        lock = self.memory_path / ".consolidate-lock"
        if lock.exists() and self._is_locked():
            return False
        try:
            self.memory_path.mkdir(parents=True, exist_ok=True)
            lock.write_text(f"pid:{os.getpid()}\n")
            return True
        except Exception:
            return False

    def release_lock(self):
        """释放锁"""
        lock = self.memory_path / ".consolidate-lock"
        try:
            lock.unlink()
        except Exception:
            pass

    # ----- 巩固流程 -----

    def autoreview(self, llm_client=None, force: bool = False) -> str:
        """执行四阶段记忆整理；force=True 时跳过门控，用于退出时强制整理一次。"""
        if not self.enabled and not force:
            return "[AutoReview] Disabled"

        if not force:
            should, reason = self.should_review()
            if not should:
                return f"[AutoReview] Skipped: {reason}"

        if not self.acquire_lock():
            return "[AutoReview] Failed to acquire lock"

        try:
            lines = ["[AutoReview] Memory consolidation started"]

            # 阶段1: Orient
            lines.append("[1/4] Orient - Listing memories...")
            memory_files = self._list_memories()
            lines.append(f"  Found {len(memory_files)} memory files")

            # 阶段2: Collect
            lines.append("[2/4] Collect - Gathering recent signals...")
            signals = self._collect_signals()
            lines.append(f"  Collected {len(signals)} signals")

            # 阶段3: Consolidate (需要 LLM)
            if llm_client and signals:
                lines.append("[3/4] Consolidate - Merging memories...")
                self._consolidate(signals, llm_client)
                lines.append("  Consolidation complete")
            else:
                lines.append("[3/4] Consolidate - Skipped (no LLM)")

            # 阶段4: Prune
            lines.append("[4/4] Prune - Indexing memories...")
            self._prune()
            lines.append("  Pruning complete")

            lines.append("AutoReview completed successfully!")
            return "\n".join(lines)

        finally:
            self.release_lock()

    def consolidate_on_exit(self, llm_client=None) -> str:
        """在退出时执行一次记忆整理（跳过门控）。"""
        return self.autoreview(llm_client=llm_client, force=True)

    def _list_memories(self) -> list[Path]:
        """列出所有记忆文件"""
        mem_dir = self.memory_path
        if not mem_dir.exists():
            return []
        return list(mem_dir.glob("session-*.md"))

    def _collect_signals(self) -> list[str]:
        """收集近期信号"""
        signals = []
        for f in self._list_memories():
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if content.strip():
                    signals.append(content[:500])
            except Exception:
                pass
        return signals

    def _consolidate(self, signals: list[str], llm_client):
        """合并记忆（保留为兼容入口；长期记忆编码由 QueryEngine 在退出时处理）。"""
        try:
            mem_dir = self.memory_path
            memory_fp = mem_dir / "MEMORY.md"
            existing = ""
            try:
                if memory_fp.exists():
                    existing = memory_fp.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                existing = ""

            sample = "\n\n".join([s for s in signals[:8] if isinstance(s, str) and s.strip()])
            prompt = (
                "你是一个终端 AI 助手的“记忆编码器”。你的工作是把近期对话碎片编码成可长期复用的协作记忆。\n"
                "要求：\n"
                "1) 必须用中文输出（专有名词/机构名可保留英文）。\n"
                "2) 只输出 Markdown（不要代码块围栏）。\n"
                "3) 只保留稳定、可复用的信息：用户偏好/协作规则/环境事实/默认策略。\n"
                "4) 不要编造事实；不确定就写“未确认”。\n"
                "5) 输出必须包含以下小节（按顺序）：\n"
                "   - # MEMORY.md\n"
                "   - ## 用户偏好与约束\n"
                "   - ## 协作规则与流程\n"
                "   - ## 环境与项目事实\n"
                "   - ## 搜索与证据策略\n"
                "6) 每个小节使用 3-8 条短 bullet；去重合并；不要把临时问题/一次性调试过程写进长期记忆。\n\n"
                f"[现有 MEMORY.md（可能为空）]\n{existing}\n\n"
                f"[近期对话/记忆碎片]\n{sample}\n"
            )
            md = llm_client.chat([], prompt, include_tools=False)
            text = (md or "").strip()
            if not text:
                return
            if not text.lstrip().startswith("# MEMORY.md"):
                text = "# MEMORY.md\n\n" + text
            try:
                memory_fp.write_text(text.strip() + "\n", encoding="utf-8")
            except Exception:
                pass
        except Exception:
            pass

    def _prune(self):
        """修剪和索引"""
        mem_dir = self.memory_path
        index_fp = self.topics_index_path
        max_keep = 50
        try:
            max_keep = int(self.cfg.get("maxSessionFiles", 50))
        except Exception:
            max_keep = 50
        if max_keep < 0:
            max_keep = 0

        sessions = self._list_memories()
        sessions_sorted = sorted(sessions, key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)

        if max_keep and len(sessions_sorted) > max_keep:
            for fp in sessions_sorted[max_keep:]:
                try:
                    fp.unlink()
                except Exception:
                    pass
            sessions_sorted = sessions_sorted[:max_keep]

        lines = ["# MEMORY.md\n", "## Topics\n"]
        for fp in sorted(sessions_sorted, key=lambda p: p.name):
            lines.append(f"- {fp.stem}")
        try:
            index_fp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass


# ==================== LLM Client ====================

class LLMClient:
    """Generic LLM client that supports OpenAI-compatible APIs and Anthropic."""

    def __init__(self, cfg: dict):
        llm = cfg.get("llm", {})
        self.provider  = llm.get("provider", "openai").lower()
        self.model     = llm.get("model", "gpt-4o")
        self.api_key   = llm.get("api_key", "")
        self.base_url  = llm.get("base_url", "https://api.openai.com/v1").rstrip("/")
        self.max_tokens = int(llm.get("max_tokens", 4096))
        self.temperature = float(llm.get("temperature", 0.7))
        self.system_prompt = llm.get(
            "system_prompt",
            "You are a helpful AI coding assistant running in a terminal shell."
        )
        self._enabled = bool(self.api_key)

        providers = cfg.get("_providers") or {}
        if isinstance(providers, dict):
            info = providers.get(self.provider)
            if isinstance(info, dict):
                if llm.get("base_url", "") in ("", DEFAULT_CONFIG["llm"]["base_url"]):
                    base = info.get("base_url")
                    if isinstance(base, str) and base.strip():
                        self.base_url = base.rstrip("/")
                if llm.get("model", "") in ("", DEFAULT_CONFIG["llm"]["model"]):
                    models = info.get("models")
                    if isinstance(models, list) and models:
                        m0 = models[0]
                        if isinstance(m0, str) and m0.strip():
                            self.model = m0

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_system_prompt(self, include_tools: bool = True) -> str:
        """Get the system prompt, optionally including tool definitions"""
        if not include_tools:
            return self.system_prompt

        agent_rules = """
## Agent Rules (Must Follow)
- When the user asks for changes, you must actually do them by calling tools, not just describe a plan.
- If the task needs multiple steps, keep calling tools and iterating until it is done.
- For multi-step tasks, maintain a short todo list and complete items as you finish them (use TodoWriteTool when an active task exists; otherwise keep it inline).
- Default output language is Chinese. All final answers and summaries must be in Chinese unless the user explicitly asks for another language.
- Only give a final answer when the work is complete (or you are blocked and have explained why).
- Prefer small, safe actions first: inspect files, then edit/write, then verify via commands if needed.
- Never fabricate external project contents. If the user asks about a GitHub repo or web content, you must fetch it (WebFetchTool / WebSearchTool / NewsSearchTool) or clone it (BashTool git), then summarize based on evidence.
- For "latest news" requests, first call NewsSearchTool to get recent links, then call WebFetchTool to read a few sources, then summarize.
- For general web research, first call WebSearchTool to get candidate links, then call WebFetchTool on the most relevant sources, then summarize with sources.
- Do not use BashTool to browse/search the web. Use WebSearchTool/NewsSearchTool/WebFetchTool for web research.
- If you feel blocked, try to unblock yourself using available tools (FileSearchTool/GrepTool/GlobTool, WebSearchTool/WebFetchTool, NewsSearchTool) before asking the user.
- Do not create random project skeletons unless the user explicitly asked you to generate code.
- For tool-heavy tasks, keep todos scoped to the current task only; do not mix unrelated tasks.
"""
        
        # Build tool definitions
        tools_text = "\n\n## Available Tools\n\n"
        for name, tool in TOOL_DESCRIPTIONS.items():
            tools_text += f"### {tool['name']}\n"
            tools_text += f"{tool['description']}\n"
            tools_text += f"Input: {json.dumps(tool['input_schema'], indent=2)}\n\n"
        
        tools_text += """
## Output Format

When you need to use a tool, output a JSON block like this:

```json
{
  "tool": "ToolName",
  "input": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

If you don't need a tool, just respond normally.

After getting tool results, continue reasoning or provide your final answer.
"""
        return self.system_prompt + agent_rules + tools_text

    def chat(self, history: list[dict], user_message: str, include_tools: bool = True) -> str:
        if not self.enabled:
            return colored(
                "[AI] No API key configured. Edit config.json and set llm.api_key.",
                Color.YELLOW,
            )

        messages = [{"role": "system", "content": self.get_system_prompt(include_tools)}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        if self.provider == "anthropic":
            return self._call_anthropic(messages)
        else:
            return self._call_openai_compat(messages)

    def _call_openai_compat(self, messages: list[dict]) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        return self._http_post(url, payload, headers)

    def _call_anthropic(self, messages: list[dict]) -> str:
        url = f"{self.base_url}/v1/messages"
        system_content = ""
        filtered = []
        for m in messages:
            if m["role"] == "system":
                system_content = m["content"]
            else:
                filtered.append(m)

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_content,
            "messages": filtered,
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        return self._http_post(url, payload, headers, anthropic=True)

    def _http_post(self, url: str, payload: dict, headers: dict, anthropic: bool = False) -> str:
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers=headers, method="POST")
        try:
            with urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            return colored(f"[AI] HTTP {e.code}: {err_body[:300]}", Color.RED)
        except URLError as e:
            return colored(f"[AI] Connection error: {e.reason}", Color.RED)
        except Exception as e:
            return colored(f"[AI] Error: {e}", Color.RED)

        try:
            if anthropic:
                return body["content"][0]["text"]
            else:
                return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            return colored(f"[AI] Unexpected response format: {body}", Color.RED)


# ==================== Tool Call Parser ====================

class ToolCallParser:
    """Parse tool calls from LLM output"""

    @staticmethod
    def _extract_fenced_blocks(text: str) -> List[str]:
        blocks = []
        for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE):
            block = (m.group(1) or "").strip()
            if block:
                blocks.append(block)
        return blocks

    @staticmethod
    def _extract_json_objects(text: str) -> List[str]:
        objs = []
        i = 0
        n = len(text)
        in_str = False
        esc = False
        depth = 0
        start = -1
        while i < n:
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == "}":
                    if depth > 0:
                        depth -= 1
                        if depth == 0 and start != -1:
                            objs.append(text[start:i + 1])
                            start = -1
            i += 1
        return objs

    @staticmethod
    def _decode_tool_calls(candidate: str) -> List["ToolCall"]:
        out: List[ToolCall] = []
        s = candidate.strip()
        if not s:
            return out
        try:
            data = json.loads(s)
        except json.JSONDecodeError:
            left = s.find("{")
            right = s.rfind("}")
            if left != -1 and right != -1 and right > left:
                try:
                    data = json.loads(s[left:right + 1])
                except Exception:
                    return out
            else:
                return out

        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            tool = item.get("tool") or item.get("Tool") or item.get("name")
            tool_input = item.get("input") or item.get("arguments") or item.get("params") or {}
            if tool and isinstance(tool_input, dict):
                out.append(ToolCall(tool_name=str(tool), tool_input=tool_input, raw_json=json.dumps(item, ensure_ascii=False)))
        return out
    
    @classmethod
    def parse(cls, text: str) -> List[ToolCall]:
        """Extract tool calls from LLM response text"""
        tool_calls: List[ToolCall] = []
        seen = set()

        for block in cls._extract_fenced_blocks(text):
            for tc in cls._decode_tool_calls(block):
                key = (tc.tool_name, json.dumps(tc.tool_input, sort_keys=True, ensure_ascii=False))
                if key not in seen:
                    seen.add(key)
                    tool_calls.append(tc)

        if tool_calls:
            return tool_calls

        for obj in cls._extract_json_objects(text):
            if '"tool"' not in obj and "'tool'" not in obj:
                continue
            for tc in cls._decode_tool_calls(obj):
                key = (tc.tool_name, json.dumps(tc.tool_input, sort_keys=True, ensure_ascii=False))
                if key not in seen:
                    seen.add(key)
                    tool_calls.append(tc)

        if tool_calls:
            return tool_calls

        for tc in cls._decode_seed_function_calls(text):
            key = (tc.tool_name, json.dumps(tc.tool_input, sort_keys=True, ensure_ascii=False))
            if key not in seen:
                seen.add(key)
                tool_calls.append(tc)

        return tool_calls

    @staticmethod
    def _decode_seed_function_calls(text: str) -> List["ToolCall"]:
        """兼容部分模型输出的 <function=...> ... </function> 格式为内部工具调用。"""
        out: List[ToolCall] = []
        if not isinstance(text, str) or not text:
            return out

        for m in re.finditer(r"<function=([a-zA-Z0-9_]+)>([\s\S]*?)</function>", text):
            fn = (m.group(1) or "").strip().lower()
            body = m.group(2) or ""
            if fn in ("sequentialthinking",):
                continue

            params: dict = {}
            for pm in re.finditer(r"<parameter=([^>]+)>([\s\S]*?)</parameter>", body):
                k = (pm.group(1) or "").strip()
                v = (pm.group(2) or "").strip()
                if k:
                    params[k] = v

            tool_name = ""
            if fn in ("websearch", "web_search"):
                tool_name = "WebSearchTool"
            elif fn in ("newssearch", "news_search"):
                tool_name = "NewsSearchTool"
            elif fn in ("webfetch", "web_fetch"):
                tool_name = "WebFetchTool"
            elif fn in ("shell_exec", "bash"):
                tool_name = "BashTool"
            elif fn == "grep":
                tool_name = "GrepTool"
            elif fn == "glob":
                tool_name = "GlobTool"

            if tool_name:
                out.append(ToolCall(tool_name=tool_name, tool_input=params, raw_json=""))

        if out:
            return out

        lm = re.search(r"<list>\s*<folderPath>([\s\S]*?)</folderPath>\s*</list>", text)
        if lm:
            folder = (lm.group(1) or "").strip() or "."
            out.append(ToolCall(tool_name="BashTool", tool_input={"command": f"ls -la {folder}"}, raw_json=""))
        return out
    
    @classmethod
    def is_final_response(cls, text: str) -> bool:
        """Check if the response is a final answer (no tool calls)"""
        return len(cls.parse(text)) == 0


# ==================== Execution Registry ====================

class Registry:
    """Command & tool execution registry"""

    def __init__(self, workspace: Optional[Path] = None, cfg: dict = None):
        self.workspace = workspace or Path.cwd()
        self.cfg = cfg or {}

        # Initialize subsystems
        self.permission = PermissionSystem(self.cfg, workspace=self.workspace)
        self.task_registry = TaskRegistry()
        self.todo_registry = TodoRegistry()
        self.current_task_id: Optional[str] = None
        self.current_task_doc_path: Optional[Path] = None
        self.team_registry = TeamRegistry(data_path=self.workspace / ".easy_ai" / "teams.json")
        self.cron_registry = CronRegistry(data_path=self.workspace / ".easy_ai" / "cronjobs.json")
        self.mcp_client = MCPClient()
        self.lsp_client = LSPClient()
        self.branch_lock = BranchLock(self.workspace)
        self.stale_detector = StaleBranchDetector(self.workspace)
        self.plugin_manager = PluginManager(self.workspace)
        self.compactor = SessionCompactor(self.workspace)
        self._load_mcp_servers_from_config()

    def _load_mcp_servers_from_config(self) -> None:
        cfg = self.cfg or {}
        servers = cfg.get("mcp_servers") if isinstance(cfg, dict) else None
        if not isinstance(servers, dict):
            return
        for name, info in servers.items():
            if not isinstance(name, str) or not isinstance(info, dict):
                continue
            url = info.get("httpUrl") or info.get("baseUrl") or info.get("url")
            headers = info.get("headers") if isinstance(info.get("headers"), dict) else {}
            if isinstance(headers, dict):
                h2 = {}
                for k, v in headers.items():
                    if isinstance(k, str) and isinstance(v, str):
                        vv = v
                        for m in re.finditer(r"\$\{([A-Z0-9_]+)\}", v):
                            env = os.environ.get(m.group(1), "")
                            if env:
                                vv = vv.replace(m.group(0), env)
                        h2[k] = vv
                    else:
                        h2[k] = v
                headers = h2
            if isinstance(url, str) and url.strip():
                self.mcp_client.add_http_server(name.strip(), url.strip(), headers=headers)

    def set_workspace(self, workspace: Path) -> ExecutionResult:
        try:
            w = Path(workspace).expanduser().resolve()
        except Exception as e:
            return ExecutionResult(False, "", str(e))
        if not w.exists() or not w.is_dir():
            return ExecutionResult(False, "", f"Not a directory: {w}")
        self.workspace = w
        self.permission.set_workspace(self.workspace)
        self.current_task_id = None
        self.current_task_doc_path = None
        self.branch_lock = BranchLock(self.workspace)
        self.stale_detector = StaleBranchDetector(self.workspace)
        self.plugin_manager = PluginManager(self.workspace)
        self.compactor = SessionCompactor(self.workspace)
        self._load_mcp_servers_from_config()
        return ExecutionResult(True, f"Workspace set to: {self.workspace}")

    def run_command(self, name: str, args: str = "") -> ExecutionResult:
        n = name.lower()
        handlers = {
            "files":    lambda: self._cmd_files(args),
            "status":   lambda: self._cmd_shell("git status"),
            "diff":     lambda: self._cmd_shell("git diff --stat"),
            "log":      lambda: self._cmd_shell("git log --oneline -10"),
            "commit":   lambda: self._cmd_commit(args),
            "push":     lambda: self._cmd_shell("git push"),
            "pull":     lambda: self._cmd_shell("git pull"),
            "branch":   lambda: self._cmd_shell("git branch -a"),
            "run":      lambda: self._cmd_shell(args) if args else ExecutionResult(False, "", "Provide a command: run <cmd>"),
            "test":     lambda: self._cmd_pkg_script("test"),
            "build":    lambda: self._cmd_pkg_script("build"),
            "install":  lambda: self._cmd_pkg_script("install"),
            "help":     lambda: self._cmd_help(),
            "version":  lambda: ExecutionResult(True, "Easy AI Shell v1.3.0 (Agent Mode)"),
            "context":  lambda: self._cmd_context(),
            "clear":    lambda: ExecutionResult(True, "", special="CLEAR"),
            "exit":     lambda: ExecutionResult(True, "", special="EXIT"),
            "quit":     lambda: ExecutionResult(True, "", special="EXIT"),
            "compact":  lambda: self._cmd_compact(),
            "autoreview": lambda: self._cmd_autoreview(),
            "memory":   lambda: self._cmd_memory(args),
            # Task commands
            "task":     lambda: self._cmd_task(args),
            # Team commands
            "team":     lambda: self._cmd_team(args),
            # Cron commands
            "cron":     lambda: self._cmd_cron(args),
            # MCP commands
            "mcp":      lambda: self._cmd_mcp(args),
            # LSP commands
            "lsp":      lambda: self._cmd_lsp(args),
            # Plugin commands
            "plugin":   lambda: self._cmd_plugin(args),
            # Branch lock commands
            "lock":     lambda: self._cmd_lock(args),
            # Stale branch commands
            "stale":    lambda: self._cmd_stale(args),
            # Permission commands
            "permissions": lambda: self._cmd_permissions(args),
            "workspace":   lambda: self._cmd_workspace(args),
            "cd":          lambda: self._cmd_workspace(args),
        }
        fn = handlers.get(n)
        if fn:
            return fn()
        return ExecutionResult(True, f"Command '{name}' dispatched with args: {args!r}")

    def _task_root_dir(self, task_id: str) -> Path:
        return self.workspace / ".easy_ai" / "tasks" / task_id

    def _task_checklist_path(self, task_id: str) -> Path:
        return self._task_root_dir(task_id) / "checklist.md"

    def _sync_task_checklist_file(self, task_id: str) -> None:
        todos = self.todo_registry.list(task_id)
        lines = ["# checklist.md", "", "## Task Checklist"]
        if not todos:
            lines.append("- [ ] (暂无任务清单)")
        else:
            for t in sorted(todos, key=lambda x: x.created_at):
                mark = "x" if t.status == TaskStatus.COMPLETED else " "
                lines.append(f"- [{mark}] {t.description} ({t.id})")
        fp = self._task_checklist_path(task_id)
        try:
            fp.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            fp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass

    def _restore_todos_from_checklist(self, task_id: str) -> int:
        fp = self._task_checklist_path(task_id)
        if not fp.exists():
            return 0
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return 0
        restored = 0
        for line in (text or "").splitlines():
            m = re.match(r"^\s*-\s*\[( |x|X)\]\s*(.+?)\s*\((todo-[0-9a-fA-F]+)\)\s*$", line)
            if not m:
                continue
            done = (m.group(1) or "").strip().lower() == "x"
            desc = (m.group(2) or "").strip()
            tid = (m.group(3) or "").strip()
            if not tid:
                continue
            self.todo_registry.restore(task_id, tid, desc, status=(TaskStatus.COMPLETED if done else TaskStatus.PENDING))
            restored += 1
        return restored

    def _is_bash_web_access(self, command: str) -> bool:
        """判断 Bash 命令是否在进行联网抓取/搜索网页（避免触发权限弹窗，统一走 WebSearch/NewsSearch/WebFetch）。"""
        if not isinstance(command, str) or not command.strip():
            return False
        s = command.strip().lower()
        if "http://" in s or "https://" in s:
            return True
        first = ""
        try:
            parts = shlex.split(command.strip())
            first = (parts[0] if parts else "").lower()
        except Exception:
            first = ""
        if first in ("curl", "wget"):
            return True
        if " news.google.com" in (" " + s) or " google.com" in (" " + s):
            return True
        return False

    def _web_cfg(self) -> dict:
        """返回 web 配置段（容错为 dict）。"""
        w = (self.cfg or {}).get("web", {})
        return w if isinstance(w, dict) else {}

    def _default_blocked_domains(self) -> list[str]:
        """默认屏蔽的低质量/反爬/问答类域名，用于提升检索有效性。"""
        raw = self._web_cfg().get("blocked_domains", [])
        out: list[str] = []
        if isinstance(raw, str):
            raw = re.split(r"[,\s]+", raw.strip())
        if isinstance(raw, list):
            for it in raw:
                if isinstance(it, str) and it.strip():
                    out.append(it.strip().lower())
        return out

    def _default_news_allowed_domains(self) -> list[str]:
        """可选：新闻检索的白名单域名（为空表示不启用白名单）。"""
        raw = self._web_cfg().get("news_allowed_domains", [])
        out: list[str] = []
        if isinstance(raw, str):
            raw = re.split(r"[,\s]+", raw.strip())
        if isinstance(raw, list):
            for it in raw:
                if isinstance(it, str) and it.strip():
                    out.append(it.strip().lower())
        return out

    def _default_news_blocked_domains(self) -> list[str]:
        """新闻检索的默认黑名单域名（优先使用 news_blocked_domains，否则回退 blocked_domains）。"""
        raw = self._web_cfg().get("news_blocked_domains", None)
        if raw is None:
            return self._default_blocked_domains()
        out: list[str] = []
        if isinstance(raw, str):
            raw = re.split(r"[,\s]+", raw.strip())
        if isinstance(raw, list):
            for it in raw:
                if isinstance(it, str) and it.strip():
                    out.append(it.strip().lower())
        return out

    def run_tool(self, name: str, payload: str = "") -> ExecutionResult:
        tool_name = TOOL_ALIASES.get(name.lower(), name) if isinstance(name, str) else name
        payload_dict = self._normalize_tool_payload(tool_name, payload)
        payload_str = json.dumps(payload_dict, ensure_ascii=False)

        if tool_name == "BashTool":
            cmd = payload_dict.get("command", "")
            if self._is_bash_web_access(cmd):
                return ExecutionResult(
                    False,
                    "",
                    "Web access via BashTool is disabled. Use NewsSearchTool/WebSearchTool to find links, then WebFetchTool to fetch sources.",
                )

        allowed, reason = self.permission.authorize_or_prompt(tool_name, payload_str)
        if not allowed:
            return ExecutionResult(False, "", f"Permission denied: {reason}")

        if tool_name == "FileReadTool":
            return self._tool_read(payload_dict.get("file_path", ""))
        if tool_name == "FileWriteTool":
            fp = payload_dict.get("file_path", "")
            content = payload_dict.get("content", "")
            return self._tool_write(f"{fp}::{content}")
        if tool_name == "BashTool":
            return self._cmd_shell(payload_dict.get("command", ""))
        if tool_name in ("GrepTool", "FileSearchTool"):
            pat = payload_dict.get("pattern", "")
            pth = payload_dict.get("path", ".")
            return self._tool_grep(f"{pat}::{pth}")
        if tool_name == "GlobTool":
            return self._tool_glob(payload_dict.get("pattern", "*"))
        if tool_name == "TodoWriteTool":
            return self._tool_todo(payload_dict)
        if tool_name == "TaskTool":
            return self._cmd_task(payload_dict.get("args", "") or "")
        if tool_name == "MCPTool":
            return self._cmd_mcp(payload_dict.get("args", "") or "")
        if tool_name == "LSPTool":
            return self._cmd_lsp(payload_dict.get("args", "") or "")
        if tool_name == "WebFetchTool":
            return self._tool_web_fetch(payload_dict)
        if tool_name == "WebSearchTool":
            return self._tool_web_search(payload_dict)
        if tool_name == "NewsSearchTool":
            return self._tool_news_search(payload_dict)
        if tool_name == "FileEditTool":
            return ExecutionResult(True, f"FileEditTool ready for: {payload_str}")
        return ExecutionResult(True, f"Tool '{tool_name}' ready. Payload: {payload_str}")

    def _normalize_tool_payload(self, tool_name: str, payload: Any) -> dict:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return payload
        if not isinstance(payload, str):
            return {"value": str(payload)}

        s = payload.strip()
        if not s:
            return {}

        if s.startswith("{") and s.endswith("}"):
            try:
                data = json.loads(s)
                return data if isinstance(data, dict) else {"value": data}
            except Exception:
                pass

        if tool_name == "FileReadTool":
            return {"file_path": s}
        if tool_name == "FileWriteTool":
            if "::" in s:
                p, c = s.split("::", 1)
                return {"file_path": p.strip(), "content": c}
            return {"file_path": s, "content": ""}
        if tool_name in ("GrepTool", "FileSearchTool"):
            if "::" in s:
                pat, pth = s.split("::", 1)
                return {"pattern": pat.strip(), "path": (pth.strip() or ".")}
            return {"pattern": s, "path": "."}
        if tool_name == "GlobTool":
            return {"pattern": s or "*"}
        if tool_name == "BashTool":
            return {"command": s}
        if tool_name in ("TaskTool", "MCPTool", "LSPTool"):
            return {"args": s}
        if tool_name == "TodoWriteTool":
            try:
                data = json.loads(s)
                return data if isinstance(data, dict) else {"value": data}
            except Exception:
                return {"action": "create", "content": s}
        if tool_name == "WebFetchTool":
            return {"url": s}
        if tool_name == "WebSearchTool":
            try:
                data = json.loads(s)
                return data if isinstance(data, dict) else {"query": str(data)}
            except Exception:
                return {"query": s}
        if tool_name == "NewsSearchTool":
            try:
                data = json.loads(s)
                return data if isinstance(data, dict) else {"query": str(data)}
            except Exception:
                return {"query": s}
        return {"value": s}

    # ----- Command implementations -----

    def _cmd_files(self, args: str) -> ExecutionResult:
        target = self.workspace / (args.strip() or ".")
        try:
            items = sorted(target.iterdir()) if target.is_dir() else [target]
            lines = []
            for p in items[:50]:
                icon = "[DIR]" if p.is_dir() else "[FILE]"
                size = f"  {p.stat().st_size:>8,} bytes" if p.is_file() else ""
                lines.append(f"  {icon} {p.name}{size}")
            out = f"Contents of {target}:\n" + "\n".join(lines)
            if len(items) == 50:
                out += "\n  ... (truncated to 50)"
            return ExecutionResult(True, out)
        except Exception as e:
            return ExecutionResult(False, "", str(e))

    def _cmd_commit(self, args: str) -> ExecutionResult:
        if not args.strip():
            args = "auto: update"
        # 转义危险的shell字符，防止命令注入
        # 移除引号、反斜杠和分号等可能导致命令注入的字符
        safe_message = args.replace('"', '\\"').replace("'", "\\'").replace(";", " ").replace("&", " ").replace("|", " ").replace("\n", " ").strip()
        if not safe_message:
            safe_message = "auto: update"
        return self._cmd_shell(f'git add -A && git commit -m "{safe_message}"')

    def _cmd_context(self) -> ExecutionResult:
        py_files  = list(self.workspace.rglob("*.py"))
        js_files  = list(self.workspace.rglob("*.ts")) + list(self.workspace.rglob("*.js"))
        lines = [
            f"Workspace: {self.workspace}",
            f"Python files: {len(py_files)}",
            f"TypeScript/JavaScript files: {len(js_files)}",
            f"Has git: {(self.workspace / '.git').exists()}",
        ]
        for name in ("README.md", "README.txt", "readme.md"):
            p = self.workspace / name
            if p.exists():
                lines.append(f"\nREADME ({name}):")
                lines.append(p.read_text(encoding="utf-8", errors="ignore")[:500])
                break
        return ExecutionResult(True, "\n".join(lines))

    def _cmd_autoreview(self) -> ExecutionResult:
        cfg = load_config()
        ad = AutoReview(self.workspace, cfg)
        if not ad.enabled:
            return ExecutionResult(True,
                "AutoReview is disabled.\nSet memory.autoReviewEnabled: true in config.json to enable.")
        should, reason = ad.should_review()
        if not should:
            return ExecutionResult(True, f"[AutoReview] Skipped: {reason}")
        result = ad.autoreview(None)
        return ExecutionResult(True, result)

    def _cmd_workspace(self, args: str) -> ExecutionResult:
        p = (args or "").strip()
        if not p:
            return ExecutionResult(True, f"Current workspace: {self.workspace}")
        return self.set_workspace(Path(p))

    def _cmd_compact(self) -> ExecutionResult:
        result = self.compactor.compact([], None)
        return ExecutionResult(True, f"Session compacted. Remaining history: {len(result)} messages")

    def _cmd_permissions(self, args: str) -> ExecutionResult:
        """Permission mode commands"""
        parts = args.strip().split()
        if not parts:
            mode = self.permission.get_mode()
            return ExecutionResult(True, f"Current permission mode: {mode}")
        subcmd = parts[0].lower()
        if subcmd == "set" and len(parts) > 1:
            self.permission.set_mode(parts[1])
            return ExecutionResult(True, f"Permission mode set to: {parts[1]}")
        elif subcmd == "list":
            return ExecutionResult(True, f"Mode: {self.permission.get_mode()}")
        return ExecutionResult(True, "Usage: permissions [set <mode>|list]")

    def _cmd_memory(self, args: str) -> ExecutionResult:
        """Memory management commands"""
        cfg = load_config()
        ad = AutoReview(self.workspace, cfg)
        if not ad.enabled:
            return ExecutionResult(False, "", "AutoReview/Memory is disabled in config.json")
        
        parts = args.strip().split(None, 1)
        subcmd = parts[0].lower() if parts else "list"
        
        if subcmd == "list":
            mem_files = ad._list_memories()
            if not mem_files:
                return ExecutionResult(True, "No memory files found.")
            lines = ["Memory Files:"]
            for f in mem_files:
                mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                size = f.stat().st_size
                lines.append(f"  {f.name} ({size} bytes, modified: {mtime})")
            return ExecutionResult(True, "\n".join(lines))
        elif subcmd == "show" and len(parts) > 1:
            name = parts[1]
            if not name.endswith(".md"):
                name += ".md"
            fp = ad.memory_path / name
            if fp.exists():
                return ExecutionResult(True, fp.read_text(encoding="utf-8", errors="replace"))
            return ExecutionResult(False, "", f"Memory file not found: {name}")
        return ExecutionResult(True, "Usage: memory [list | show <name>]")

    def _cmd_task(self, args: str) -> ExecutionResult:
        """Task management"""
        parts = args.strip().split(None, 1)
        subcmd = parts[0].lower() if parts else "list"
        arg = parts[1] if len(parts) > 1 else ""

        if subcmd == "create":
            task = self.task_registry.create(arg or "New task", arg)
            return ExecutionResult(True, f"Created task: {task.id}")
        elif subcmd == "use" and arg:
            task = self.task_registry.get(arg)
            if not task:
                return ExecutionResult(False, "", f"Task not found: {arg}")
            self.current_task_id = task.id
            self.current_task_doc_path = None
            return ExecutionResult(True, f"Current task set to: {task.id}")
        elif subcmd == "resume" and arg:
            task_id = arg.strip()
            root = self._task_root_dir(task_id)
            index_fp = root / "index.json"
            doc_fp = root / "task.md"
            if not root.exists():
                return ExecutionResult(False, "", f"Task folder not found: {root}")
            desc = task_id
            prompt = ""
            try:
                if index_fp.exists():
                    data = json.loads(index_fp.read_text(encoding="utf-8", errors="replace") or "{}")
                    if isinstance(data, dict):
                        desc = str(data.get("description") or desc)
                        prompt = str(data.get("prompt") or "")
            except Exception:
                pass
            if not self.task_registry.get(task_id):
                self.task_registry.restore(task_id, desc or task_id, prompt or "", status=TaskStatus.RUNNING)
            self.current_task_id = task_id
            self.current_task_doc_path = doc_fp if doc_fp.exists() else None
            self.todo_registry.clear(task_id)
            restored = self._restore_todos_from_checklist(task_id)
            return ExecutionResult(True, f"Resumed task: {task_id} (restored todos: {restored})")
        elif subcmd == "current":
            if not self.current_task_id:
                return ExecutionResult(True, "No active task")
            return ExecutionResult(True, f"Current task: {self.current_task_id}")
        elif subcmd == "close":
            target = arg or (self.current_task_id or "")
            if not target:
                return ExecutionResult(False, "", "No task to close")
            if not self.task_registry.get(target):
                return ExecutionResult(False, "", f"Task not found: {target}")
            self.task_registry.update(target, status=TaskStatus.COMPLETED, completed_at=datetime.now())
            if self.current_task_id == target:
                self.current_task_id = None
                self.current_task_doc_path = None
            return ExecutionResult(True, f"Closed task: {target}")
        elif subcmd == "list":
            tasks = self.task_registry.list()
            if not tasks:
                return ExecutionResult(True, "No tasks")
            lines = ["Tasks:"]
            for t in tasks[:10]:
                lines.append(f"  [{t.status}] {t.id}: {t.description}")
            return ExecutionResult(True, "\n".join(lines))
        elif subcmd == "get" and arg:
            task = self.task_registry.get(arg)
            if task:
                return ExecutionResult(True, json.dumps(task.to_dict(), indent=2))
            return ExecutionResult(False, "", f"Task not found: {arg}")
        elif subcmd == "stop" and arg:
            if self.task_registry.stop(arg):
                return ExecutionResult(True, f"Stopped task: {arg}")
            return ExecutionResult(False, "", f"Failed to stop: {arg}")
        return ExecutionResult(True, "Task commands: create <desc>, list, get <id>, use <id>, resume <id>, current, close [id], stop <id>")

    def _cmd_team(self, args: str) -> ExecutionResult:
        """Team management"""
        parts = args.strip().split(None, 1)
        subcmd = parts[0].lower() if parts else "list"
        arg = parts[1] if len(parts) > 1 else ""

        if subcmd == "create":
            team = self.team_registry.create(arg or "New team", arg)
            return ExecutionResult(True, f"Created team: {team.id}")
        elif subcmd == "list":
            teams = self.team_registry.list()
            if not teams:
                return ExecutionResult(True, "No teams")
            lines = ["Teams:"]
            for t in teams:
                lines.append(f"  {t.id}: {t.name}")
            return ExecutionResult(True, "\n".join(lines))
        elif subcmd == "delete" and arg:
            if self.team_registry.delete(arg):
                return ExecutionResult(True, f"Deleted team: {arg}")
            return ExecutionResult(False, "", f"Team not found: {arg}")
        return ExecutionResult(True, "Team commands: create <name>, list, delete <id>")

    def _cmd_cron(self, args: str) -> ExecutionResult:
        """Cron job management"""
        parts = args.strip().split(None, 3)
        subcmd = parts[0].lower() if parts else "list"
        name = parts[1] if len(parts) > 1 else ""
        command = parts[2] if len(parts) > 2 else ""
        schedule = parts[3] if len(parts) > 3 else ""

        if subcmd == "create":
            if not name or not command or not schedule:
                return ExecutionResult(False, "", "Usage: cron create <name> <command> <schedule>")
            job = self.cron_registry.create(name, command, schedule)
            return ExecutionResult(True, f"Created cron job: {job.id}")
        elif subcmd == "list":
            jobs = self.cron_registry.list()
            if not jobs:
                return ExecutionResult(True, "No cron jobs")
            lines = ["Cron Jobs:"]
            for j in jobs:
                status = "enabled" if j.enabled else "disabled"
                lines.append(f"  [{status}] {j.id}: {j.name} ({j.schedule})")
            return ExecutionResult(True, "\n".join(lines))
        elif subcmd == "delete" and name:
            if self.cron_registry.delete(name):
                return ExecutionResult(True, f"Deleted cron job: {name}")
            return ExecutionResult(False, "", f"Cron job not found: {name}")
        elif subcmd == "enable" and name:
            if self.cron_registry.enable(name):
                return ExecutionResult(True, f"Enabled cron job: {name}")
            return ExecutionResult(False, "", f"Cron job not found: {name}")
        elif subcmd == "disable" and name:
            if self.cron_registry.disable(name):
                return ExecutionResult(True, f"Disabled cron job: {name}")
            return ExecutionResult(False, "", f"Cron job not found: {name}")
        return ExecutionResult(True, "Cron commands: create <name> <schedule>, list, delete <id>, enable <id>, disable <id>")

    def _cmd_mcp(self, args: str) -> ExecutionResult:
        """MCP server management"""
        parts = args.strip().split(None, 2)
        subcmd = parts[0].lower() if parts else "list"
        name = parts[1] if len(parts) > 1 else ""
        rest = parts[2] if len(parts) > 2 else ""

        if subcmd == "add":
            if not name:
                return ExecutionResult(False, "", "Usage: mcp add <name> <command>")
            self.mcp_client.add_server(name, rest, [])
            return ExecutionResult(True, f"Added MCP server: {name}")
        elif subcmd == "list":
            servers = self.mcp_client.list_servers()
            if not servers:
                return ExecutionResult(True, "No MCP servers")
            lines = ["MCP Servers:"]
            for s in servers:
                lines.append(f"  {s['name']}: {s.get('command', 'N/A')}")
            return ExecutionResult(True, "\n".join(lines))
        elif subcmd == "remove" and name:
            if self.mcp_client.remove_server(name):
                return ExecutionResult(True, f"Removed MCP server: {name}")
            return ExecutionResult(False, "", f"MCP server not found: {name}")
        elif subcmd == "tools":
            tools = self.mcp_client.list_tools(name or None)
            if not tools:
                return ExecutionResult(True, "No MCP tools")
            lines = ["MCP Tools:"]
            for t in tools:
                lines.append(f"  {t.get('server', 'unknown')}.{t.get('name', 'unknown')}")
            return ExecutionResult(True, "\n".join(lines))
        return ExecutionResult(True, "MCP commands: add <name> <cmd>, list, remove <name>, tools [server]")

    def _cmd_lsp(self, args: str) -> ExecutionResult:
        """LSP operations"""
        parts = args.strip().split(None, 2)
        subcmd = parts[0].lower() if parts else "list"
        name = parts[1] if len(parts) > 1 else ""
        rest = parts[2] if len(parts) > 2 else ""

        if subcmd == "add":
            if not name or not rest:
                return ExecutionResult(False, "", "Usage: lsp add <language> <command>")
            self.lsp_client.add_server(name, name, rest)
            return ExecutionResult(True, f"Added LSP server for: {name}")
        elif subcmd == "list":
            servers = self.lsp_client.list_servers()
            if not servers:
                return ExecutionResult(True, "No LSP servers")
            lines = ["LSP Servers:"]
            for s in servers:
                lines.append(f"  {s['name']}: {s.get('language', 'unknown')}")
            return ExecutionResult(True, "\n".join(lines))
        elif subcmd == "diagnose" and name:
            diagnostics = self.lsp_client.diagnose(name)
            if not diagnostics:
                return ExecutionResult(True, "No diagnostics")
            return ExecutionResult(True, json.dumps(diagnostics, indent=2))
        elif subcmd == "hover" and name and rest:
            parts = rest.split(":")
            result = self.lsp_client.hover(name, int(parts[0]), int(parts[1])) if len(parts) >= 2 else "Usage: lsp hover <file> <line>:<col>"
            return ExecutionResult(True, result)
        return ExecutionResult(True, "LSP commands: add <lang> <cmd>, list, diagnose <file>, hover <file> <line>:<col>")

    def _cmd_plugin(self, args: str) -> ExecutionResult:
        """Plugin management"""
        parts = args.strip().split(None, 1)
        subcmd = parts[0].lower() if parts else "list"
        name = parts[1] if len(parts) > 1 else ""

        if subcmd == "install":
            if not name:
                return ExecutionResult(False, "", "Usage: plugin install <name>")
            plugin = self.plugin_manager.install(name)
            return ExecutionResult(True, f"Installed plugin: {plugin.id}")
        elif subcmd == "list":
            plugins = self.plugin_manager.list()
            if not plugins:
                return ExecutionResult(True, "No plugins installed")
            lines = ["Plugins:"]
            for p in plugins:
                status = "enabled" if p.enabled else "disabled"
                lines.append(f"  [{status}] {p.name} v{p.version}")
            return ExecutionResult(True, "\n".join(lines))
        elif subcmd == "uninstall" and name:
            if self.plugin_manager.uninstall(name):
                return ExecutionResult(True, f"Uninstalled plugin: {name}")
            return ExecutionResult(False, "", f"Plugin not found: {name}")
        elif subcmd == "enable" and name:
            if self.plugin_manager.enable(name):
                return ExecutionResult(True, f"Enabled plugin: {name}")
            return ExecutionResult(False, "", f"Plugin not found: {name}")
        elif subcmd == "disable" and name:
            if self.plugin_manager.disable(name):
                return ExecutionResult(True, f"Disabled plugin: {name}")
            return ExecutionResult(False, "", f"Plugin not found: {name}")
        return ExecutionResult(True, "Plugin commands: install <name>, list, uninstall <name>, enable <name>, disable <name>")

    def _cmd_lock(self, args: str) -> ExecutionResult:
        """Branch lock operations"""
        parts = args.strip().split(None, 1)
        subcmd = parts[0].lower() if parts else "list"
        branch = parts[1] if len(parts) > 1 else ""

        if subcmd == "lock":
            if not branch:
                return ExecutionResult(False, "", "Usage: lock lock <branch> [reason]")
            reason = " ".join(parts[2:]) if len(parts) > 2 else ""
            if self.branch_lock.lock(branch, reason):
                return ExecutionResult(True, f"Locked branch: {branch}")
            return ExecutionResult(False, "", "Failed to lock branch")
        elif subcmd == "unlock" and branch:
            if self.branch_lock.unlock(branch):
                return ExecutionResult(True, f"Unlocked branch: {branch}")
            return ExecutionResult(False, "", "Failed to unlock branch")
        elif subcmd == "list":
            locks = self.branch_lock.list_locks()
            if not locks:
                return ExecutionResult(True, "No branch locks")
            lines = ["Branch Locks:"]
            for l in locks:
                lines.append(f"  {l['branch']}: {l.get('reason', 'No reason')}")
            return ExecutionResult(True, "\n".join(lines))
        elif subcmd == "check" and branch:
            if self.branch_lock.is_locked(branch):
                return ExecutionResult(True, f"Branch '{branch}' is locked")
            return ExecutionResult(True, f"Branch '{branch}' is not locked")
        return ExecutionResult(True, "Lock commands: lock <branch>, unlock <branch>, list, check <branch>")

    def _cmd_stale(self, args: str) -> ExecutionResult:
        """Stale branch detection"""
        parts = args.strip().split()
        days = 90
        if parts and parts[0].isdigit():
            days = int(parts[0])

        stale = self.stale_detector.detect(days)
        if not stale:
            return ExecutionResult(True, f"No stale branches (older than {days} days)")

        lines = [f"Stale branches (>{days} days):"]
        for b in stale[:10]:
            lines.append(f"  {b['branch']}: {b['days_since']} days since {b['last_commit']}")
        return ExecutionResult(True, "\n".join(lines))

    def _cmd_help(self) -> ExecutionResult:
        lines = [
            "Available commands:",
            "",
            "Git:  status, diff, log, commit, push, pull, branch",
            "File: files, run, test, build, install",
            "Mem:  context, memory, autoreview, compact",
            "Task: task, team, cron",
            "Sys:  mcp, lsp, plugin, lock, stale, permissions",
            "Misc: help, version, clear, exit",
            "",
            "Type 'help' for more details on a specific command.",
        ]
        return ExecutionResult(True, "\n".join(lines))

    def _cmd_pkg_script(self, script: str) -> ExecutionResult:
        pkg = self.workspace / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                scripts = data.get("scripts", {})
                if script in scripts:
                    return self._cmd_shell(scripts[script])
            except Exception:
                pass
        if (self.workspace / "setup.py").exists() or (self.workspace / "pyproject.toml").exists():
            if script == "test":
                return self._cmd_shell("python -m pytest")
            elif script == "install":
                return self._cmd_shell("pip install -e .")
        if (self.workspace / "Cargo.toml").exists():
            cmds = {"test": "cargo test", "build": "cargo build", "install": "cargo build --release"}
            if script in cmds:
                return self._cmd_shell(cmds[script])
        return ExecutionResult(True, f"No '{script}' script configured for this workspace")

    def _cmd_shell(self, command: str) -> ExecutionResult:
        if not command.strip():
            return ExecutionResult(False, "", "Empty command")
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=self.workspace,
                shell=True,
                encoding="utf-8",
                errors="replace",
            )
            output = (result.stdout or "") + (result.stderr or "")
            output = output.strip() or "(no output)"
            return ExecutionResult(result.returncode == 0, output)
        except Exception as e:
            return ExecutionResult(False, "", str(e))

    # ----- Tool implementations -----

    def _tool_read(self, path: str) -> ExecutionResult:
        path = path.strip()
        if not path:
            return ExecutionResult(False, "", "Provide a file path")
        try:
            fp = self._resolve(path, action="read")
            if not fp.exists():
                return ExecutionResult(False, "", f"File not found: {path}")
            content = fp.read_text(encoding="utf-8", errors="replace")
            if len(content) > 8000:
                content = content[:8000] + "\n... (truncated)"
            lines = content.splitlines()
            numbered = "\n".join(f"{i+1:4}: {line}" for i, line in enumerate(lines))
            return ExecutionResult(True, f"=== {fp.name} ({len(lines)} lines) ===\n{numbered}")
        except Exception as e:
            return ExecutionResult(False, "", str(e))

    def _tool_write(self, payload: str) -> ExecutionResult:
        if "::" not in payload:
            return ExecutionResult(False, "", "Format: path::content")
        path, content = payload.split("::", 1)
        try:
            fp = self._resolve(path.strip(), action="write")
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")
            return ExecutionResult(True, f"Written {len(content)} chars to {fp}")
        except Exception as e:
            return ExecutionResult(False, "", str(e))

    def _tool_grep(self, payload: str) -> ExecutionResult:
        parts = payload.split("::", 1)
        pattern = parts[0].strip()
        search_in = parts[1].strip() if len(parts) > 1 else "."
        if not pattern:
            return ExecutionResult(False, "", "Provide a search pattern")
        try:
            result = subprocess.run(
                ["grep", "-rn", pattern, search_in],
                capture_output=True, text=True, cwd=self.workspace,
                encoding="utf-8", errors="replace",
            )
            output = result.stdout.strip() or f"No matches for '{pattern}'"
            return ExecutionResult(True, output)
        except FileNotFoundError:
            return self._python_grep(pattern)
        except Exception as e:
            return ExecutionResult(False, "", str(e))

    def _python_grep(self, pattern: str) -> ExecutionResult:
        results = []
        try:
            for fp in self.workspace.rglob("*.py"):
                for i, line in enumerate(fp.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if re.search(pattern, line):
                        rel = fp.relative_to(self.workspace)
                        results.append(f"{rel}:{i}: {line.strip()}")
                        if len(results) >= 30:
                            break
        except Exception:
            pass
        output = "\n".join(results) if results else f"No matches for '{pattern}'"
        return ExecutionResult(True, output)

    def _tool_glob(self, pattern: str) -> ExecutionResult:
        pattern = pattern.strip() or "*"
        try:
            matches = list(self.workspace.rglob(pattern))[:30]
            out = "\n".join(str(m.relative_to(self.workspace)) for m in matches) if matches else f"No matches for '{pattern}'"
            return ExecutionResult(True, out)
        except Exception as e:
            return ExecutionResult(False, "", str(e))

    def _tool_todo(self, payload: str) -> ExecutionResult:
        """Handle TodoWriteTool calls"""
        try:
            if isinstance(payload, str):
                data = json.loads(payload)
            else:
                data = payload
            
            action = data.get("action", "list")
            content = data.get("content", "")
            todo_id = data.get("todo_id", "")

            if not self.current_task_id:
                return ExecutionResult(False, "", "No active task. Use: task create <desc> then task use <id> (or run an agent task that needs tools).")
            task_id = self.current_task_id
            
            if action == "create":
                todo = self.todo_registry.create(task_id, content)
                self._sync_task_checklist_file(task_id)
                return ExecutionResult(True, f"Created todo: {todo.id}")
            elif action == "list":
                todos = self.todo_registry.list(task_id)
                if not todos:
                    return ExecutionResult(True, "No todos for current task")
                lines = ["Todos:"]
                for t in todos[:10]:
                    lines.append(f"  [{t.status}] {t.id}: {t.description}")
                return ExecutionResult(True, "\n".join(lines))
            elif action == "complete" and todo_id:
                if self.todo_registry.complete(task_id, todo_id):
                    self._sync_task_checklist_file(task_id)
                    return ExecutionResult(True, f"Completed todo: {todo_id}")
                return ExecutionResult(False, "", f"Todo not found in current task: {todo_id}")
            elif action == "delete" and todo_id:
                if self.todo_registry.delete(task_id, todo_id):
                    self._sync_task_checklist_file(task_id)
                    return ExecutionResult(True, f"Deleted todo: {todo_id}")
                return ExecutionResult(False, "", f"Todo not found in current task: {todo_id}")
            return ExecutionResult(True, "Todo actions: create, list, complete, delete")
        except json.JSONDecodeError:
            return ExecutionResult(False, "", "Invalid JSON payload")

    def _tool_web_fetch(self, payload: dict) -> ExecutionResult:
        """抓取网页内容（read-only）；遇到 403/部分反爬时自动回退 r.jina.ai。"""
        url = (payload or {}).get("url", "")
        if not isinstance(url, str) or not url.strip():
            return ExecutionResult(False, "", "Provide url")
        u = url.strip()
        if u.startswith("//"):
            u = "https:" + u
        if u.startswith("/"):
            u = urljoin("https://", u)
        try:
            req = Request(u, headers={"User-Agent": "Easy-AI-Shell/1.3.0"})
            with urlopen(req, timeout=30) as resp:
                raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            if len(text) > 12000:
                text = text[:12000] + "\n... (truncated)"
            return ExecutionResult(True, text)
        except HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            if int(getattr(e, "code", 0) or 0) in (401, 403, 429):
                try:
                    ju = f"https://r.jina.ai/{u}"
                    req = Request(ju, headers={"User-Agent": "Mozilla/5.0"})
                    with urlopen(req, timeout=30) as resp:
                        raw = resp.read()
                    text = raw.decode("utf-8", errors="replace")
                    if len(text) > 12000:
                        text = text[:12000] + "\n... (truncated)"
                    return ExecutionResult(True, text)
                except Exception:
                    pass
            return ExecutionResult(False, "", f"HTTP {e.code}: {(err_body or str(e))[:300]}")
        except URLError as e:
            try:
                ju = f"https://r.jina.ai/{u}"
                req = Request(ju, headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                text = raw.decode("utf-8", errors="replace")
                if len(text) > 12000:
                    text = text[:12000] + "\n... (truncated)"
                return ExecutionResult(True, text)
            except Exception:
                return ExecutionResult(False, "", f"Connection error: {e.reason}")
        except Exception as e:
            return ExecutionResult(False, "", str(e))

    def _build_web_search_url(self, query: str) -> str:
        """构造 WebSearch 的请求 URL：优先 CLAWD_WEB_SEARCH_BASE_URL，否则默认 DuckDuckGo HTML。"""
        q = (query or "").strip()
        base = (os.environ.get("CLAWD_WEB_SEARCH_BASE_URL", "") or "").strip()
        if not base:
            base = (os.environ.get("EASY_AI_WEB_SEARCH_BASE_URL", "") or "").strip()
        if base:
            p = urlparse(base)
            if not p.scheme or not p.netloc:
                raise ValueError(f"Invalid CLAWD_WEB_SEARCH_BASE_URL: {base}")
            pairs = list(parse_qsl(p.query or "", keep_blank_values=True))
            pairs.append(("q", q))
            new_query = urlencode(pairs, doseq=True)
            return p._replace(query=new_query).geturl()
        return "https://html.duckduckgo.com/html/?" + urlencode({"q": q})

    def _html_to_text(self, s: str) -> str:
        """将 HTML 片段转换为纯文本（去标签+实体反解+空白折叠）。"""
        text = re.sub(r"<[^>]+>", " ", s or "")
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_quoted_value(self, s: str, start: int) -> tuple[str, int]:
        """从 s[start:] 解析引号包裹的属性值，返回 (value, next_index)。"""
        if start < 0 or start >= len(s):
            return "", start
        q = s[start]
        if q not in ("'", '"'):
            return "", start
        end = s.find(q, start + 1)
        if end == -1:
            return "", start
        return s[start + 1:end], end + 1

    def _decode_duckduckgo_redirect(self, url: str) -> Optional[str]:
        """解码 DuckDuckGo HTML 结果链接与跳转链接，返回可用的绝对 URL。"""
        u = (url or "").strip()
        if not u:
            return None
        u = html.unescape(u)
        if u.startswith("http://") or u.startswith("https://"):
            return u
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = "https://duckduckgo.com" + u
        else:
            return None
        try:
            p = urlparse(u)
            if p.path in ("/l/", "/l"):
                qs = parse_qs(p.query or "")
                uddg = qs.get("uddg")
                if uddg and isinstance(uddg, list) and uddg[0]:
                    return html.unescape(unquote(uddg[0]))
            return u
        except Exception:
            return u

    def _normalize_domain_filter(self, domain: str) -> str:
        """标准化域名过滤项：支持传 URL / 带点 / 带斜杠，统一为 host 小写。"""
        d = (domain or "").strip()
        if not d:
            return ""
        try:
            p = urlparse(d)
            if p.scheme and p.netloc:
                d = p.netloc
        except Exception:
            pass
        d = d.strip().lower()
        d = d.lstrip(".")
        d = d.rstrip("/")
        return d

    def _host_matches_list(self, url: str, domains: list[str]) -> bool:
        """判断 url 的 host 是否命中域名列表（支持子域名）。"""
        if not domains:
            return False
        try:
            host = (urlparse(url).netloc or "").lower()
        except Exception:
            return False
        if not host:
            return False
        for d in domains:
            nd = self._normalize_domain_filter(d)
            if not nd:
                continue
            if host == nd or host.endswith("." + nd):
                return True
        return False

    def _dedupe_hits(self, hits: list[dict]) -> list[dict]:
        """按 url 去重（保留首次出现）。"""
        out: list[dict] = []
        seen: set[str] = set()
        for h in hits:
            u = (h or {}).get("url")
            if not isinstance(u, str) or not u.strip():
                continue
            if u in seen:
                continue
            seen.add(u)
            out.append(h)
        return out

    def _extract_search_hits_ddg(self, html_text: str) -> list[dict]:
        """解析 DuckDuckGo HTML 结果页结构，提取 hits（title,url）。"""
        hits: list[dict] = []
        s = html_text or ""
        pos = 0
        while True:
            idx = s.find("result__a", pos)
            if idx == -1:
                break
            href_idx = s.find("href=", idx)
            if href_idx == -1:
                pos = idx + 1
                continue
            qpos = href_idx + len("href=")
            if qpos >= len(s):
                pos = idx + 1
                continue
            href, after = self._extract_quoted_value(s, qpos)
            if not href:
                pos = idx + 1
                continue
            gt = s.find(">", after)
            if gt == -1:
                pos = idx + 1
                continue
            end_a = s.find("</a>", gt)
            if end_a == -1:
                pos = idx + 1
                continue
            title_html = s[gt + 1:end_a]
            title = self._html_to_text(title_html)
            url = self._decode_duckduckgo_redirect(href)
            if url and title:
                hits.append({"title": title, "url": url})
            pos = end_a + 4
        return hits

    def _extract_search_hits_generic(self, html_text: str) -> list[dict]:
        """兜底解析：扫描通用 <a href=...> 链接，提取 hits（title,url）。"""
        hits: list[dict] = []
        s = html_text or ""
        pos = 0
        while True:
            a_idx = s.find("<a", pos)
            if a_idx == -1:
                break
            href_idx = s.find("href=", a_idx)
            if href_idx == -1:
                pos = a_idx + 2
                continue
            qpos = href_idx + len("href=")
            href, after = self._extract_quoted_value(s, qpos)
            gt = s.find(">", after)
            if gt == -1:
                pos = a_idx + 2
                continue
            end_a = s.find("</a>", gt)
            if end_a == -1:
                pos = a_idx + 2
                continue
            title = self._html_to_text(s[gt + 1:end_a])
            if not title:
                pos = end_a + 4
                continue
            url = self._decode_duckduckgo_redirect(href) or (href or "").strip()
            if url.startswith("http://") or url.startswith("https://"):
                hits.append({"title": title, "url": url})
            pos = end_a + 4
        return hits

    def _extract_search_hits_bing(self, html_text: str) -> list[dict]:
        """解析 Bing 搜索结果页结构，提取 hits（title,url）。"""
        hits: list[dict] = []
        s = html_text or ""
        for m in re.finditer(r'<li class="b_algo"[\s\S]*?<h2[^>]*>[\s\S]*?<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', s, re.IGNORECASE):
            url = (m.group(1) or "").strip()
            title = self._html_to_text(m.group(2) or "")
            if not url or not title:
                continue
            if not (url.startswith("http://") or url.startswith("https://")):
                continue
            hits.append({"title": title, "url": url})
        return hits

    def _tool_web_search(self, payload: dict) -> ExecutionResult:
        t0 = time.monotonic()
        query = (payload or {}).get("query", "")
        if not isinstance(query, str) or not query.strip():
            return ExecutionResult(False, "", "Provide query")
        q = query.strip()

        num = 8
        if isinstance(payload, dict) and "num_results" in payload:
            try:
                num = int(payload.get("num_results", 8))
            except Exception:
                num = 8
        num = max(1, min(num, 8))

        allowed_domains = payload.get("allowed_domains") if isinstance(payload, dict) else None
        blocked_domains = payload.get("blocked_domains") if isinstance(payload, dict) else None

        allow = allowed_domains if isinstance(allowed_domains, list) else ([] if allowed_domains is None else [str(allowed_domains)])
        block = blocked_domains if isinstance(blocked_domains, list) else ([] if blocked_domains is None else [str(blocked_domains)])
        allow = [str(x) for x in allow if isinstance(x, str) and str(x).strip()]
        block = [str(x) for x in block if isinstance(x, str) and str(x).strip()]

        mcp_tried: list[dict] = []
        if self.mcp_client.has_server("WebSearch"):
            try:
                server_info = self.mcp_client.servers.get("WebSearch") or {}
                auth = ""
                if isinstance(server_info.get("headers"), dict):
                    auth = str(server_info["headers"].get("Authorization", "") or "")
                if auth and "YOUR_" not in auth and "${" not in auth:
                    raw = self.mcp_client.call_tool("WebSearch", "", {"query": q, "num_results": num, "allowed_domains": allow, "blocked_domains": block})
                    mcp_tried.append({"provider": "mcp:WebSearch", "ok": True})
                    hits: list[dict] = []
                    blob = ""
                    try:
                        data = json.loads(raw) if isinstance(raw, str) else raw
                    except Exception:
                        data = raw

                    def _add_hit(title: str, url: str, snippet: str = "") -> None:
                        t = (title or "").strip()
                        u = (url or "").strip()
                        if not t or not u:
                            return
                        if not (u.startswith("http://") or u.startswith("https://")):
                            return
                        hits.append({"title": t, "url": u, "snippet": (snippet or "").strip()})

                    def _parse_list(items: Any) -> None:
                        if not isinstance(items, list):
                            return
                        for it in items:
                            if isinstance(it, dict):
                                _add_hit(str(it.get("title") or it.get("name") or ""), str(it.get("url") or it.get("link") or ""), str(it.get("snippet") or it.get("summary") or it.get("description") or ""))

                    if isinstance(data, list):
                        _parse_list(data)
                    if isinstance(data, dict):
                        _parse_list(data.get("results"))
                        _parse_list(data.get("items"))
                        _parse_list(data.get("data"))
                        content = data.get("content")
                        texts: list[str] = []
                        if isinstance(content, list):
                            for it in content:
                                if isinstance(it, dict) and it.get("type") == "text" and isinstance(it.get("text"), str):
                                    texts.append(it["text"])
                        blob = "\n".join(texts).strip()

                    if blob and not hits:
                        parsed = None
                        try:
                            m = re.search(r"\[[\s\S]*\]|\{[\s\S]*\}", blob)
                            parsed = json.loads(m.group(0)) if m else None
                        except Exception:
                            parsed = None
                        if isinstance(parsed, list):
                            _parse_list(parsed)
                        elif isinstance(parsed, dict):
                            _parse_list(parsed.get("results"))
                            _parse_list(parsed.get("items"))

                    if blob and not hits:
                        for m in re.finditer(r"\[([^\]]+)\]\((https?://[^)]+)\)", blob):
                            _add_hit(m.group(1) or "", m.group(2) or "", "")
                    if blob and not hits:
                        for m in re.finditer(r"(https?://[^\s)]+)", blob):
                            u = (m.group(1) or "").strip()
                            if u:
                                _add_hit(u, u, "")
                    if allow:
                        hits = [h for h in hits if self._host_matches_list(h.get("url", ""), allow)]
                    if block:
                        hits = [h for h in hits if not self._host_matches_list(h.get("url", ""), block)]
                    hits = self._dedupe_hits(hits)[:num]
                    if hits:
                        lines = [f"“{q}”的搜索结果（来自 MCP WebSearch；最终回答请包含 Sources 来源列表）："]
                        for h in hits:
                            lines.append(f"- [{h.get('title','')}]({h.get('url','')})")
                        out = {
                            "query": q,
                            "provider": "mcp:WebSearch",
                            "results": [
                                {"type": "commentary", "content": "\n".join(lines)},
                                {"type": "search_result", "tool_use_id": "web_search_1", "content": hits},
                            ],
                            "duration_seconds": round(time.monotonic() - t0, 3),
                        }
                        return ExecutionResult(True, json.dumps(out, ensure_ascii=False, indent=2))
                    mcp_tried.append({"provider": "mcp:WebSearch", "ok": False, "reason": "no_hits"})
                else:
                    mcp_tried.append({"provider": "mcp:WebSearch", "ok": False, "reason": "no_auth"})
            except Exception:
                mcp_tried.append({"provider": "mcp:WebSearch", "ok": False, "reason": "exception"})

        try:
            url = self._build_web_search_url(q)
        except Exception as e:
            return ExecutionResult(False, "", str(e))

        providers_tried: list[dict] = []
        html_text = ""
        final_url = url

        def _fetch_html(u: str) -> tuple[str, str]:
            req = Request(u, headers={"User-Agent": "clawd-rust-tools/0.1"})
            with urlopen(req, timeout=20) as resp:
                return resp.geturl(), resp.read(600000).decode("utf-8", errors="replace")

        try:
            final_url, html_text = _fetch_html(url)
            providers_tried.append({"provider": "duckduckgo_html", "url": final_url})
        except Exception as e:
            providers_tried.append({"provider": "duckduckgo_html", "error": str(e)})
            try:
                ju = f"https://r.jina.ai/{url}"
                final_url, html_text = _fetch_html(ju)
                providers_tried.append({"provider": "jina_proxy", "url": ju})
            except Exception as e2:
                providers_tried.append({"provider": "jina_proxy", "error": str(e2)})

        if not html_text.strip():
            try:
                has_cjk = bool(re.search(r"[\u4e00-\u9fff]", q))
                extra = "&setlang=zh-hans&cc=CN&mkt=zh-CN" if has_cjk else ""
                bing_url = "https://cn.bing.com/search?q=" + quote(q) + extra
                final_url, html_text = _fetch_html(bing_url)
                providers_tried.append({"provider": "bing_html", "url": final_url})
            except Exception as e:
                providers_tried.append({"provider": "bing_html", "error": str(e)})
                return ExecutionResult(False, "", json.dumps({"error": "All providers failed", "tried": providers_tried}, ensure_ascii=False))

        host = (urlparse(final_url).netloc or "").lower()
        if "bing.com" in host:
            hits = self._extract_search_hits_bing(html_text)
        else:
            hits = self._extract_search_hits_ddg(html_text)
            if not hits and (urlparse(final_url).netloc or ""):
                hits = self._extract_search_hits_generic(html_text)

        if allow:
            hits = [h for h in hits if self._host_matches_list(h.get("url", ""), allow)]
        if block:
            hits = [h for h in hits if not self._host_matches_list(h.get("url", ""), block)]

        hits = self._dedupe_hits(hits)
        hits = hits[:num]

        if not hits:
            summary = f"没有找到匹配查询“{q}”的网页搜索结果。"
        else:
            lines = [f"“{q}”的搜索结果（最终回答请包含 Sources 来源列表）："]
            for h in hits:
                lines.append(f"- [{h.get('title','')}]({h.get('url','')})")
            summary = "\n".join(lines)

        out = {
            "query": q,
            "provider": "html",
            "results": [
                {"type": "commentary", "content": summary},
                {"type": "search_result", "tool_use_id": "web_search_1", "content": hits},
            ],
            "duration_seconds": round(time.monotonic() - t0, 3),
        }
        if mcp_tried:
            out["mcp_tried"] = mcp_tried
        return ExecutionResult(True, json.dumps(out, ensure_ascii=False, indent=2))

    def _tool_news_search(self, payload: dict) -> ExecutionResult:
        """搜索最新资讯（read-only）：默认优先 Bing HTML，可选 Google News RSS。"""
        query = (payload or {}).get("query", "")
        if not isinstance(query, str) or not query.strip():
            return ExecutionResult(False, "", "Provide query")

        q = query.strip()
        if "美伊" in q and ("伊朗" not in q):
            q = q.replace("美伊", "美国 伊朗")
        num = payload.get("num_results", 8) if isinstance(payload, dict) else 8
        try:
            num = int(num)
        except Exception:
            num = 8
        num = max(1, min(num, 20))

        language = payload.get("language", "zh-CN") if isinstance(payload, dict) else "zh-CN"
        region = payload.get("region", "CN") if isinstance(payload, dict) else "CN"
        ceid = payload.get("ceid", "CN:zh-Hans") if isinstance(payload, dict) else "CN:zh-Hans"
        if not isinstance(language, str) or not language.strip():
            language = "zh-CN"
        if not isinstance(region, str) or not region.strip():
            region = "CN"
        if not isinstance(ceid, str) or not ceid.strip():
            ceid = "CN:zh-Hans"

        providers_tried: list[dict] = []
        provider = (payload.get("provider") if isinstance(payload, dict) else "") or "bing"
        provider = str(provider).strip().lower()
        if provider not in ("bing", "google_news_rss"):
            provider = "bing"

        allowed_domains = payload.get("allowed_domains") if isinstance(payload, dict) else None
        blocked_domains = payload.get("blocked_domains") if isinstance(payload, dict) else None
        has_allow_key = bool(isinstance(payload, dict) and ("allowed_domains" in payload))
        has_block_key = bool(isinstance(payload, dict) and ("blocked_domains" in payload))

        def _norm_domains(v: Any) -> list[str]:
            if v is None:
                return []
            if isinstance(v, str):
                parts = re.split(r"[,\s]+", v.strip())
                return [p.strip().lower() for p in parts if p and p.strip()]
            if isinstance(v, list):
                out = []
                for it in v:
                    if isinstance(it, str) and it.strip():
                        out.append(it.strip().lower())
                return out
            return []

        allow = _norm_domains(allowed_domains)
        block = _norm_domains(blocked_domains)
        if not has_allow_key:
            allow = self._default_news_allowed_domains()
        if not has_block_key:
            block = self._default_news_blocked_domains()

        def _host_ok(link: str) -> bool:
            try:
                host = (urlparse(link).netloc or "").lower()
            except Exception:
                host = ""
            if not host:
                return False
            if allow and not any(host == d or host.endswith("." + d) for d in allow):
                return False
            if block and any(host == d or host.endswith("." + d) for d in block):
                return False
            return True

        def _try_bing_news() -> Optional[list[dict]]:
            has_cjk = bool(re.search(r"[\u4e00-\u9fff]", q))
            extra = "&setlang=zh-hans&cc=CN&mkt=zh-CN" if has_cjk else ""
            bing_url = f"https://cn.bing.com/search?q={quote(q)}{extra}"
            try:
                req = Request(bing_url, headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(req, timeout=15) as resp:
                    html_text = resp.read(240000).decode("utf-8", errors="replace")
            except Exception as e:
                providers_tried.append({"provider": "bing_search", "error": str(e)})
                return None
            results = []
            try:
                for m in re.finditer(r'<li class="b_algo"[\s\S]*?<h2[^>]*>[\s\S]*?<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>[\s\S]*?</li>', html_text, re.IGNORECASE):
                    link = (m.group(1) or "").strip()
                    title_html = (m.group(2) or "").strip()
                    block = m.group(0) or ""
                    snippet_html = ""
                    pm = re.search(r"<p[^>]*>([\s\S]*?)</p>", block, re.IGNORECASE)
                    if pm:
                        snippet_html = (pm.group(1) or "").strip()
                    title = re.sub(r"<[^>]+>", "", title_html)
                    snippet = re.sub(r"<[^>]+>", "", snippet_html)
                    title = html.unescape(title).strip()
                    snippet = html.unescape(snippet).strip()
                    if not _host_ok(link):
                        continue
                    if title or link:
                        item = {"title": title, "link": link, "source": "bing"}
                        if snippet:
                            item["snippet"] = snippet
                        results.append(item)
                    if len(results) >= num:
                        break
            except Exception as e:
                providers_tried.append({"provider": "bing_search", "error": str(e)})
                return None
            if results:
                return results
            providers_tried.append({"provider": "bing_search", "error": "No results"})
            return []

        def _try_google_news_rss() -> Optional[list[dict]]:
            url = f"https://news.google.com/rss/search?q={quote(q)}&hl={quote(language)}&gl={quote(region)}&ceid={quote(ceid)}"
            text = ""
            last_err: Optional[Exception] = None
            for fetch_url in (url, f"https://r.jina.ai/{url}"):
                try:
                    req = Request(fetch_url, headers={"User-Agent": "Easy-AI-Shell/1.3.0"})
                    with urlopen(req, timeout=15) as resp:
                        raw = resp.read()
                    text = raw.decode("utf-8", errors="replace")
                    if text.strip():
                        break
                except Exception as e:
                    last_err = e
                    continue
            if not text.strip():
                providers_tried.append({"provider": "google_news_rss", "error": str(last_err or "Fetch failed")})
                return None
            try:
                root = ET.fromstring(text)
                items = []
                for it in root.findall(".//item"):
                    title = it.findtext("title") or ""
                    link = it.findtext("link") or ""
                    pub = it.findtext("pubDate") or ""
                    source_el = it.find("source")
                    source = source_el.text if source_el is not None and source_el.text else ""
                    title = html.unescape(title.strip())
                    link = link.strip()
                    pub = pub.strip()
                    source = html.unescape((source or "").strip())
                    if link and not _host_ok(link):
                        continue
                    if title or link:
                        items.append({"title": title, "link": link, "published": pub, "source": source})
                    if len(items) >= num:
                        break
                if items:
                    return items
            except Exception as e:
                providers_tried.append({"provider": "google_news_rss", "error": str(e)})
                return None
            providers_tried.append({"provider": "google_news_rss", "error": "No results"})
            return []

        results: Optional[list[dict]] = None
        if provider == "bing":
            results = _try_bing_news()
            if results is None or results == []:
                alt = _try_google_news_rss()
                if alt:
                    results = alt
        else:
            results = _try_google_news_rss()
            if results is None or results == []:
                alt = _try_bing_news()
                if alt:
                    results = alt

        if results:
            return ExecutionResult(True, json.dumps(results, ensure_ascii=False, indent=2))

        return ExecutionResult(False, "", json.dumps({"error": "No results", "tried": providers_tried}, ensure_ascii=False))


    def _resolve(self, path: str, action: str = "read") -> Path:
        p = Path(path)
        try:
            base = self.workspace.resolve()
        except Exception:
            base = self.workspace

        try:
            rp = p.expanduser().resolve() if p.is_absolute() else (base / p).resolve()
        except Exception:
            rp = p if p.is_absolute() else (base / p)

        try:
            inside = rp.is_relative_to(base)
        except Exception:
            inside = str(rp).lower().startswith(str(base).lower().rstrip("\\/") + os.sep)

        if inside:
            return rp

        ok, _ = self.permission.authorize_or_prompt(
            "ExternalPathTool",
            json.dumps({"path": str(rp), "action": action, "workspace": str(base)}, ensure_ascii=False),
        )
        if ok:
            return rp
        raise PermissionError(f"Path is outside workspace: {rp}")


# ==================== Agent Loop ====================

class AgentLoop:
    """
    Agent Loop - ReAct (Reasoning + Acting) pattern
    输入自然语言 → LLM 理解 → 调用工具 → 返回结果 → 循环直到完成
    """
    
    def __init__(self, registry: Registry, llm: LLMClient, max_turns: int = 32):
        self.registry = registry
        self.llm = llm
        self.max_turns = max_turns
        self.steps: List[AgentStep] = []
    
    def _classify_intent(self, user_prompt: str) -> dict:
        """用 LLM 做意图判定：是否进入工具循环、是否必须先联网检索，以及首个检索工具与查询词。"""
        p = (user_prompt or "").strip()
        if not p:
            return {"mode": "single_turn", "force_web_research": False, "search_tool": "", "search_query": ""}

        router_prompt = (
            "你是一个路由与任务分解助手。给定用户输入，请判断：\n"
            "1) 是否需要进入工具循环（tool_loop）而不是单轮回答（single_turn）。需要工具循环的情况包括：代码生成/编写/编程/创建文件/执行命令/搜索信息等；\n"
            "2) 是否必须先进行联网检索再回答（force_web_research）。\n"
            "如果需要联网检索，请给出首选工具（NewsSearchTool 或 WebSearchTool）与一个合适的 search_query。\n"
            "只输出严格 JSON（不要代码块，不要额外文字）。JSON schema：\n"
            "{\n"
            '  "mode": "tool_loop" | "single_turn",\n'
            '  "force_web_research": true | false,\n'
            '  "search_tool": "NewsSearchTool" | "WebSearchTool" | "",\n'
            '  "search_query": "string"\n'
            "}\n\n"
            f"用户输入：{p}\n"
        )
        try:
            raw = self.llm.chat([], router_prompt, include_tools=False)
            m = re.search(r"\{[\s\S]*\}", raw or "")
            data = json.loads(m.group(0)) if m else {}
            if not isinstance(data, dict):
                raise ValueError("router json is not an object")
            mode = str(data.get("mode", "tool_loop")).strip().lower()
            mode = "tool_loop" if mode == "tool_loop" else "single_turn"
            force = bool(data.get("force_web_research", False))
            tool = str(data.get("search_tool", "") or "").strip()
            if tool not in ("NewsSearchTool", "WebSearchTool"):
                tool = ""
            q = str(data.get("search_query", "") or "").strip()
            if force and not tool:
                tool = "NewsSearchTool"
            if force and not q:
                q = p
            if re.search(r"[\u4e00-\u9fff]", p) and (not re.search(r"[\u4e00-\u9fff]", q)):
                q = p
            if force and re.search(r"[\u4e00-\u9fff]", q) and (not any(k in q for k in ("新闻", "动态", "进展", "最新"))):
                q = q + " 新闻"
            return {"mode": mode, "force_web_research": force, "search_tool": tool, "search_query": q}
        except Exception:
            return {"mode": "tool_loop", "force_web_research": False, "search_tool": "", "search_query": ""}

    def _load_memory_context(self, max_chars: int = 1600) -> str:
        """读取用户级/项目级长期记忆，用于在对话中注入（少而有用）。"""
        try:
            mem_cfg = (self.registry.cfg or {}).get("memory", {})
            mem_dir = mem_cfg.get("memoryDir", ".easy_ai/memory") if isinstance(mem_cfg, dict) else ".easy_ai/memory"
            mem_dir = str(mem_dir or ".easy_ai/memory").strip() or ".easy_ai/memory"

            user_path = "~/.easy_ai_shell/memory/USER_MEMORY.md"
            project_file = "PROJECT_MEMORY.md"
            if isinstance(mem_cfg, dict):
                user_path = str(mem_cfg.get("userMemoryPath", user_path) or user_path)
                project_file = str(mem_cfg.get("projectMemoryFile", project_file) or project_file)
            user_fp = Path(user_path).expanduser()
            proj_fp = (self.registry.workspace / mem_dir / project_file)

            user_text = ""
            proj_text = ""
            try:
                if user_fp.exists():
                    user_text = user_fp.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                user_text = ""
            try:
                if proj_fp.exists():
                    proj_text = proj_fp.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                proj_text = ""

            parts = []
            if user_text:
                parts.append("[User Memory]\n" + user_text)
            if proj_text:
                parts.append("[Project Memory]\n" + proj_text)
            text = "\n\n".join(parts).strip()
            if not text:
                return ""
            if len(text) > int(max_chars):
                text = text[: int(max_chars)]
            return text
        except Exception:
            return ""

    def _load_instruction_context(self, max_chars: int = 2000) -> str:
        candidates: List[Path] = []
        w = self.registry.workspace
        candidates.extend([
            w / "EASY_AI.md",
            w / "EASY_AI.local.md",
            w / ".easy_ai" / "EASY_AI.md",
            w / ".easy_ai" / "instructions.md",
        ])
        blocks: List[str] = []
        for p in candidates:
            try:
                if not p.exists() or not p.is_file():
                    continue
                txt = p.read_text(encoding="utf-8", errors="replace").strip()
                if not txt:
                    continue
                if len(txt) > max_chars:
                    txt = txt[:max_chars]
                blocks.append(f"[{p.name}]\n{txt}".strip())
            except Exception:
                continue
        return "\n\n".join(blocks).strip()

    def run(self, user_prompt: str, seed_history: Optional[List[dict]] = None) -> tuple[str, List[AgentStep], str]:
        """
        执行 Agent 循环。
        - 对于不涉及工程操作的纯输出任务：单轮生成最终回答（不注入工具定义、不读取 说明文档.md）。
        - 对于涉及工程操作的任务：采用 ReAct 循环，允许调用工具，并按需读取 说明文档.md 作为工程任务上下文。
        返回: (最终回答, 执行的步骤列表, stop_reason)
        """
        if not self.llm.enabled:
            return "AI is not enabled. Please configure API key in config.json.", [], "ai_disabled"
        
        self.steps = []
        intent = self._classify_intent(user_prompt)
        mode = intent.get("mode", "tool_loop")
        force_web = bool(intent.get("force_web_research", False))
        search_tool = str(intent.get("search_tool") or "")
        search_query = str(intent.get("search_query") or "")

        history: List[dict] = list(seed_history or [])
        try:
            py_files = list(self.registry.workspace.rglob("*.py"))
        except Exception:
            py_files = []
        context_prefix = (
            f"[Workspace: {self.registry.workspace} | Python files: {len(py_files)} | "
            f"Has git: {(self.registry.workspace / '.git').exists()}]\n"
        )
        instruction_context = self._load_instruction_context()
        memory_context = self._load_memory_context()
        current_prompt = context_prefix + user_prompt
        if instruction_context:
            current_prompt = context_prefix + "[Instructions]\n" + instruction_context + "\n\n" + user_prompt
        if memory_context:
            current_prompt = current_prompt + "\n\n[Memory]\n" + memory_context
        doc_path = self.registry.current_task_doc_path
        if mode == "tool_loop" and doc_path and doc_path.exists():
            try:
                excerpt = doc_path.read_text(encoding="utf-8", errors="replace")
                excerpt = excerpt[:2000] + ("\n... (truncated)" if len(excerpt) > 2000 else "")
                current_prompt = (
                    current_prompt
                    + "\n\n[Task Doc]\n"
                    + excerpt
                    + "\n\n你必须按清单逐项执行：每完成一项，就调用 TodoWriteTool 把对应 todo 标记为 completed，并保持 checklist.md 实时更新。"
                )
            except Exception:
                pass
        task_id = self.registry.current_task_id or ""
        if mode == "tool_loop" and task_id:
            try:
                task_root = self.registry.workspace / ".easy_ai" / "tasks" / task_id
                checklist_fp = task_root / "checklist.md"
                if checklist_fp.exists():
                    checklist_text = checklist_fp.read_text(encoding="utf-8", errors="replace").strip()
                    if checklist_text:
                        checklist_text = checklist_text[:1800]
                        current_prompt = current_prompt + "\n\n[Task Checklist]\n" + checklist_text
                folder_blocks: List[str] = []
                folders_root = task_root / "folders"
                if folders_root.exists():
                    for p in sorted(folders_root.glob("*/INDEX.md"))[:4]:
                        index_text = p.read_text(encoding="utf-8", errors="replace").strip()[:700]
                        usage_fp = p.with_name("USAGE.md")
                        usage_text = usage_fp.read_text(encoding="utf-8", errors="replace").strip()[:700] if usage_fp.exists() else ""
                        block = f"[Folder Index]\n{index_text}\n\n[Folder Usage]\n{usage_text}".strip()
                        if block:
                            folder_blocks.append(block)
                if folder_blocks:
                    current_prompt = current_prompt + "\n\n[Folder Context]\n" + "\n\n".join(folder_blocks)
            except Exception:
                pass

        if mode != "tool_loop" and not force_web:
            llm_response = self.llm.chat(history, current_prompt, include_tools=False)
            self.steps.append(AgentStep(step_num=1, thought="Final response (single turn)", action=None, observation=llm_response, is_final=True))
            return llm_response, self.steps, "completed"
        
        if force_web and search_query:
            st = search_tool if search_tool in ("NewsSearchTool", "WebSearchTool") else "NewsSearchTool"
            tool_input: dict = {"query": search_query}
            if st == "NewsSearchTool":
                tool_input = {"query": search_query, "num_results": 8, "provider": "bing"}
            else:
                tool_input = {"query": search_query, "num_results": 6}
            pre = self.registry.run_tool(st, tool_input)
            pre_obs = pre.output if pre.success else f"Error: {pre.error}"
            self.steps.append(AgentStep(step_num=0, thought=f"Pre-search via {st}", action=ToolCall(tool_name=st, tool_input=tool_input, raw_json=""), observation=pre_obs))
            history.append({"role": "user", "content": f"Tool: {st}\nInput: {json.dumps(tool_input, ensure_ascii=False)}\nOutput: {pre_obs}"})
            current_prompt = "继续。基于以上工具结果，给出下一步动作（工具调用）或最终回答（必须用中文）。"
        
        for step_num in range(1, self.max_turns + 1):
            # 调用 LLM
            llm_response = self.llm.chat(history, current_prompt, include_tools=True)
            
            # 解析工具调用
            tool_calls = ToolCallParser.parse(llm_response)
            
            if not tool_calls:
                # 没有工具调用，这是最终回答
                if step_num < self.max_turns and mode == "tool_loop":
                    history.append({"role": "assistant", "content": llm_response})
                    current_prompt = (
                        "你没有调用任何工具。如果任务涉及文件/命令/联网检索，你必须调用工具。\n"
                        "如果你感觉卡住，先用可用工具自救（NewsSearchTool/WebSearchTool/WebFetchTool、FileSearchTool/GrepTool/GlobTool），不要用 BashTool 访问网页。\n"
                        "下一步只输出工具调用的 JSON block；或者在穷尽工具后明确说明你被阻塞的原因。"
                    )
                    continue
                self.steps.append(AgentStep(step_num=step_num, thought="Final response (no tools needed)", action=None, observation=llm_response, is_final=True))
                return llm_response, self.steps, "completed"
            
            # 有工具调用，执行它
            tool_results = []
            any_failed = False
            for tc in tool_calls:
                # 执行工具
                if task_id:
                    try:
                        trace_fp = self.registry.workspace / ".easy_ai" / "tasks" / task_id / "trace.jsonl"
                        trace_fp.parent.mkdir(parents=True, exist_ok=True)
                        with trace_fp.open("a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "ts": datetime.now().isoformat(timespec="seconds"),
                                "event": "tool_execution_started",
                                "task_id": task_id,
                                "tool": tc.tool_name,
                                "input": tc.tool_input,
                            }, ensure_ascii=False) + "\n")
                    except Exception:
                        pass
                result = self.registry.run_tool(tc.tool_name, tc.tool_input)
                
                observation = result.output if result.success else f"Error: {result.error}"
                if not result.success:
                    any_failed = True
                if task_id:
                    try:
                        trace_fp = self.registry.workspace / ".easy_ai" / "tasks" / task_id / "trace.jsonl"
                        trace_fp.parent.mkdir(parents=True, exist_ok=True)
                        with trace_fp.open("a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "ts": datetime.now().isoformat(timespec="seconds"),
                                "event": "tool_execution_finished",
                                "task_id": task_id,
                                "tool": tc.tool_name,
                                "success": bool(result.success),
                            }, ensure_ascii=False) + "\n")
                    except Exception:
                        pass
                
                self.steps.append(AgentStep(
                    step_num=step_num,
                    thought=f"Calling {tc.tool_name}",
                    action=tc,
                    observation=observation
                ))
                
                # 添加到历史
                tool_results.append({
                    "tool": tc.tool_name,
                    "input": tc.tool_input,
                    "output": observation
                })
            
            # 构建下一轮的消息
            # 添加 assistant 的思考和工具调用
            history.append({"role": "assistant", "content": llm_response})
            
            # 添加工具结果
            for tr in tool_results:
                result_text = f"Tool: {tr['tool']}\nInput: {json.dumps(tr['input'])}\nOutput: {tr['output']}"
                history.append({"role": "user", "content": result_text})
            
            # 继续下一轮
            if any_failed:
                current_prompt = (
                    "继续。一个或多个工具执行失败。\n"
                    "请尝试替代工具或调整策略；若缺少信息，先用 NewsSearchTool/WebSearchTool 找链接，再用 WebFetchTool 抓取证据。\n"
                    "给出下一步动作（工具调用）或（如果已解决）给出最终回答（必须用中文）。"
                )
            else:
                current_prompt = "继续。基于以上工具结果，给出下一步动作（工具调用）或最终回答（必须用中文）。"
            if force_web and step_num >= 6:
                current_prompt = (
                    "停止继续调用工具，现在就给出最终回答（必须用中文）。\n"
                    "只能使用现有的搜索结果/片段作为证据；若无法抓取权威来源，请清楚说明局限与证据缺口。"
                )
        
        final_prompt = (
            "你已经达到工具调用的最大轮数限制。\n"
            "请基于以上对话里已有的工具结果，给出一个尽力而为的最终回答：\n"
            "1) 用中文总结要点；\n"
            "2) 明确哪些结论是基于哪些来源；\n"
            "3) 如果证据不足，直接说明缺口，并给出下一步应当检索/抓取哪些来源。\n"
            "4) 必须用中文输出（除非专有名词/机构名需要保留英文）。\n"
            "不要再调用工具。"
        )
        llm_response = self.llm.chat(history, final_prompt, include_tools=False)
        self.steps.append(AgentStep(step_num=self.max_turns + 1, thought="Final response (max turns fallback)", action=None, observation=llm_response, is_final=True))
        return llm_response, self.steps, "max_turns_reached"


# ==================== Query Engine ====================

class QueryEngine:
    """Routes prompts -> commands + tools; falls back to AI for free-form input."""

    def __init__(self, workspace: Optional[Path] = None, cfg: Optional[dict] = None):
        self.cfg = cfg or DEFAULT_CONFIG
        self.registry = Registry(workspace, self.cfg)
        self.session = Session()
        self.llm = LLMClient(self.cfg)
        self.ai_mode = self.cfg["shell"].get("ai_mode", True)
        self.max_context_turns = int(self.cfg["shell"].get("max_context_turns", 20))
        self.max_agent_turns = int(self.cfg["shell"].get("max_agent_turns", 10))
        self.context_rounds = int(self.cfg["shell"].get("context_rounds", 3))
        
        # Agent Loop
        self.agent = AgentLoop(self.registry, self.llm, self.max_agent_turns)
        
        self.auto_review = AutoReview(workspace, self.cfg)

    def _memory_cfg(self) -> dict:
        """返回 memory 配置段（容错为 dict）。"""
        m = (self.cfg or {}).get("memory", {})
        return m if isinstance(m, dict) else {}

    def _memory_dir(self) -> Path:
        """返回 memoryDir 的绝对路径，并确保目录存在。"""
        mem_dir = str(self._memory_cfg().get("memoryDir", ".easy_ai/memory") or ".easy_ai/memory").strip() or ".easy_ai/memory"
        p = (self.registry.workspace / mem_dir)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return p

    def _expand_user_path(self, path_str: str) -> Path:
        """展开用户路径（支持 ~），并返回绝对 Path。"""
        p = Path(str(path_str or "").strip() or "~/.easy_ai_shell/memory/USER_MEMORY.md").expanduser()
        try:
            return p.resolve()
        except Exception:
            return p

    def _user_memory_path(self) -> Path:
        """返回用户级长期记忆文件路径（默认在用户主目录）。"""
        cfg = self._memory_cfg()
        p = self._expand_user_path(cfg.get("userMemoryPath", "~/.easy_ai_shell/memory/USER_MEMORY.md"))
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.parent.exists():
                return p
        except Exception:
            pass
        return self._memory_dir() / "USER_MEMORY.md"

    def _project_memory_path(self) -> Path:
        """返回项目级长期记忆文件路径（默认在 workspace 的 memoryDir 下）。"""
        cfg = self._memory_cfg()
        name = str(cfg.get("projectMemoryFile", "PROJECT_MEMORY.md") or "PROJECT_MEMORY.md").strip() or "PROJECT_MEMORY.md"
        return self._memory_dir() / name

    def _topics_index_path(self) -> Path:
        """返回 Topics 索引文件路径（默认 MEMORY.md）。"""
        cfg = self._memory_cfg()
        name = str(cfg.get("topicsIndexFile", "MEMORY.md") or "MEMORY.md").strip() or "MEMORY.md"
        return self._memory_dir() / name

    def _read_text_safe(self, fp: Path, max_chars: int = 8000) -> str:
        """安全读取文本文件并截断，避免超大内容进入 prompt。"""
        try:
            if not fp.exists():
                return ""
            text = fp.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                return ""
            if len(text) > int(max_chars):
                return text[: int(max_chars)]
            return text
        except Exception:
            return ""

    def _write_text_safe(self, fp: Path, text: str) -> bool:
        """安全写入文本文件（确保父目录存在）。"""
        try:
            fp.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            fp.write_text((text or "").rstrip() + "\n", encoding="utf-8")
            return True
        except Exception:
            return False

    def _task_root_dir(self, task_id: str) -> Path:
        """返回任务根目录。"""
        return self.registry.workspace / ".easy_ai" / "tasks" / task_id

    def _task_doc_path(self, task_id: str) -> Path:
        """返回任务主文档路径。"""
        return self._task_root_dir(task_id) / "task.md"

    def _task_checklist_path(self, task_id: str) -> Path:
        """返回任务清单路径。"""
        return self._task_root_dir(task_id) / "checklist.md"

    def _task_index_path(self, task_id: str) -> Path:
        """返回任务索引文件路径。"""
        return self._task_root_dir(task_id) / "index.json"

    def _task_trace_path(self, task_id: str) -> Path:
        """返回任务执行轨迹文件路径。"""
        return self._task_root_dir(task_id) / "trace.jsonl"

    def _task_folder_refs_dir(self, task_id: str) -> Path:
        """返回任务目录下的文件夹索引快照目录。"""
        return self._task_root_dir(task_id) / "folders"

    def _indexes_root_dir(self) -> Path:
        """返回工作区索引根目录。"""
        p = self.registry.workspace / ".easy_ai" / "indexes"
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return p

    def _folder_indexes_dir(self) -> Path:
        """返回文件夹索引目录。"""
        p = self._indexes_root_dir() / "folders"
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return p

    def _folder_relpath(self, folder: Path) -> str:
        """返回 folder 相对 workspace 的路径字符串。"""
        try:
            rel = folder.resolve().relative_to(self.registry.workspace.resolve())
            s = str(rel).replace("\\", "/")
            return "." if s in ("", ".") else s
        except Exception:
            return str(folder)

    def _folder_slug(self, relpath: str) -> str:
        """把相对路径转换为稳定的文件夹索引 slug。"""
        rel = (relpath or ".").strip() or "."
        digest = hashlib.sha1(rel.encode("utf-8", errors="ignore")).hexdigest()[:12]
        name = rel.replace("\\", "_").replace("/", "_").replace(":", "_")
        name = re.sub(r"[^0-9A-Za-z._-]+", "_", name).strip("._") or "root"
        return f"{name}__{digest}"

    def _indexable_folders(self, max_dirs: int = 80) -> List[Path]:
        """收集需要建立索引的工作区文件夹列表。"""
        out: List[Path] = [self.registry.workspace]
        skip_names = {".git", ".easy_ai", "__pycache__", "node_modules", ".venv", "venv"}
        try:
            for p in self.registry.workspace.rglob("*"):
                if not p.is_dir():
                    continue
                if any(part in skip_names for part in p.parts):
                    continue
                out.append(p)
                if len(out) >= max_dirs:
                    break
        except Exception:
            pass
        uniq: List[Path] = []
        seen: set[str] = set()
        for p in out:
            key = str(p)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(p)
        return uniq

    def _guess_folder_usage(self, folder: Path) -> List[str]:
        """根据文件名和扩展名生成文件夹用途说明。"""
        names = set()
        suffixes: Dict[str, int] = {}
        try:
            for child in folder.iterdir():
                names.add(child.name.lower())
                if child.is_file():
                    suf = child.suffix.lower()
                    if suf:
                        suffixes[suf] = suffixes.get(suf, 0) + 1
        except Exception:
            pass

        lines: List[str] = []
        if folder == self.registry.workspace:
            lines.append("- 这是当前任务的工作区根目录，执行前应先查看整体结构、关键文件与隐藏目录。")
        if "readme.md" in names or "readme" in names:
            lines.append("- 目录内包含说明文档，优先阅读 README/说明文件理解用途与约束。")
        if any(s in suffixes for s in (".py", ".ipynb")):
            lines.append("- 目录以 Python 代码为主，执行前优先关注入口脚本、依赖与相邻模块。")
        if "package.json" in names:
            lines.append("- 目录包含前端或 Node 项目，优先查看 package.json、脚本命令与构建入口。")
        if "cargo.toml" in names:
            lines.append("- 目录包含 Rust 项目，优先查看 Cargo.toml、crate 结构与 src/。")
        if any(s in suffixes for s in (".md", ".txt", ".docx", ".pptx")):
            lines.append("- 目录包含文档资料，适合作为背景知识、输入材料或输出归档位置。")
        if any(s in suffixes for s in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
            lines.append("- 目录包含图片素材，适合做资源引用，不应当作代码入口。")
        if not lines:
            lines.append("- 目录用途未明确，执行前先查看目录索引中的文件与子目录列表。")
        lines.append("- 若任务明确涉及本目录，应优先读取该目录的 INDEX.md 与 USAGE.md 再行动。")
        return lines[:6]

    def _write_folder_index_files(self, folder: Path) -> Optional[dict]:
        """为单个文件夹写入索引与使用说明。"""
        rel = self._folder_relpath(folder)
        slug = self._folder_slug(rel)
        base = self._folder_indexes_dir() / slug
        index_fp = base / "INDEX.md"
        usage_fp = base / "USAGE.md"
        try:
            base.mkdir(parents=True, exist_ok=True)
        except Exception:
            return None

        subdirs: List[str] = []
        files: List[str] = []
        try:
            for child in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                name = child.name
                if name in {".git", ".easy_ai", "__pycache__", "node_modules", ".venv", "venv"}:
                    continue
                if child.is_dir():
                    subdirs.append(name)
                else:
                    files.append(name)
        except Exception:
            pass

        index_lines = [
            f"# INDEX.md",
            "",
            f"- 相对路径: {rel}",
            f"- 绝对路径: {folder}",
            f"- 子目录数: {len(subdirs)}",
            f"- 文件数: {len(files)}",
            "",
            "## 子目录",
        ]
        index_lines.extend([f"- {x}" for x in subdirs[:30]] or ["- (无)"])
        index_lines.extend(["", "## 文件"])
        index_lines.extend([f"- {x}" for x in files[:60]] or ["- (无)"])
        usage_lines = ["# USAGE.md", "", f"- 目录: {rel}", "", "## 功能使用说明"]
        usage_lines.extend(self._guess_folder_usage(folder))

        self._write_text_safe(index_fp, "\n".join(index_lines))
        self._write_text_safe(usage_fp, "\n".join(usage_lines))
        return {"relpath": rel, "slug": slug, "index_path": str(index_fp), "usage_path": str(usage_fp)}

    def _write_workspace_indexes(self) -> List[dict]:
        """为工作区建立文件夹索引清单。"""
        manifest: List[dict] = []
        for folder in self._indexable_folders():
            item = self._write_folder_index_files(folder)
            if item:
                manifest.append(item)
        root_index = self._indexes_root_dir() / "WORKSPACE_INDEX.md"
        lines = ["# WORKSPACE_INDEX.md", "", f"- Workspace: {self.registry.workspace}", "", "## Folders"]
        for item in manifest:
            lines.append(f"- {item['relpath']} -> {item['slug']}")
        self._write_text_safe(root_index, "\n".join(lines))
        return manifest

    def _choose_relevant_folders(self, prompt: str, manifest: List[dict], max_items: int = 6) -> List[dict]:
        """根据任务提示选择相关的文件夹索引。"""
        p = (prompt or "").lower()
        scored: List[tuple[int, dict]] = []
        for item in manifest:
            rel = str(item.get("relpath", "")).lower()
            score = 0
            if rel == ".":
                score += 100
            parts = [x for x in re.split(r"[\\/]", rel) if x and x != "."]
            for part in parts:
                if part and part.lower() in p:
                    score += 20
            if rel and rel != "." and rel in p:
                score += 30
            if score > 0:
                scored.append((score, item))
        if not scored:
            for item in manifest[:max_items]:
                scored.append((100 if item.get("relpath") == "." else 10, item))
        scored.sort(key=lambda x: (-x[0], str(x[1].get("relpath", ""))))
        out: List[dict] = []
        seen: set[str] = set()
        for _, item in scored:
            key = str(item.get("slug", ""))
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= max_items:
                break
        return out

    def _snapshot_task_folder_refs(self, task_id: str, prompt: str) -> List[dict]:
        """将任务相关文件夹索引快照到任务目录，便于追溯与执行时读取。"""
        manifest = self._write_workspace_indexes()
        selected = self._choose_relevant_folders(prompt, manifest)
        target_dir = self._task_folder_refs_dir(task_id)
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            return []
        refs: List[dict] = []
        for item in selected:
            slug = str(item.get("slug", "") or "")
            src_index = Path(str(item.get("index_path", "") or ""))
            src_usage = Path(str(item.get("usage_path", "") or ""))
            if not slug or not src_index.exists() or not src_usage.exists():
                continue
            dst = target_dir / slug
            try:
                dst.mkdir(parents=True, exist_ok=True)
            except Exception:
                continue
            index_text = self._read_text_safe(src_index, max_chars=12000)
            usage_text = self._read_text_safe(src_usage, max_chars=12000)
            self._write_text_safe(dst / "INDEX.md", index_text)
            self._write_text_safe(dst / "USAGE.md", usage_text)
            refs.append({
                "relpath": item.get("relpath", "."),
                "slug": slug,
                "index_path": str(dst / "INDEX.md"),
                "usage_path": str(dst / "USAGE.md"),
            })
        ref_lines = ["# folder_refs.md", "", "## Relevant Folders"]
        for ref in refs:
            ref_lines.append(f"- {ref['relpath']} -> {ref['slug']}")
        self._write_text_safe(self._task_root_dir(task_id) / "folder_refs.md", "\n".join(ref_lines))
        return refs

    def _build_task_folder_context(self, task_id: str, max_chars: int = 2400) -> str:
        """读取任务相关文件夹索引快照，用于执行时注入上下文。"""
        root = self._task_folder_refs_dir(task_id)
        if not root.exists():
            return ""
        blocks: List[str] = []
        try:
            for p in sorted(root.glob("*/INDEX.md"))[:4]:
                index_text = self._read_text_safe(p, max_chars=700)
                usage_text = self._read_text_safe(p.with_name("USAGE.md"), max_chars=700)
                rel = p.parent.name
                blocks.append(f"[Folder Snapshot: {rel}]\n{index_text}\n\n{usage_text}".strip())
        except Exception:
            return ""
        text = "\n\n".join([b for b in blocks if b.strip()]).strip()
        if len(text) > max_chars:
            text = text[:max_chars]
        return text

    def _sync_task_checklist_file(self, task_id: str) -> None:
        """将当前任务的 TodoRegistry 同步为 checklist.md 文件。"""
        todos = self.registry.todo_registry.list(task_id)
        lines = ["# checklist.md", "", "## Task Checklist"]
        if not todos:
            lines.append("- [ ] (暂无任务清单)")
        else:
            for t in sorted(todos, key=lambda x: x.created_at):
                mark = "x" if t.status == TaskStatus.COMPLETED else " "
                lines.append(f"- [{mark}] {t.description} ({t.id})")
        self._write_text_safe(self._task_checklist_path(task_id), "\n".join(lines))

    def _task_checklist_context(self, task_id: str, max_chars: int = 1800) -> str:
        """读取任务清单文件，用于执行时注入上下文。"""
        return self._read_text_safe(self._task_checklist_path(task_id), max_chars=max_chars)

    def _write_task_index_file(self, task: Task, extra: Optional[dict] = None) -> None:
        """写入任务索引文件，记录状态、清单、相关文件夹与产物。"""
        data = {
            "task_id": task.id,
            "description": task.description,
            "prompt": task.prompt,
            "status": task.status,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if isinstance(task.started_at, datetime) else None,
            "completed_at": task.completed_at.isoformat() if isinstance(task.completed_at, datetime) else None,
            "task_doc": str(self._task_doc_path(task.id)),
            "checklist": str(self._task_checklist_path(task.id)),
            "trace": str(self._task_trace_path(task.id)),
            "folder_refs": str(self._task_root_dir(task.id) / "folder_refs.md"),
        }
        if extra and isinstance(extra, dict):
            data.update(extra)
        self._write_text_safe(self._task_index_path(task.id), json.dumps(data, ensure_ascii=False, indent=2))

    def _append_task_trace(self, task_id: str, event: str, payload: Optional[dict] = None) -> None:
        """向任务 trace.jsonl 追加事件。"""
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            "task_id": task_id,
            "payload": payload or {},
        }
        try:
            fp = self._task_trace_path(task_id)
            fp.parent.mkdir(parents=True, exist_ok=True)
            with fp.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _recent_conversation_text(self, max_msgs: int = 40, max_chars: int = 6000) -> str:
        """获取最近对话片段（用于记忆编码）。"""
        recent = self.session.history[-max_msgs:]
        convo = "\n".join([f"{m.get('role','')}: {m.get('content','')}".strip() for m in recent if isinstance(m, dict)])
        convo = convo.strip()
        if len(convo) > max_chars:
            convo = convo[: max_chars - 800] + "\n... (truncated)\n" + convo[-800:]
        return convo

    def _encode_long_term_memories(self) -> None:
        """在退出时把对话“编码”为少而有用的长期记忆（用户级 + 项目级）。"""
        cfg = self._memory_cfg()
        if not bool(cfg.get("autoMemoryEnabled", True)):
            return
        if not self.llm.enabled:
            return
        convo = self._recent_conversation_text()
        if not convo:
            return

        user_fp = self._user_memory_path()
        proj_fp = self._project_memory_path()
        existing_user = self._read_text_safe(user_fp, max_chars=6000)
        existing_proj = self._read_text_safe(proj_fp, max_chars=6000)
        if not existing_user:
            existing_user = "# USER_MEMORY.md\n\n## 用户偏好与约束\n- (待沉淀)\n\n## 协作规则与流程\n- (待沉淀)\n"
            self._write_text_safe(user_fp, existing_user)
        if not existing_proj:
            existing_proj = "# PROJECT_MEMORY.md\n\n## 环境与项目事实\n- (待沉淀)\n\n## 默认策略\n- (待沉淀)\n\n## 搜索与证据策略\n- (待沉淀)\n"
            self._write_text_safe(proj_fp, existing_proj)

        prompt = (
            "你是一个终端 AI 助手的“长期记忆编码器”。目标：记忆不在于多，而在于有用。\n"
            "请基于近期对话与现有记忆，提取并更新两类长期记忆：\n"
            "A) 用户级（跨项目稳定）：语言偏好、系统环境、协作规则、代码风格偏好等。\n"
            "B) 项目级（当前 workspace 稳定）：工作目录、权限模式、工具策略、默认流程等。\n"
            "强约束：\n"
            "1) 只保留稳定可复用信息；不要写一次性调试过程、具体时事结论、临时任务内容。\n"
            "2) 不要编造事实；不确定就不要写。\n"
            "3) 输出必须是严格 JSON（不要代码块，不要额外文字）。\n"
            "JSON schema：\n"
            "{\n"
            '  "user_update": true|false,\n'
            '  "user_markdown": "string",\n'
            '  "project_update": true|false,\n'
            '  "project_markdown": "string"\n'
            "}\n"
            "当 update=false 时，对应 markdown 必须为空字符串。\n"
            "当 update=true 时：\n"
            "- user_markdown 必须以 '# USER_MEMORY.md' 开头，包含小节：'## 用户偏好与约束'、'## 协作规则与流程'。\n"
            "- project_markdown 必须以 '# PROJECT_MEMORY.md' 开头，包含小节：'## 环境与项目事实'、'## 默认策略'、'## 搜索与证据策略'。\n"
            "每个小节 3-8 条短 bullet，去重合并。\n\n"
            f"[现有 USER_MEMORY.md]\n{existing_user}\n\n"
            f"[现有 PROJECT_MEMORY.md]\n{existing_proj}\n\n"
            f"[近期对话]\n{convo}\n"
        )

        try:
            raw = self.llm.chat([], prompt, include_tools=False)
            m = re.search(r"\{[\s\S]*\}", raw or "")
            data = json.loads(m.group(0)) if m else {}
            if not isinstance(data, dict):
                return
        except Exception:
            return

        user_update = bool(data.get("user_update", False))
        proj_update = bool(data.get("project_update", False))
        user_md = str(data.get("user_markdown", "") or "").strip()
        proj_md = str(data.get("project_markdown", "") or "").strip()

        if user_update and user_md.startswith("# USER_MEMORY.md"):
            self._write_text_safe(user_fp, user_md)
        if proj_update and proj_md.startswith("# PROJECT_MEMORY.md"):
            self._write_text_safe(proj_fp, proj_md)

    def _append_session_jsonl(self, record: dict) -> None:
        """以 JSONL 追加写入 session 轨迹，便于回放与后续整理。"""
        try:
            p = self._memory_dir() / "sessions.jsonl"
            line = json.dumps(record, ensure_ascii=False)
            with p.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def _write_session_memory_md(self) -> Optional[Path]:
        """把当前会话的关键内容写成一条 memory.md，用于 AutoReview 整理。"""
        cfg = self._memory_cfg()
        if not bool(cfg.get("autoMemoryEnabled", True)):
            return None
        if not self.session.history:
            return None

        mem_dir = self._memory_dir()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        sid = self.session.session_id
        fp = mem_dir / f"session-{sid}-{stamp}.md"

        recent = self.session.history[-40:]
        convo = "\n".join([f"{m.get('role','')}: {m.get('content','')}".strip() for m in recent if isinstance(m, dict)])
        convo = convo.strip()
        if len(convo) > 6000:
            convo = convo[:5000] + "\n... (truncated)\n" + convo[-800:]

        if self.llm.enabled:
            prompt = (
                "你是一个终端 AI 助手的“会话记忆整理器”。请把下面的对话提炼成可长期复用的记忆笔记。\n"
                "要求：\n"
                "1) 必须用中文输出（专有名词/机构名可保留英文）。\n"
                "2) 只输出 Markdown（不要代码块围栏）。\n"
                "3) 结构固定：## 关键结论 / ## 事实与证据 / ## 待办与风险 / ## 重要偏好与约束。\n"
                "4) 不要编造事实；若缺证据，写清楚“未验证/需进一步抓取”。\n\n"
                f"[对话片段]\n{convo}\n"
            )
            md = self.llm.chat([], prompt, include_tools=False)
            content = md.strip() + "\n"
        else:
            content = "# 会话记忆\n\n## 对话摘录\n\n" + convo + "\n"

        try:
            fp.write_text(content, encoding="utf-8")
            return fp
        except Exception:
            return None

    def consolidate_on_exit(self) -> None:
        """退出时整理一次 memory：写 session、编码长期记忆、更新 Topics 索引。"""
        cfg = self._memory_cfg()
        if not bool(cfg.get("autoMemoryEnabled", True)):
            return
        if not bool(cfg.get("consolidateOnExit", True)):
            return

        self._write_session_memory_md()
        self._encode_long_term_memories()
        try:
            self.auto_review.consolidate_on_exit(None)
        except Exception:
            pass

    # ----- Routing -----

    def route(self, prompt: str) -> list:
        tokens = {t.lower() for t in prompt.replace("/", " ").replace("-", " ").split() if t}
        matches = []
        for cmd in COMMANDS:
            s = self._score(tokens, cmd)
            if s > 0:
                matches.append(Match("command", cmd.name, cmd.source_hint, s))
        for tool in TOOLS:
            s = self._score(tokens, tool)
            if s > 0:
                matches.append(Match("tool", tool.name, tool.source_hint, s))
        matches.sort(key=lambda m: (-m.score, m.kind, m.name))
        return matches

    @staticmethod
    def _score(tokens: set, module: Module) -> int:
        haystacks = [module.name.lower(), module.responsibility.lower()]
        return sum(1 for t in tokens if any(t in h for h in haystacks))

    # ----- Main submit -----

    def submit(self, prompt: str) -> TurnResult:
        if len(self.session.messages) >= self.session.max_turns:
            return TurnResult(prompt, "Max turns reached.", (), (), "max_turns_reached")

        # Check session compaction
        if self.registry.compactor.should_compact(self.session.history):
            self.session.history = self.registry.compactor.compact(self.session.history, self.llm)

        # 1. Try direct command (/cmd or bare cmd)
        cmd_name, args = self._parse_direct_command(prompt)
        if cmd_name:
            result = self.registry.run_command(cmd_name, args)
            if result.special:
                return TurnResult(prompt, result.special, (cmd_name,), (), "user_request")
            output = colored(f"Error: {result.error}", Color.RED) if result.error else result.output
            self.session.messages.append(prompt)
            return TurnResult(prompt, output, (cmd_name,), (), "completed")

        # 2. Try tool call shorthand (read / grep / bash ...)
        tool_name, tool_args = self._parse_tool_call(prompt)
        if tool_name:
            result = self.registry.run_tool(tool_name, tool_args)
            output = colored(f"Error: {result.error}", Color.RED) if result.error else result.output
            self.session.messages.append(prompt)
            return TurnResult(prompt, output, (), (tool_name,), "completed")

        # 3. Agent Mode (if AI enabled) - 自然语言理解 + 工具循环调用
        if self.ai_mode and self.llm.enabled:
            if self._is_xiaobao_article_task(prompt):
                return self._submit_xiaobao_article(prompt)
            return self._submit_agent(prompt)

        # 4. Fuzzy routing (no AI)
        return self._submit_fuzzy(prompt)

    def _submit_agent(self, prompt: str) -> TurnResult:
        """Agent 循环模式: 自然语言 → LLM 理解 → 循环调用工具 → 返回结果。"""
        # 显示正在使用 Agent 模式
        log_line(colored("[Agent Mode] ", Color.CYAN) + colored("Processing your request...", Color.GRAY))

        created_task: Optional[Task] = None
        intent = {}
        try:
            if hasattr(self.agent, "_classify_intent"):
                intent = self.agent._classify_intent(prompt) or {}
        except Exception:
            intent = {}
        mode = str(intent.get("mode") or "").strip().lower()
        force_web = bool(intent.get("force_web_research", False))
        needs_tools = (mode == "tool_loop") or force_web

        if self._is_complex_task(prompt) and needs_tools:
            created_task = self.registry.task_registry.create(description=prompt[:80], prompt=prompt)
            self.registry.task_registry.update(created_task.id, status=TaskStatus.RUNNING, started_at=datetime.now())
            self.registry.current_task_id = created_task.id
            self.registry.current_task_doc_path = self._prepare_task_doc(created_task.id, prompt)
            self._append_task_trace(created_task.id, "task_started", {"prompt": prompt})
            self._write_task_index_file(created_task)
        
        # 运行 Agent 循环
        seed = self._recent_context(self.context_rounds)
        final_answer, steps, stop_reason = self.agent.run(prompt, seed_history=seed)

        def _is_time_sensitive(p: str) -> bool:
            s = (p or "")
            return any(k in s for k in ("最近", "最新", "刚刚", "过去", "小时内", "12小时", "24小时", "今日", "今天", "实时"))

        def _webfetch_sources(stps: List[AgentStep]) -> List[dict]:
            out: List[dict] = []
            for st in stps or []:
                tc = getattr(st, "action", None)
                if not tc or getattr(tc, "tool_name", "") != "WebFetchTool":
                    continue
                url = ""
                try:
                    if isinstance(tc.tool_input, dict):
                        url = str(tc.tool_input.get("url") or "")
                except Exception:
                    url = ""
                ok = isinstance(st.observation, str) and (not st.observation.startswith("Error:"))
                host = ""
                try:
                    host = (urlparse(url).netloc or "").lower()
                except Exception:
                    host = ""
                out.append({"url": url, "host": host, "ok": ok})
            return out

        if _is_time_sensitive(prompt):
            sources = _webfetch_sources(steps or [])
            ok_hosts = sorted({s["host"] for s in sources if s.get("ok") and s.get("host")})
            if len(ok_hosts) < 2:
                fetched_ok = [s for s in sources if s.get("ok") and s.get("url")]
                fetched_fail = [s for s in sources if (not s.get("ok")) and s.get("url")]
                lines = [
                    "由于未能抓取到至少 2 个不同域名的来源正文进行交叉验证，我无法可靠地给出“最近若干小时内”的事实性更新。",
                    "",
                    "## 已尝试抓取的来源",
                ]
                if fetched_ok:
                    lines.append("### 抓取成功")
                    for s in fetched_ok[:6]:
                        lines.append(f"- {s['url']}")
                if fetched_fail:
                    lines.append("### 抓取失败")
                    for s in fetched_fail[:6]:
                        lines.append(f"- {s['url']}")
                lines.extend([
                    "",
                    "## 下一步建议",
                    "- 继续用 WebSearchTool/NewsSearchTool 找到权威通讯社/官方渠道链接，再用 WebFetchTool 抓取全文",
                    "- 只有在来源正文可读且至少 2 个独立来源一致时，才输出具体条款/时间点/伤亡等细节",
                ])
                final_answer = "\n".join(lines).strip()
                stop_reason = "insufficient_evidence"
        
        # 显示执行步骤
        if self.cfg["shell"].get("show_tool_calls", True) and steps:
            log_line(colored("--- Agent Steps ---", Color.GRAY))
            for step in steps:
                if step.action:
                    log_line(colored(f"[{step.step_num}] ", Color.MAGENTA) + colored(f"{step.action.tool_name}", Color.YELLOW) + f" -> {step.observation[:80]}...")
                else:
                    log_line(colored(f"[{step.step_num}] ", Color.MAGENTA) + "Final answer")
            log_line(colored("-------------------", Color.GRAY))
        
        # 更新历史
        self.session.history.append({"role": "user", "content": prompt})
        self.session.history.append({"role": "assistant", "content": final_answer})
        self.session.messages.append(prompt)

        try:
            tools_used: list[str] = []
            for s in (steps or []):
                tc = getattr(s, "action", None)
                if tc and getattr(tc, "tool_name", ""):
                    tools_used.append(str(tc.tool_name))
            record = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "session_id": self.session.session_id,
                "prompt": prompt,
                "stop_reason": stop_reason,
                "tools_used": tools_used,
            }
            if created_task:
                record["task_id"] = created_task.id
            self._append_session_jsonl(record)
        except Exception:
            pass
        
        if self.auto_review.enabled:
            should, reason = self.auto_review.should_review()
            if should:
                self.auto_review.autoreview(self.llm if self.llm.enabled else None)

        if created_task:
            self._sync_task_checklist_file(created_task.id)
            pending = [t for t in self.registry.todo_registry.list(created_task.id) if t.status != TaskStatus.COMPLETED]
            status = TaskStatus.COMPLETED if stop_reason == "completed" and not pending else TaskStatus.FAILED
            self.registry.task_registry.update(created_task.id, status=status, completed_at=datetime.now())
            created_task = self.registry.task_registry.get(created_task.id) or created_task
            self._write_task_index_file(created_task, extra={
                "stop_reason": stop_reason,
                "pending_todo_count": len(pending),
                "final_answer_preview": final_answer[:500],
            })
            self._append_task_trace(created_task.id, "task_finished", {
                "stop_reason": stop_reason,
                "status": status,
                "pending_todo_count": len(pending),
            })
            self.registry.current_task_id = None
            self.registry.current_task_doc_path = None

        # 代码/文件生成任务验证：检查声称创建的文件是否真的存在
        self._verify_file_creation(prompt, steps or [])

        return TurnResult(prompt, final_answer, (), (), stop_reason, ai_used=True)

    def _verify_file_creation(self, user_prompt: str, steps: List[AgentStep]) -> None:
        """验证代码/文件生成任务的文件创建结果."""
        p = (user_prompt or "").strip().lower()
        is_code_task = any(k in p for k in ("编程", "代码", "游戏", "写一个", "创建", "实现", "生成"))
        if not is_code_task:
            return
        
        all_writes: List[str] = []
        for st in steps:
            tc = getattr(st, "action", None)
            if not tc or getattr(tc, "tool_name", "") != "FileWriteTool":
                continue
            try:
                if isinstance(tc.tool_input, dict):
                    path = str(tc.tool_input.get("file_path") or "")
                    if path:
                        all_writes.append(path)
            except Exception:
                pass
        
        if not all_writes:
            return
        
        missing: List[str] = []
        for wp in all_writes:
            fp = Path(wp)
            if not fp.is_absolute():
                fp = self.registry.workspace / wp
            if not fp.exists():
                missing.append(wp)
        
        if missing:
            log_line(colored("[文件验证警告] ", Color.RED) + colored(f"以下声称创建的文件不存在: {', '.join(missing)}", Color.YELLOW))

    def _is_complex_task(self, prompt: str) -> bool:
        p = (prompt or "").strip()
        if not p:
            return False
        if "\n" in p:
            return True
        if len(p) >= 60:
            return True
        keywords = ["并且", "然后", "同时", "分别", "一步步", "逐步", "规划", "方案", "实现", "重构", "优化", "搭建", "研究", "调研", "分析", "编程", "代码", "游戏", "写一个", "创建一个"]
        if any(k in p for k in keywords):
            return True
        punct = sum(1 for ch in p if ch in "，,。.;；:：")
        if punct >= 2:
            return True
        return False

    def _prepare_task_doc(self, task_id: str, user_prompt: str) -> Optional[Path]:
        """为任务建立可追溯产物：任务文档、清单、索引、文件夹索引快照。"""
        task_dir = self._task_root_dir(task_id)
        try:
            task_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            return None

        doc_path = self._task_doc_path(task_id)
        base = ""
        if doc_path.exists():
            try:
                base = doc_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                base = ""

        planning_prompt = (
            "你是一个终端里的 AI 工程代理。请为下面用户需求生成可执行的任务分解，用于写入任务文档。\n"
            "要求：\n"
            "1) 只输出 Markdown（不要代码块围栏）。\n"
            "2) 包含：任务目标、验收标准、ToDoList（每项以 - [Todo] 开头）、风险与权限（需要哪些权限/工具）。\n"
            "3) 不允许编造外部项目内容；如果涉及 GitHub/网页/远程仓库，必须写清楚“先拉取/抓取证据再分析”。\n"
            f"\n用户需求：\n{user_prompt}\n"
        )
        plan_md = self.llm.chat([], planning_prompt, include_tools=False)
        uniq: list[str] = []
        try:
            todos: list[str] = []
            for line in (plan_md or "").splitlines():
                m = re.match(r"\s*-\s*\[todo\]\s*(.+)\s*$", line, re.IGNORECASE)
                if not m:
                    continue
                item = (m.group(1) or "").strip()
                if item:
                    todos.append(item)
            if todos:
                seen: set[str] = set()
                for t in todos:
                    k = t.strip().lower()
                    if k and k not in seen:
                        seen.add(k)
                        uniq.append(t.strip())
            need_verify = True
            for t in uniq:
                if re.search(r"(验证|自测|测试|test|verify|check)", t, re.IGNORECASE):
                    need_verify = False
                    break
            if need_verify:
                uniq.append("执行验证/自测并记录结果（例如运行测试/检查输出/复现步骤）")
                self.registry.todo_registry.clear(task_id)
                for t in uniq[:30]:
                    self.registry.todo_registry.create(task_id, t)
        except Exception:
            pass
        self._sync_task_checklist_file(task_id)
        folder_hint = user_prompt + ("\n" + "\n".join(uniq[:30]) if uniq else "")
        folder_refs = self._snapshot_task_folder_refs(task_id, folder_hint)
        stamp = now_ts()
        section = f"\n\n## Task [{task_id}] [{stamp}]\n\n{plan_md.strip()}\n"
        try:
            doc_path.write_text((base + section).strip() + "\n", encoding="utf-8")
        except Exception:
            return None
        task = self.registry.task_registry.get(task_id)
        if task:
            self._write_task_index_file(task, extra={
                "folder_ref_count": len(folder_refs),
                "task_dir": str(task_dir),
            })
        self._append_task_trace(task_id, "task_prepared", {
            "task_doc": str(doc_path),
            "checklist": str(self._task_checklist_path(task_id)),
            "folder_ref_count": len(folder_refs),
        })
        return doc_path

    def _is_xiaobao_article_task(self, prompt: str) -> bool:
        """判断是否为“基于 xiaobao 技能的写作”类任务（避免进入工程型工具循环导致跑偏）。"""
        p = (prompt or "").strip().lower()
        if not p:
            return False
        return ("xiaobao" in p) and ("技能" in prompt) and any(k in prompt for k in ("文章", "写一篇", "写一篇文章", "写文章"))

    def _find_xiaobao_root(self) -> Optional[Path]:
        """在当前 workspace 内定位 xiaobao 目录。"""
        w = self.registry.workspace
        direct = w / "xiaobao"
        if direct.exists() and direct.is_dir():
            return direct
        try:
            for p in w.rglob("xiaobao"):
                if p.is_dir():
                    return p
        except Exception:
            return None
        return None

    def _recent_context(self, rounds: int) -> List[dict]:
        n = 3
        try:
            n = int(rounds)
        except Exception:
            n = 3
        n = max(0, min(n, 10))
        if n == 0:
            return []
        items = self.session.history[-(n * 2):]
        out: List[dict] = []
        for m in items:
            role = m.get("role")
            content = m.get("content", "")
            if role not in ("user", "assistant"):
                continue
            if not isinstance(content, str):
                content = str(content)
            content = content.strip()
            if not content:
                continue
            if len(content) > 1200:
                content = content[:1000] + "\n... (truncated)\n" + content[-120:]
            out.append({"role": role, "content": content})
        return out

    @staticmethod
    def _decode_seed_function_calls(text: str) -> List["ToolCall"]:
        """
        兼容部分模型输出的 <seed:tool_call> / <function=...> ... </function> 格式。
        仅解析为内部工具调用，不执行任何外部函数。
        """
        out: List[ToolCall] = []
        if not isinstance(text, str) or not text:
            return out

        for m in re.finditer(r"<function=([a-zA-Z0-9_]+)>([\s\S]*?)</function>", text):
            fn = (m.group(1) or "").strip().lower()
            body = m.group(2) or ""
            if fn in ("sequentialthinking",):
                continue

            params: dict = {}
            for pm in re.finditer(r"<parameter=([^>]+)>([\s\S]*?)</parameter>", body):
                k = (pm.group(1) or "").strip()
                v = (pm.group(2) or "").strip()
                if k:
                    params[k] = v

            tool_name = ""
            if fn == "websearch":
                tool_name = "NewsSearchTool"
            elif fn == "webfetch":
                tool_name = "WebFetchTool"
            elif fn == "shell_exec":
                tool_name = "BashTool"
            elif fn == "bash":
                tool_name = "BashTool"
            elif fn == "grep":
                tool_name = "GrepTool"
            elif fn == "glob":
                tool_name = "GlobTool"

            if tool_name:
                out.append(ToolCall(tool_name=tool_name, tool_input=params, raw_json=""))

        if out:
            return out

        lm = re.search(r"<list>\s*<folderPath>([\s\S]*?)</folderPath>\s*</list>", text)
        if lm:
            folder = (lm.group(1) or "").strip() or "."
            out.append(ToolCall(tool_name="BashTool", tool_input={"command": f"ls -la {folder}"}, raw_json=""))
        return out

    def _submit_xiaobao_article(self, prompt: str) -> TurnResult:
        """读取 xiaobao 目录的技能材料并生成文章（不暴露工具定义、不写入无关文件）。"""
        xroot = self._find_xiaobao_root()
        if not xroot:
            out = "未在当前 workspace 内找到 xiaobao 目录（期望路径类似：./xiaobao 或 ./files/xiaobao）。"
            self.session.messages.append(prompt)
            return TurnResult(prompt, out, (), (), "completed", ai_used=False)

        skill_dir = xroot / "3_System_Core" / "skills"
        memory_dir = xroot / "3_System_Core" / "memory"
        candidates: list[Path] = []

        if skill_dir.exists():
            candidates.extend(sorted(skill_dir.glob("*.md")))
        for extra in ("key_insights.md", "approval_rules.md", "AGENTS.md", "README.md"):
            p = (xroot / "3_System_Core" / extra)
            if p.exists():
                candidates.append(p)
        if memory_dir.exists():
            for extra in ("key_insights.md", "README.md"):
                p = memory_dir / extra
                if p.exists():
                    candidates.append(p)

        materials = []
        for fp in candidates[:8]:
            try:
                txt = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            txt = txt.strip()
            if not txt:
                continue
            if len(txt) > 1800:
                txt = txt[:1800] + "\n... (truncated)"
            materials.append(f"[{fp.name}]\n{txt}")

        material_block = "\n\n".join(materials) if materials else "(未找到可用技能材料文件)"

        writing_prompt = (
            "你将基于给定的 xiaobao 技能材料，用中文写一篇文章。\n"
            "主题：AI 时代组织可能会变成“钻石型”：基层执行岗位减少，中层判断/协调岗位增加。\n\n"
            "写作要求：\n"
            "1) 文章结构清晰：引言→机制解释→组织结构变化→管理建议→结语。\n"
            "2) 给出至少 3 个具体例子（岗位/流程/场景）。\n"
            "3) 讨论潜在风险（信息过载、决策拥堵、责任模糊）与对应治理方式（流程/指标/授权/工具）。\n"
            "4) 尽量吸收技能材料中的表达方式与分析框架，但不要逐字抄袭。\n"
            "5) 只输出文章正文，不输出工具 JSON，不创建/修改任何文件。\n\n"
            f"【xiaobao 技能材料】\n{material_block}\n\n"
            f"【用户需求】\n{prompt}\n"
        )

        seed = self._recent_context(self.context_rounds)
        article = self.llm.chat(seed, writing_prompt, include_tools=False).strip()

        self.session.history.append({"role": "user", "content": prompt})
        self.session.history.append({"role": "assistant", "content": article})
        self.session.messages.append(prompt)

        return TurnResult(prompt, article, (), (), "completed", ai_used=True)

    def _submit_to_ai(self, prompt: str) -> TurnResult:
        """Send prompt to LLM, update conversation history."""
        # Build context: workspace summary prepended to first turn
        context_prefix = ""
        if not self.session.history:
            py_files = list(self.registry.workspace.rglob("*.py"))
            context_prefix = (
                f"[Workspace: {self.registry.workspace}  "
                f"Python files: {len(py_files)}  "
                f"Has git: {(self.registry.workspace / '.git').exists()}]\n\n"
            )

        user_message = context_prefix + prompt

        # Keep history trimmed to max_context_turns (pairs)
        trimmed_history = self.session.history[-(self.max_context_turns * 2):]

        ai_reply = self.llm.chat(trimmed_history, user_message)

        # Update history
        self.session.history.append({"role": "user",      "content": prompt})
        self.session.history.append({"role": "assistant", "content": ai_reply})
        self.session.messages.append(prompt)

        if self.auto_review.enabled:
            should, reason = self.auto_review.should_review()
            if should:
                self.auto_review.autoreview(self.llm if self.llm.enabled else None)

        return TurnResult(prompt, ai_reply, (), (), "completed", ai_used=True)

    def _submit_fuzzy(self, prompt: str) -> TurnResult:
        """Fuzzy token-score routing without AI."""
        matches = self.route(prompt)[:3]
        outputs, cmd_names, tool_names = [], [], []
        for m in matches:
            if m.kind == "command":
                r = self.registry.run_command(m.name, prompt)
                if r.special:
                    return TurnResult(prompt, r.special, (m.name,), (), "user_request")
                outputs.append(r.output if r.success else colored(f"[{m.name}] Error: {r.error}", Color.RED))
                cmd_names.append(m.name)
            else:
                r = self.registry.run_tool(m.name, prompt)
                outputs.append(r.output if r.success else colored(f"[{m.name}] Error: {r.error}", Color.RED))
                tool_names.append(m.name)

        if not outputs:
            output = colored(
                f"No command matched: {prompt!r}\n"
                "  (Hint: configure AI in config.json for free-form questions)",
                Color.YELLOW,
            )
        else:
            output = "\n\n".join(outputs)

        self.session.messages.append(prompt)
        return TurnResult(prompt, output, tuple(cmd_names), tuple(tool_names), "completed")

    # ----- Parsing helpers -----

    def _parse_direct_command(self, prompt: str) -> tuple:
        stripped = prompt.strip()
        if stripped.startswith("/"):
            parts = stripped[1:].split(None, 1)
            name = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            if any(c.name == name for c in COMMANDS):
                return name, args
        parts = stripped.split(None, 1)
        if parts:
            name = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            if any(c.name == name for c in COMMANDS):
                return name, args
        return "", ""

    def _parse_tool_call(self, prompt: str) -> tuple:
        parts = prompt.strip().split(None, 1)
        if not parts:
            return "", ""
        first = parts[0].lower()
        args  = parts[1] if len(parts) > 1 else ""
        if first in TOOL_ALIASES:
            return TOOL_ALIASES[first], args
        for t in TOOLS:
            if t.name.lower() == first:
                return t.name, args
        return "", ""


# ==================== Interactive Shell ====================

class EasyAIShell:
    """Interactive CLI shell with AI support for natural language to command execution."""

    VERSION = "1.3.0"

    def __init__(self, workspace: Optional[Path] = None, cfg: Optional[dict] = None, ai_enabled: bool = True):
        self.cfg = cfg or DEFAULT_CONFIG
        if not ai_enabled:
            self.cfg["shell"]["ai_mode"] = False
        self.workspace = workspace or Path.cwd()
        self.engine = QueryEngine(self.workspace, self.cfg)

    # ----- Printing helpers -----

    def _print(self, text: str, end: str = "\n"):
        print(text, end=end)

    def _print_banner(self):
        w   = self.engine.registry.workspace
        sid = self.engine.session.session_id
        perm_mode = self.engine.registry.permission.get_mode()
        ai_status = (
            colored("[ON]", Color.GREEN)
            if (self.engine.ai_mode and self.engine.llm.enabled)
            else colored("[OFF]", Color.YELLOW)
        )
        model_info = (
            colored(f" {self.engine.llm.model} ({self.engine.llm.provider})", Color.MAGENTA)
            if (self.engine.ai_mode and self.engine.llm.enabled)
            else ""
        )

        self._print(colored("=================================================", Color.CYAN))
        self._print(colored(f" Easy AI Shell v{self.VERSION} (Agent Mode)", Color.CYAN, bold=True))
        self._print(colored("=================================================", Color.CYAN))
        self._print(f"  Session: {colored(sid, Color.YELLOW)}")
        self._print(f"  Workspace: {colored(str(w), Color.GREEN)}")
        self._print(f"  Permission: {colored(perm_mode, Color.BLUE)}")
        self._print(f"  AI: {ai_status}{model_info}")
        self._print(colored("-------------------------------------------------", Color.GRAY))
        self._print("  Agent Mode: Natural language → LLM → Tools → Result")
        self._print(f"  Commands: workspace, autoreview, memory, task, team, cron, mcp, lsp, plugin, lock, stale")
        self._print(f"  Type {colored('help', Color.CYAN)} for commands  |  {colored('exit', Color.CYAN)} to quit")
        if not (self.engine.ai_mode and self.engine.llm.enabled):
            self._print(f"  {colored('-> Edit config.json to enable AI.', Color.YELLOW)}")
        self._print(colored("-------------------------------------------------", Color.GRAY))
        self._print("")

    def _prompt_str(self) -> str:
        sid  = self.engine.session.session_id
        turn = len(self.engine.session.messages)
        wd   = self.engine.registry.workspace.name
        ai_marker = colored("*", Color.MAGENTA) if (self.engine.ai_mode and self.engine.llm.enabled) else ""
        return f"{colored(wd, Color.GREEN)}:{colored(sid, Color.YELLOW)}[{turn}]{ai_marker}> "

    def _print_result(self, result: TurnResult):
        if result.output:
            self._print(result.output)

        # Metadata footer (dim)
        parts = []
        if result.ai_used:
            parts.append(colored("ai", Color.MAGENTA))
        if result.matched_commands:
            parts.append(f"cmd:{','.join(result.matched_commands)}")
        if result.matched_tools:
            parts.append(f"tool:{','.join(result.matched_tools)}")
        if parts:
            self._print(colored(f"  [{' | '.join(parts)}]", Color.GRAY))
        self._print("")

    # ----- Run modes -----

    def run_interactive(self):
        """Interactive REPL loop"""
        self._print_banner()
        while True:
            try:
                user_input = input(self._prompt_str()).strip()
            except EOFError:
                try:
                    self.engine.consolidate_on_exit()
                except Exception:
                    pass
                self._print(colored("\nGoodbye!", Color.CYAN))
                break
            except KeyboardInterrupt:
                self._print(colored("\n(Ctrl+C - type 'exit' to quit)", Color.YELLOW))
                continue

            if not user_input:
                continue

            result = self.engine.submit(user_input)

            if result.output in ("CLEAR", "EXIT"):
                if result.output == "CLEAR":
                    os.system("cls" if os.name == "nt" else "clear")
                    self._print_banner()
                else:
                    try:
                        self.engine.consolidate_on_exit()
                    except Exception:
                        pass
                    self._print(colored("Goodbye!", Color.CYAN))
                    break
            else:
                self._print_result(result)

    def run_once(self, prompt: str):
        """Run a single prompt and print output"""
        try:
            result = self.engine.submit(prompt)
            if result.output not in ("CLEAR", "EXIT"):
                print(result.output)
        finally:
            try:
                self.engine.consolidate_on_exit()
            except Exception:
                pass


# ==================== Entry Point ====================

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Easy AI Shell - Lightweight AI Coding Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Features:
  - Agent Mode: Natural language → LLM understanding → Tool execution → Loop until done
  - Permission System (read-only/workspace-write/danger-full-access)
  - Task Management (create/get/list/stop)
  - Team & Cron Jobs
  - MCP Client
  - LSP Client
  - Session Compact
  - Branch Lock
  - Stale Branch Detection
  - Plugin System
  - AutoReview Memory Consolidation

Examples:
  python easy_ai_shell.py                    # interactive Agent mode
  python easy_ai_shell.py -p "帮我创建一个Python文件"  # Agent 自动执行
  python easy_ai_shell.py -p "查看当前目录文件"        # Agent 自动选择工具
  python easy_ai_shell.py -p "用git status"           # 也可以用命令
  python easy_ai_shell.py --no-ai -p "files"        # 纯命令模式
  python easy_ai_shell.py -w C:\\myproject          # 指定工作目录
  python easy_ai_shell.py -c my_config.json         # 使用自定义配置
        """,
    )
    parser.add_argument("-p", "--print",     dest="prompt",  help="Run a single prompt (non-interactive)")
    parser.add_argument("-w", "--workspace", default=None,   help="Workspace directory")
    parser.add_argument("-c", "--config",    default=None,   help="Path to config.json")
    parser.add_argument("--no-ai",           action="store_true", help="Disable AI, use command routing only")
    args = parser.parse_args()

    # Load config
    config_path = Path(args.config) if args.config else None
    cfg = load_config(config_path)
    if args.prompt:
        cfg.setdefault("shell", {})
        cfg["shell"]["non_interactive"] = True

    workspace = Path(args.workspace) if args.workspace else None
    shell = EasyAIShell(workspace=workspace, cfg=cfg, ai_enabled=not args.no_ai)

    if args.prompt:
        shell.run_once(args.prompt)
    else:
        shell.run_interactive()


if __name__ == "__main__":
    main()
