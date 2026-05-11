"""Shared data structures and summary builders for actual Mininet experiments."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from eval.metrics import compute_all_video_metrics


@dataclass(frozen=True)
class ExperimentConfig:
    video_name: str
    video_path: Path
    policy_name: str
    python_executable: str
    bandwidth_mbps: float
    round_trip_time_ms: float
    loss_rate: float
    playback_buffer_ms: float
    repeat_index: int
    output_directory: Path


@dataclass(frozen=True)
class ClientTransmissionEvent:
    experiment_start_time_ns: int
    video_name: str
    policy_name: str
    frame_index: int
    frame_type: str
    key_frame: int
    gop_id: int
    payload_bytes: int
    frame_pts_ms: float
    display_deadline_ms: float
    selected_action_name: str
    transport_protocol: str
    send_start_time_ns: int
    dropped_by_policy: bool


@dataclass(frozen=True)
class ServerReceiveEvent:
    frame_index: int
    transport_protocol: str
    receive_time_ns: int
    payload_bytes: int


@dataclass(frozen=True)
class ExperimentSummary:
    video_name: str
    policy_name: str
    bandwidth_mbps: float
    round_trip_time_ms: float
    loss_rate: float
    repeat_index: int
    frame_count: int
    late_frame_count: int
    late_frame_ratio: float
    late_frame_fraction: str
    late_frames_per_1000: float
    dropped_frame_count: int
    mean_deadline_miss_ms_on_late: float
    max_deadline_miss_ms: float
    useful_goodput_bytes: float
    keyframe_late_ratio: float
    decodable_gop_ratio: float
    sent_bytes: float
    on_time_bytes: float
    late_bytes: float
    dropped_bytes: float
    wasted_late_bytes_ratio: float
    on_time_goodput_ratio: float
    dropped_keyframe_count: int
    reliable_single_count: int
    unreliable_count: int
    drop_count: int
    reliable_single_late_count: int
    unreliable_late_count: int


def _write_rows(rows: Sequence[dict[str, object]], output_path: Path, fieldnames: list[str]) -> None:
    resolved_output_path = Path(output_path).resolve()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_client_events(events: Sequence[ClientTransmissionEvent], output_path: Path) -> None:
    rows = [asdict(event) for event in events]
    fieldnames = list(ClientTransmissionEvent.__dataclass_fields__.keys())
    _write_rows(rows, output_path, fieldnames)


def write_server_events(events: Sequence[ServerReceiveEvent], output_path: Path) -> None:
    rows = [asdict(event) for event in events]
    fieldnames = list(ServerReceiveEvent.__dataclass_fields__.keys())
    _write_rows(rows, output_path, fieldnames)


def _load_event_dataframe(event_source: Sequence[dict[str, object]] | Path) -> pd.DataFrame:
    if isinstance(event_source, Path):
        return pd.read_csv(event_source)
    return pd.DataFrame(event_source)


def _merge_client_and_server_events(
    client_event_source: Sequence[dict[str, object]] | Path,
    server_event_source: Sequence[dict[str, object]] | Path,
) -> pd.DataFrame:
    client_dataframe = _load_event_dataframe(client_event_source)
    server_dataframe = _load_event_dataframe(server_event_source)

    if client_dataframe.empty:
        raise RuntimeError("Client event log is empty.")

    if server_dataframe.empty:
        merged_dataframe = client_dataframe.copy()
        merged_dataframe["received_transport_protocol"] = pd.NA
        merged_dataframe["received_payload_bytes"] = pd.NA
        merged_dataframe["receive_time_ns"] = pd.NA
    else:
        server_dataframe = (
            server_dataframe.sort_values(["frame_index", "receive_time_ns"])
            .drop_duplicates(subset=["frame_index"], keep="first")
            .rename(
                columns={
                    "transport_protocol": "received_transport_protocol",
                    "payload_bytes": "received_payload_bytes",
                }
            )
        )
        merged_dataframe = client_dataframe.merge(
            server_dataframe,
            on="frame_index",
            how="left",
        )
    merged_dataframe["receive_time_ms_from_start"] = (
        (merged_dataframe["receive_time_ns"] - merged_dataframe["experiment_start_time_ns"]) / 1_000_000.0
    )
    merged_dataframe["on_time"] = (
        merged_dataframe["receive_time_ms_from_start"].notna()
        & (merged_dataframe["receive_time_ms_from_start"] <= merged_dataframe["display_deadline_ms"])
    )
    merged_dataframe["deadline_miss_ms"] = (
        merged_dataframe["receive_time_ms_from_start"] - merged_dataframe["display_deadline_ms"]
    )
    merged_dataframe.loc[merged_dataframe["deadline_miss_ms"] < 0, "deadline_miss_ms"] = 0.0
    return merged_dataframe


def build_experiment_summary(
    experiment_config: ExperimentConfig,
    client_event_source: Sequence[dict[str, object]] | Path,
    server_event_source: Sequence[dict[str, object]] | Path,
) -> ExperimentSummary:
    merged_dataframe = _merge_client_and_server_events(client_event_source, server_event_source)
    frame_count = int(len(merged_dataframe))
    late_frame_count = int((~merged_dataframe["on_time"]).sum())
    dropped_frame_count = int(merged_dataframe["dropped_by_policy"].astype(bool).sum())
    late_frame_ratio = float(late_frame_count / frame_count) if frame_count else 0.0
    late_frames_per_1000 = float(late_frame_ratio * 1000.0)
    dropped_mask = merged_dataframe["dropped_by_policy"].astype(bool)
    sent_mask = ~dropped_mask
    late_mask = ~merged_dataframe["on_time"].astype(bool)
    action_names = merged_dataframe["selected_action_name"].astype(str).str.upper()

    sent_bytes = float(merged_dataframe.loc[sent_mask, "payload_bytes"].sum())
    on_time_bytes = float(merged_dataframe.loc[sent_mask & (~late_mask), "payload_bytes"].sum())
    late_bytes = float(merged_dataframe.loc[sent_mask & late_mask, "payload_bytes"].sum())
    dropped_bytes = float(merged_dataframe.loc[dropped_mask, "payload_bytes"].sum())
    wasted_late_bytes_ratio = float(late_bytes / sent_bytes) if sent_bytes else 0.0
    on_time_goodput_ratio = float(on_time_bytes / sent_bytes) if sent_bytes else 0.0
    dropped_keyframe_count = int(
        (dropped_mask & (merged_dataframe["key_frame"].astype(int) == 1)).sum()
    )

    reliable_single_mask = action_names == "RELIABLE_SINGLE"
    unreliable_mask = action_names == "UNRELIABLE"
    drop_mask = action_names == "DROP"

    received_late_dataframe = merged_dataframe[
        merged_dataframe["receive_time_ms_from_start"].notna() & (~merged_dataframe["on_time"])
    ]
    mean_deadline_miss_ms_on_late = (
        float(received_late_dataframe["deadline_miss_ms"].mean())
        if not received_late_dataframe.empty
        else 0.0
    )
    max_deadline_miss_ms = (
        float(received_late_dataframe["deadline_miss_ms"].max())
        if not received_late_dataframe.empty
        else 0.0
    )

    frame_metric_records = merged_dataframe[
        ["frame_index", "frame_type", "key_frame", "gop_id", "payload_bytes", "on_time"]
    ].to_dict("records")
    video_metrics = compute_all_video_metrics(frame_metric_records)

    return ExperimentSummary(
        video_name=experiment_config.video_name,
        policy_name=experiment_config.policy_name,
        bandwidth_mbps=float(experiment_config.bandwidth_mbps),
        round_trip_time_ms=float(experiment_config.round_trip_time_ms),
        loss_rate=float(experiment_config.loss_rate),
        repeat_index=int(experiment_config.repeat_index),
        frame_count=frame_count,
        late_frame_count=late_frame_count,
        late_frame_ratio=late_frame_ratio,
        late_frame_fraction=f"{late_frame_count}/{frame_count}",
        late_frames_per_1000=late_frames_per_1000,
        dropped_frame_count=dropped_frame_count,
        mean_deadline_miss_ms_on_late=mean_deadline_miss_ms_on_late,
        max_deadline_miss_ms=max_deadline_miss_ms,
        useful_goodput_bytes=float(video_metrics["useful_goodput_bytes"]),
        keyframe_late_ratio=float(video_metrics["keyframe_late_ratio"]),
        decodable_gop_ratio=float(video_metrics["decodable_gop_ratio"]),
        sent_bytes=sent_bytes,
        on_time_bytes=on_time_bytes,
        late_bytes=late_bytes,
        dropped_bytes=dropped_bytes,
        wasted_late_bytes_ratio=wasted_late_bytes_ratio,
        on_time_goodput_ratio=on_time_goodput_ratio,
        dropped_keyframe_count=dropped_keyframe_count,
        reliable_single_count=int(reliable_single_mask.sum()),
        unreliable_count=int(unreliable_mask.sum()),
        drop_count=int(drop_mask.sum()),
        reliable_single_late_count=int((reliable_single_mask & late_mask).sum()),
        unreliable_late_count=int((unreliable_mask & late_mask).sum()),
    )


def aggregate_experiment_summaries(
    experiment_summaries: Iterable[ExperimentSummary],
    *,
    repeat_index: int = -1,
) -> ExperimentSummary:
    summary_list = list(experiment_summaries)
    if not summary_list:
        raise RuntimeError("Cannot aggregate an empty summary list.")

    first_summary = summary_list[0]
    frame_count = sum(summary.frame_count for summary in summary_list)
    late_frame_count = sum(summary.late_frame_count for summary in summary_list)
    dropped_frame_count = sum(summary.dropped_frame_count for summary in summary_list)
    late_frame_ratio = float(late_frame_count / frame_count) if frame_count else 0.0
    sent_bytes = float(sum(summary.sent_bytes for summary in summary_list))
    on_time_bytes = float(sum(summary.on_time_bytes for summary in summary_list))
    late_bytes = float(sum(summary.late_bytes for summary in summary_list))
    dropped_bytes = float(sum(summary.dropped_bytes for summary in summary_list))
    wasted_late_bytes_ratio = float(late_bytes / sent_bytes) if sent_bytes else 0.0
    on_time_goodput_ratio = float(on_time_bytes / sent_bytes) if sent_bytes else 0.0

    return ExperimentSummary(
        video_name=first_summary.video_name,
        policy_name=first_summary.policy_name,
        bandwidth_mbps=first_summary.bandwidth_mbps,
        round_trip_time_ms=first_summary.round_trip_time_ms,
        loss_rate=first_summary.loss_rate,
        repeat_index=repeat_index,
        frame_count=frame_count,
        late_frame_count=late_frame_count,
        late_frame_ratio=late_frame_ratio,
        late_frame_fraction=f"{late_frame_count}/{frame_count}",
        late_frames_per_1000=float(late_frame_ratio * 1000.0),
        dropped_frame_count=dropped_frame_count,
        mean_deadline_miss_ms_on_late=float(
            sum(summary.mean_deadline_miss_ms_on_late for summary in summary_list) / len(summary_list)
        ),
        max_deadline_miss_ms=float(max(summary.max_deadline_miss_ms for summary in summary_list)),
        useful_goodput_bytes=float(sum(summary.useful_goodput_bytes for summary in summary_list)),
        keyframe_late_ratio=float(
            sum(summary.keyframe_late_ratio for summary in summary_list) / len(summary_list)
        ),
        decodable_gop_ratio=float(
            sum(summary.decodable_gop_ratio for summary in summary_list) / len(summary_list)
        ),
        sent_bytes=sent_bytes,
        on_time_bytes=on_time_bytes,
        late_bytes=late_bytes,
        dropped_bytes=dropped_bytes,
        wasted_late_bytes_ratio=wasted_late_bytes_ratio,
        on_time_goodput_ratio=on_time_goodput_ratio,
        dropped_keyframe_count=sum(summary.dropped_keyframe_count for summary in summary_list),
        reliable_single_count=sum(summary.reliable_single_count for summary in summary_list),
        unreliable_count=sum(summary.unreliable_count for summary in summary_list),
        drop_count=sum(summary.drop_count for summary in summary_list),
        reliable_single_late_count=sum(
            summary.reliable_single_late_count for summary in summary_list
        ),
        unreliable_late_count=sum(summary.unreliable_late_count for summary in summary_list),
    )


def write_experiment_summaries(summaries: Sequence[ExperimentSummary], output_path: Path) -> None:
    rows = [asdict(summary) for summary in summaries]
    fieldnames = list(ExperimentSummary.__dataclass_fields__.keys())
    _write_rows(rows, output_path, fieldnames)
