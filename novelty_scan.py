"""欧洲 PMC 新颖性扫描 + PMID 批量核验。

把"生成假设前先确认这件事有没有被做过"这一步固化成命令：
跑 N 条检索式，输出命中数与 top 标题，供人工判读。

用法（检索模式）:
    python tools/novelty_scan.py --title-abs "query1" "query2" [--pagesize 10] [--save novelty.md]

用法（PMID 核验模式）:
    python tools/novelty_scan.py --verify 36888921 39089305 0000000
    python tools/novelty_scan.py --verify --file pmids.txt

注意:
    - 默认搜索包含全文，噪音极大；加 --title-abs 把整条检索式限制在标题+摘要；
    - 短语必须加引号，否则每个词单独匹配（"MET inhibitor" ≠ MET 与 inhibitor）；
    - 脚本只负责把证据摆到桌面，不做"新颖/不新颖"的自动裁决；
    - 判定标准建议：出现"同一现象 + 同一机制 + 定量刻画"才叫直接命中；
    - --verify 与检索模式互斥：核验只接受 PMID，不接受检索式。
"""
import argparse
import html
import os
import sys


from europepmc_client import search  # noqa: E402


def render(queries, page_size: int, title_abs: bool, sort: str) -> str:
    lines = ["# Novelty scan", ""]
    scope = "title+abstract" if title_abs else "full text"
    for q in queries:
        data = search(q, page_size, title_abs, sort)
        hits = data.get("hitCount", 0)
        rows = data.get("resultList", {}).get("result", [])
        lines.append(f"## {q}")
        lines.append("")
        lines.append(f"scope: {scope} | hits: **{hits}**")
        lines.append("")
        if not rows:
            lines.append("(no results)")
            lines.append("")
            continue
        lines.append("| PMID | Year | Journal | Title |")
        lines.append("|---|---|---|---|")
        for r in rows:
            title = html.unescape(r.get("title") or "").replace("|", "\\|")
            lines.append(
                f"| {r.get('pmid', '')} | {r.get('pubYear', '')} | "
                f"{r.get('journalTitle', '')} | {title} |"
            )
        lines.append("")
    return "\n".join(lines)


def validate_query(q: str) -> None:
    """拒绝被 shell 拆坏的碎片：裸运算符、引号不配对、过短。"""
    s = q.strip()
    if s.upper() in {"AND", "OR", "NOT"}:
        raise SystemExit(f"ERROR: 检索式是裸运算符 {q!r}，多半被 shell 拆开了；请用单引号包住整条")
    if len(s) < 8:
        raise SystemExit(f"ERROR: 检索式过短 {q!r}，多半被 shell 拆开了；请用单引号包住整条")
    if s.count('"') % 2 != 0:
        raise SystemExit(f"ERROR: 双引号不配对 {q!r}；Windows 下请用单引号包整条，内部再用双引号")


def verify_one(pmid: str) -> dict:
    """核验单个 PMID，返回结构化判定（失败不抛异常，落在 verdict 上）。

    Args:
        pmid: 待核验的 PMID（可能含首尾空白）。

    Returns:
        结构化结果，字段包括:
        - verdict: "real" / "not_found" / "unavailable" / "format_invalid"
        - suspicious: 位数超出 7~9 位时为 True（仍会发起一次查询）
        - title / year / journal / author: 仅 verdict == "real" 时非空
    """
    s = str(pmid).strip()
    if not s.isdigit():
        return {"pmid": pmid, "verdict": "format_invalid", "suspicious": False,
                "title": "", "year": "", "journal": "", "author": ""}

    suspicious = not (7 <= len(s) <= 9)

    try:
        # 客户端内部会自动追加 "AND SRC:MED"，这里只传 EXT_ID 避免重复拼接。
        data = search(f"EXT_ID:{s}", title_abs=False)
    except RuntimeError as e:
        return {"pmid": pmid, "verdict": "unavailable", "suspicious": suspicious,
                "title": "", "year": "", "journal": "", "author": "", "error": str(e)}

    rows = (data or {}).get("resultList", {}).get("result", [])
    if not rows:
        return {"pmid": pmid, "verdict": "not_found", "suspicious": suspicious,
                "title": "", "year": "", "journal": "", "author": ""}

    r = rows[0]
    author_str = (r.get("authorString") or "").strip()
    author = author_str.split(",")[0].strip() if author_str else ""
    return {
        "pmid": pmid,
        "verdict": "real",
        "suspicious": suspicious,
        "title": html.unescape(r.get("title") or "").replace("|", "\\|"),
        "year": r.get("pubYear", ""),
        "journal": (r.get("journalTitle") or "").replace("|", "\\|"),
        "author": author.replace("|", "\\|"),
    }


