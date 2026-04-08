#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Easy AI Shell - Enhanced Version with AGI Growth Engine
轻量级 Python AI 编码助手，集成了仿生人类成长模式的AGI架构，
具备自主成长能力，能够通过与用户的持续交互实现渐进式发展。

核心功能:
- Agent Mode (自然语言 → LLM理解 → 自动调用工具 → 循环执行)
- Permission System (权限系统)
- TaskRegistry (任务管理 - 简化版)
- AutoReview (记忆自动整理)
- AGI Growth Engine (仿生人类成长模式的五层架构)

Usage:
    python easy_ai_shell_minimal.py              # 交互模式（AI Agent + 工具调用）
    python easy_ai_shell_minimal.py -p "prompt"  # 单次执行模式
    python easy_ai_shell_minimal.py -w <dir>     # 指定工作目录
    python easy_ai_shell_minimal.py --no-ai      # 纯命令模式（不调用 AI）
"""

import os
import sys
import json
import hashlib
import subprocess
import re
import shlex
import sqlite3
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

# 导入AGI成长系统
try:
    from agi_growth_engine import AGIGrowthSystem
except ImportError:
    print("Warning: AGI Growth Engine not found. Install it to enable advanced growth features.")
    AGIGrowthSystem = None

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


# ==================== Provider Registry ====================

class ProviderRegistry:
    PROVIDERS = {
        "openai": {
            "name": "OpenAI",
            "transport": "openai_chat",
            "base_url": "https://api.openai.com/v1",
            "env_keys": ["OPENAI_API_KEY"],
        },
        "anthropic": {
            "name": "Anthropic",
            "transport": "anthropic_messages",
            "base_url": "https://api.anthropic.com/v1",
            "env_keys": ["ANTHROPIC_API_KEY"],
        },
        "openrouter": {
            "name": "OpenRouter",
            "transport": "openai_chat",
            "base_url": "https://openrouter.ai/api/v1",
            "is_aggregator": True,
            "env_keys": ["OPENAI_API_KEY"],
        },
        "qwen": {
            "name": "通义千问 (Qwen)",
            "transport": "openai_chat",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "env_keys": ["DASHSCOPE_API_KEY"],
        },
    }

    @classmethod
    def get(cls, provider_name: str) -> Optional[Dict[str, Any]]:
        return cls.PROVIDERS.get(provider_name)

    @classmethod
    def list_all(cls) -> List[str]:
        return list(cls.PROVIDERS.keys())

    @classmethod
    def get_env_keys(cls, provider_name: str) -> List[str]:
        provider = cls.get(provider_name)
        return provider.get("env_keys", []) if provider else []

    @classmethod
    def is_valid_provider(cls, provider_name: str) -> bool:
        return provider_name in cls.PROVIDERS


# ==================== Data Models ====================

@dataclass
class Module:
    name: str
    path: str
    size: int
    mtime: float

@dataclass
class Match:
    path: str
    line_number: int
    content: str
    score: float = 0.0

@dataclass
class ExecutionResult:
    success: bool
    output: str
    error: str = ""

@dataclass
class TurnResult:
    prompt: str
    output: str
    matched_tools: tuple
    matched_commands: tuple
    stop_reason: str
    ai_used: bool

@dataclass
class ToolCall:
    tool_name: str
    tool_input: dict
    id: str = ""

@dataclass
class AgentStep:
    step_num: int
    action: Optional[ToolCall]
    observation: str

@dataclass
class Session:
    session_id: str
    created_at: datetime
    history: List[dict] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ==================== Tool Registry ====================

class ToolRegistry:
    """Simplified tool registry without MCP/LSP dependencies"""

    def __init__(self):
        self.tools = {}
        self._lock = threading.Lock()
        self._register_default_tools()

    def _register_default_tools(self):
        """Register default tools"""
        self.register("FileWriteTool", {
            "name": "FileWriteTool",
            "description": "Write content to a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["file_path", "content"]
            }
        })

        self.register("FileReadTool", {
            "name": "FileReadTool",
            "description": "Read content from a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                },
                "required": ["file_path"]
            }
        })

        self.register("ShellTool", {
            "name": "ShellTool",
            "description": "Execute shell commands",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"},
                },
                "required": ["command"]
            }
        })

        self.register("WebSearchTool", {
            "name": "WebSearchTool",
            "description": "Search the web for information",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "description": "Number of results", "default": 5},
                },
                "required": ["query"]
            }
        })

        self.register("WebFetchTool", {
            "name": "WebFetchTool",
            "description": "Fetch content from a URL",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                },
                "required": ["url"]
            }
        })

    def register(self, name: str, tool_spec: dict):
        """Register a new tool"""
        with self._lock:
            self.tools[name] = tool_spec

    def get(self, name: str) -> Optional[dict]:
        """Get a tool by name"""
        with self._lock:
            return self.tools.get(name)

    def list_all(self) -> List[dict]:
        """List all registered tools"""
        with self._lock:
            return [{"name": name, **spec} for name, spec in self.tools.items()]

    def execute(self, name: str, payload: dict) -> ExecutionResult:
        """Execute a tool with given payload"""
        tool = self.get(name)
        if not tool:
            return ExecutionResult(False, "", f"Tool '{name}' not found")

        # Execute the specific tool
        if name == "FileWriteTool":
            return self._tool_file_write(payload)
        elif name == "FileReadTool":
            return self._tool_file_read(payload)
        elif name == "ShellTool":
            return self._tool_shell(payload)
        elif name == "WebSearchTool":
            return self._tool_web_search(payload)
        elif name == "WebFetchTool":
            return self._tool_web_fetch(payload)
        else:
            return ExecutionResult(False, "", f"Unknown tool: {name}")

    def _tool_file_write(self, payload: dict) -> ExecutionResult:
        """Write content to a file"""
        try:
            file_path = payload.get("file_path", "")
            content = payload.get("content", "")

            if not file_path:
                return ExecutionResult(False, "", "Missing file_path parameter")

            # Validate file path for security
            path_obj = Path(file_path)
            if not path_obj.is_absolute():
                path_obj = Path.cwd() / path_obj

            # Resolve to prevent directory traversal
            resolved_path = path_obj.resolve()
            cwd_resolved = Path.cwd().resolve()
            
            if not str(resolved_path).startswith(str(cwd_resolved)):
                return ExecutionResult(False, "", "File path outside working directory not allowed")

            # Create parent directories if they don't exist
            resolved_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            with open(resolved_path, "w", encoding="utf-8") as f:
                f.write(content)

            return ExecutionResult(True, f"Successfully wrote {len(content)} characters to {resolved_path}")
        except Exception as e:
            return ExecutionResult(False, "", f"Error writing file: {str(e)}")

    def _tool_file_read(self, payload: dict) -> ExecutionResult:
        """Read content from a file"""
        try:
            file_path = payload.get("file_path", "")

            if not file_path:
                return ExecutionResult(False, "", "Missing file_path parameter")

            # Validate file path for security
            path_obj = Path(file_path)
            if not path_obj.is_absolute():
                path_obj = Path.cwd() / path_obj

            # Resolve to prevent directory traversal
            resolved_path = path_obj.resolve()
            cwd_resolved = Path.cwd().resolve()
            
            if not str(resolved_path).startswith(str(cwd_resolved)):
                return ExecutionResult(False, "", "File path outside working directory not allowed")

            # Read the file
            with open(resolved_path, "r", encoding="utf-8") as f:
                content = f.read()

            return ExecutionResult(True, content[:4000] + "..." if len(content) > 4000 else content, "")
        except FileNotFoundError:
            return ExecutionResult(False, "", f"File not found: {file_path}")
        except Exception as e:
            return ExecutionResult(False, "", f"Error reading file: {str(e)}")

    def _tool_shell(self, payload: dict) -> ExecutionResult:
        """Execute shell commands"""
        try:
            command = payload.get("command", "")

            if not command:
                return ExecutionResult(False, "", "Missing command parameter")

            # Security check: only allow safe commands
            forbidden_patterns = [
                r'\bsudo\b',
                r'\brm\b.*\s+-',
                r'\bmv\b.*\s+/dev/null',
                r'\bcat\b.*\s+/\w+/shadow',
                r'\bcat\b.*\s+/\w+/passwd',
            ]

            for pattern in forbidden_patterns:
                if re.search(pattern, command, re.IGNORECASE):
                    return ExecutionResult(False, "", f"Forbidden command pattern detected: {pattern}")

            # Execute the command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            output = result.stdout
            error = result.stderr
            return_code = result.returncode

            if return_code != 0 and error:
                return ExecutionResult(False, "", f"Command failed with error: {error}")

            return ExecutionResult(True, output, "")
        except subprocess.TimeoutExpired:
            return ExecutionResult(False, "", "Command timed out after 30 seconds")
        except Exception as e:
            return ExecutionResult(False, "", f"Error executing command: {str(e)}")

    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML to plain text"""
        try:
            # Simple HTML tag removal
            clean = re.sub(r'<[^>]+>', '', html_content)
            # Unescape HTML entities
            clean = html.unescape(clean)
            # Clean up extra whitespace
            clean = re.sub(r'\s+', ' ', clean).strip()
            return clean
        except Exception:
            return html_content

    def _tool_web_search(self, payload: dict) -> ExecutionResult:
        """Search the web for information"""
        try:
            query = payload.get("query", "")
            if not isinstance(query, str) or not query.strip():
                return ExecutionResult(False, "", "Provide query")

            q = query.strip()
            num = min(max(int(payload.get("num_results", 5)), 1), 10)

            # Using DuckDuckGo Lite as a simple search API alternative
            import urllib.parse
            search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(q)}"
            
            req = Request(search_url, headers={"User-Agent": "Mozilla/5.0 (compatible; EasyAI/1.0)"})
            with urlopen(req, timeout=15) as resp:
                html_content = resp.read().decode('utf-8', errors='replace')

            # Extract search results from DuckDuckGo HTML
            hits = []
            # Look for result containers in DuckDuckGo HTML
            result_pattern = r'<div class="result">[^<]*<a href="([^"]*)"[^>]*><span class="result__title">([^<]*)</span>'
            for match in re.finditer(result_pattern, html_content):
                url = match.group(1)
                title = self._html_to_text(match.group(2))
                if url and title:
                    hits.append({"title": title.strip(), "url": url})

            # Alternative pattern for newer layouts
            if not hits:
                alt_pattern = r'<a href="([^"]*)"[^>]*class="[^"]*result__a[^"]*"[^>]*>([^<]*)</a>'
                for match in re.finditer(alt_pattern, html_content):
                    url = match.group(1)
                    title = self._html_to_text(match.group(2))
                    if url and title:
                        hits.append({"title": title.strip(), "url": url})

            hits = hits[:num]

            if not hits:
                return ExecutionResult(False, "", f"No results found for query: {q}")

            # Format results
            result_lines = [f"Search results for '{q}':"]
            for hit in hits:
                result_lines.append(f"- [{hit['title']}]({hit['url']})")

            return ExecutionResult(True, "\n".join(result_lines), "")
        except Exception as e:
            return ExecutionResult(False, "", f"Web search error: {str(e)}")

    def _tool_web_fetch(self, payload: dict) -> ExecutionResult:
        """Fetch content from a URL"""
        try:
            url = payload.get("url", "")

            if not url:
                return ExecutionResult(False, "", "Missing URL parameter")

            # Basic URL validation
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return ExecutionResult(False, "", "Invalid URL")

            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; EasyAI/1.0)"})
            with urlopen(req, timeout=15) as resp:
                content = resp.read().decode('utf-8', errors='replace')

            # Extract text content from HTML if it looks like HTML
            if '<html' in content[:1000].lower():
                # Simple HTML to text conversion
                text_content = re.sub(r'<[^>]+>', ' ', content)
                text_content = html.unescape(text_content)
                text_content = re.sub(r'\s+', ' ', text_content).strip()
                
                # Return both raw and processed content
                result = f"URL: {url}\n\nExtracted text:\n{text_content[:2000]}..."
                if len(text_content) > 2000:
                    result += f"\n\n(Truncated from {len(text_content)} characters)"
            else:
                result = f"URL: {url}\n\nContent:\n{content[:2000]}..."
                if len(content) > 2000:
                    result += f"\n\n(Truncated from {len(content)} characters)"

            return ExecutionResult(True, result, "")
        except HTTPError as e:
            return ExecutionResult(False, "", f"HTTP error {e.code}: {e.reason}")
        except URLError as e:
            return ExecutionResult(False, "", f"URL error: {str(e)}")
        except Exception as e:
            return ExecutionResult(False, "", f"Web fetch error: {str(e)}")


