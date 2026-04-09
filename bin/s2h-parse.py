#!/usr/bin/env python3
"""
s2h-parse.py — Deterministic SKILL.md structural parser.

Extracts: frontmatter, heading tree, code blocks, tables, URLs, CLI commands,
file operations, binary references, companion files.

NO semantic analysis. Output is identical regardless of which LLM calls it.

Usage:
  python3 s2h-parse.py <skill_path> [--output <json_path>]
"""

import json
import os
import re
import sys
from pathlib import Path


def parse_frontmatter(lines):
    """Extract YAML frontmatter between --- fences.
    Simple key:value parser — no PyYAML dependency.
    Handles: scalar values, multiline | strings, simple lists (- item).
    """
    if not lines or lines[0].strip() != '---':
        return {}, 0

    end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end = i
            break

    if end == -1:
        return {}, 0

    fm = {}
    current_key = None
    current_val_lines = []
    is_multiline = False
    is_list = False

    for i in range(1, end):
        line = lines[i]
        stripped = line.strip()

        # new key: value
        m = re.match(r'^(\w[\w-]*)\s*:\s*(.*)', line)
        if m and not line[0].isspace():
            # flush previous
            if current_key is not None:
                if is_list:
                    fm[current_key] = current_val_lines
                elif is_multiline:
                    fm[current_key] = '\n'.join(current_val_lines).strip()
                else:
                    fm[current_key] = current_val_lines[0] if current_val_lines else ''
            current_key = m.group(1)
            val = m.group(2).strip()
            current_val_lines = []
            is_multiline = val in ('|', '>')
            is_list = False
            if not is_multiline and val:
                current_val_lines = [val]
        elif current_key and stripped.startswith('- '):
            is_list = True
            current_val_lines.append(stripped[2:].strip())
        elif current_key and line and line[0].isspace():
            current_val_lines.append(stripped)

    # flush last
    if current_key is not None:
        if is_list:
            fm[current_key] = current_val_lines
        elif is_multiline:
            fm[current_key] = '\n'.join(current_val_lines).strip()
        else:
            fm[current_key] = current_val_lines[0] if current_val_lines else ''

    return fm, end + 1


def _build_code_block_ranges(lines, start=0):
    """Pre-compute which lines are inside fenced code blocks."""
    in_block = set()
    fence_pattern = re.compile(r'^(`{3,}|~{3,})')
    i = start
    while i < len(lines):
        m = fence_pattern.match(lines[i])
        if m:
            fence_char = m.group(1)[0]
            fence_len = len(m.group(1))
            in_block.add(i)
            j = i + 1
            while j < len(lines):
                in_block.add(j)
                if re.match(r'^' + re.escape(fence_char) + r'{' + str(fence_len) + r',}\s*$', lines[j]):
                    break
                j += 1
            i = j + 1
        else:
            i += 1
    return in_block


def parse_headings(lines, start=0):
    """Extract markdown heading tree with line ranges.
    Skips lines inside fenced code blocks to avoid treating bash comments as headings.
    """
    headings = []
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
    code_lines = _build_code_block_ranges(lines, start)

    for i in range(start, len(lines)):
        if i in code_lines:
            continue
        m = heading_pattern.match(lines[i])
        if m:
            headings.append({
                "level": len(m.group(1)),
                "title": m.group(2).strip(),
                "line": i + 1  # 1-indexed
            })

    # compute end_line for each heading (next heading of same or higher level, or EOF)
    for idx, h in enumerate(headings):
        end = len(lines)
        for j in range(idx + 1, len(headings)):
            if headings[j]["level"] <= h["level"]:
                end = headings[j]["line"] - 1
                break
        h["end_line"] = end

    # compute parent
    for idx, h in enumerate(headings):
        h["parent"] = None
        for j in range(idx - 1, -1, -1):
            if headings[j]["level"] < h["level"]:
                h["parent"] = headings[j]["title"]
                break

    return headings


