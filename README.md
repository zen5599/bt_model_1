# General-Purpose Strategy Backtesting Framework

**English** | [中文版](README.zh-CN.md)

A configurable, multi-timeframe parameter-sweep backtesting framework with an interactive Dash results dashboard. It can be used with different instruments and is not tied to Bitcoin or a specific timeframe.

## Requirements

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/)

Install the locked dependencies from this directory:

```bash
uv sync
```

## Supported timeframes

The backtesting engine supports the following timeframes and uses their corresponding annualization factors:

| Timeframe | Minutes per bar | Included demo data |
| --- | ---: | :---: |
| 1m | 1 | No |
| 5m | 5 | Yes |
| 10m | 10 | No |
| 15m | 15 | No |
| 30m | 30 | No |
| 1h | 60 | No |
| 4h | 240 | No |
| 1d | 1,440 | No |

Set `RESOLUTION` and `DATA_PATH` in `bt_main.py` when using another timeframe or dataset.

## Demo dataset

The bundled BTCUSDT dataset is provided **only as a runnable demonstration**. Bitcoin is not a requirement of the framework and can be replaced with another instrument that follows the same schema.

The demo file is located at:

```text
data/btcusdt_5m.parquet
```

It contains BTCUSDT 5-minute candles beginning at `2020-01-01 00:00:00 UTC` and ending at the last completed candle when the dataset was generated. `bt_main.py` reads this file directly and reports a clear error if it is missing.

Required and optional columns:

- Required: `timestamp`, `open`, `high`, `low`, `close`, `volume`
- Optional demo fields: `quote_volume`, `number_of_trades`, `taker_buy_base_volume`, `taker_buy_quote_volume`
- Optional backtester field: `funding`

## Running the backtest

```bash
uv run python bt_main.py
```

The program will:

1. Load the bundled Parquet dataset.
2. Calculate buy-and-hold metrics.
3. Run the configured strategy parameter sweep in parallel.
4. Save the results under `results/sweep_5m_*.parquet`.
5. Start the Dash dashboard at <http://127.0.0.1:8050>.

The full parameter sweep can take a significant amount of time because it evaluates many parameter combinations over the complete dataset.

## Configuration

Strategy definitions and parameter ranges are located in `strategy_module.py`, particularly `get_strategy_params()`.

The default transaction cost is `0.0005` and is configured in the `Backtester` constructor in `backtester_engine1.py`.

The bundled dataset does not contain funding rates, so funding is not deducted. The backtester automatically includes funding costs when a `funding` column is present.

## Project structure

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

## Sharing the project

Include the following when sharing the project:

- Source files
- `pyproject.toml`
- `uv.lock`
- `data/btcusdt_5m.parquet`

Do not include `.venv/`; the recipient can recreate it with `uv sync`.
