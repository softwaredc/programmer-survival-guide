#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_links.py —— 内部链接检查

检查仓库内所有 Markdown / HTML 文件中的相对路径链接是否真实存在。

设计取舍：
- 跳过围栏代码块（``` ... ```）与行内代码（`...`）—— 写作规范里的示例路径本就不是真链接
- 跳过 http/https/mailto/纯锚点 —— 外链无法离线校验，且不应因网络波动让 CI 失败
- 目录型链接（以 / 结尾或指向目录）视为指向 index.html 或 README.md，两者任一存在即通过

用法：
    python scripts/check_links.py
退出码 0 = 全部通过，1 = 存在断链
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
SCAN_EXT = (".md", ".html")
LINK_RE = re.compile(r"\]\(([^)]+)\)")
FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")


def iter_files():
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if name.endswith(SCAN_EXT):
                yield os.path.join(root, name)


def strip_code(text):
    """把围栏代码块与行内代码块替换成等长空白，保留行列结构，便于定位。"""
    out = []
    in_fence = False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        if in_fence:
            out.append("")
            continue
        # 行内代码
        out.append(re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), line))
    return "\n".join(out)


def resolve(base_dir, target):
    target = target.split("#")[0].split("?")[0].strip()
    if not target:
        return None
    path = os.path.normpath(os.path.join(base_dir, target))
    if os.path.exists(path):
        return path
    if os.path.isdir(path):
        for candidate in ("index.html", "README.md"):
            p = os.path.join(path, candidate)
            if os.path.exists(p):
                return p
    return None


def main():
    broken = []
    total = 0
    for path in iter_files():
        try:
            raw = open(path, encoding="utf-8").read()
        except UnicodeDecodeError as exc:
            print("[编码错误] %s: %s" % (rel(path), exc))
            broken.append((path, "<文件编码不是 UTF-8>"))
            continue

        cleaned = strip_code(raw)
        base_dir = os.path.dirname(path)

        for m in LINK_RE.finditer(cleaned):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "//")):
                continue
            if target.startswith("#"):
                continue
            total += 1
            if resolve(base_dir, target) is None:
                broken.append((path, target))

    print("已检查内部链接：%d 条" % total)
    if broken:
        print("\n发现 %d 条断链：" % len(broken))
        for path, target in broken:
            print("  %s -> %s" % (rel(path), target))
        return 1
    print("全部通过。")
    return 0


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


if __name__ == "__main__":
    sys.exit(main())