def parse_code_blocks(lines, start=0):
    """Extract fenced code blocks with language tags."""
    blocks = []
    fence_pattern = re.compile(r'^(`{3,}|~{3,})(\w*)')
    i = start
    while i < len(lines):
        m = fence_pattern.match(lines[i])
        if m:
            fence_char = m.group(1)[0]
            fence_len = len(m.group(1))
            lang = m.group(2) or ""
            block_start = i + 1
            # find closing fence
            j = block_start
            while j < len(lines):
                close_m = re.match(r'^' + re.escape(fence_char) + r'{' + str(fence_len) + r',}\s*$', lines[j])
                if close_m:
                    break
                j += 1
            content = '\n'.join(lines[block_start:j])
            blocks.append({
                "lang": lang,
                "line_start": i + 1,  # 1-indexed
                "line_end": j + 1,
                "content": content,
                "length": j - block_start
            })
            i = j + 1
        else:
            i += 1
    return blocks


def parse_tables(lines, start=0):
    """Extract markdown tables."""
    tables = []
    i = start
    while i < len(lines):
        line = lines[i].strip()
        # detect table: line with | and next line is separator
        if '|' in line and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if re.match(r'^[\|\s\-:]+$', next_line):
                # parse header
                headers = [c.strip() for c in line.split('|') if c.strip()]
                rows = []
                j = i + 2
                while j < len(lines) and '|' in lines[j]:
                    row = [c.strip() for c in lines[j].split('|') if c.strip()]
                    if row and not re.match(r'^[\-:]+$', row[0]):
                        rows.append(row)
                    j += 1
                tables.append({
                    "line": i + 1,
                    "headers": headers,
                    "row_count": len(rows)
                })
                i = j
                continue
        i += 1
    return tables


def extract_urls(lines):
    """Extract all URLs from text."""
    url_pattern = re.compile(r'https?://[^\s\)\]\>\"\'\`]+')
    urls = []
    seen = set()
    for i, line in enumerate(lines):
        for m in url_pattern.finditer(line):
            url = m.group(0).rstrip('.,;:')
            if url not in seen:
                seen.add(url)
                urls.append({
                    "url": url,
                    "line": i + 1
                })
    return urls


# CLI commands to detect in code blocks
CLI_PATTERNS = [
    (r'\bcurl\b', 'curl'),
    (r'\bwget\b', 'wget'),
    (r'\bopen\b\s+', 'open'),
    (r'\bxdg-open\b', 'xdg-open'),
    (r'\bgit\b\s+\w+', 'git'),
    (r'\bnpm\b\s+\w+', 'npm'),
    (r'\bbun\b\s+\w+', 'bun'),
    (r'\bpip\b\s+\w+', 'pip'),
    (r'\bpython3?\b\s+', 'python'),
    (r'\bffmpeg\b', 'ffmpeg'),
    (r'\bdocker\b', 'docker'),
    (r'\bkubectl\b', 'kubectl'),
    (r'\bgh\b\s+\w+', 'gh'),
    (r'\brm\b\s+-', 'rm'),
    (r'\bmkdir\b', 'mkdir'),
    (r'\btouch\b\s+', 'touch'),
    (r'\bchmod\b', 'chmod'),
    (r'\bsudo\b', 'sudo'),
]


def extract_cli_commands(code_blocks):
    """Extract CLI command patterns from code blocks."""
    commands = []
    seen = set()
    for block in code_blocks:
        if block["lang"] not in ("bash", "sh", "shell", "zsh", ""):
            continue
        for line_offset, line in enumerate(block["content"].split('\n')):
            for pattern, name in CLI_PATTERNS:
                if re.search(pattern, line):
                    key = (name, block["line_start"] + line_offset)
                    if key not in seen:
                        seen.add(key)
                        commands.append({
                            "cmd": name,
                            "line": block["line_start"] + line_offset,
                            "in_code_block": True,
                            "snippet": line.strip()[:120]
                        })
    return commands