# ==================== Permission System ====================

class PermissionMode:
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"
    DANGEROUS_FULL_ACCESS = "dangerous_full_access"


class PermissionRule:
    def __init__(self, pattern: str, allowed: bool, description: str = ""):
        self.pattern = pattern
        self.allowed = allowed
        self.description = description


class PermissionSystem:
    """Simplified permission system"""
    
    def __init__(self, mode: str = PermissionMode.WORKSPACE_WRITE):
        self.mode = mode
        self.rules = []
        self._setup_default_rules()

    def _setup_default_rules(self):
        """Setup default permission rules based on mode"""
        if self.mode == PermissionMode.READ_ONLY:
            # Allow read operations, deny writes
            self.rules.append(PermissionRule(r"file_read", True, "Allow file reading"))
            self.rules.append(PermissionRule(r"shell", False, "Deny shell commands in read-only mode"))
            self.rules.append(PermissionRule(r"file_write", False, "Deny file writing in read-only mode"))
        elif self.mode == PermissionMode.WORKSPACE_WRITE:
            # Allow workspace operations, restrict dangerous operations
            self.rules.append(PermissionRule(r"file_read", True, "Allow file reading"))
            self.rules.append(PermissionRule(r"file_write", True, "Allow file writing in workspace"))
            self.rules.append(PermissionRule(r"shell", True, "Allow shell commands"))
        elif self.mode == PermissionMode.DANGEROUS_FULL_ACCESS:
            # Allow everything
            self.rules.append(PermissionRule(r".*", True, "Allow all operations"))

    def check_permission(self, operation: str, resource: str = "") -> bool:
        """Check if an operation is allowed"""
        # Apply rules in order
        for rule in self.rules:
            if re.match(rule.pattern, operation):
                return rule.allowed
        
        # Default to denied if no rule matches
        return False

    def get_mode(self) -> str:
        return self.mode

    def set_mode(self, mode: str):
        self.mode = mode
        self._setup_default_rules()


