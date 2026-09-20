# backtester_engine.py
import multiprocessing as mp
from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class StrategyResult:
    window: int
    entry_threshold: float
    exit_threshold: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    mddd: int
    total_return: float
    annualized_return: float
    avg_return: float
    std_return: float
    total_trade: int
    trade_frequency: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float


@dataclass
class BuyHoldResult:
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    interval: int
    composition: str


@dataclass
class BatchResult:
    window_range: tuple[int, int]
    strategy_results: list[StrategyResult]
    indicators: dict[str, pd.DataFrame]


class Backtester:
    def __init__(
        self,
        data: pd.DataFrame,
        strategy: Any,
        interval: int,
        initial_balance: float = 1000,
        transaction_cost: float = 0.0005,
    ):
        self.data = data
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.transaction_cost = transaction_cost
        self.interval = interval
        self.annualization_factor = self._calculate_annualization_factor(interval)
        self.results_df = None
        self.buy_hold_metrics = None

    def _calculate_annualization_factor(self, interval: int) -> float:
        intervals = {
            1: 365 * 24 * 60,  # 1-minute data
            5: 365 * 24 * 12,  # 5-minute data
            10: 365 * 24 * 6,  # 10-minute data
            15: 365 * 24 * 4,  # 15-minute data
            30: 365 * 24 * 2,  # 30-minute data
            60: 365 * 24,  # 1-hour data
            240: 365 * 6,  # 4-hour data
            1440: 365,  # Daily data
        }
        return np.sqrt(intervals.get(interval, 365))

    def calculate_buy_hold_metrics(self) -> BuyHoldResult:
        if self.buy_hold_metrics is None:
            df = self.data.copy()
            df["returns"] = df["close"].pct_change()
            df["buy_hold_returns"] = df["returns"]
            df["buy_hold_cumulative_returns"] = (1 + df["buy_hold_returns"]).cumprod()
            df["buy_hold_equity_curve"] = (
                self.initial_balance * df["buy_hold_cumulative_returns"]
            )
            df["buy_hold_drawdown"] = (
                df["buy_hold_equity_curve"].cummax() - df["buy_hold_equity_curve"]
            ) / df["buy_hold_equity_curve"].cummax()

            buy_hold_total_return = (
                df["buy_hold_equity_curve"].iloc[-1] / self.initial_balance
            ) - 1
            buy_hold_sharpe_ratio = (
                self.annualization_factor
                * df["buy_hold_returns"].mean()
                / df["buy_hold_returns"].std()
            )
            buy_hold_max_drawdown = df["buy_hold_drawdown"].max()

            self.buy_hold_metrics = BuyHoldResult(
                sharpe_ratio=buy_hold_sharpe_ratio,
                max_drawdown=buy_hold_max_drawdown,
                total_return=buy_hold_total_return,
                interval=self.interval,
                composition="",
            )

        return self.buy_hold_metrics

    def run(self) -> tuple[StrategyResult, BuyHoldResult]:
        df = self.strategy.calculate_signals(self.data.copy())

        # Positions before the first signal are NaN; treat as flat.
        pos = np.nan_to_num(df["pos"].to_numpy(dtype=float), nan=0.0)
        prices = df["close"].to_numpy(dtype=float)

        # returns[i] is the return over bar i -> i+1, earned by the position held
        # entering that bar, i.e. pos[i]. Turnover is charged on the same bar as
        # the position change that causes it.
        returns = np.diff(prices) / prices[:-1]
        turnover = np.abs(np.diff(pos))
        initial_trade = abs(pos[0])
        strategy_returns = pos[:-1] * returns - turnover * self.transaction_cost

        # Perp funding: longs pay shorts when the rate is positive, so a position
        # of `pos` accrues -pos * rate. Zero on bars with no settlement.
        if "funding" in df.columns:
            funding = np.nan_to_num(df["funding"].to_numpy(dtype=float), nan=0.0)
            strategy_returns = strategy_returns - pos[:-1] * funding[:-1]

        equity_curve = self.initial_balance * np.cumprod(1 + strategy_returns)
        peak = np.maximum.accumulate(equity_curve)
        drawdown = np.where(peak > 0, (peak - equity_curve) / peak, 0)

        total_return = (equity_curve[-1] / self.initial_balance) - 1
        max_drawdown = np.max(drawdown)

        # Max drawdown duration: longest consecutive run of underwater periods.
        underwater = drawdown > 0
        if underwater.any():
            edges = np.diff(np.concatenate([[0], underwater.astype(int), [0]]))
            starts = np.where(edges == 1)[0]
            ends = np.where(edges == -1)[0]
            mddd = int((ends - starts).max())
        else:
            mddd = 0

        num_periods = len(strategy_returns)
        avg_return = np.mean(strategy_returns) if num_periods > 0 else 0.0
        std_return = np.std(strategy_returns, ddof=1) if num_periods > 1 else 0.0

        sharpe_ratio = (
            self.annualization_factor * avg_return / std_return
            if std_return > 0
            else 0.0
        )

        downside_returns = strategy_returns[strategy_returns < 0]
        downside_std = (
            np.std(downside_returns, ddof=1) if len(downside_returns) > 1 else 0.0
        )
        sortino_ratio = (
            self.annualization_factor * avg_return / downside_std
            if downside_std > 0
            else 0.0
        )

        # Geometric annualized return (consistent with the geometric equity curve).
        periods_per_year = self.annualization_factor**2
        years = num_periods / periods_per_year
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0

        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else np.inf

        # Turnover is summed in position units, so a +1 -> -1 flip counts as 2.
        total_trade = int(initial_trade + np.sum(turnover))
        trade_frequency = total_trade / num_periods if num_periods > 0 else 0.0

        winning_returns = strategy_returns[strategy_returns > 0]
        losing_returns = strategy_returns[strategy_returns < 0]

        # Note: per-bar win rate, not per-trade.
        win_rate = len(winning_returns) / num_periods if num_periods > 0 else 0.0
        avg_win = np.mean(winning_returns) if len(winning_returns) > 0 else 0.0
        avg_loss = np.mean(losing_returns) if len(losing_returns) > 0 else 0.0

        total_wins = np.sum(winning_returns) if len(winning_returns) > 0 else 0.0
        total_losses = -np.sum(losing_returns) if len(losing_returns) > 0 else 0.0
        profit_factor = total_wins / total_losses if total_losses > 0 else np.inf

        df["strategy_returns"] = np.concatenate([[np.nan], strategy_returns])
        df["equity_curve"] = np.concatenate([[self.initial_balance], equity_curve])
        self.results_df = df

        strategy_result = StrategyResult(
            window=self.strategy.window,
            entry_threshold=self.strategy.entry_threshold,
            exit_threshold=self.strategy.exit_threshold,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            mddd=mddd,
            total_return=total_return,
            annualized_return=annualized_return,
            avg_return=avg_return,
            std_return=std_return,
            total_trade=total_trade,
            trade_frequency=trade_frequency,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
        )

        return strategy_result, self.calculate_buy_hold_metrics()


