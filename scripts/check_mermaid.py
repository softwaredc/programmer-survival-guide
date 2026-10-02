#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_mermaid.py —— Mermaid 图表语法自检

为什么需要它：Mermaid 只有在渲染时才报错，CI 里没人渲染。
写错的图会静默变成一块灰色代码块，直到有人打开页面才发现。

检查项：
1. ```mermaid 围栏是否闭合
2. classDef 定义的类名与 `:::` 引用是否一致
3. 连线两侧引用的节点是否已定义
4. 引号 / 方括号 / 尖括号是否配对
5. 图类型是否已知

用法：python scripts/check_mermaid.py
退出码 0 = 通过，1 = 存在问题
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
SCAN_EXT = (".md", ".html")

FENCE = re.compile(r"^\s{0,3}```\s*mermaid\s*$")
FENCE_END = re.compile(r"^\s{0,3}```\s*$")
CLASS_USE = re.compile(r":::\s*([A-Za-z_][\w-]*)")
CLASS_DEF = re.compile(r"classDef\s+([A-Za-z_][\w-]*)")
# `class A,B,C styleName` 语句中的样式名（另一种引用 class 的写法）
CLASS_STMT = re.compile(r"^\s*class\s+[\w,\s-]+?\s+([A-Za-z_][\w-]*)\s*$")
EDGE = re.compile(
    r"([A-Za-z_][\w]*)\s*(?:-\.->|--+[>\-/x]|==+>)\s*(?:\|[^|]*\|\s*)?([A-Za-z_][\w]*)"
)
KNOWN_TYPES = (
    "flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram",
    "erDiagram", "journey", "gantt", "pie", "gitGraph", "mindmap", "timeline",
)


def find_blocks(lines):
    """返回 [(起始行号, 内容行列表, 是否闭合)]。"""
    blocks = []
    i = 0
    while i < len(lines):
        if FENCE.match(lines[i]):
            start, i, body, closed = i, i + 1, [], False
            while i < len(lines):
                if FENCE_END.match(lines[i]):
                    closed = True
                    break
                body.append(lines[i])
                i += 1
            blocks.append((start + 1, body, closed))
        i += 1
    return blocks


def check_block(lineno, body):
    errors = []
    first = body[0].strip() if body else ""
    errors = []
    if first and not any(first.startswith(t) for t in KNOWN_TYPES):
        errors.append("第 %d 行：未知图类型开头「%s」" % (lineno, first[:40]))

    # 围栏串味检测：缺少结束围栏时，图会一直吞到后面某个 ``` 才停下，
    # 把 Markdown 正文当成图语法。这时要给出准确提示，
    # 否则只会报一堆无关的行内错误，把人引到错误的地方去。
    for offset, line in enumerate(body):
        s = line.lstrip()
        if s.startswith("#") or s.startswith("|") or s.startswith("---"):
            errors.append(
                "第 %d 行起：图块内混入了 Markdown 正文「%s」——"
                "极可能是 ```mermaid 围栏缺少闭合，导致后面的内容被吞了进来" % (lineno + offset, s[:40])
            )
            return errors

    text = "\n".join(body)
    defined = set(CLASS_DEF.findall(text))
    # class 的两种引用写法都要覆盖：节点后的 `:::style`，以及 `class A,B style` 语句
    used = set(CLASS_USE.findall(text))
    for offset, line in enumerate(body):
        m = CLASS_STMT.match(line)
        if m:
            used.add(m.group(1))
    missing = used - defined
    if missing:
        errors.append(
            "第 %d 行起：使用了未定义的 class %s（需用 classDef 定义）"
            % (lineno, "、".join(sorted(missing)))
        )

    defined_nodes = set()
    for line in body:
        s = line.strip()
        if s.startswith(("classDef", "class ", "%%", "subgraph", "end")):
            continue
        m = re.match(r"^([A-Za-z_][\w]*)\s*(\[|\{|\()", s)
        if m:
            defined_nodes.add(m.group(1))

    for offset, line in enumerate(body):
        s = line.strip()
        if s.startswith(("%%", "classDef", "class ")):
            continue
        for em in EDGE.finditer(s):
            for nid in (em.group(1), em.group(2)):
                if nid not in defined_nodes and nid not in ("subgraph", "end"):
                    errors.append(
                        "第 %d 行：连线引用了未定义的节点「%s」"
                        % (lineno + offset, nid)
                    )
        is_edge = EDGE.search(s) is not None
        if s.count('"') % 2 != 0:
            errors.append("第 %d 行：引号未闭合 -> %s" % (lineno + offset, s[:50]))
        if s.count("[") != s.count("]"):
            errors.append("第 %d 行：方括号不配对 -> %s" % (lineno + offset, s[:50]))
        # 尖括号检查要跳过连线行：箭头本身含 > （-->、-.->），会被误判
        if not is_edge and s.count("<") != s.count(">"):
            errors.append("第 %d 行：尖括号不配对 -> %s" % (lineno + offset, s[:50]))

    return errors


def main():
    problems, total = [], 0
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if not name.endswith(SCAN_EXT):
                continue
            path = os.path.join(root, name)
            if ".git" in path.replace("\\", "/").split(os.sep):
                continue
            lines = io.open(path, encoding="utf-8").read().split("\n")
            for lineno, body, closed in find_blocks(lines):
                total += 1
                rel = os.path.relpath(path, ROOT).replace("\\", "/")
                if not closed:
                    # 围栏未闭合时不要继续做语法检查：那会把后面的 Markdown 正文
                    # 当成图语法，报出一堆无关噪音，反而掩盖真正的问题
                    problems.append(
                        "%s: 第 %d 行 ```mermaid 未闭合（已跳过该块的语法检查）"
                        % (rel, lineno)
                    )
                elif not body:
                    problems.append("%s: 第 %d 行 mermaid 块为空" % (rel, lineno))
                else:
                    problems.extend(
                        "%s: %s" % (rel, e) for e in check_block(lineno, body)
                    )

    print("已检查 Mermaid 图：%d 个" % total)
    if problems:
        print("\n发现 %d 个问题：" % len(problems))
        for p in problems:
            print("  " + p)
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