def extract_file_operations(code_blocks):
    """Extract file read/write operations from code blocks."""
    ops = []
    write_patterns = [
        (r'>>\s*([^\s]+)', 'append'),
        (r'>\s*([^\s]+)', 'write'),
        (r'-o\s+([^\s]+)', 'write'),
        (r'tee\s+([^\s]+)', 'write'),
        (r'\bwrite\b.*?["\']([^"\']+)["\']', 'write'),
        (r'mkdir\s+-p\s+([^\s;]+)', 'mkdir'),
        (r'touch\s+([^\s;]+)', 'touch'),
        (r'rm\s+-[rf]*\s+([^\s;]+)', 'delete'),
    ]
    read_patterns = [
        (r'cat\s+([^\s|;]+)', 'read'),
        (r'source\s+([^\s;]+)', 'source'),
        (r'\bread\b.*?["\']([^"\']+)["\']', 'read'),
    ]

    for block in code_blocks:
        if block["lang"] not in ("bash", "sh", "shell", "zsh", ""):
            continue
        for line_offset, line in enumerate(block["content"].split('\n')):
            for pattern, op_type in write_patterns + read_patterns:
                for m in re.finditer(pattern, line):
                    path = m.group(1).strip('"\'')
                    if path and not path.startswith('-') and path not in ('/dev/null', '2>/dev/null'):
                        ops.append({
                            "op": op_type,
                            "path": path,
                            "line": block["line_start"] + line_offset
                        })
    return ops


def extract_binary_references(code_blocks, lines):
    """Extract references to non-standard binaries."""
    binaries = []
    seen = set()

    # from code blocks: look for variable assignments to binary paths
    bin_assign = re.compile(r'(\w+)=.*?/bin/(\w[\w-]+)')
    bin_exec = re.compile(r'~/\.claude/skills/\w+/bin/([\w-]+)')
    bin_which = re.compile(r'which\s+(\w[\w-]+)')

    for block in code_blocks:
        for line_offset, line in enumerate(block["content"].split('\n')):
            for pattern in [bin_assign, bin_exec, bin_which]:
                for m in pattern.finditer(line):
                    name = m.group(m.lastindex)
                    if name not in seen and name not in ('bash', 'sh', 'zsh', 'python3', 'python', 'node', 'bun'):
                        seen.add(name)
                        binaries.append({
                            "name": name,
                            "line": block["line_start"] + line_offset
                        })

    # also check plain text for skill-specific binary patterns
    for i, line in enumerate(lines):
        for m in bin_exec.finditer(line):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                binaries.append({"name": name, "line": i + 1})

    return binaries


def find_companion_files(skill_path):
    """Scan skill directory for companion files."""
    skill_dir = Path(skill_path).parent
    companions = []
    skip_names = {'SKILL.md', '.DS_Store', '__pycache__', 'node_modules'}

    for item in sorted(skill_dir.rglob('*')):
        if item.is_file():
            rel = item.relative_to(skill_dir)
            if rel.name in skip_names or any(p in str(rel) for p in ('node_modules', '__pycache__', '.git')):
                continue
            companions.append({
                "path": str(rel),
                "type": _classify_file(item),
                "size": item.stat().st_size
            })

    return companions[:50]  # cap at 50 files


def _classify_file(path):
    ext = path.suffix.lower()
    name = path.name.lower()
    if ext in ('.py', '.js', '.ts', '.sh'):
        return 'script'
    elif ext in ('.html', '.css'):
        return 'template'
    elif ext in ('.md', '.txt', '.rst'):
        return 'doc'
    elif ext in ('.json', '.yaml', '.yml', '.toml'):
        return 'config'
    elif ext in ('.png', '.jpg', '.svg', '.gif'):
        return 'image'
    elif ext in ('.min.js',):
        return 'vendor'
    elif name in ('makefile', 'dockerfile'):
        return 'build'
    elif 'tmpl' in name:
        return 'template'
    else:
        return 'other'


# ========================================================================
# Security scanning — deterministic pattern extraction for companion files
# ========================================================================

import math
import string as _string

# --- Secret patterns ---
# (regex, name, description)
SECRET_PATTERNS = [
    (r'(?:api[_-]?key|apikey)\s*[:=]\s*["\']?([A-Za-z0-9_\-]{20,})', 'api_key', 'API key assignment'),
    (r'(?:secret|token|password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\']{8,})', 'credential', 'Credential assignment'),
    (r'sk-[A-Za-z0-9]{20,}', 'openai_key', 'OpenAI API key pattern'),
    (r'sk-ant-[A-Za-z0-9\-]{20,}', 'anthropic_key', 'Anthropic API key pattern'),
    (r'ghp_[A-Za-z0-9]{36}', 'github_pat', 'GitHub personal access token'),
    (r'gho_[A-Za-z0-9]{36}', 'github_oauth', 'GitHub OAuth token'),
    (r'glpat-[A-Za-z0-9\-]{20,}', 'gitlab_pat', 'GitLab personal access token'),
    (r'xox[bpors]-[A-Za-z0-9\-]{10,}', 'slack_token', 'Slack token'),
    (r'AKIA[0-9A-Z]{16}', 'aws_access_key', 'AWS access key ID'),
    (r'(?:-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----)', 'private_key', 'Private key block'),
    (r'(?:Bearer\s+)[A-Za-z0-9\-_.~+/]{20,}', 'bearer_token', 'Bearer token'),
]

