#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
筛选最近 N 个交易日内出现 "MA5 上穿 MA10"(金叉)的 A 股股票。

数据源:akshare(默认走东方财富接口,免费、无需 token)。
用法示例:
    python ma_crossover.py                 # 最近 3 个交易日内金叉,全市场扫描
    python ma_crossover.py --days 3        # 显式指定回看窗口
    python ma_crossover.py --limit 200     # 只扫前 200 只(调试用)
    python ma_crossover.py --adjust qfq    # 前复权(默认 qfq)
    python ma_crossover.py --workers 16    # 并发线程数
    python ma_crossover.py --out result.csv

金叉定义:
    某交易日 t 满足  MA5[t]  >  MA10[t]  且  MA5[t-1] <= MA10[t-1]
只要该"上穿"发生在最近 --days 个交易日内,即视为命中。
"""

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

try:
    import akshare as ak
    import pandas as pd
except ImportError:
    sys.exit("缺少依赖,请先运行:  pip install akshare pandas")


def get_symbol_list():
    """返回全部 A 股 (代码, 名称) 列表。"""
    df = ak.stock_zh_a_spot_em()
    # 过滤北交所可按需处理;这里保留全部主板/创业板/科创板/北交所
    return list(zip(df["代码"].astype(str), df["名称"].astype(str)))


def find_cross(symbol, name, start_date, end_date, adjust, lookback, retries=2):
    """
    对单只股票拉取日线,判断最近 lookback 个交易日内是否发生 MA5 上穿 MA10。
    命中返回 dict,否则返回 None。
    """
    for attempt in range(retries + 1):
        try:
            hist = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            break
        except Exception:
            if attempt == retries:
                return None
            time.sleep(0.5 * (attempt + 1))
    else:
        return None

    if hist is None or len(hist) < 11:
        return None

    close = hist["收盘"].astype(float)
    ma5 = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()

    # 金叉布尔序列:今天 ma5>ma10 且 昨天 ma5<=ma10
    cross = (ma5 > ma10) & (ma5.shift(1) <= ma10.shift(1))

    # 只看最近 lookback 个交易日
    recent = cross.iloc[-lookback:]
    if recent.any():
        # 找出最近一次金叉的日期
        idx = recent[recent].index[-1]
        cross_date = str(hist.loc[idx, "日期"])
        return {
            "代码": symbol,
            "名称": name,
            "金叉日期": cross_date,
            "最新收盘": round(float(close.iloc[-1]), 2),
            "MA5": round(float(ma5.iloc[-1]), 3),
            "MA10": round(float(ma10.iloc[-1]), 3),
        }
    return None


def main():
    p = argparse.ArgumentParser(description="筛选最近 N 个交易日内 MA5 上穿 MA10 的 A 股")
    p.add_argument("--days", type=int, default=3, help="回看窗口(交易日),默认 3")
    p.add_argument("--adjust", default="qfq", choices=["qfq", "hfq", ""], help="复权方式,默认 qfq")
    p.add_argument("--limit", type=int, default=0, help="仅扫描前 N 只(0=全部)")
    p.add_argument("--workers", type=int, default=12, help="并发线程数,默认 12")
    p.add_argument("--out", default="ma5_ma10_crossover.csv", help="输出 CSV 路径")
    args = p.parse_args()

    # 多取一些日历天,保证有足够的交易日算 MA10(约 30 个自然日足够 10 个交易日 + 缓冲)
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")

    print(f"[1/3] 获取 A 股列表 ...")
    symbols = get_symbol_list()
    if args.limit > 0:
        symbols = symbols[: args.limit]
    print(f"      共 {len(symbols)} 只待扫描;回看 {args.days} 个交易日;复权={args.adjust or '不复权'}")

    print(f"[2/3] 并发拉取日线并计算 MA5/MA10 ...")
    hits = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(find_cross, code, name, start_date, end_date, args.adjust, args.days): code
            for code, name in symbols
        }
        for fut in as_completed(futures):
            done += 1
            res = fut.result()
            if res:
                hits.append(res)
            if done % 200 == 0:
                print(f"      进度 {done}/{len(symbols)},已命中 {len(hits)}")

    print(f"[3/3] 完成,命中 {len(hits)} 只")
    if not hits:
        print("最近该窗口内没有股票出现 MA5 上穿 MA10。")
        return

    result = pd.DataFrame(hits).sort_values("金叉日期", ascending=False).reset_index(drop=True)
    result.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"结果已写入:{args.out}\n")
    # 控制台打印前 50 行
    with pd.option_context("display.max_rows", 50, "display.width", 120):
        print(result.head(50).to_string(index=False))


if __name__ == "__main__":
    main()
