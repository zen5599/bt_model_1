# bt-model-1

基于 Binance USD-M 永续合约 5 分钟 K 线的参数扫描回测，并用 Dash 展示结果。
项目不依赖原工程中的数据库。

## 环境

安装 [uv](https://docs.astral.sh/uv/) 后，在本目录运行：

```bash
uv sync
```

## 数据

行情已经保存在 `data/btcusdt_5m.parquet`，范围是从 `2020-01-01 00:00:00 UTC`
到数据生成时最后一根已收盘的 5 分钟 K 线。`bt_main.py` 会直接读取该文件；如果
文件不存在，会提示将它放入 `data/` 目录。

Parquet 的主要字段为：

- `timestamp`（UTC）
- `open`, `high`, `low`, `close`
- `volume`, `quote_volume`
- `number_of_trades`
- `taker_buy_base_volume`, `taker_buy_quote_volume`

## 运行回测

```bash
uv run python bt_main.py
```

回测结束后：

- 参数扫描结果保存到 `results/sweep_5m_*.parquet`
- Dashboard 默认打开在 <http://127.0.0.1:8050>

策略扫描范围在 `strategy_module.py` 的 `get_strategy_params()` 中设置；交易手续费
默认是 `0.0005`，位于 `backtester_engine1.py` 的 `Backtester` 构造函数中。

当前 Binance REST 数据只有 OHLCV，不包含资金费率，因此回测不会扣除 funding；
`Backtester` 仅在输入数据存在 `funding` 字段时计算资金费率。

## 分享

分享时需要包含源码、`pyproject.toml`、`uv.lock` 和
`data/btcusdt_5m.parquet`，不需要包含 `.venv/`。
