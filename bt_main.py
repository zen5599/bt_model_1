from pathlib import Path

import logging
import multiprocessing as mp
import time
from itertools import product

import pandas as pd
from backtest_dashboard import run_dashboard
from backtester_engine1 import Backtester  # , create_batches
from data_composer import advanced_multi_compose_data
from strategy_module import StrategyType, get_param_ranges, make_strategy

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COMPOSE_COLS: list[str] = ["close"]
BATCH_SIZE = 50

# Binance BTCUSDT USD-M perpetual futures.
RESOLUTION = "5m"
PROJECT_DIR = Path(__file__).resolve().parent
DATA_PATH = PROJECT_DIR / "data" / "btcusdt_5m.parquet"
RESULTS_DIR = PROJECT_DIR / "results"

# Minutes per bar, for the backtester's annualization lookup.
INTERVAL_MINUTES = {
    "1m": 1,
    "5m": 5,
    "10m": 10,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


def create_strategy(
    strategy_type,
    window: int,
    entry_threshold: float,
    exit_threshold: float,
    composed_col: str,
):
    return make_strategy(
        strategy_type,
        int(window),
        float(entry_threshold),
        float(exit_threshold),
        composed_col,
    )


def calculate_buy_hold_metrics(df: pd.DataFrame, interval: int) -> dict:
    logger.info("Calculating Buy-and-Hold metrics...")
    dummy_backtester = Backtester(df.copy(), None, interval)
    buy_hold_metrics = dummy_backtester.calculate_buy_hold_metrics()
    return {
        "buy_hold_sharpe": float(buy_hold_metrics.sharpe_ratio),
        "buy_hold_max_drawdown": float(buy_hold_metrics.max_drawdown),
        "buy_hold_total_return": float(buy_hold_metrics.total_return),
    }


def optimize_result_for_dashboard(
    result: dict, strategy_type: str, composition_name: str
) -> dict:
    try:
        return {
            "strategy_type": strategy_type,
            "composition": composition_name,
            "window": int(result.get("window", 0)),
            "entry_threshold": float(result.get("entry_threshold", 0)),
            "exit_threshold": float(result.get("exit_threshold", 0)),
            "sharpe_ratio": float(result.get("sharpe_ratio", 0)),
            "sortino_ratio": float(result.get("sortino_ratio", 0)),
            "calmar_ratio": float(result.get("calmar_ratio", 0)),
            "max_drawdown": float(result.get("max_drawdown", 0)),
            "mddd": int(result.get("mddd", 0)),
            "total_return": float(result.get("total_return", 0)),
            "annualized_return": float(result.get("annualized_return", 0)),
            "total_trade": int(result.get("total_trade", 0)),
            "trade_frequency": float(result.get("trade_frequency", 0)),
            "win_rate": float(result.get("win_rate", 0)),
            "profit_factor": float(result.get("profit_factor", 0)),
        }
    except Exception as e:
        logger.error(f"Error optimizing result: {str(e)}")
        logger.debug(f"Problem result: {result}")
        raise


def run_strategy_combination(
    params: tuple[StrategyType, str, pd.DataFrame, int, int, float, float],
) -> dict:
    strategy_type, composition_name, data, interval, window, entry, exit = params
    try:
        strategy = create_strategy(strategy_type, window, entry, exit, composition_name)
        backtester = Backtester(data.copy(), strategy, interval)
        result, _ = backtester.run()
        return optimize_result_for_dashboard(
            result.__dict__, strategy_type.value, composition_name
        )
    except Exception as e:
        logger.error(f"Error in run_strategy_combination: {str(e)}")
        return None


def main():
    start_time = time.perf_counter()
    dashboard_results = []
    buy_hold_metrics = None

    try:
        if not DATA_PATH.exists():
            raise FileNotFoundError(
                f"Market data not found: {DATA_PATH}. "
                "Place btcusdt_5m.parquet in the data directory."
            )

        logger.info(f"Loading data from {DATA_PATH}")
        df = pd.read_parquet(DATA_PATH)
        required_columns = {"timestamp", "open", "high", "low", "close", "volume"}
        missing_columns = required_columns.difference(df.columns)
        if missing_columns:
            raise ValueError(
                f"Market data is missing columns: {sorted(missing_columns)}"
            )
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        interval = INTERVAL_MINUTES[RESOLUTION]
        logger.info(f"{len(df):,} bars: {df.index.min()} .. {df.index.max()}")

        # Calculate buy-hold metrics once
        buy_hold_metrics = calculate_buy_hold_metrics(df, interval)
        logger.info(f"Buy-and-Hold metrics calculated: {buy_hold_metrics}")

        composed_dfs = advanced_multi_compose_data(df, COMPOSE_COLS)

        # Create all parameter combinations
        all_params = []
        for composition_name, composed_df in composed_dfs.items():
            for strategy_type in StrategyType:
                window_range, entry_range, exit_range = get_param_ranges(strategy_type)
                params = product(
                    [strategy_type],
                    [composition_name],
                    [composed_df],
                    [interval],
                    window_range,
                    entry_range,
                    exit_range,
                )
                all_params.extend(params)

        # Process combinations in parallel
        n_processes = mp.cpu_count()
        with mp.Pool(processes=n_processes) as pool:
            results = pool.map(run_strategy_combination, all_params)
            dashboard_results = [r for r in results if r is not None]

        elapsed_time = time.perf_counter() - start_time
        logger.info(f"Backtest completed in {elapsed_time:.2f} seconds")

        # Persist before rendering: run_dashboard blocks, so results would
        # otherwise be lost on Ctrl-C and need a full re-run to see again.
        if dashboard_results:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            out_path = RESULTS_DIR / f"sweep_{RESOLUTION}_{stamp}.parquet"
            pd.DataFrame(dashboard_results).to_parquet(out_path, index=False)
            logger.info(f"Saved {len(dashboard_results):,} results -> {out_path}")

            logger.info(f"Launching dashboard with {len(dashboard_results)} results...")
            logger.debug(f"Sample of results: {dashboard_results[:2]}")
            logger.debug(f"Buy-hold metrics: {buy_hold_metrics}")
            run_dashboard(dashboard_results, buy_hold_metrics, port=8050)
        else:
            logger.warning("No results to display in dashboard")
            logger.debug("Results list is empty")
            logger.debug(f"Buy-hold metrics: {buy_hold_metrics}")

    except KeyboardInterrupt:
        logger.info("\nBacktest interrupted by user")
    except Exception as e:
        logger.error(f"Error during backtest: {str(e)}", exc_info=True)
        logger.error(
            f"Results length: {len(dashboard_results) if dashboard_results else 0}"
        )
        logger.error(f"Buy-hold metrics: {buy_hold_metrics}")
        raise


if __name__ == "__main__":
    main()
