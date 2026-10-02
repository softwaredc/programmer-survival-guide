#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 front-matter 自动生成目录。

用法：
    python scripts/gen_toc.py                 # 打印目录到标准输出
    python scripts/gen_toc.py --write         # 同步更新 README.md 中的目录区块
    python scripts/gen_toc.py --check         # 只检查目录是否是最新的（CI 用）

为什么必须自动生成：
    手写目录是内容仓库腐烂的开始。一旦目录和内容不同步，
    读者立刻失去信任，而且维护者自己看不出来哪里不同步。
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")
README = os.path.join(ROOT, "README.md")

VOL_NAME = {
    "1": "卷一 · 入场 —— 在信息最不对称的阶段，少踩几个坑就够了",
    "2": "卷二 · 在场 —— 你的目标不是「努力」，是降低可替代性",
    "3": "卷三 · 离场 —— 被裁不是终局，是一场有流程、有时限、有筹码的谈判",
    "G": "通用层 —— 三卷共享的底层资料",
}
VOL_DIR = {"1": "vol1", "2": "vol2", "3": "vol3", "G": "general"}
VOL_ORDER = ["1", "2", "3", "G"]

START = "<!-- TOC:START -->"
END = "<!-- TOC:END -->"


def parse_fm(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = {}
    for line in text[3:end].strip().split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, text[end + 4:]


def collect():
    """返回 {vol: [ (order, filename, title, summary) ]}"""
    result = {v: [] for v in VOL_ORDER}
    for vol, d in VOL_DIR.items():
        path = os.path.join(CONTENT, d)
        if not os.path.isdir(path):
            continue
        for f in sorted(os.listdir(path)):
            if not f.endswith(".md"):
                continue
            with io.open(os.path.join(path, f), encoding="utf-8") as fh:
                fm, _ = parse_fm(fh.read())
            if not fm.get("title"):
                continue
            try:
                order = int(fm.get("order", 999))
            except ValueError:
                order = 999
            result[vol].append((order, f, fm["title"], fm.get("summary", "")))
        result[vol].sort(key=lambda x: (x[0], x[1]))
    return result


def render():
    data = collect()
    lines = []
    for vol in VOL_ORDER:
        items = data[vol]
        if not items:
            continue
        lines.append("### %s\n" % VOL_NAME[vol])
        is_general = vol == "G"
        if is_general:
            lines.append("| # | 章节 |")
            lines.append("|---|---|")
        else:
            lines.append("| # | 章节 | 解决什么 |")
            lines.append("|---|---|---|")
        for order, fn, title, summary in items:
            link = "content/%s/%s" % (VOL_DIR[vol], fn)
            label = fn.replace(".md", "")
            if is_general:
                lines.append("| %s | [%s](%s) |" % (label, title, link))
            else:
                lines.append("| %02d | [%s](%s) | %s |" % (order, title, link, summary))
        lines.append("")
    return "\n".join(lines)


def main():
    toc = render()

    if "--check" in sys.argv:
        with io.open(README, encoding="utf-8") as f:
            readme = f.read()
        if START not in readme or END not in readme:
            print("README.md 中未找到 TOC 标记区块")
            return 1
        current = readme.split(START, 1)[1].split(END, 1)[0].strip()
        if current != toc.strip():
            print("❌ README 目录不是最新的，请运行：python scripts/gen_toc.py --write")
            return 1
        print("✅ README 目录是最新的")
        return 0

    if "--write" in sys.argv:
        with io.open(README, encoding="utf-8") as f:
            readme = f.read()
        if START not in readme:
            print("README.md 中未找到 %s / %s 标记，无法写入" % (START, END))
            return 1
        new = re.sub(
            re.escape(START) + r".*?" + re.escape(END),
            START + "\n\n" + toc.strip() + "\n\n" + END,
            readme,
            flags=re.S,
        )
        with io.open(README, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        print("✅ 已更新 README.md 的目录区块")
        return 0

    print(toc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
