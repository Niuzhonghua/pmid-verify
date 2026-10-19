"""Europe PMC REST API 客户端（仅标准库，无第三方依赖）。

从 tools/novelty_scan.py 抽取出的 HTTP 查询逻辑，供新颖性闸门等模块复用，
确保全项目只有一套 Europe PMC 检索实现。

失败语义：重试耗尽后必须 raise RuntimeError，绝不用空 dict 冒充"没查到"——
联网失败不等于没有命中，下游必须据此区分"查不到"与"查不了"。
"""

import json
import time
import urllib.parse
import urllib.request

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_TIMEOUT = 20


def search(query: str, page_size: int = 10, title_abs: bool = True,
           sort: str = "", retries: int = 3, result_type: str = "lite") -> dict:
    """查询 Europe PMC，返回完整 JSON 响应。

    Args:
        query: 原始检索式（不含 TITLE_ABS 包装与 SRC 限制）。
        page_size: 返回条数。
        title_abs: 为 True 时把整条检索式包成 TITLE_ABS:(...)。
        sort: 排序方式，如 "CITED desc"；空字符串表示默认排序。
        retries: 重试次数，采用指数退避（1s / 2s / 4s ...）。
        result_type: Europe PMC resultType，如 "lite"（仅题录）或 "core"（含摘要）。

    Returns:
        Europe PMC 返回的 JSON 对象（含 hitCount 与 resultList.result）。

    Raises:
        RuntimeError: 重试耗尽后仍未成功（含超时、网络错误、非法 JSON）。
    """
    q = f"TITLE_ABS:({query})" if title_abs else query
    params = {
        "query": f"{q} AND SRC:MED",
        "format": "json",
        "resultType": result_type,
        "pageSize": page_size,
    }
    if sort:
        params["sort"] = sort
    url = API + "?" + urllib.parse.urlencode(params)

    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=_TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 —— 联网/解析/超时统一失败
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"检索失败 {query!r}: {last}")