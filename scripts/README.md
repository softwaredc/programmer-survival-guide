# 脚本说明

本目录下的脚本均为**零依赖**（只用 Python 标准库），不需要 pip install。

| 脚本 | 防什么 |
|---|---|
| `check_content.py` | 内容结构退化 |
| `gen_toc.py` | 目录与内容脱节 |
| `check_links.py` | 死链 |
| `check_mermaid.py` | 图表静默失效 |

---

## check_content.py

内容质量检查。PR 时由 GitHub Actions 自动运行，不合规则 fail。

```bash
python scripts/check_content.py              # 检查全部内容
python scripts/check_content.py content/vol3 # 只检查卷三
python scripts/check_content.py --strict     # 警告也视为失败
```

**检查项**：

| 项 | 级别 |
|---|---|
| 八段结构完整 | ERROR |
| 第 4 段「可直接抄的话术」不得为空 | ERROR |
| 第 3 段「现在就做」必须含「今天」 | ERROR |
| front-matter 必填字段完整 | ERROR |
| `updated` 超过 400 天未更新 | WARN |
| 超过 `review-cycle` 未复核（法条/数据类章节） | WARN |
| 疑似点名公司 / 编造数据 / 结果承诺 | WARN |

**不适用八段结构的文件**在脚本里通过 `STRUCTURE_EXEMPT` 声明（目前是 `G5-术语表.md`）。

---

## gen_toc.py

从 front-matter 自动生成目录，避免手写目录与内容脱节。

```bash
python scripts/gen_toc.py           # 打印目录
python scripts/gen_toc.py --write   # 写回 README.md 的 TOC 区块
python scripts/gen_toc.py --check   # 只检查是否最新（CI 用）
```

README.md 中需要有这两个标记：

```markdown
<!-- TOC:START -->
（自动生成的内容）
<!-- TOC:END -->
```

---

## check_links.py

检查所有 Markdown / HTML 中的内部相对链接是否真实存在。

```bash
python scripts/check_links.py
```

**一个关键设计**：跳过围栏代码块（```）与行内代码（`）。

原因是写作规范里会出现示例路径（如 `../../tools/xxx/index.html`），它们本就不是真链接。
如果不跳过，每次都会被误报成断链。

跳过范围也包含 `http/https/mailto/纯锚点`——外链无法离线校验，不该因网络波动让 CI 失败。

---

## check_mermaid.py

Mermaid 图表语法自检。

```bash
python scripts/check_mermaid.py
```

**为什么需要它**：Mermaid 只有在渲染时才报错，而 CI 里没人渲染。
写错的图不会让构建失败，它会**静默地变成一块灰色代码块**，直到有人打开页面才发现。

检查项：

| 项 | 说明 |
|---|---|
| ```mermaid 围栏是否闭合 | 未闭合会吞掉后面的正文 |
| **`classDef` 与两种引用写法是否一致** | `:::` 写法和 `class A,B style` 写法都要覆盖。只查前者会漏检一半的错误 |
| 连线引用的节点是否已定义 | 幽灵节点会让图渲染失败 |
| 引号 / 方括号是否配对 | 最常见的手误 |
| 尖括号是否配对 | 仅检查非连线行（箭头含 `>`，连线行要跳过） |
| **是否混入了 Markdown 正文** | 围栏缺失时图会一路吞到后面的 ```，此时要报"围栏缺闭合"而不是无关的行内错误 |

### 两个已知的坑

写这个脚本时真实踩到的，改脚本前先看这里：

1. **尖括号检查必须跳过连线行** —— `-->`、`-.->` 箭头本身就是 `>`，不跳过会全表误报
2. **`class` 语句是第二种 class 引用方式** —— 只在节点后面写 `:::style` 的项目不会遇到，
   但一旦有人写 `class A,B style`，只认 `:::` 的旧版本就会漏检

### 修改脚本前请先验证它仍然有效

脚本自身也可能出错。**用"故意注入错误"的方式确认它能抓到问题**，而不是只看它通过：

```python
# 把下面几种错误分别注入任一含图的文件，脚本必须返回非 0
"GA -->|x| OUTX"                      # 幽灵节点
"class STOP1,STOP2 redline"           # 未定义的 class（经由 class 语句）
"classDef yes fill:#eaf5ef" -> "classDef ok ..."   # 未定义的 class（经由 :::）
'OUT3["配送 / 跑腿'                   # 引号未闭合
"删掉某个 ```mermaid 的结束围栏"       # 围栏缺失
```

注入后务必还原文件。**一个从没失败过的检查脚本，可能只是从没被验证过。**

---

## 为什么要写这四个脚本

内容仓库会腐烂，腐烂的方式只有四种：

1. **内容退化** —— 新人投稿不遵守模板，慢慢变成"正确的废话"
2. **索引失效** —— 目录和内容对不上，读者找不到东西
3. **链接失效** —— 移动文件后留下死链，信任感随之崩塌
4. **图表失效** —— 代码块静默降级，看的人以为是流程图坏了

这四个脚本分别对应这四件事。**它们不是流程装饰，是这个仓库能不能活过一年的关键。**

---

## 本地运行

提交前自检，四条全绿再 push：

```bash
python scripts/check_content.py
python scripts/gen_toc.py --check
python scripts/check_links.py
python scripts/check_mermaid.py
```

如果 CI 报错，先在本地跑这四条，通常就能复现。