# ==================== Simplified Task Registry ====================

class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: str
    description: str
    status: str = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    prompt: str = ""


class TaskRegistry:
    """Simplified task registry without team/cron functionality"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()

    def create(self, description: str, prompt: str = "") -> Task:
        """Create a new task"""
        task_id = f"task-{uuid4().hex[:8]}"
        task = Task(task_id, description, prompt=prompt)
        
        with self._lock:
            self.tasks[task_id] = task
            
        return task

    def get(self, task_id: str) -> Optional[Task]:
        """Get a task by ID"""
        with self._lock:
            return self.tasks.get(task_id)

    def update(self, task_id: str, **kwargs) -> bool:
        """Update task properties"""
        with self._lock:
            if task_id not in self.tasks:
                return False
                
            task = self.tasks[task_id]
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
                    
            return True

    def delete(self, task_id: str) -> bool:
        """Delete a task"""
        with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                return True
            return False

    def list(self, status: str = None) -> List[Task]:
        """List tasks, optionally filtered by status"""
        with self._lock:
            tasks = list(self.tasks.values())
            
            if status:
                tasks = [t for t in tasks if t.status == status]
                
            return tasks

    def clear_completed(self):
        """Clear completed tasks"""
        with self._lock:
            completed_ids = [tid for tid, task in self.tasks.items() if task.status == TaskStatus.COMPLETED]
            for tid in completed_ids:
                del self.tasks[tid]


# ==================== Error Classification and Failover ====================

class FailoverReason:
    RATE_LIMIT = "rate_limit"
    NETWORK_ERROR = "network_error"
    AUTH_ERROR = "auth_error"
    SERVER_ERROR = "server_error"
    CONTENT_FILTER = "content_filter"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class ErrorClassifier:
    @classmethod
    def classify(cls, error: Exception, status_code: int = None, response_body: str = "") -> FailoverReason:
        """Classify error type for failover decisions"""
        error_str = str(error).lower()
        
        if "rate" in error_str or "limit" in error_str:
            return FailoverReason.RATE_LIMIT
        elif "timeout" in error_str or status_code == 408:
            return FailoverReason.TIMEOUT
        elif status_code == 401 or "auth" in error_str or "key" in error_str:
            return FailoverReason.AUTH_ERROR
        elif status_code and 500 <= status_code < 600:
            return FailoverReason.SERVER_ERROR
        elif "filter" in error_str or "content" in error_str:
            return FailoverReason.CONTENT_FILTER
        elif "connection" in error_str or "network" in error_str:
            return FailoverReason.NETWORK_ERROR
        else:
            return FailoverReason.UNKNOWN


class FailoverManager:
    def __init__(self, providers: List[str]):
        self.providers = providers
        self.current_idx = 0
        self.failure_counts = {p: 0 for p in providers}
        self.last_failure_time = {p: None for p in providers}

    def get_next_provider(self) -> Optional[str]:
        """Get next available provider based on failure history"""
        eligible_providers = [
            p for p in self.providers 
            if self.failure_counts[p] < 3  # Skip providers with too many failures
        ]
        
        if not eligible_providers:
            # Reset failure counts after 5 minutes
            now = datetime.now()
            for p in self.providers:
                if self.last_failure_time[p] and (now - self.last_failure_time[p]).seconds > 300:
                    self.failure_counts[p] = 0
                    
            eligible_providers = [p for p in self.providers if self.failure_counts[p] < 3]
        
        if eligible_providers:
            # Round-robin among eligible providers
            provider = eligible_providers[self.current_idx % len(eligible_providers)]
            self.current_idx = (self.current_idx + 1) % len(eligible_providers)
            return provider
            
        return None

    def record_failure(self, provider: str, reason: FailoverReason):
        """Record provider failure"""
        self.failure_counts[provider] += 1
        self.last_failure_time[provider] = datetime.now()

    def record_success(self, provider: str):
        """Record provider success"""
        self.failure_counts[provider] = max(0, self.failure_counts[provider] - 1)


# ==================== Context Reference Parser ====================

@dataclass
class ContextReference:
    type: str  # file, url, command, etc.
    value: str
    description: str = ""


class ContextReferenceParser:
    """Parse context references from user input"""
    
    def __init__(self):
        self.patterns = {
            'file': r'\b(?:file://|/)([^\s\'"<>|*?#]+(?:/[^\s\'"<>|*?#]+)*)\b',
            'url': r'https?://[^\s\'"<>\[\]{}|\\^`\[\]]+',
            'command': r'`([^`]+)`|```(?:\w+\n)?\s*([^`]+?)\s*```',
        }

    def parse(self, text: str) -> List[ContextReference]:
        """Parse context references from text"""
        refs = []
        
        # Find file references
        for match in re.finditer(self.patterns['file'], text):
            path = match.group(1)
            if Path(path).exists():
                refs.append(ContextReference('file', path, f'File: {path}'))
        
        # Find URLs
        for match in re.finditer(self.patterns['url'], text):
            url = match.group(0)
            refs.append(ContextReference('url', url, f'URL: {url}'))
        
        # Find commands
        for match in re.finditer(self.patterns['command'], text):
            cmd = match.group(1) or match.group(2)
            if cmd:
                refs.append(ContextReference('command', cmd, f'Command: {cmd}'))
        
        return refs


# ==================== Code Sandbox ====================

class CodeSandbox:
    """Simple code execution sandbox"""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def execute_python(self, code: str) -> ExecutionResult:
        """Execute Python code in a restricted environment"""
        try:
            # For safety, we'll just return the code to be reviewed
            # In a real implementation, you'd want to use something like RestrictedPython
            return ExecutionResult(True, f"Python code received for execution:\n{code[:500]}...", "")
        except Exception as e:
            return ExecutionResult(False, "", f"Python execution error: {str(e)}")

    def execute_shell(self, command: str) -> ExecutionResult:
        """Execute shell command safely"""
        try:
            # Use the existing ShellTool for this
            tool_registry = ToolRegistry()
            return tool_registry.execute("ShellTool", {"command": command})
        except Exception as e:
            return ExecutionResult(False, "", f"Shell execution error: {str(e)}")


# ==================== Browser Tool (Simplified) ====================

class BrowserTool:
    """Simplified browser automation tool"""
    
    def __init__(self):
        pass

    def navigate(self, url: str) -> ExecutionResult:
        """Navigate to a URL and extract content"""
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; EasyAI/1.0)"})
            with urlopen(req, timeout=15) as resp:
                content = resp.read().decode('utf-8', errors='replace')
            
            # Extract text content
            text_content = re.sub(r'<[^>]+>', ' ', content)
            text_content = html.unescape(text_content)
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            
            return ExecutionResult(True, text_content[:2000] + "..." if len(text_content) > 2000 else text_content, "")
        except Exception as e:
            return ExecutionResult(False, "", f"Browser navigation error: {str(e)}")


# ==================== Background Process Management ====================

@dataclass
class BackgroundProcess:
    id: str
    command: str
    status: str  # running, completed, failed
    start_time: datetime
    end_time: Optional[datetime] = None
    output: str = ""


class ProcessRegistry:
    """Track background processes"""
    
    def __init__(self):
        self.processes: Dict[str, BackgroundProcess] = {}
        self._lock = threading.Lock()

    def create(self, command: str) -> BackgroundProcess:
        """Create a new background process"""
        proc_id = f"proc-{uuid4().hex[:8]}"
        proc = BackgroundProcess(
            id=proc_id,
            command=command,
            status="running",
            start_time=datetime.now()
        )
        
        with self._lock:
            self.processes[proc_id] = proc
            
        return proc

    def get(self, proc_id: str) -> Optional[BackgroundProcess]:
        """Get a process by ID"""
        with self._lock:
            return self.processes.get(proc_id)

    def update_status(self, proc_id: str, status: str, output: str = ""):
        """Update process status"""
        with self._lock:
            if proc_id in self.processes:
                proc = self.processes[proc_id]
                proc.status = status
                if output:
                    proc.output = output
                if status in ["completed", "failed"]:
                    proc.end_time = datetime.now()


# ==================== Todo Registry (Simplified) ====================

@dataclass
class TodoItem:
    id: str
    task_id: str
    description: str
    status: str = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class TodoRegistry:
    """Simplified todo registry"""
    
    def __init__(self):
        self.todos: Dict[str, Dict[str, TodoItem]] = {}  # task_id -> {todo_id -> todo_item}
        self._lock = threading.Lock()

    def create(self, task_id: str, description: str) -> TodoItem:
        """Create a new todo item for a task"""
        todo_id = f"todo-{uuid4().hex[:8]}"
        todo = TodoItem(todo_id, task_id, description)
        
        with self._lock:
            if task_id not in self.todos:
                self.todos[task_id] = {}
            self.todos[task_id][todo_id] = todo
            
        return todo

    def get(self, task_id: str, todo_id: str) -> Optional[TodoItem]:
        """Get a specific todo item"""
        with self._lock:
            if task_id in self.todos and todo_id in self.todos[task_id]:
                return self.todos[task_id][todo_id]
            return None

    def list(self, task_id: str) -> List[TodoItem]:
        """List all todos for a task"""
        with self._lock:
            if task_id in self.todos:
                return list(self.todos[task_id].values())
            return []

    def update_status(self, task_id: str, todo_id: str, status: str) -> bool:
        """Update todo status"""
        with self._lock:
            if task_id in self.todos and todo_id in self.todos[task_id]:
                todo = self.todos[task_id][todo_id]
                todo.status = status
                if status == TaskStatus.COMPLETED:
                    todo.completed_at = datetime.now()
                return True
            return False

    def clear(self, task_id: str):
        """Clear all todos for a task"""
        with self._lock:
            if task_id in self.todos:
                del self.todos[task_id]


# ==================== Session Management ====================

class SessionCompactor:
    """Compact session history to save tokens"""
    
    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages

    def compact(self, session: Session) -> Session:
        """Compact session history"""
        if len(session.history) <= self.max_messages:
            return session
            
        # Keep the first few and last few messages
        keep_first = 5
        keep_last = self.max_messages - keep_first
        
        compacted_history = session.history[:keep_first] + session.history[-keep_last:]
        
        new_session = Session(
            session_id=session.session_id,
            created_at=session.created_at,
            history=compacted_history,
            messages=session.messages[-self.max_messages:],  # Also limit messages
            metadata=session.metadata
        )
        
        return new_session


class SessionStore:
    """Store and manage sessions"""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = workspace / ".easy_ai" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.active_sessions: Dict[str, Session] = {}

    def create(self) -> Session:
        """Create a new session"""
        session_id = f"sess-{uuid4().hex[:12]}"
        session = Session(
            session_id=session_id,
            created_at=datetime.now()
        )
        
        self.active_sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID"""
        return self.active_sessions.get(session_id)

    def save(self, session: Session):
        """Save session to disk"""
        session_file = self.sessions_dir / f"{session.session_id}.json"
        data = {
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
            "history": session.history,
            "messages": session.messages,
            "metadata": session.metadata
        }
        
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, session_id: str) -> Optional[Session]:
        """Load session from disk"""
        session_file = self.sessions_dir / f"{session.session_id}.json"
        if not session_file.exists():
            return None
            
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            session = Session(
                session_id=data["session_id"],
                created_at=datetime.fromisoformat(data["created_at"]),
                history=data.get("history", []),
                messages=data.get("messages", []),
                metadata=data.get("metadata", {})
            )
            
            self.active_sessions[session_id] = session
            return session
        except Exception:
            return None