# --- Dangerous code patterns (by language) ---
DANGEROUS_CODE = {
    'python': [
        (r'\beval\s*\(', 'eval', 'Dynamic code evaluation'),
        (r'\bexec\s*\(', 'exec', 'Dynamic code execution'),
        (r'\b(?:os\.system|os\.popen)\s*\(', 'os_exec', 'OS command execution'),
        (r'\bsubprocess\.\w+\s*\(', 'subprocess', 'Subprocess call'),
        (r'\b__import__\s*\(', 'dynamic_import', 'Dynamic import'),
        (r'\bcompile\s*\(.*["\']exec["\']', 'compile_exec', 'Compile with exec mode'),
        (r'\bpickle\.loads?\s*\(', 'pickle', 'Pickle deserialization (arbitrary code exec)'),
        (r'\bctypes\b', 'ctypes', 'C foreign function interface'),
    ],
    'javascript': [
        (r'\beval\s*\(', 'eval', 'Dynamic code evaluation'),
        (r'\bFunction\s*\(', 'function_constructor', 'Function constructor (eval equivalent)'),
        (r'\bchild_process', 'child_process', 'Child process module'),
        (r'\brequire\s*\(\s*["\']child_process', 'require_child_process', 'Require child_process'),
        (r'\bexecSync\s*\(', 'exec_sync', 'Synchronous command execution'),
        (r'\bspawn\s*\(', 'spawn', 'Process spawn'),
    ],
    'shell': [
        (r'\beval\b', 'eval', 'Shell eval'),
        (r'\bcurl\b.*\|\s*(?:bash|sh|zsh)', 'pipe_to_shell', 'Pipe remote content to shell'),
        (r'\bwget\b.*\|\s*(?:bash|sh|zsh)', 'pipe_to_shell', 'Pipe remote content to shell'),
        (r'\bsource\s+/dev/stdin', 'source_stdin', 'Source from stdin'),
    ],
}

# --- Network access patterns ---
NETWORK_PATTERNS = {
    'python': [
        (r'\brequests\.(?:get|post|put|delete|patch|head)\s*\(', 'requests', 'HTTP request via requests'),
        (r'\burllib\.request\.urlopen\s*\(', 'urllib', 'HTTP request via urllib'),
        (r'\bhttpx\.\w+\s*\(', 'httpx', 'HTTP request via httpx'),
        (r'\baiohttp\.ClientSession', 'aiohttp', 'Async HTTP session'),
        (r'\bsocket\.(?:connect|create_connection)', 'raw_socket', 'Raw socket connection'),
        (r'\bsmtplib\b', 'smtp', 'SMTP email sending'),
        (r'\bparamiko\b', 'ssh', 'SSH connection'),
    ],
    'javascript': [
        (r'\bfetch\s*\(', 'fetch', 'Fetch API call'),
        (r'\baxios\b', 'axios', 'HTTP request via axios'),
        (r'\bXMLHttpRequest\b', 'xhr', 'XMLHttpRequest'),
        (r'\bhttp\.request\s*\(', 'http_request', 'Node http request'),
        (r'\bWebSocket\b', 'websocket', 'WebSocket connection'),
    ],
    'shell': [
        (r'\bcurl\b', 'curl', 'HTTP request via curl'),
        (r'\bwget\b', 'wget', 'HTTP request via wget'),
        (r'\bnc\b\s', 'netcat', 'Netcat connection'),
        (r'\bssh\b\s', 'ssh', 'SSH connection'),
        (r'\bscp\b\s', 'scp', 'SCP file transfer'),
    ],
}

