"""Objective score 계산 및 best-config 선택."""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

from core.constants import OBJECTIVE_WEIGHTS, REVERSE_SCORE_METRICS


def build_metric_ranges(df: pd.DataFrame) -> Dict[str, Tuple[float, float]]:
    metric_weights = OBJECTIVE_WEIGHTS[str(df["workload_kind"].iloc[0])]
    return {metric: (float(df[metric].min()), float(df[metric].max())) for metric in metric_weights}


def normalize_metric(value: float, lower: float, upper: float, reverse: bool = False) -> float:
    if upper > lower:
        normalized = (value - lower) / (upper - lower)
    else:
        normalized = 0.5
    normalized = float(np.clip(normalized, 0.0, 1.0))
    return 1.0 - normalized if reverse else normalized


def score_policy_rows(
    df: pd.DataFrame,
    metric_ranges: Dict[str, Tuple[float, float]],
) -> pd.DataFrame:
    scored = df.copy()
    workload = str(scored["workload_kind"].iloc[0])
    objective = np.zeros(len(scored), dtype=float)
    for metric, weight in OBJECTIVE_WEIGHTS[workload].items():
        lower, upper = metric_ranges[metric]
        reverse = metric in REVERSE_SCORE_METRICS
        normalized = scored[metric].apply(
            lambda value: normalize_metric(float(value), lower, upper, reverse=reverse)
        )
        scored[f"{metric}_score"] = normalized
        objective += weight * normalized.to_numpy(dtype=float)
    scored["objective_score"] = objective
    return scored


def score_policy_result(
    policy_result: Dict[str, object],
    metric_ranges: Dict[str, Tuple[float, float]],
) -> float:
    policy_result_df = pd.DataFrame([policy_result])
    scored = score_policy_rows(policy_result_df, metric_ranges)
    return float(scored.iloc[0]["objective_score"])


def select_best_fixed_config(
    fixed_grid_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Dict[str, Tuple[float, float]]]]:
    scored_groups: List[pd.DataFrame] = []
    metric_ranges_by_scenario: Dict[str, Dict[str, Tuple[float, float]]] = {}
    for scenario_key, group in fixed_grid_df.groupby("scenario_id", sort=False):
        local = group.reset_index(drop=True)
        metric_ranges = build_metric_ranges(local)
        scored_local = score_policy_rows(local, metric_ranges)
        scored_groups.append(scored_local)
        metric_ranges_by_scenario[str(scenario_key)] = metric_ranges
    scored = pd.concat(scored_groups, ignore_index=True) if scored_groups else pd.DataFrame()
    if scored.empty:
        return scored, scored, metric_ranges_by_scenario
    best_row_index = scored.groupby("scenario_id")["objective_score"].idxmax()
    best_fixed_config_df = scored.loc[best_row_index].copy().reset_index(drop=True)
    return scored, best_fixed_config_df, metric_ranges_by_scenario