# ==================== AutoReview System ====================

class AutoReview:
    """Automatic memory consolidation and review"""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = workspace / ".easy_ai" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.enabled = True

    def should_review(self) -> tuple[bool, str]:
        """Determine if a review should be triggered"""
        # Review every 10 interactions or if memory directory is getting large
        interaction_count = len(list(self.memory_dir.glob("*.json")))
        
        if interaction_count >= 10:
            return True, "Reached interaction threshold"
            
        # Check if any memory files are getting large
        for mem_file in self.memory_dir.glob("*.json"):
            if mem_file.stat().st_size > 100000:  # 100KB
                return True, "Large memory file detected"
                
        return False, "No review needed"

    def autoreview(self, llm_client):
        """Perform automatic review and consolidation"""
        if not self.enabled or not llm_client:
            return
            
        try:
            # Collect recent memories
            recent_files = list(self.memory_dir.glob("*.json"))[-5:]  # Last 5 files
            
            if not recent_files:
                return
                
            # Combine recent memories
            combined_content = ""
            for mem_file in recent_files:
                try:
                    content = mem_file.read_text(encoding="utf-8")
                    combined_content += f"\n\n--- Memory from {mem_file.name} ---\n{content}"
                except Exception:
                    continue
            
            if not combined_content.strip():
                return
                
            # Ask LLM to consolidate
            review_prompt = f"""
            Please review and consolidate the following memories into key insights and learnings.
            Focus on:
            1. Important patterns or recurring themes
            2. Key decisions made
            3. Lessons learned
            4. Action items for future reference
            
            Memories:
            {combined_content[:3000]}  # Truncate to avoid token limits
            """
            
            consolidated = llm_client.chat([], review_prompt, include_tools=False)
            
            # Save consolidated memory
            review_file = self.memory_dir / f"consolidated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            review_file.write_text(consolidated or "No consolidation performed", encoding="utf-8")
            
        except Exception as e:
            print(f"AutoReview error: {e}")