# --- Dangerous filesystem paths ---
DANGEROUS_PATHS = [
    (r'(?:/etc/(?:passwd|shadow|hosts|sudoers|crontab))', 'system_config', 'System configuration file'),
    (r'(?:~|/home/\w+)/\.ssh/', 'ssh_dir', 'SSH directory access'),
    (r'(?:~|/home/\w+)/\.gnupg/', 'gpg_dir', 'GPG directory access'),
    (r'(?:~|/home/\w+)/\.aws/', 'aws_config', 'AWS config directory'),
    (r'/etc/systemd/', 'systemd', 'Systemd service modification'),
    (r'/etc/init\.d/', 'init_script', 'Init script modification'),
    (r'(?:~|/home/\w+)/\.bashrc|\.zshrc|\.profile|\.bash_profile', 'shell_rc', 'Shell config modification'),
    (r'/usr/local/bin/', 'usr_bin', 'System binary directory'),
    (r'(?:~|/home/\w+)/\.config/autostart', 'autostart', 'Autostart entry'),
    (r'LaunchAgents|LaunchDaemons', 'launchd', 'macOS launch daemon/agent'),
    (r'HKEY_|\\Registry\\', 'windows_registry', 'Windows registry access'),
]

# --- Obfuscation patterns ---
OBFUSCATION_PATTERNS = [
    (r'[A-Za-z0-9+/]{40,}={0,2}', 'base64_long', 'Long base64-encoded string'),
    (r'\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){5,}', 'hex_escape', 'Hex-escaped byte sequence'),
    (r'\\u[0-9a-fA-F]{4}(?:\\u[0-9a-fA-F]{4}){5,}', 'unicode_escape', 'Unicode-escaped sequence'),
    (r'String\.fromCharCode\s*\(', 'fromcharcode', 'String.fromCharCode (JS obfuscation)'),
    (r'chr\s*\(\s*\d+\s*\)\s*(?:\+|\.)\s*chr', 'chr_concat', 'chr() concatenation (Python obfuscation)'),
    (r'[\u200b\u200c\u200d\ufeff\u00ad]{3,}', 'invisible_chars', 'Invisible Unicode characters'),
    (r'atob\s*\(', 'atob', 'Base64 decode in JS'),
]


def _shannon_entropy(s):
    """Calculate Shannon entropy of a string. High entropy (>4.5) suggests randomness/secrets."""
    if not s:
        return 0.0
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def _detect_language(filepath):
    """Map file extension to language group for pattern matching."""
    ext = Path(filepath).suffix.lower()
    if ext in ('.py',):
        return 'python'
    elif ext in ('.js', '.ts', '.mjs', '.cjs'):
        return 'javascript'
    elif ext in ('.sh', '.bash', '.zsh'):
        return 'shell'
    return None


def scan_secrets(content, filepath, line_offset=0):
    """Scan content for hardcoded secrets using regex + entropy."""
    findings = []
    for i, line in enumerate(content.split('\n')):
        stripped = line.strip()
        # skip comments and obvious examples
        if stripped.startswith('#') and 'TODO' not in stripped:
            continue
        if 'example' in stripped.lower() or 'placeholder' in stripped.lower():
            continue

        for pattern, name, desc in SECRET_PATTERNS:
            for m in re.finditer(pattern, line):
                matched = m.group(0)
                # entropy check: filter out low-entropy false positives
                value = m.group(1) if m.lastindex else matched
                entropy = _shannon_entropy(value)
                if entropy < 3.0 and name not in ('private_key',):
                    continue
                findings.append({
                    "category": "secret_exposure",
                    "pattern": name,
                    "description": desc,
                    "file": str(filepath),
                    "line": i + 1 + line_offset,
                    "entropy": round(entropy, 2),
                    "snippet": stripped[:100]
                })
    return findings


def scan_dangerous_code(content, filepath, lang=None):
    """Scan for dangerous code execution patterns."""
    if lang is None:
        lang = _detect_language(filepath)
    if lang is None:
        return []

    patterns = DANGEROUS_CODE.get(lang, [])
    findings = []
    for i, line in enumerate(content.split('\n')):
        for pattern, name, desc in patterns:
            if re.search(pattern, line):
                findings.append({
                    "category": "code_execution",
                    "pattern": name,
                    "description": desc,
                    "file": str(filepath),
                    "line": i + 1,
                    "snippet": line.strip()[:100]
                })
    return findings


