#!/usr/bin/env python3
"""
Security Scan — 扫描代码库中的敏感信息（API Keys、Token、Secrets）。

检测模式:
    - OpenAI/DeepSeek API Key 格式: sk-[a-zA-Z0-9]{32,}
    - Anthropic API Key 格式: sk-ant-[a-zA-Z0-9]{32,}
    - 硬编码密文赋值: api_key = "..."
    - Bearer token 中包含真实密钥（排除占位符）
    - .env 文件泄露检查

排除规则:
    - docs/ 中的文档示例（sk-xxx, sk-*** 等占位符）
    - .env.example 模板文件
    - 本扫描脚本自身
    - .git/ 目录

返回码:
    0 - 无安全问题
    1 - 发现高危问题（真实密钥）
    2 - 发现中危问题（需人工审查）

用法:
    python scripts/security_scan.py
    python scripts/security_scan.py --json  # JSON 输出（CI 集成）
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 扫描排除目录
EXCLUDED_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env", ".tox",
    "node_modules", ".idea", ".vscode", "dist", "build",
    "*.egg-info",
}

# 扫描排除文件（相对项目根路径）
EXCLUDED_FILES = {
    ".env.example",           # 模板文件
    "scripts/security_scan.py",  # 本脚本
    "token_monitor.db",       # 运行时数据库
    "*.db", "*.db-shm", "*.db-wal",
    "*.log",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dll",
    "*.exe",
    "*.png", "*.ico", "*.jpg", "*.gif",
}

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {
    ".py", ".yaml", ".yml", ".json", ".md", ".txt",
    ".toml", ".cfg", ".ini", ".env", ".sh", ".bat",
    ".js", ".ts", ".html", ".css",
}

# ═══════════════════════════════════════════════════════════════════
# 检测规则
# ═══════════════════════════════════════════════════════════════════

# (正则, 严重级别, 规则名称, 说明)
RULES: list[tuple[str, str, str, str]] = [
    # P0 — 真实密钥模式
    (
        r'sk-[a-zA-Z0-9]{32,}',
        "P0-CRITICAL",
        "OpenAI/DeepSeek API Key",
        "sk- 开头的 API Key（32+ 字符随机串）"
    ),
    (
        r'sk-ant-[a-zA-Z0-9]{32,}',
        "P0-CRITICAL",
        "Anthropic API Key",
        "sk-ant- 开头的 Anthropic API Key"
    ),
    (
        r'api_key\s*[:=]\s*["\'][a-zA-Z0-9_-]{20,}["\']',
        "P0-CRITICAL",
        "Hardcoded API Key assignment",
        "代码中直接赋值 API Key"
    ),
    (
        r'Bearer\s+sk-[a-zA-Z0-9]{20,}',
        "P0-CRITICAL",
        "Bearer token with real key",
        "Authorization header 中使用真实密钥"
    ),

    # P1 — 敏感模式（需人工审查）
    (
        r'(password|passwd|secret|token)\s*[:=]\s*["\'][^"\']{8,}["\']',
        "P1-HIGH",
        "Password/secret assignment",
        "密码或 token 硬编码赋值"
    ),
    (
        r'-----BEGIN\s+(RSA|EC|DSA|OPENSSH)\s+PRIVATE KEY-----',
        "P1-HIGH",
        "Private key in source",
        "SSH/TLS 私钥"
    ),

    # P2 — 信息
    (
        r'\.env\b(?!\.example)',
        "P2-INFO",
        ".env file reference",
        "引用 .env 文件（确认已在 .gitignore 中）"
    ),
]

# 安全的占位符模式（匹配则跳过）
SAFE_PATTERNS = [
    r'sk-xxx\b',               # 通用占位符
    r'sk-ant-xxx\b',           # Anthropic 占位符
    r'sk-\*{3,}',              # 脱敏显示
    r'sk-test-placeholder\b',  # 测试占位符
    r'sk-your-key-here\b',     # 示例文本
    r'sk-invalid-key-\d+\b',   # 明显的无效测试 key
    r'<your[_-]?api[_-]?key>', # 模板占位符
    r'<api[_-]?key>',
    r'YOUR_API_KEY',
    r'xxx',                    # 通用占位符
]


def is_safe_placeholder(text: str) -> bool:
    """检查是否仅匹配安全占位符。"""
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def should_exclude(rel_path: str) -> bool:
    """判断文件是否应被排除。"""
    path_parts = set(Path(rel_path).parts)

    # 检查排除目录
    if path_parts & EXCLUDED_DIRS:
        return True
    for part in path_parts:
        for exc in EXCLUDED_DIRS:
            if Path(part).match(exc):
                return True

    # 检查排除文件
    filename = Path(rel_path).name
    for pattern in EXCLUDED_FILES:
        if Path(rel_path).match(pattern) or filename == pattern:
            return True
        if pattern.startswith("*") and filename.endswith(pattern[1:]):
            return True

    # 检查扩展名
    ext = Path(rel_path).suffix.lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        return True

    return False


def scan_file(filepath: Path, rel_path: str) -> list[dict[str, Any]]:
    """扫描单个文件。"""
    findings: list[dict[str, Any]] = []

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings

    lines = content.split("\n")

    for regex, severity, rule_name, description in RULES:
        for match in re.finditer(regex, content, re.IGNORECASE):
            matched_text = match.group(0)

            # 跳过安全占位符
            if is_safe_placeholder(matched_text):
                continue

            # 对于文档文件中的示例，降低严重级别
            effective_severity = severity
            if rel_path.startswith("docs/") or rel_path.endswith(".md"):
                if severity.startswith("P0"):
                    effective_severity = "P1-HIGH (docs — verify)"

            # 计算行号
            line_no = content[:match.start()].count("\n") + 1

            findings.append({
                "file": rel_path,
                "line": line_no,
                "severity": effective_severity,
                "rule": rule_name,
                "description": description,
                "match": _mask_match(matched_text),
            })

    return findings


def _mask_match(text: str) -> str:
    """脱敏显示匹配文本（保留前4后4字符）。"""
    if len(text) <= 12:
        return text[:4] + "***"
    return text[:4] + "*" * (len(text) - 8) + text[-4:]


def scan_project(root: Path) -> dict[str, Any]:
    """扫描整个项目。"""
    all_findings: list[dict[str, Any]] = []
    files_scanned = 0
    files_skipped = 0

    for filepath in root.rglob("*"):
        if filepath.is_dir():
            continue

        try:
            rel_path = str(filepath.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue

        if should_exclude(rel_path):
            files_skipped += 1
            continue

        files_scanned += 1
        findings = scan_file(filepath, rel_path)
        all_findings.extend(findings)

    # 分类
    critical = [f for f in all_findings if f["severity"].startswith("P0")]
    high = [f for f in all_findings if f["severity"].startswith("P1")]
    info = [f for f in all_findings if f["severity"].startswith("P2")]

    return {
        "files_scanned": files_scanned,
        "files_skipped": files_skipped,
        "total_findings": len(all_findings),
        "critical": len(critical),
        "high": len(high),
        "info": len(info),
        "findings": all_findings,
        "critical_findings": critical,
        "high_findings": high,
        "info_findings": info,
    }


def main() -> int:
    """主入口。"""
    json_output = "--json" in sys.argv

    if not json_output:
        print("=" * 60)
        print("  TokenMonitor Security Scan")
        print("=" * 60)
        print(f"  Root: {PROJECT_ROOT}")
        print()

    result = scan_project(PROJECT_ROOT)

    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"  Files scanned: {result['files_scanned']}")
        print(f"  Files skipped: {result['files_skipped']}")
        print(f"  Total findings: {result['total_findings']}")
        print(f"    P0-CRITICAL: {result['critical']}")
        print(f"    P1-HIGH:     {result['high']}")
        print(f"    P2-INFO:     {result['info']}")
        print()

        if result["findings"]:
            print("-" * 60)
            for f in result["findings"]:
                print(f"  [{f['severity']}] {f['file']}:{f['line']}")
                print(f"    Rule: {f['rule']}")
                print(f"    Match: {f['match']}")
            print("-" * 60)
            print()
        else:
            print("  ✅ No security issues found.")
            print()

    # 返回码
    if result["critical"] > 0:
        if not json_output:
            print(f"❌ {result['critical']} CRITICAL finding(s) — must be fixed.")
        return 1
    elif result["high"] > 0:
        if not json_output:
            print(f"⚠️  {result['high']} HIGH finding(s) — review required.")
        return 2
    else:
        if not json_output:
            print("✅ Security scan PASSED — no critical or high issues.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