# ==================== LLM Client ====================

class LLMClient:
    """Simplified LLM client supporting multiple providers"""
    
    def __init__(self, config: dict):
        self.config = config
        self.provider = config.get("llm", {}).get("provider", "openai")
        self.model = config.get("llm", {}).get("model", "gpt-4o")
        self.api_key = self._get_api_key()
        self.base_url = self._get_base_url()
        self.enabled = bool(self.api_key)
        self.failover_manager = FailoverManager([self.provider])

    def _get_api_key(self) -> str:
        """Get API key from config or environment"""
        # Try config first
        api_key = self.config.get("llm", {}).get("api_key")
        if api_key:
            return api_key
            
        # Try environment variables based on provider
        env_keys = ProviderRegistry.get_env_keys(self.provider)
        for env_key in env_keys:
            api_key = os.getenv(env_key)
            if api_key:
                return api_key
                
        return ""

    def _get_base_url(self) -> str:
        """Get base URL for the provider"""
        provider_info = ProviderRegistry.get(self.provider)
        if provider_info:
            return provider_info.get("base_url", "")
        return ""

    def chat(self, history: List[dict], prompt: str, include_tools: bool = True) -> str:
        """Send chat request to LLM"""
        if not self.enabled:
            return "LLM is not configured. Please set up your API key."
            
        # Prepare messages
        messages = history + [{"role": "user", "content": prompt}]
        
        # Try to make the request
        try:
            import urllib.request
            import urllib.parse
            
            # Prepare the request payload
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
            }
            
            # Include tools if requested and available
            if include_tools:
                tool_registry = ToolRegistry()
                tools = tool_registry.list_all()
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "auto"
            
            # Convert to JSON
            data = json.dumps(payload).encode('utf-8')
            
            # Create request
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}',
                }
            )
            
            # Send request
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            # Extract the response
            if 'choices' in result and len(result['choices']) > 0:
                message = result['choices'][0]['message']
                
                # Handle tool calls if present
                if 'tool_calls' in message and message['tool_calls']:
                    # For now, just return a message indicating tool calls were made
                    tool_names = [tc['function']['name'] for tc in message['tool_calls']]
                    return f"LLM suggested using tools: {', '.join(tool_names)}. Processing..."
                else:
                    content = message.get('content', '')
                    return content if content else "No response from LLM"
            else:
                return "No response from LLM"
                
        except Exception as e:
            # Record failure and try failover
            reason = ErrorClassifier.classify(e)
            self.failover_manager.record_failure(self.provider, reason)
            
            # Try with next provider if available
            next_provider = self.failover_manager.get_next_provider()
            if next_provider and next_provider != self.provider:
                old_provider = self.provider
                self.provider = next_provider
                self.api_key = self._get_api_key()
                self.base_url = self._get_base_url()
                
                # Retry once with new provider
                try:
                    result = self.chat(history, prompt, include_tools)
                    self.failover_manager.record_success(self.provider)
                    return result
                except:
                    # Restore original provider
                    self.provider = old_provider
                    self.api_key = self._get_api_key()
                    self.base_url = self._get_base_url()
            
            return f"Error communicating with LLM: {str(e)}"


