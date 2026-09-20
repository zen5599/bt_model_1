"""Strategy definitions.

The nine strategies are one rule on three axes, not nine separate classes:

    indicator   z-score  |  min-max normalisation
    trigger     level comparison (mean-reversion)  |  threshold crossing (trend)
    side        +1 long  |  -1 short   (flip=True exits to -side instead of flat)

Long and short collapse into one expression because multiplying a comparison by
`side` flips the inequality for shorts. Adding a strategy is one entry in
STRATEGIES plus one in `get_strategy_params`' map.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd


class StrategyType(Enum):
    # Mean Reversion Strategies
    MR_ZSCORE_LONG = "MR Z-Score Long"
    MR_ZSCORE_SHORT = "MR Z-Score Short"
    MR_MINMAX_LONG = "MR MinMax Long"
    MR_MINMAX_SHORT = "MR MinMax Short"
    MR_MINMAX_FLIP = "MR MinMax Flip"
    # Trend Following Strategies
    TF_ZSCORE_LONG = "TF Z-Score Long"
    TF_ZSCORE_SHORT = "TF Z-Score Short"
    TF_MINMAX_LONG = "TF MinMax Long"
    TF_MINMAX_SHORT = "TF MinMax Short"


@dataclass
class StrategyParams:
    window_start: int = 50
    window_end: int = 311
    window_step: int = 20
    entry_start: float = -2.5
    entry_end: float = -0.5
    entry_step: float = 0.2
    exit_start: float = 0.5
    exit_end: float = 2.5
    exit_step: float = 0.05


def zscore(s: pd.Series, window: int) -> pd.Series:
    """Rolling z-score, lagged one bar so it uses only data through t-1."""
    return ((s - s.rolling(window).mean()) / s.rolling(window).std()).shift()


def minmax(s: pd.Series, window: int) -> pd.Series:
    """Rolling position within the window's range, in [0, 1], lagged one bar."""
    lo, hi = s.rolling(window).min().shift(), s.rolling(window).max().shift()
    return (s.shift() - lo) / (hi - lo).replace(0, 1)


INDICATORS = {"z": zscore, "mm": minmax}


def _cross(x: pd.Series, level: float, up: bool) -> np.ndarray:
    """Bars where `x` crosses `level` upward (up=True) or downward."""
    prev = x.shift(1)
    hit = (prev <= level) & (x > level) if up else (prev >= level) & (x < level)
    return hit.to_numpy()


class Strategy:
    """One parameterised rule covering every entry in STRATEGIES."""

    def __init__(
        self,
        col: str,
        window: int,
        entry: float,
        exit: float,
        indicator: str = "z",
        trigger: str = "level",
        side: int = 1,
        flip: bool = False,
    ):
        self.col = col
        self.window = int(window)
        self.entry_threshold = float(entry)
        self.exit_threshold = float(exit)
        self.indicator = indicator
        self.trigger = trigger
        self.side = int(side)
        self.flip = flip

    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        x = INDICATORS[self.indicator](df[self.col], self.window)
        s = self.side
        exit_val = -s if self.flip else 0.0
        if self.trigger == "level":
            # Multiplying by `side` mirrors the comparison for shorts. Entry
            # wins ties, matching the nested np.where this replaced.
            pos = np.where(
                s * x < s * self.entry_threshold,
                float(s),
                np.where(s * x > s * self.exit_threshold, exit_val, np.nan),
            )
        else:
            # Exit wins ties, matching the ordered assignment this replaced.
            pos = np.full(len(df), np.nan)
            pos[_cross(x, self.entry_threshold, s > 0)] = float(s)
            pos[_cross(x, self.exit_threshold, s < 0)] = exit_val
        df["pos"] = pd.Series(pos, index=df.index).ffill()
        return df