def scan_network_access(content, filepath, lang=None):
    """Scan for network access patterns."""
    if lang is None:
        lang = _detect_language(filepath)
    if lang is None:
        return []

    patterns = NETWORK_PATTERNS.get(lang, [])
    findings = []
    for i, line in enumerate(content.split('\n')):
        for pattern, name, desc in patterns:
            if re.search(pattern, line):
                findings.append({
                    "category": "network_access",
                    "pattern": name,
                    "description": desc,
                    "file": str(filepath),
                    "line": i + 1,
                    "snippet": line.strip()[:100]
                })
    return findings


def scan_dangerous_paths(content, filepath):
    """Scan for access to sensitive filesystem paths."""
    findings = []
    for i, line in enumerate(content.split('\n')):
        for pattern, name, desc in DANGEROUS_PATHS:
            if re.search(pattern, line):
                findings.append({
                    "category": "dangerous_path",
                    "pattern": name,
                    "description": desc,
                    "file": str(filepath),
                    "line": i + 1,
                    "snippet": line.strip()[:100]
                })
    return findings


def scan_obfuscation(content, filepath):
    """Scan for obfuscation techniques."""
    findings = []
    for i, line in enumerate(content.split('\n')):
        for pattern, name, desc in OBFUSCATION_PATTERNS:
            for m in re.finditer(pattern, line):
                matched = m.group(0)
                # base64: only flag if entropy is high (real data, not code)
                if name == 'base64_long':
                    if _shannon_entropy(matched) < 4.0:
                        continue
                    # skip if it looks like a hash, commit SHA, or common code pattern
                    if len(matched) < 44:
                        continue
                findings.append({
                    "category": "obfuscation",
                    "pattern": name,
                    "description": desc,
                    "file": str(filepath),
                    "line": i + 1,
                    "snippet": line.strip()[:100]
                })
    return findings


