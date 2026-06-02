"""
数据抓取模块 —— 多信源并行 + SQLite 缓存

Tier 1（第一梯队，并行抢答）: 新浪日K, baostock
Tier 2（备选）: 当前环境无其他可用源
"""

import os
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, as_completed
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import requests

# 绕过系统代理
NO_PROXY = {"http": None, "https": None}

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache.db")


# ======================== 股票代码处理 ========================
def normalise_code(raw: str) -> str:
    """清洗股票代码 → 6位纯数字"""
    raw = raw.strip().upper()
    for sfx in [".SH", ".SZ", ".BJ"]:
        if raw.endswith(sfx):
            raw = raw[:6]
            break
    for pfx in ["SH", "SZ", "BJ"]:
        if raw.startswith(pfx) and len(raw) > 6:
            raw = raw[2:]
            break
    return raw if (raw.isdigit() and len(raw) == 6) else raw


def _market_prefix(code: str) -> str:
    """sz / sh 前缀"""
    return "sh" if code.startswith("6") else "sz"


# ======================== SQLite 缓存 ========================
def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_cache (
            code TEXT, date TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            PRIMARY KEY (code, date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_names (
            code TEXT PRIMARY KEY, name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            code    TEXT PRIMARY KEY,
            name    TEXT,
            added_at TEXT DEFAULT (datetime('now'))
        )
    """)
    return conn


def _read_cache(code: str, start: str, end: str) -> Optional[pd.DataFrame]:
    try:
        conn = _get_db()
        df = pd.read_sql_query(
            "SELECT date,open,high,low,close,volume FROM stock_cache "
            "WHERE code=? AND date>=? AND date<=? ORDER BY date",
            conn, params=(code, start, end),
        )
        conn.close()
        return df if not df.empty else None
    except Exception:
        return None


def _save_cache(code: str, df: pd.DataFrame) -> None:
    try:
        conn = _get_db()
        for _, r in df.iterrows():
            conn.execute(
                "INSERT OR REPLACE INTO stock_cache VALUES (?,?,?,?,?,?,?)",
                (code, str(r["date"]), float(r["open"]), float(r["high"]),
                 float(r["low"]), float(r["close"]), float(r["volume"])),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[WARN] cache write: {e}")


def _save_name(code: str, name: str) -> None:
    try:
        conn = _get_db()
        conn.execute("INSERT OR REPLACE INTO stock_names VALUES (?,?)", (code, name))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _read_name(code: str) -> Optional[str]:
    try:
        conn = _get_db()
        cur = conn.execute("SELECT name FROM stock_names WHERE code=?", (code,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def clear_cache(code: Optional[str] = None) -> None:
    conn = _get_db()
    if code:
        for t in ["stock_cache", "stock_names"]:
            conn.execute(f"DELETE FROM {t} WHERE code=?", (code,))
    else:
        for t in ["stock_cache", "stock_names"]:
            conn.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()


# ======================== 历史记录 ========================
def save_history(code: str, name: str) -> None:
    try:
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO history (code, name, added_at) VALUES (?,?, datetime('now'))",
            (code, name),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def load_history(limit: int = 20) -> list:
    try:
        conn = _get_db()
        cur = conn.execute(
            "SELECT code, name FROM history ORDER BY added_at DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        conn.close()
        return [(r[0], r[1]) for r in rows]
    except Exception:
        return []


# ======================== 股票名称 ========================
def get_stock_name(code: str) -> Optional[str]:
    """从新浪实时行情获取股票名称"""
    code = normalise_code(code)
    if not code or not code.isdigit():
        return None

    # 缓存
    cached = _read_name(code)
    if cached:
        return cached

    prefix = _market_prefix(code)
    try:
        url = f"https://hq.sinajs.cn/list={prefix}{code}"
        r = requests.get(
            url, timeout=5,
            headers={"Referer": "https://finance.sina.com.cn"},
            proxies=NO_PROXY,
        )
        if r.status_code == 200:
            # var hq_str_sz000001="平安银行,10.98,..."
            match = re.search(r'"([^"]+)"', r.text)
            if match:
                name = match.group(1).split(",")[0]
                if name:
                    _save_name(code, name)
                    return name
    except Exception:
        pass
    return None


# ======================== 各信源实现 ========================
def _fetch_sina(code: str, days: int) -> Optional[pd.DataFrame]:
    """信源1: 新浪日K线"""
    prefix = _market_prefix(code)
    datalen = max(days * 2, 60)  # 多拉一些确保够用
    try:
        url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {
            "symbol": f"{prefix}{code}",
            "scale": "240",    # 日K
            "ma": "no",
            "datalen": str(min(datalen, 800)),
        }
        r = requests.get(url, params=params, timeout=8, proxies=NO_PROXY)
        if r.status_code != 200:
            return None

        import json
        data = json.loads(r.text)
        if not data:
            return None

        rows = []
        for item in data:
            rows.append({
                "date": item["day"][:10],
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": float(item["volume"]),
            })

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df = df.sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        print(f"[SINA] fetch fail: {e}")
        return None


def _fetch_baostock(code: str, days: int) -> Optional[pd.DataFrame]:
    """信源2: baostock（备选）"""
    try:
        import baostock as bs

        end = datetime.today()
        start = end - timedelta(days=days * 2 + 20)
        prefix = _market_prefix(code)

        bs.login()
        rs = bs.query_history_k_data_plus(
            f"{prefix}.{code}",
            "date,open,high,low,close,volume",
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            frequency="d",
            adjustflag="2",
        )
        rows = []
        while rs.next():
            row = rs.get_row_data()
            if row[1] == "" or row[4] == "":
                continue
            rows.append({
                "date": row[0],
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })
        bs.logout()

        if not rows:
            return None

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df = df.sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        print(f"[BAOSTOCK] fetch fail: {e}")
        return None


# ======================== 核心：多信源并行获取 ========================
def fetch_stock_data(
    code: str,
    time_range_days: int = 60,
    force_refresh: bool = False,
) -> Optional[pd.DataFrame]:
    """
    多信源并行获取股票日 K 数据

    Tier 1（并行抢答）: 新浪日K, baostock
    谁先返回有效数据就用谁

    Returns
    -------
    DataFrame with columns: [date, open, high, low, close, volume]
    """
    code = normalise_code(code)
    if not code or not code.isdigit() or len(code) != 6:
        print(f"[ERROR] invalid code: {code}")
        return None

    end_date = datetime.today()
    start_date = end_date - timedelta(days=time_range_days * 2 + 20)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    # ---------- 1. 查缓存 ----------
    if not force_refresh:
        cached = _read_cache(code, start_str, end_str)
        if cached is not None and len(cached) >= time_range_days // 2:
            return cached.tail(time_range_days)

    # ---------- 2. Tier 1 并行抢答 ----------
    tier1_sources = [
        ("sina", lambda: _fetch_sina(code, time_range_days)),
        ("baostock", lambda: _fetch_baostock(code, time_range_days)),
    ]

    best_df = None

    with ThreadPoolExecutor(max_workers=len(tier1_sources)) as pool:
        futures = {pool.submit(fn): name for name, fn in tier1_sources}

        for future in as_completed(futures):
            name = futures[future]
            try:
                df = future.result(timeout=15)
                if df is not None and not df.empty:
                    print(f"[{name}] got {len(df)} rows for {code}")
                    best_df = df
                    # 取消其他未完成的
                    for f in futures:
                        if not f.done():
                            f.cancel()
                    break
            except Exception as e:
                print(f"[{name}] error: {e}")

    # ---------- 3. 结果处理 ----------
    if best_df is None:
        print(f"[ERROR] all sources failed for {code}")
        return None

    # 自动缓存名称（从输出中提取，或从新浪响应获取）
    name = get_stock_name(code)
    if name:
        _save_name(code, name)

    _save_cache(code, best_df)
    return best_df.tail(time_range_days)
