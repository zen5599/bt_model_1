# 通用策略回测框架

[English](README.md) | **中文版**

一个支持多时间周期和参数扫描的通用回测框架，并使用 Dash 提供交互式结果面板。框架可以用于不同交易标的，并不局限于比特币或某个特定时间周期。

## 环境要求

- Python 3.11 或更高版本
- [uv](https://docs.astral.sh/uv/)

在项目目录中安装锁定的依赖：

```bash
uv sync
```

## 支持的时间周期

回测引擎支持以下时间周期，并使用对应的年化系数：

| 时间周期 | 每根 K 线分钟数 | 是否附带演示数据 |
| --- | ---: | :---: |
| 1m | 1 | 否 |
| 5m | 5 | 是 |
| 10m | 10 | 否 |
| 15m | 15 | 否 |
| 30m | 30 | 否 |
| 1h | 60 | 否 |
| 4h | 240 | 否 |
| 1d | 1,440 | 否 |

使用其他时间周期或数据集时，请修改 `bt_main.py` 中的 `RESOLUTION` 和 `DATA_PATH`。

## 演示数据

项目附带的 BTCUSDT 数据**仅用于演示如何运行框架**。框架本身不依赖比特币，可以替换成任何符合相同字段格式的交易标的数据。

演示文件位于：

```text
data/btcusdt_5m.parquet
```

其中包含从 `2020-01-01 00:00:00 UTC` 开始，到数据生成时最后一根已收盘 K 线为止的 BTCUSDT 5 分钟行情。`bt_main.py` 会直接读取该文件；如果文件不存在，程序会给出明确提示。

必需和可选字段：

- 必需字段：`timestamp`, `open`, `high`, `low`, `close`, `volume`
- 演示数据的可选字段：`quote_volume`, `number_of_trades`, `taker_buy_base_volume`, `taker_buy_quote_volume`
- 回测器可选字段：`funding`

## 运行回测

```bash
uv run python bt_main.py
```

程序会依次：

1. 读取附带的 Parquet 行情。
2. 计算买入并持有指标。
3. 使用多进程执行策略参数扫描。
4. 将结果保存至 `results/sweep_5m_*.parquet`。
5. 在 <http://127.0.0.1:8050> 启动 Dash 面板。

由于程序会使用完整数据计算大量参数组合，完整扫描可能需要较长时间。

## 配置

策略定义和参数范围位于 `strategy_module.py`，主要在 `get_strategy_params()` 中修改。

默认交易手续费为 `0.0005`，可以在 `backtester_engine1.py` 的 `Backtester` 构造函数中调整。

附带的数据不包含资金费率，因此默认不会扣除 funding。当输入数据存在 `funding` 字段时，回测器会自动计入资金费用。

## 项目结构

```text
bt_model_1/
├── data/
│   └── btcusdt_5m.parquet
├── results/
├── backtest_dashboard.py
├── backtester_engine1.py
├── bt_main.py
├── data_composer.py
├── strategy_module.py
├── pyproject.toml
├── uv.lock
├── README.md
└── README.zh-CN.md
```

## 分享项目

分享时需要包含：

- 源代码
- `pyproject.toml`
- `uv.lock`
- `data/btcusdt_5m.parquet`

不需要包含 `.venv/`，接收者可以通过 `uv sync` 重新创建环境。