# ==================== Tool Call Parser ====================

class ToolCallParser:
    """Parse tool calls from LLM responses"""
    
    @classmethod
    def parse(cls, response: str) -> List[ToolCall]:
        """Parse tool calls from LLM response"""
        tool_calls = []
        
        # Look for tool call patterns in the response
        # This is a simplified version - in practice, you'd want more robust parsing
        tool_call_pattern = r'"tool_calls"\s*:\s*\[(.*?)\]'
        match = re.search(tool_call_pattern, response, re.DOTALL)
        
        if match:
            tool_calls_str = match.group(1)
            # Parse individual tool calls
            call_pattern = r'\{[^}]*"function"[^}]*\}'
            for call_match in re.finditer(call_pattern, tool_calls_str):
                try:
                    call_data = json.loads(call_match.group(0))
                    function_data = call_data.get("function", {})
                    name = function_data.get("name", "")
                    arguments_str = function_data.get("arguments", "{}")
                    
                    if name:
                        # Parse arguments
                        try:
                            arguments = json.loads(arguments_str) if arguments_str else {}
                        except json.JSONDecodeError:
                            arguments = {}
                            
                        tool_call = ToolCall(
                            tool_name=name,
                            tool_input=arguments,
                            id=call_data.get("id", f"call_{uuid4().hex[:8]}")
                        )
                        tool_calls.append(tool_call)
                except json.JSONDecodeError:
                    continue
        
        return tool_calls


# ==================== Registry (Without Removed Components) ====================

class Registry:
    """Central registry for all components (simplified)"""
    
    def __init__(self, workspace: Path, config: dict):
        self.workspace = workspace
        self.config = config
        
        # Core components
        self.tool_registry = ToolRegistry()
        self.permission = PermissionSystem(config.get("permission", {}).get("mode", PermissionMode.WORKSPACE_WRITE))
        self.task_registry = TaskRegistry()
        self.todo_registry = TodoRegistry()
        self.session_store = SessionStore(workspace)
        self.process_registry = ProcessRegistry()
        
        # Removed components (for reference):
        # self.team_registry = TeamRegistry()  # REMOVED
        # self.cron_registry = CronRegistry()  # REMOVED
        # self.mcp_client = MCPClient()       # REMOVED
        # self.lsp_client = LSPClient()       # REMOVED
        # self.branch_lock = BranchLock(workspace)  # REMOVED
        # self.stale_detector = StaleBranchDetector(workspace)  # REMOVED
        # self.plugin_manager = PluginManager(workspace)  # REMOVED
        
        # State tracking
        self.current_task_id: Optional[str] = None
        self.current_task_doc_path: Optional[Path] = None


# ==================== Agent Loop ====================

