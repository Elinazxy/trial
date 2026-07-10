# trial

A 股均线金叉筛选:找出最近 N 个交易日内 **MA5 上穿 MA10** 的股票。

## 依赖

```bash
pip install -r requirements.txt
```

## 使用

```bash
# 最近 3 个交易日内出现 MA5 上穿 MA10 的全部 A 股
python ma_crossover.py --days 3

# 调试:只扫前 200 只
python ma_crossover.py --days 3 --limit 200

# 指定复权方式与并发数,并写出到指定文件
python ma_crossover.py --days 3 --adjust qfq --workers 16 --out result.csv
```

运行结束后:
- 结果写入 CSV(默认 `ma5_ma10_crossover.csv`,含代码、名称、金叉日期、最新收盘、MA5、MA10);
- 控制台打印前 50 条。

## 金叉定义

某交易日 `t` 满足:

```
MA5[t] > MA10[t]   且   MA5[t-1] <= MA10[t-1]
```

只要该"上穿"发生在最近 `--days` 个交易日内即视为命中。

## 说明

- 数据源为 [akshare](https://akshare.akfamily.xyz/)(默认东方财富接口,免费、无需 token)。
- **需要能访问行情数据源的网络环境**;在受限的沙箱/CI 中若外网被拦截将无法拉取数据,请在本地运行。
- 本工具仅用于技术面筛选,**不构成任何投资建议**。