def create_batches(
    window_start: int, window_end: int, batch_size: int = 50
) -> list[tuple[int, int]]:
    """Create window range batches."""
    ranges = []
    for start in range(window_start, window_end, batch_size):
        end = min(start + batch_size, window_end)
        ranges.append((start, end))
    return ranges


def process_batch(
    batch_params: tuple[
        tuple[int, int], list[tuple[float, float, float]], pd.DataFrame, int, Any
    ],
) -> list[tuple[StrategyResult, BuyHoldResult]]:
    window_range, param_combinations, data, interval, strategy_class = batch_params
    results = []

    # Pre-calculate indicators for the window range
    indicators = {}
    for window in range(window_range[0], window_range[1]):
        df = data.copy()
        # Store rolling calculations
        indicators[window] = {
            "mean": df["close"].rolling(window=window).mean(),
            "std": df["close"].rolling(window=window).std(),
            "min": df["close"].rolling(window=window).min(),
            "max": df["close"].rolling(window=window).max(),
        }

    # Process parameter combinations for this window range
    for window, entry, exit in param_combinations:
        if window_range[0] <= window < window_range[1]:
            strategy = strategy_class(window, entry, exit)
            strategy._cached_indicators = indicators[
                window
            ]  # Pass pre-calculated indicators
            backtester = Backtester(data, strategy, interval)
            results.append(backtester.run())

    return results


def run_grid_search(
    data: pd.DataFrame,
    window_range: list[int],
    entry_threshold_range: list[float],
    exit_threshold_range: list[float],
    interval: int,
    strategy_class: Any,
    n_processes: int = None,
    batch_size: int = 50,
) -> tuple[pd.DataFrame, BuyHoldResult]:
    if n_processes is None:
        n_processes = mp.cpu_count()

    # Create batches for windows
    window_batches = create_batches(
        min(window_range), max(window_range) + 1, batch_size
    )

    # Generate all parameter combinations
    all_params = list(
        product(window_range, entry_threshold_range, exit_threshold_range)
    )

    # Prepare batch parameters
    batch_params = [
        (w_range, all_params, data, interval, strategy_class)
        for w_range in window_batches
    ]

    # Initialize the multiprocessing pool
    with mp.Pool(processes=n_processes) as pool:
        try:
            # Process batches in parallel
            batch_results = pool.map(process_batch, batch_params)

            # Flatten results
            all_results = [result for batch in batch_results for result in batch]

            # Split strategy results and buy-hold results
            strategy_results, buy_hold_results = zip(*all_results, strict=True)

            # Convert to DataFrame
            strategy_df = pd.DataFrame(strategy_results)

            return strategy_df, buy_hold_results[0]

        except Exception as e:
            pool.terminate()
            raise Exception(f"Error during grid search: {str(e)}") from e

        finally:
            pool.close()
            pool.join()
