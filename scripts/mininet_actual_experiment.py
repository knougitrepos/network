from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import shlex
import shutil
import subprocess
import time
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.mininet_actual_experiment import (
    ExperimentConfig,
    aggregate_experiment_summaries,
    build_experiment_summary,
    write_experiment_summaries,
)
from core.video_assets import require_pyav


logger = logging.getLogger(__name__)

MOVIE_VIDEO_NAMES = (
    "archive_popeye_512kb",
    "echo_mediaelement",
    "w3c_movie_300",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an actual single-path Mininet experiment from a real video file.")
    parser.add_argument("--video-name", choices=MOVIE_VIDEO_NAMES, required=True)
    parser.add_argument(
        "--policy-name",
        choices=("heuristic_frame_aware", "frame_action_single_path"),
        required=True,
    )
    parser.add_argument("--bandwidth-mbps", type=float, required=True)
    parser.add_argument("--round-trip-time-ms", type=float, default=10.0)
    parser.add_argument("--loss-rate", type=float, default=0.0)
    parser.add_argument("--playback-buffer-ms", type=float, default=50.0)
    parser.add_argument("--repeat-count", type=int, default=3)
    parser.add_argument("--output-dir", default="output/mininet_actual_experiment")
    parser.add_argument("--python-executable", default="python3")
    parser.add_argument("--base-tcp-port", type=int, default=5001)
    parser.add_argument("--base-udp-port", type=int, default=6001)
    parser.add_argument("--idle-timeout-seconds", type=float, default=2.0)
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def ensure_command_available(command_name: str) -> None:
    if shutil.which(command_name) is None:
        raise RuntimeError(f"Required command is missing from PATH: {command_name}")


def ensure_wsl2_environment() -> None:
    if platform.system() != "Linux":
        raise RuntimeError("This experiment runner must be executed inside WSL2 Ubuntu.")

    kernel_release = platform.release().lower()
    proc_version_path = Path("/proc/version")
    proc_version = proc_version_path.read_text(encoding="utf-8", errors="ignore").lower()
    if "microsoft" not in kernel_release and "microsoft" not in proc_version and "wsl" not in proc_version:
        raise RuntimeError("This runner is restricted to WSL2 Ubuntu.")


def ensure_root_privileges() -> None:
    if os.geteuid() != 0:
        raise RuntimeError("Run this script with sudo inside WSL2 Ubuntu.")


def ensure_actual_experiment_dependencies(python_executable: str) -> None:
    ensure_wsl2_environment()
    ensure_root_privileges()
    ensure_command_available(python_executable)
    ensure_command_available("ffprobe")
    ensure_command_available("mn")
    require_pyav()


def build_output_directory(args: argparse.Namespace) -> Path:
    return (
        Path(args.output_dir).resolve()
        / args.video_name
        / args.policy_name
        / f"{int(args.bandwidth_mbps)}mbps"
    )


def build_video_path(repo_root: Path, video_name: str) -> Path:
    video_path = repo_root / "dataset" / "videos" / f"{video_name}.mp4"
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    return video_path


def build_mininet_network(
    *,
    bandwidth_mbps: float,
    round_trip_time_ms: float,
    loss_rate: float,
):
    try:
        from mininet.link import TCLink
        from mininet.net import Mininet
        from mininet.node import OVSBridge
        from mininet.topo import Topo
    except ImportError as exc:  # pragma: no cover - only exercised in WSL2 Mininet env
        raise RuntimeError("Mininet Python package is not available in this environment.") from exc

    one_way_delay_ms = float(round_trip_time_ms) / 2.0

    class SingleBottleneckTopo(Topo):
        def build(self) -> None:  # type: ignore[override]
            client_host = self.addHost("h1")
            server_host = self.addHost("h2")
            switch = self.addSwitch("s1", cls=OVSBridge)
            link_options = {
                "bw": float(bandwidth_mbps),
                "delay": f"{one_way_delay_ms}ms",
                "loss": float(loss_rate),
            }
            self.addLink(client_host, switch, cls=TCLink, **link_options)
            self.addLink(server_host, switch, cls=TCLink, **link_options)

    network = Mininet(topo=SingleBottleneckTopo(), controller=None, switch=OVSBridge, autoSetMacs=True)
    network.start()
    return network


def run_host_command(host, command_parts: list[str], log_path: Path):
    quoted_command = " ".join(shlex.quote(part) for part in command_parts)
    full_command = f"{quoted_command} > {shlex.quote(str(log_path))} 2>&1"
    return host.popen(full_command, shell=True)


def wait_for_process(process, *, timeout_seconds: float, description: str, log_path: Path) -> None:
    try:
        exit_code = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        raise RuntimeError(f"{description} timed out. See log: {log_path}") from exc

    if exit_code != 0:
        raise RuntimeError(f"{description} failed with exit code {exit_code}. See log: {log_path}")


def run_single_repeat(
    *,
    experiment_config: ExperimentConfig,
    tcp_port: int,
    udp_port: int,
    idle_timeout_seconds: float,
) -> object:
    repo_root = Path(__file__).resolve().parents[1]
    repeat_output_directory = experiment_config.output_directory / f"repeat_{experiment_config.repeat_index:02d}"
    repeat_output_directory.mkdir(parents=True, exist_ok=True)

    client_event_csv_path = repeat_output_directory / "client_events.csv"
    server_event_csv_path = repeat_output_directory / "server_events.csv"
    repeat_summary_csv_path = repeat_output_directory / "summary.csv"
    stop_flag_path = repeat_output_directory / "client_finished.flag"
    server_log_path = repeat_output_directory / "server.log"
    client_log_path = repeat_output_directory / "client.log"

    if stop_flag_path.exists():
        stop_flag_path.unlink()

    network = build_mininet_network(
        bandwidth_mbps=experiment_config.bandwidth_mbps,
        round_trip_time_ms=experiment_config.round_trip_time_ms,
        loss_rate=experiment_config.loss_rate,
    )
    try:
        client_host = network.get("h1")
        server_host = network.get("h2")
        server_ip_address = server_host.IP()

        server_process = run_host_command(
            server_host,
            [
                experiment_config.python_executable,
                str(repo_root / "scripts" / "mininet_frame_endpoint.py"),
                "server",
                "--tcp-port",
                str(tcp_port),
                "--udp-port",
                str(udp_port),
                "--output-csv",
                str(server_event_csv_path),
                "--stop-flag-path",
                str(stop_flag_path),
                "--idle-timeout-seconds",
                str(idle_timeout_seconds),
            ],
            server_log_path,
        )
        time.sleep(1.0)

        client_process = run_host_command(
            client_host,
            [
                experiment_config.python_executable,
                str(repo_root / "scripts" / "mininet_frame_endpoint.py"),
                "client",
                "--video-path",
                str(experiment_config.video_path),
                "--video-name",
                experiment_config.video_name,
                "--policy-name",
                experiment_config.policy_name,
                "--server-host",
                server_ip_address,
                "--tcp-port",
                str(tcp_port),
                "--udp-port",
                str(udp_port),
                "--bandwidth-mbps",
                str(experiment_config.bandwidth_mbps),
                "--round-trip-time-ms",
                str(experiment_config.round_trip_time_ms),
                "--loss-rate",
                str(experiment_config.loss_rate),
                "--playback-buffer-ms",
                str(experiment_config.playback_buffer_ms),
                "--output-csv",
                str(client_event_csv_path),
                "--stop-flag-path",
                str(stop_flag_path),
            ],
            client_log_path,
        )

        wait_for_process(
            client_process,
            timeout_seconds=1800.0,
            description="Mininet client process",
            log_path=client_log_path,
        )
        wait_for_process(
            server_process,
            timeout_seconds=60.0,
            description="Mininet server process",
            log_path=server_log_path,
        )

        summary = build_experiment_summary(
            experiment_config=experiment_config,
            client_event_source=client_event_csv_path,
            server_event_source=server_event_csv_path,
        )
        write_experiment_summaries([summary], repeat_summary_csv_path)
        return summary
    finally:
        network.stop()


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    ensure_actual_experiment_dependencies(args.python_executable)

    repo_root = Path(__file__).resolve().parents[1]
    output_directory = build_output_directory(args)
    output_directory.mkdir(parents=True, exist_ok=True)

    experiment_summaries = []
    for repeat_index in range(1, int(args.repeat_count) + 1):
        experiment_config = ExperimentConfig(
            video_name=args.video_name,
            video_path=build_video_path(repo_root, args.video_name),
            policy_name=args.policy_name,
            python_executable=args.python_executable,
            bandwidth_mbps=float(args.bandwidth_mbps),
            round_trip_time_ms=float(args.round_trip_time_ms),
            loss_rate=float(args.loss_rate),
            playback_buffer_ms=float(args.playback_buffer_ms),
            repeat_index=repeat_index,
            output_directory=output_directory,
        )
        logger.info(
            "Starting repeat %s/%s for video=%s policy=%s bandwidth=%s Mbps",
            repeat_index,
            args.repeat_count,
            args.video_name,
            args.policy_name,
            args.bandwidth_mbps,
        )
        summary = run_single_repeat(
            experiment_config=experiment_config,
            tcp_port=int(args.base_tcp_port) + repeat_index - 1,
            udp_port=int(args.base_udp_port) + repeat_index - 1,
            idle_timeout_seconds=float(args.idle_timeout_seconds),
        )
        experiment_summaries.append(summary)

    write_experiment_summaries(
        experiment_summaries,
        output_directory / "by_repeat_summary.csv",
    )
    aggregated_summary = aggregate_experiment_summaries(experiment_summaries, repeat_index=-1)
    write_experiment_summaries(
        [aggregated_summary],
        output_directory / "summary.csv",
    )

    print(
        json.dumps(
            {
                "video_name": args.video_name,
                "policy_name": args.policy_name,
                "bandwidth_mbps": args.bandwidth_mbps,
                "repeat_count": args.repeat_count,
                "output_directory": str(output_directory),
                "summary_csv": str((output_directory / "summary.csv").resolve()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