class AgentLoop:
    """Main agent loop for processing user requests"""
    
    def __init__(self, registry: Registry, llm: LLMClient, config: dict):
        self.registry = registry
        self.llm = llm
        self.config = config
        self.max_turns = config.get("agent", {}).get("max_turns", 10)
        self.context_rounds = config.get("agent", {}).get("context_rounds", 3)

    def _classify_intent(self, user_prompt: str) -> dict:
        """Classify user intent to determine processing strategy"""
        prompt_lower = user_prompt.lower()
        
        intent = {
            "mode": "standard",
            "needs_tools": True,
            "force_web_research": False,
        }
        
        # Check for web research intent
        web_keywords = ["search", "find", "latest", "news", "information about", "what is", "who is", "when did"]
        if any(keyword in prompt_lower for keyword in web_keywords):
            intent["force_web_research"] = True
            
        # Check for file operations
        if any(word in prompt_lower for word in ["create file", "write file", "read file", "update file"]):
            intent["mode"] = "file_operation"
            
        # Check for command execution
        if any(word in prompt_lower for word in ["run", "execute", "command", "shell", "terminal"]):
            intent["mode"] = "command_execution"
            
        return intent

    def run(self, user_prompt: str, seed_history: List[dict] = None) -> tuple[str, List[AgentStep], str]:
        """Run the agent loop to process user request"""
        history = seed_history or []
        steps = []
        step_num = 1
        
        # Classify intent
        intent = self._classify_intent(user_prompt)
        needs_tools = intent.get("needs_tools", True) or intent.get("force_web_research", False)
        
        # Initial prompt to LLM
        current_prompt = user_prompt
        
        while step_num <= self.max_turns:
            # Get LLM response
            if self.llm.enabled:
                response = self.llm.chat(history, current_prompt, include_tools=needs_tools)
            else:
                response = f"LLM is disabled. Original prompt: {current_prompt}"
            
            # Add to history
            history.append({"role": "user", "content": current_prompt})
            history.append({"role": "assistant", "content": response})
            
            # Parse for tool calls
            tool_calls = ToolCallParser.parse(response) if needs_tools else []
            
            if not tool_calls:
                # No more tools to call, return final answer
                return response, steps, "completed"
            
            # Execute each tool call
            for tool_call in tool_calls:
                # Check permissions
                if not self.registry.permission.check_permission("tool_use", tool_call.tool_name):
                    observation = f"Permission denied for tool: {tool_call.tool_name}"
                else:
                    # Execute the tool
                    result = self.registry.tool_registry.execute(tool_call.tool_name, tool_call.tool_input)
                    observation = result.output if result.success else f"Error: {result.error}"
                
                # Add step
                step = AgentStep(step_num, tool_call, observation)
                steps.append(step)
                
                # Add tool result to history for next iteration
                history.append({
                    "role": "tool",
                    "name": tool_call.tool_name,
                    "content": observation
                })
                
                # Update prompt for next iteration
                current_prompt = f"Based on the result of {tool_call.tool_name}, please continue with the task: {user_prompt}"
                
                step_num += 1
                
                # Check if we've reached max turns
                if step_num > self.max_turns:
                    return response, steps, "max_turns_reached"
        
        return response, steps, "max_turns_reached"


# ==================== Query Engine (Simplified) ====================

class QueryEngine:
    """Main query processing engine (without removed components)"""
    
    def __init__(self, workspace: Path, config: dict):
        self.workspace = workspace
        self.cfg = config
        self.registry = Registry(workspace, config)
        self.llm = LLMClient(config)
        self.agent = AgentLoop(self.registry, self.llm, config)
        self.session = self.registry.session_store.create()
        self.ai_mode = config.get("shell", {}).get("ai_mode", True)
        self.context_rounds = config.get("shell", {}).get("context_rounds", 3)
        self.auto_review = AutoReview(workspace)
        
        # Initialize AGI Growth System
        if AGIGrowthSystem:
            try:
                self.agi_growth_system = AGIGrowthSystem(workspace)
                # Start nightly scheduler
                self.agi_growth_system.start_nightly_scheduler()
                print(colored("AGI Growth System initialized and nightly scheduler started.", Color.GREEN))
            except Exception as e:
                print(colored(f"Failed to initialize AGI Growth System: {e}", Color.RED))
                self.agi_growth_system = None
        else:
            self.agi_growth_system = None
        
        # Removed components initialization (for reference):
        # self.mcp_client = self.registry.mcp_client  # REMOVED
        # self.lsp_client = self.registry.lsp_client  # REMOVED

    def submit(self, prompt: str) -> TurnResult:
        """Submit a query/prompt for processing"""
        # Check if this is a complex task that needs to be tracked
        created_task = None
        if self._is_complex_task(prompt):
            created_task = self.registry.task_registry.create(description=prompt[:80], prompt=prompt)
            self.registry.task_registry.update(created_task.id, status=TaskStatus.RUNNING, started_at=datetime.now())
            self.registry.current_task_id = created_task.id
        
        # Use AGI Growth System if available, otherwise fall back to regular agent
        if self.agi_growth_system:
            # Process interaction through AGI Growth System
            user_id = "default_user"  # In a real implementation, you'd have actual user identification
            result = self.agi_growth_system.process_interaction(user_id, prompt)
            final_answer = result.get('response', 'No response generated')
            steps = []  # AGI system handles steps internally
            stop_reason = "agi_processed"
        else:
            # Run Agent loop (fallback)
            seed = self._recent_context(self.context_rounds)
            final_answer, steps, stop_reason = self.agent.run(prompt, seed_history=seed)
        
        # Show execution steps if configured
        if self.cfg["shell"].get("show_tool_calls", True) and steps:
            log_line(colored("--- Agent Steps ---", Color.GRAY))
            for step in steps:
                if step.action:
                    log_line(colored(f"[{step.step_num}] ", Color.MAGENTA) + colored(f"{step.action.tool_name}", Color.YELLOW) + f" -> {step.observation[:80]}...")
                else:
                    log_line(colored(f"[{step.step_num}] ", Color.MAGENTA) + "Final answer")
            log_line(colored("-------------------", Color.GRAY))
        
        # Update history
        self.session.history.append({"role": "user", "content": prompt})
        self.session.history.append({"role": "assistant", "content": final_answer})
        self.session.messages.append(prompt)
        
        # Record execution
        try:
            tools_used: list[str] = []
            for s in steps or []:
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
        except Exception:
            pass
        
        # Perform auto review if enabled
        if self.auto_review.enabled:
            should, reason = self.auto_review.should_review()
            if should:
                self.auto_review.autoreview(self.llm if self.llm.enabled else None)
        
        # Update task status if applicable
        if created_task:
            pending = [t for t in self.registry.todo_registry.list(created_task.id) if t.status != TaskStatus.COMPLETED]
            status = TaskStatus.COMPLETED if stop_reason == "completed" and not pending else TaskStatus.FAILED
            self.registry.task_registry.update(created_task.id, status=status, completed_at=datetime.now())
            self.registry.current_task_id = None
        
        return TurnResult(prompt, final_answer, (), (), stop_reason, ai_used=True)

    def _is_complex_task(self, prompt: str) -> bool:
        """Determine if a prompt represents a complex task"""
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

    def _recent_context(self, rounds: int) -> List[dict]:
        """Get recent conversation context"""
        n = max(0, min(int(rounds), 10))
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
                continue
            out.append({"role": role, "content": content})
        return out

    def consolidate_on_exit(self):
        """Consolidate session data on exit"""
        try:
            self.registry.session_store.save(self.session)
            
            # Trigger daily consolidation in AGI system if available
            if self.agi_growth_system:
                self.agi_growth_system.trigger_daily_consolidation(force=True)
                
                # Stop nightly scheduler
                self.agi_growth_system.stop_nightly_scheduler()
        except Exception:
            pass