def _verdict_label(r: dict) -> str:
    """把结构化判定转成表格里的可读标签。

    只用 ASCII 标记（[X] / [!]），不用 emoji：Windows 默认控制台是 GBK，
    GBK 编码不了 ❌/⚠️，print 会直接抛 UnicodeEncodeError 把进程打崩。
    """
    if r["verdict"] == "format_invalid":
        return "[X] 格式非法"
    base = {
        "real": "真实",
        "not_found": "[X] 不存在",
        "unavailable": "[!] 无法核验",
    }[r["verdict"]]
    if r["suspicious"]:
        return f"[!] 位数可疑 → {base}"
    return base


def run_verify(pmids) -> int:
    """核验一批 PMID，打印表格与汇总，返回进程退出码（0=全部真实）。"""
    results = [verify_one(p) for p in pmids]
    lines = ["| PMID | 判定 | 年份 | 期刊 | 标题 | 第一作者 |",
             "|---|---|---|---|---|---|"]
    for r in results:
        lines.append(
            f"| {r['pmid']} | {_verdict_label(r)} | {r['year']} | "
            f"{r['journal']} | {r['title']} | {r['author']} |"
        )
    print("\n".join(lines))

    real = sum(1 for r in results if r["verdict"] == "real")
    not_found = sum(1 for r in results if r["verdict"] in ("not_found", "format_invalid"))
    unavailable = sum(1 for r in results if r["verdict"] == "unavailable")
    print()
    print(f"共 {len(results)} 条：真实 {real} / 不存在 {not_found} / 无法核验 {unavailable}")

    ok = all(r["verdict"] == "real" and not r["suspicious"] for r in results)
    return 0 if ok else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Europe PMC novelty scan (manual judgement)")
    ap.add_argument("queries", nargs="*",
                    help="one or more queries (search mode) or PMIDs (with --verify)")
    ap.add_argument("--file", help="UTF-8 file, one entry per line (queries or PMIDs)")
    ap.add_argument("--verify", action="store_true",
                    help="verify PMIDs (EXT_ID lookup in Europe PMC MEDLINE) instead of scanning")
    ap.add_argument("--pagesize", type=int, default=10)
    ap.add_argument("--title-abs", action="store_true",
                    help="restrict the whole query to title+abstract (recommended)")
    ap.add_argument("--sort", default="", help='e.g. "CITED desc"')
    ap.add_argument("--save", help="also write markdown to this path (search mode only)")
    args = ap.parse_args()

    if args.verify:
        if args.title_abs or args.sort:
            ap.error("--verify 与检索模式互斥：--title-abs / --sort 只用于检索式，不能与 --verify 同时使用")
        pmids = list(args.queries)
        if args.file:
            with open(args.file, "r", encoding="utf-8-sig") as f:
                pmids += [ln.strip() for ln in f if ln.strip()]
        if not pmids:
            ap.error("no PMIDs: pass them as arguments or via --file")
        sys.exit(run_verify(pmids))

    queries = list(args.queries)
    if args.file:
        with open(args.file, "r", encoding="utf-8-sig") as f:
            queries += [ln.strip() for ln in f if ln.strip()]
    if not queries:
        ap.error("no queries: pass them as arguments or via --file")
    for q in queries:
        validate_query(q)
    if len(queries) > 1:
        print(f"(received {len(queries)} queries)")

    out = render(queries, args.pagesize, args.title_abs, args.sort)
    print(out)
    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(out + "\n")
        print(f"\nsaved: {args.save}")


if __name__ == "__main__":
    main()