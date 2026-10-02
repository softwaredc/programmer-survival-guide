#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容质量检查：在 PR 时运行，不合规则 fail。

检查项：
1. 八段结构是否齐全（G5 术语表等纯参考页除外）
2. 第 4 段「可直接抄的话术 / 模板」不得为空
3. 第 3 段「现在就做」必须包含「今天」这一行
4. front-matter 必填字段完整
5. 红线扫描：是否出现了公司点名的高风险表述
6. review-cycle 到期提醒（输出 needs-update 清单）

用法：
    python scripts/check_content.py              # 检查全部
    python scripts/check_content.py content/vol3 # 只检查某个目录
    python scripts/check_content.py --strict     # 警告也视为失败
"""

import os
import re
import sys
import io
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")

REQUIRED_SECTIONS = [
    "1. 三十秒自检",
    "2. 结论先行",
    "3. 现在就做",
    "4. 可直接抄的话术",
    "5. 五个常见错误",
    "6. 真实案例",
    "7. 延伸与依据",
    "8. 免责",
]

# 不适用八段结构的文件（纯参考页）
STRUCTURE_EXEMPT = {"G5-术语表.md"}

# front-matter 必填
REQUIRED_FM = ["title", "vol", "order", "status", "updated", "summary"]

# 红线：这些词出现时需要人工确认（只提示，不直接 fail）
# 第三项 negatable=True：否定语境下的免责表述（「不是"这样做一定能成功"」）不算承诺
RED_FLAG_PATTERNS = [
    (r"(?<!《)(阿里|腾讯|字节|百度|美团|京东|华为|小米|网易|网约车平台)", "可能点名了具体公司", False),
    (r"\d{4}年[全]?国[^。]{0,10}(平均薪资|薪资水平|平均工资)\s*为?\s*\d", "疑似编造统计数据", False),
    (r"(一定|保证|必然)(能|会)(拿到|成功|通过)", "出现了结果承诺", True),
]

# 否定语境判定的窗口与词表
NEGATION_WINDOW = 24
NEGATION_WORDS = (
    "不是", "不能", "并非", "无法", "未必", "并不", "难以",
    "绝不", "从不", "别指望", "不可能", "没有", "不等于", "不代表",
)


def is_negated(text, pos):
    """判断匹配位置之前是否处于否定语境，避免把免责声明误判成承诺。"""
    prefix = text[max(0, pos - NEGATION_WINDOW):pos]
    return any(w in prefix for w in NEGATION_WORDS)


def parse_front_matter(text):
    """提取 YAML front-matter，返回 (dict, body)。"""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 4:]
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body


def check_file(path):
    """返回 (errors, warnings)。"""
    errors, warnings = [], []
    name = os.path.basename(path)
    rel = os.path.relpath(path, ROOT)

    with io.open(path, encoding="utf-8") as f:
        text = f.read()

    fm, body = parse_front_matter(text)

    if not fm:
        errors.append("缺少 front-matter")
    else:
        for k in REQUIRED_FM:
            if k not in fm:
                errors.append("front-matter 缺少字段：%s" % k)
        if "updated" in fm:
            try:
                d = datetime.strptime(fm["updated"], "%Y-%m-%d").date()
                if (date.today() - d).days > 400:
                    warnings.append("内容超过 400 天未更新（updated=%s）" % fm["updated"])
            except ValueError:
                errors.append("updated 格式应为 YYYY-MM-DD，当前为：%s" % fm["updated"])
        if "review-cycle" in fm:
            m = re.match(r"(\d+)d", fm["review-cycle"])
            if m and "updated" in fm:
                try:
                    d = datetime.strptime(fm["updated"], "%Y-%m-%d").date()
                    if (date.today() - d).days > int(m.group(1)):
                        warnings.append(
                            "已超过 review-cycle（%s），应复核：本页涉及法条或数据" % fm["review-cycle"]
                        )
                except ValueError:
                    pass

    if name not in STRUCTURE_EXEMPT:
        for sec in REQUIRED_SECTIONS:
            if sec not in body:
                errors.append("缺少段落：%s" % sec)

        # 第 4 段不得为空
        m4 = re.search(r"##\s*4\.\s*可直接抄的话术[^\n]*\n(.*?)(?=\n##\s*5\.)", body, re.S)
        if not m4:
            errors.append("无法定位第 4 段（可直接抄的话术）")
        else:
            content4 = m4.group(1)
            # 去掉标题行与注释后，检查是否还有实质内容
            stripped = re.sub(r"[>\-\*\s`#]", "", content4)
            if len(stripped.strip()) < 80:
                errors.append("第 4 段（可直接抄的话术）内容过少或为空 —— 这是硬性标准")

        # 第 3 段必须有「今天」
        m3 = re.search(r"##\s*3\.\s*现在就做[^\n]*\n(.*?)(?=\n##\s*4\.)", body, re.S)
        if m3 and "今天" not in m3.group(1):
            errors.append("第 3 段（现在就做）缺少「今天」这一行")

    # 红线扫描（仅警告）
    for pat, desc, negatable in RED_FLAG_PATTERNS:
        for mm in re.finditer(pat, body):
            # 免责声明里常出现否定式引用（「不是"这样做一定能成功"」），那不是承诺
            if negatable and is_negated(body, mm.start()):
                continue
            warnings.append("红线提示（%s）：「%s」" % (desc, mm.group(0)[:20]))

    return errors, warnings


def main():
    targets = [a for a in sys.argv[1:] if not a.startswith("-")]
    strict = "--strict" in sys.argv

    base = os.path.join(CONTENT, targets[0]) if targets else CONTENT
    if not os.path.isdir(base):
        print("目录不存在：%s" % base)
        return 2

    files = []
    for root, dirs, fs in os.walk(base):
        for f in sorted(fs):
            if f.endswith(".md") and not f.startswith("_"):
                files.append(os.path.join(root, f))

    total_e = total_w = 0
    for p in files:
        e, w = check_file(p)
        rel = os.path.relpath(p, ROOT)
        if e or w:
            print("\n── %s" % rel)
            for x in e:
                print("   [ERROR] %s" % x)
            for x in w:
                print("   [WARN ] %s" % x)
        total_e += len(e)
        total_w += len(w)

    print("\n" + "=" * 60)
    print("检查文件 %d 个：错误 %d，警告 %d" % (len(files), total_e, total_w))
    print("=" * 60)

    if total_e > 0:
        print("\n❌ 检查未通过。请修复上述 ERROR 后重新提交。")
        return 1
    if strict and total_w > 0:
        print("\n❌ --strict 模式下警告视为失败。")
        return 1
    print("\n✅ 检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