# ==================== Main Shell Interface ====================

class EasyAIShell:
    """Interactive CLI shell with AI support for natural language to command execution."""

    VERSION = "1.3.0-minimal"

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
        self._print(colored(f" Easy AI Shell v{self.VERSION} (Minimal Version)", Color.CYAN, bold=True))
        self._print(colored("=================================================", Color.CYAN))
        self._print(f"  Session: {colored(sid, Color.YELLOW)}")
        self._print(f"  Workspace: {colored(str(w), Color.GREEN)}")
        self._print(f"  Permission: {colored(perm_mode, Color.BLUE)}")
        self._print(f"  AI: {ai_status}{model_info}")
        self._print(colored("-------------------------------------------------", Color.GRAY))
        self._print("  Agent Mode: Natural language → LLM → Tools → Result")
        self._print(f"  Commands: task, todo, session, memory")
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

        # ===== 执行反馈 =====
        feedback_parts = []
        if result.stop_reason == "completed":
            feedback_parts.append(colored("✅ 执行完成", Color.GREEN))
        elif result.stop_reason == "max_turns_reached":
            feedback_parts.append(colored("⚠️ 达到最大循环次数", Color.YELLOW))
        elif result.stop_reason == "insufficient_evidence":
            feedback_parts.append(colored("⚠️ 证据不足", Color.YELLOW))
        elif result.stop_reason == "user_request":
            feedback_parts.append(colored("✅ 用户指令执行", Color.GREEN))
        else:
            feedback_parts.append(colored(f"📋 状态: {result.stop_reason}", Color.GRAY))

        if result.matched_tools:
            tools = ", ".join(result.matched_tools)
            feedback_parts.append(colored(f"🔧 工具: {tools}", Color.CYAN))
        if result.matched_commands:
            cmds = ", ".join(result.matched_commands)
            feedback_parts.append(colored(f"⚡ 指令: {cmds}", Color.MAGENTA))

        if feedback_parts:
            self._print(colored("--- 执行反馈 ---", Color.GRAY))
            self._print(" | ".join(feedback_parts))
            self._print(colored("-------------------", Color.GRAY))

        # Metadata footer (dim)
        parts = []
        if result.ai_used:
            parts.append(colored("ai", Color.MAGENTA))
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


# ==================== Configuration ====================

DEFAULT_CONFIG = {
    "llm": {
        "provider": "openai",
        "model": "gpt-4o",
        "api_key": "",
        "temperature": 0.7,
    },
    "shell": {
        "ai_mode": True,
        "show_tool_calls": True,
        "context_rounds": 3,
        "non_interactive": False,
    },
    "permission": {
        "mode": "workspace_write",
    },
    "agent": {
        "max_turns": 10,
        "context_rounds": 3,
    }
}


def load_config(config_path: Optional[Path] = None) -> dict:
    """Load configuration from file or return default"""
    if config_path and config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            # Merge with defaults
            config = DEFAULT_CONFIG.copy()
            config.update(user_config)
            return config
        except Exception as e:
            print(f"Error loading config: {e}. Using defaults.")
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG


# ==================== Entry Point ====================

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Easy AI Shell - Minimal Version (No Team/Cron/MCP/LSP/Branch/Plugin)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Features:
  - Agent Mode: Natural language → LLM understanding → Tool execution → Loop until done
  - Permission System (read-only/workspace-write/danger-full-access)
  - Task Management (create/get/list/stop) - Simplified
  - Session Compact
  - AutoReview Memory Consolidation
  - FileWrite/FileRead/Shell/WebSearch/WebFetch Tools

Examples:
  python easy_ai_shell_minimal.py                    # interactive Agent mode
  python easy_ai_shell_minimal.py -p "帮我创建一个Python文件"  # Agent 自动执行
  python easy_ai_shell_minimal.py -p "查看当前目录文件"        # Agent 自动选择工具
  python easy_ai_shell_minimal.py --no-ai -p "files"        # 纯命令模式
  python easy_ai_shell_minimal.py -w /path/to/project       # 指定工作目录
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