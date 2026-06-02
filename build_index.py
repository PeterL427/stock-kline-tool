"""
全量 A 股索引构建脚本 —— 从新浪拉取所有股票 + 生成拼音

运行： python build_index.py
"""

import csv
import json
import os
import sys

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NO_PROXY = {"http": None, "https": None}


def fetch_all_stocks() -> list:
    """从新浪财经拉取全量 A 股列表（约 5500 只）"""
    url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    all_stocks = []

    for page in range(1, 100):
        params = {
            "page": page,
            "num": 100,
            "sort": "symbol",
            "asc": 1,
            "node": "hs_a",
        }
        try:
            r = requests.get(url, params=params, timeout=10, proxies=NO_PROXY)
            data = r.json()
            if not data:
                break
            for item in data:
                all_stocks.append((item["code"], item["name"]))
            print(f"  Page {page}: {len(data)} stocks (total {len(all_stocks)})")
        except Exception as e:
            print(f"  Page {page}: FAIL - {e}")
            break

    return all_stocks


def build_pinyin_index(stocks: list) -> list:
    """生成拼音首字母索引"""
    try:
        from pypinyin import lazy_pinyin, Style
    except ImportError:
        print("[ERROR] pypinyin not installed. Run: pip install pypinyin")
        return [{"c": c, "n": n, "p": ""} for c, n in stocks]

    index = []
    for i, (code, name) in enumerate(stocks):
        try:
            initials = "".join(
                p[0].upper() for p in lazy_pinyin(name, style=Style.FIRST_LETTER)
            )
        except Exception:
            initials = ""
        index.append({"c": code, "n": name, "p": initials})
        if (i + 1) % 1000 == 0:
            print(f"  Pinyin: {i+1}/{len(stocks)}")
    return index


def main():
    print("=" * 40)
    print("  全量 A 股索引构建工具")
    print("=" * 40)

    # Step 1: 拉取
    print("\n[1/3] 从新浪财经拉取股票列表...")
    stocks = fetch_all_stocks()
    if not stocks:
        print("[ERROR] 未获取到任何股票")
        return
    print(f"  共 {len(stocks)} 只股票")

    # Step 2: 保存原始 CSV（备份）
    csv_path = os.path.join(BASE_DIR, "all_stocks_raw.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "name"])
        w.writerows(stocks)
    print(f"\n[2/3] 原始数据已保存: {csv_path}")

    # Step 3: 生成拼音索引
    print("\n[3/3] 生成拼音索引...")
    index = build_pinyin_index(stocks)

    json_path = os.path.join(BASE_DIR, "stock_index.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)

    size_kb = os.path.getsize(json_path) / 1024
    pinyin_count = sum(1 for i in index if i.get("p", ""))
    print(f"\n✅ 完成！")
    print(f"   索引文件: {json_path} ({size_kb:.0f} KB)")
    print(f"   股票总数: {len(index)}")
    print(f"   有拼音:   {pinyin_count}")
    print(f"\n   搜索示例: PA → 平安银行/普昂医疗/平安电工...")


if __name__ == "__main__":
    main()
