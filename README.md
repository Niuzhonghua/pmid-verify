# pmid-check

[English](#english) | 中文

**核验 PMID 是否真实存在，并快速查新（Europe PMC，无需 API key，无第三方依赖）。**

---

## 为什么做这个

大语言模型很容易生成**格式完全正确、但根本不存在**的参考文献。例如 `0000000`——7 位数字，符合"PMID 是数字"的形式要求，能通过大多数脚本的格式校验，但它不是任何一篇论文。

这类错误不会报错，只会安静地出现在你的参考文献、综述或开题报告里。

这个工具做两件事：

1. 给一串 PMID，告诉你哪些**查无此文**；
2. 给一条检索式，告诉你这个方向**是否已经被人做过**。

它只负责把证据摆到桌面上，**不替你判断**"这算不算新颖"。判定必须人来做。

## 安装

需要 Python 3.8 或更高版本。没有第三方依赖，不需要 pip install，不需要注册 API key。

```bash
git clone <你的仓库地址>
cd pmid-verify
```

## 用法一：核验 PMID

```bash
python novelty_scan.py --verify 36888921 39089305 0000000
```

```
| PMID     | 判定      | 年份 | 期刊            | 标题                                  | 第一作者  |
|----------|-----------|------|-----------------|---------------------------------------|-----------|
| 36888921 | 真实      | 2023 | Mol Cancer Ther | Pharmacokinetic/Pharmacodynamic ...   | Jones RDO |
| 39089305 | 真实      | 2024 | Lancet Oncol    | Tepotinib plus osimertinib ...        | Wu YL     |
| 0000000  | [X] 不存在 |      |                 |                                       |           |

共 3 条：真实 2 / 不存在 1 / 无法核验 0
```

> 判定标签只用 ASCII 的 `[X]` / `[!]`，不用 emoji——Windows 默认控制台是 GBK 编码，
> 打印 ❌ 会直接抛 `UnicodeEncodeError` 把程序打崩。这是实测踩到的坑。

也可以从文件读（一行一个）：

```bash
python novelty_scan.py --verify --file pmids.txt
```

**退出码**：全部真实返回 `0`；出现"不存在""无法核验""格式非法""位数可疑"返回 `1`。可以直接用在脚本或 CI 里。

四种判定：

| 判定 | 含义 |
|---|---|
| 真实 | Europe PMC 的 MEDLINE 记录中查到该文献 |
| ❌ 不存在 | 查无此记录 |
| ⚠️ 无法核验 | 网络请求失败——**不等于不存在**，重试即可 |
| ❌ 格式非法 | 不是纯数字（如 `abc123`） |

## 用法二：检索式查新

```bash
python novelty_scan.py --title-abs '"MET inhibitor" AND "EGFR" AND resistance'
```

默认把整条检索式限定在**标题 + 摘要**。加 `--pagesize 20` 可多取，加 `--save out.md` 可存成文件。

## 已知坑（都是实际踩过的）

- **不要去掉 `--title-abs`。** 默认搜索包含全文，同样的词会命中千万量级，全是噪音。
- **短语必须加引号。** `MET inhibitor` 会被拆成两个词分别匹配，`"MET inhibitor"` 才是一个短语。
- **Windows PowerShell 5.1 会吃掉参数里的双引号。** 带引号的检索式请写进文件，用 `--file` 传入。
- **只覆盖 MEDLINE 收录的文献。** 预印本、部分期刊、非英文文献可能查不到——**查不到 ≠ 一定不存在**。判定"不存在"前请再用 PubMed 或期刊官网确认一次。

## 局限

- 依赖 Europe PMC 的公开 API，受其可用性与速率限制影响。
- 不做文本相似度判断，"是否已被做过"最终仍需人读标题和摘要。
- 不替代同行评议，也不替代你自己读文献。

## 许可证

MIT。见 [LICENSE](LICENSE)。

## 作者

高中生独立开发。工具辅助人工核查，不替代同行评议。

---

<a name="english"></a>
## English

A small command-line tool to **verify whether PMIDs actually exist** and to run quick novelty checks against Europe PMC. No API key, no dependencies, standard library only.

```bash
python novelty_scan.py --verify 36888921 0000000
python novelty_scan.py --title-abs '"MET inhibitor" AND "EGFR"'
```

LLMs frequently produce plausible-looking but non-existent citations. This tool checks each PMID against the MEDLINE records in Europe PMC and flags the ones that cannot be found, so fabricated references never make it into a manuscript unnoticed.

Exit code is `0` only when every PMID resolves. Licensed under MIT.