def scan_companion_security(skill_path):
    """Orchestrate security scanning across all companion files.

    Scans SKILL.md itself (code blocks only) + all companion scripts/configs.
    Returns structured findings for LLM semantic classification in Phase 3.
    """
    skill_dir = Path(skill_path).parent
    all_findings = []

    # 1. Scan SKILL.md code blocks (already parsed) — handled by caller via code_blocks
    #    We scan the raw SKILL.md for secrets and dangerous paths in prose too
    skill_content = Path(skill_path).read_text(encoding='utf-8')
    all_findings.extend(scan_secrets(skill_content, 'SKILL.md'))
    all_findings.extend(scan_dangerous_paths(skill_content, 'SKILL.md'))
    all_findings.extend(scan_obfuscation(skill_content, 'SKILL.md'))

    # 2. Scan companion files
    scannable_exts = {'.py', '.js', '.ts', '.mjs', '.cjs', '.sh', '.bash', '.zsh'}
    config_exts = {'.json', '.yaml', '.yml', '.toml', '.env'}
    html_exts = {'.html', '.htm', '.css'}
    skip_names = {'node_modules', '__pycache__', '.git', '.DS_Store'}

    for item in sorted(skill_dir.rglob('*')):
        if not item.is_file():
            continue
        if item.name == 'SKILL.md':
            continue
        rel = str(item.relative_to(skill_dir))
        if any(skip in rel for skip in skip_names):
            continue

        ext = item.suffix.lower()
        try:
            content = item.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        # Size guard: skip files > 500KB (likely vendor/minified)
        if item.stat().st_size > 500_000:
            continue

        rel_path = str(item.relative_to(skill_dir))

        if ext in scannable_exts:
            lang = _detect_language(item)
            all_findings.extend(scan_secrets(content, rel_path))
            all_findings.extend(scan_dangerous_code(content, rel_path, lang))
            all_findings.extend(scan_network_access(content, rel_path, lang))
            all_findings.extend(scan_dangerous_paths(content, rel_path))
            all_findings.extend(scan_obfuscation(content, rel_path))

        elif ext in config_exts:
            all_findings.extend(scan_secrets(content, rel_path))
            all_findings.extend(scan_dangerous_paths(content, rel_path))

        elif ext in html_exts:
            # HTML/CSS: check for external resource loading and inline scripts
            all_findings.extend(scan_secrets(content, rel_path))
            all_findings.extend(scan_obfuscation(content, rel_path))
            # Check for script src pointing to external domains
            for j, line in enumerate(content.split('\n')):
                if re.search(r'<script[^>]+src\s*=\s*["\']https?://', line):
                    all_findings.append({
                        "category": "network_access",
                        "pattern": "external_script",
                        "description": "External script loaded in HTML",
                        "file": rel_path,
                        "line": j + 1,
                        "snippet": line.strip()[:100]
                    })
                if re.search(r'<link[^>]+href\s*=\s*["\']https?://(?!fonts\.googleapis)', line):
                    all_findings.append({
                        "category": "network_access",
                        "pattern": "external_resource",
                        "description": "External resource loaded in HTML (non-font)",
                        "file": rel_path,
                        "line": j + 1,
                        "snippet": line.strip()[:100]
                    })

    # Deduplicate
    seen = set()
    unique = []
    for f in all_findings:
        key = (f["category"], f["pattern"], f["file"], f["line"])
        if key not in seen:
            seen.add(key)
            unique.append(f)

    # Sort by severity heuristic: code_execution > secret > network > dangerous_path > obfuscation
    severity_order = {
        "code_execution": 0,
        "secret_exposure": 1,
        "network_access": 2,
        "dangerous_path": 3,
        "obfuscation": 4,
    }
    unique.sort(key=lambda f: (severity_order.get(f["category"], 9), f["file"], f["line"]))

    # Summary stats
    summary = {}
    for f in unique:
        cat = f["category"]
        summary[cat] = summary.get(cat, 0) + 1

    return {
        "findings": unique[:200],  # cap at 200
        "summary": summary,
        "total": len(unique),
        "files_scanned": len([
            p for p in skill_dir.rglob('*')
            if p.is_file() and p.name != 'SKILL.md'
            and p.suffix.lower() in scannable_exts | config_exts | html_exts
            and not any(s in str(p) for s in skip_names)
        ]) + 1  # +1 for SKILL.md
    }


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(f"Usage: {sys.argv[0]} <skill_path> [--output <json_path>]")
        sys.exit(0)

    skill_path = sys.argv[1]
    output_path = None
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    if not os.path.isfile(skill_path):
        print(f"ERROR: {skill_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(skill_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    # Parse
    frontmatter, fm_end = parse_frontmatter(lines)
    headings = parse_headings(lines, start=fm_end)
    code_blocks = parse_code_blocks(lines, start=fm_end)
    tables = parse_tables(lines, start=fm_end)
    urls = extract_urls(lines)
    cli_commands = extract_cli_commands(code_blocks)
    file_ops = extract_file_operations(code_blocks)
    binaries = extract_binary_references(code_blocks, lines)
    companions = find_companion_files(skill_path)
    security = scan_companion_security(skill_path)

    result = {
        "source_path": os.path.abspath(skill_path),
        "total_lines": len(lines),
        "frontmatter": frontmatter,
        "heading_tree": headings,
        "code_blocks": [
            {k: v for k, v in b.items() if k != 'content'}
            for b in code_blocks
        ],
        "code_blocks_full": code_blocks,  # separate key with content for downstream use
        "tables": tables,
        "urls": urls,
        "cli_commands": cli_commands,
        "file_operations": file_ops,
        "binary_references": binaries,
        "companion_files": companions,
        "security_scan": security,
        "stats": {
            "headings": len(headings),
            "heading_count": len(headings),  # alias for LLM convenience
            "code_blocks": len(code_blocks),
            "tables": len(tables),
            "urls": len(urls),
            "url_count": len(urls),  # alias for LLM fold-decision
            "cli_commands": len(cli_commands),
            "file_operations": len(file_ops),
            "binaries": len(binaries),
            "companions": len(companions),
            "security_findings": security["total"],
            "security_files_scanned": security["files_scanned"]
        }
    }

    output = json.dumps(result, ensure_ascii=False, indent=2)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"OK: {output_path}")
    else:
        print(output)


if __name__ == '__main__':
    main()