# The nine strategies as configuration rather than nine classes.
STRATEGIES: dict[StrategyType, dict] = {
    StrategyType.MR_ZSCORE_LONG: dict(indicator="z", trigger="level", side=+1),
    StrategyType.MR_ZSCORE_SHORT: dict(indicator="z", trigger="level", side=-1),
    StrategyType.MR_MINMAX_LONG: dict(indicator="mm", trigger="level", side=+1),
    StrategyType.MR_MINMAX_SHORT: dict(indicator="mm", trigger="level", side=-1),
    StrategyType.MR_MINMAX_FLIP: dict(
        indicator="mm", trigger="level", side=+1, flip=True
    ),
    StrategyType.TF_ZSCORE_LONG: dict(indicator="z", trigger="cross", side=+1),
    StrategyType.TF_ZSCORE_SHORT: dict(indicator="z", trigger="cross", side=-1),
    StrategyType.TF_MINMAX_LONG: dict(indicator="mm", trigger="cross", side=+1),
    StrategyType.TF_MINMAX_SHORT: dict(indicator="mm", trigger="cross", side=-1),
}


def make_strategy(
    strategy_type: StrategyType,
    window: int,
    entry_threshold: float,
    exit_threshold: float,
    col: str,
) -> Strategy:
    """Build the strategy for `strategy_type` over the column `col`."""
    return Strategy(
        col, window, entry_threshold, exit_threshold, **STRATEGIES[strategy_type]
    )


def get_strategy_params(strategy_type: StrategyType) -> StrategyParams:
    params_map = {
        # Mean Reversion Parameters
        StrategyType.MR_ZSCORE_LONG: StrategyParams(
            entry_start=-2.7,
            entry_end=-0.5,
            entry_step=0.2,
            exit_start=0.5,
            exit_end=2.7,
            exit_step=0.2,
        ),
        StrategyType.MR_ZSCORE_SHORT: StrategyParams(
            entry_start=0.5,
            entry_end=2.7,
            entry_step=0.2,
            exit_start=-2.7,
            exit_end=-0.5,
            exit_step=0.2,
        ),
        StrategyType.MR_MINMAX_LONG: StrategyParams(
            entry_start=0.1,
            entry_end=0.4,
            entry_step=0.02,
            exit_start=0.6,
            exit_end=0.9,
            exit_step=0.02,
        ),
        StrategyType.MR_MINMAX_SHORT: StrategyParams(
            entry_start=0.6,
            entry_end=0.9,
            entry_step=0.02,
            exit_start=0.1,
            exit_end=0.4,
            exit_step=0.02,
        ),
        StrategyType.MR_MINMAX_FLIP: StrategyParams(
            entry_start=0.1,
            entry_end=0.4,
            entry_step=0.02,
            exit_start=0.6,
            exit_end=0.9,
            exit_step=0.02,
        ),
        # Trend Following Parameters
        StrategyType.TF_ZSCORE_LONG: StrategyParams(
            entry_start=-2.7,
            entry_end=0.5,
            entry_step=0.2,
            exit_start=1.0,
            exit_end=2.7,
            exit_step=0.2,
        ),
        StrategyType.TF_ZSCORE_SHORT: StrategyParams(
            entry_start=0.5,
            entry_end=2.7,
            entry_step=0.2,
            exit_start=-2.7,
            exit_end=0.0,
            exit_step=0.2,
        ),
        StrategyType.TF_MINMAX_LONG: StrategyParams(
            entry_start=0.1,
            entry_end=0.4,
            entry_step=0.02,
            exit_start=0.5,
            exit_end=0.9,
            exit_step=0.02,
        ),
        StrategyType.TF_MINMAX_SHORT: StrategyParams(
            entry_start=0.5,
            entry_end=0.9,
            entry_step=0.02,
            exit_start=0.1,
            exit_end=0.4,
            exit_step=0.02,
        ),
    }
    return params_map[strategy_type]


def get_param_ranges(strategy_type: StrategyType) -> tuple:
    params = get_strategy_params(strategy_type)
    window_range = range(params.window_start, params.window_end, params.window_step)
    entry_threshold_range = np.arange(
        params.entry_start, params.entry_end, params.entry_step
    )
    exit_threshold_range = np.arange(
        params.exit_start, params.exit_end, params.exit_step
    )
    return window_range, entry_threshold_range, exit_threshold_range


def print_results_with_title(result_df: pd.DataFrame, strategy_name: str):
    separator = "=" * 100
    print(f"\n{separator}")
    print(f"{strategy_name} - Top 10 Results".center(100))
    print(separator)
    print(result_df.head(10))

    print(f"\n{separator}")
    print(f"{strategy_name} - Bottom 10 Results".center(100))
    print(separator)
    print(result_df.tail(10))
