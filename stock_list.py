"""
股票搜索数据库 —— 全量 A 股（5524 只） 代码/名称/拼音 搜索

数据来源: 新浪财经全量股票列表
索引文件: stock_index.json（自动生成，首次运行自动拉取）
"""

import json
import os
from typing import List, Tuple, Optional

_INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_index.json")
_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_stocks_raw.csv")

# 全局缓存
_stock_index: List[dict] = []


def _load_index() -> List[dict]:
    """加载股票索引（惰性加载 + 缓存）"""
    global _stock_index
    if _stock_index:
        return _stock_index

    # 从 JSON 加载
    if os.path.exists(_INDEX_PATH):
        with open(_INDEX_PATH, "r", encoding="utf-8") as f:
            _stock_index = json.load(f)
        return _stock_index

    # JSON 不存在 → 尝试从 CSV 生成
    if os.path.exists(_CSV_PATH):
        print("[INFO] Building stock index from CSV...")
        try:
            from pypinyin import lazy_pinyin, Style
        except ImportError:
            print("[WARN] pypinyin not installed, pinyin search disabled")
            import csv
            with open(_CSV_PATH, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader)
                _stock_index = [{"c": r[0], "n": r[1], "p": ""} for r in reader]
            return _stock_index

        import csv
        with open(_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            items = [(r[0], r[1]) for r in reader]

        _stock_index = []
        for code, name in items:
            try:
                initials = "".join(p[0].upper() for p in lazy_pinyin(name, style=Style.FIRST_LETTER))
            except Exception:
                initials = ""
            _stock_index.append({"c": code, "n": name, "p": initials})

        with open(_INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(_stock_index, f, ensure_ascii=False)
        print(f"[INFO] Saved {len(_stock_index)} stocks to {_INDEX_PATH}")

    return _stock_index


def search_stocks(query: str, max_results: int = 5) -> List[Tuple[str, str, str]]:
    """
    按股票代码 / 中文名称 / 拼音首字母搜索全量 A 股

    Returns
    -------
    [(code, name, match_type), ...]
        match_type: 'code' | 'name' | 'pinyin'
    """
    if not query or not query.strip():
        return []

    q = query.strip().upper()
    index = _load_index()
    if not index:
        return []

    results = []

    for item in index:
        code = item["c"]
        name = item["n"]
        pinyin = item.get("p", "")

        # 匹配股票代码（前缀）
        if code.startswith(q):
            results.append((code, name, "code"))
            if len(results) >= max_results:
                return results[:max_results]

        # 匹配中文名称（子串）
        if q in name.upper():
            results.append((code, name, "name"))
            if len(results) >= max_results:
                return results[:max_results]

        # 匹配拼音首字母
        if len(q) >= 1 and pinyin and pinyin.startswith(q):
            results.append((code, name, "pinyin"))
            if len(results) >= max_results:
                return results[:max_results]

    return results[:max_results]


def get_name_by_code(code: str) -> Optional[str]:
    """通过代码查找股票名称"""
    for item in _load_index():
        if item["c"] == code:
            return item["n"]
    return None


def get_all_codes() -> List[str]:
    """返回所有股票代码列表（约 5500 个）"""
    return [item["c"] for item in _load_index()]


def get_index_stats() -> dict:
    """返回索引统计信息"""
    idx = _load_index()
    return {
        "total": len(idx),
        "has_pinyin": sum(1 for i in idx if i.get("p", "")),
    }
