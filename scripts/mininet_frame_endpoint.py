from __future__ import annotations

import argparse
import logging
import selectors
import socket
import struct
import time
from pathlib import Path
import sys
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.mininet_actual_experiment import (
    ClientTransmissionEvent,
    ServerReceiveEvent,
    write_client_events,
    write_server_events,
)
from core.transport import TransportConfig
from core.video_assets import VideoFrameAsset, load_video_frame_assets
from policy.action import FrameAction, select_action
from policy.importance import HeuristicImportanceScorer, NetworkState
from policy.legacy import resolve_video_queue_policy


logger = logging.getLogger(__name__)

FRAME_HEADER = struct.Struct("!II")
TCP_PROTOCOL = "tcp"
UDP_PROTOCOL = "udp"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Actual frame sender/receiver used inside Mininet hosts.")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    server_parser = subparsers.add_parser("server", help="Run the Mininet frame receiver.")
    server_parser.add_argument("--host", default="0.0.0.0")
    server_parser.add_argument("--tcp-port", type=int, required=True)
    server_parser.add_argument("--udp-port", type=int, required=True)
    server_parser.add_argument("--output-csv", required=True)
    server_parser.add_argument("--stop-flag-path", required=True)
    server_parser.add_argument("--idle-timeout-seconds", type=float, default=2.0)

    client_parser = subparsers.add_parser("client", help="Run the Mininet frame sender.")
    client_parser.add_argument("--video-path", required=True)
    client_parser.add_argument("--video-name", required=True)
    client_parser.add_argument("--policy-name", required=True)
    client_parser.add_argument("--server-host", required=True)
    client_parser.add_argument("--tcp-port", type=int, required=True)
    client_parser.add_argument("--udp-port", type=int, required=True)
    client_parser.add_argument("--bandwidth-mbps", type=float, required=True)
    client_parser.add_argument("--round-trip-time-ms", type=float, required=True)
    client_parser.add_argument("--loss-rate", type=float, default=0.0)
    client_parser.add_argument("--playback-buffer-ms", type=float, default=50.0)
    client_parser.add_argument("--delayed-ack-ms", type=float, default=40.0)
    client_parser.add_argument("--output-csv", required=True)
    client_parser.add_argument("--stop-flag-path", required=True)

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


def sleep_until_ns(target_time_ns: int) -> None:
    remaining_ns = target_time_ns - time.monotonic_ns()
    if remaining_ns > 0:
        time.sleep(remaining_ns / 1_000_000_000.0)


def build_frame_packet(frame_asset: VideoFrameAsset) -> bytes:
    return FRAME_HEADER.pack(frame_asset.frame_index, frame_asset.payload_bytes) + frame_asset.payload


def send_frame_over_tcp(tcp_connection: socket.socket, frame_asset: VideoFrameAsset) -> int:
    packet_bytes = build_frame_packet(frame_asset)
    send_start_time_ns = time.monotonic_ns()
    tcp_connection.sendall(packet_bytes)
    return send_start_time_ns


def send_frame_over_udp(udp_socket: socket.socket, server_host: str, udp_port: int, frame_asset: VideoFrameAsset) -> int:
    packet_bytes = build_frame_packet(frame_asset)
    send_start_time_ns = time.monotonic_ns()
    udp_socket.sendto(packet_bytes, (server_host, udp_port))
    return send_start_time_ns


def build_client_event(
    *,
    experiment_start_time_ns: int,
    video_name: str,
    policy_name: str,
    frame_asset: VideoFrameAsset,
    selected_action_name: str,
    transport_protocol: str,
    send_start_time_ns: int,
    dropped_by_policy: bool,
) -> ClientTransmissionEvent:
    return ClientTransmissionEvent(
        experiment_start_time_ns=experiment_start_time_ns,
        video_name=video_name,
        policy_name=policy_name,
        frame_index=frame_asset.frame_index,
        frame_type=frame_asset.frame_type,
        key_frame=frame_asset.key_frame,
        gop_id=frame_asset.gop_id,
        payload_bytes=frame_asset.payload_bytes,
        frame_pts_ms=frame_asset.pts_ms,
        display_deadline_ms=frame_asset.display_deadline_ms,
        selected_action_name=selected_action_name,
        transport_protocol=transport_protocol,
        send_start_time_ns=send_start_time_ns,
        dropped_by_policy=dropped_by_policy,
    )


def build_network_state(
    *,
    round_trip_time_ms: float,
    bandwidth_mbps: float,
    loss_rate: float,
    queued_payload_bytes: int,
) -> NetworkState:
    return NetworkState(
        rtt_ms=float(round_trip_time_ms),
        bandwidth_mbps=float(bandwidth_mbps),
        loss_rate=float(loss_rate),
        buffer_level_ms=0.0,
        queue_bytes=int(queued_payload_bytes),
        estimated_batch_gain=0.0,
    )


def compute_frame_interval_ms(frame_assets: Iterable[VideoFrameAsset]) -> float:
    duration_values_ms = [frame_asset.duration_ms for frame_asset in frame_assets if frame_asset.duration_ms > 0]
    if not duration_values_ms:
        return 0.0
    sorted_values = sorted(duration_values_ms)
    return float(sorted_values[len(sorted_values) // 2])


def flush_heuristic_queue(
    *,
    queued_frame_assets: list[VideoFrameAsset],
    client_events: list[ClientTransmissionEvent],
    tcp_connection: socket.socket,
    experiment_start_time_ns: int,
    video_name: str,
    policy_name: str,
) -> None:
    for queued_frame_asset in queued_frame_assets:
        send_start_time_ns = send_frame_over_tcp(tcp_connection, queued_frame_asset)
        client_events.append(
            build_client_event(
                experiment_start_time_ns=experiment_start_time_ns,
                video_name=video_name,
                policy_name=policy_name,
                frame_asset=queued_frame_asset,
                selected_action_name="HEURISTIC_TCP_BATCH",
                transport_protocol=TCP_PROTOCOL,
                send_start_time_ns=send_start_time_ns,
                dropped_by_policy=False,
            )
        )


def run_heuristic_frame_aware_client(args: argparse.Namespace, frame_assets: list[VideoFrameAsset]) -> list[ClientTransmissionEvent]:
    transport_config = TransportConfig(
        rtt_ms=float(args.round_trip_time_ms),
        bandwidth_mbps=float(args.bandwidth_mbps),
        delayed_ack_ms=float(args.delayed_ack_ms),
    )
    frame_interval_ms = compute_frame_interval_ms(frame_assets)
    client_events: list[ClientTransmissionEvent] = []
    queued_frame_assets: list[VideoFrameAsset] = []
    queued_frame_rows: list[dict[str, object]] = []
    queued_payload_bytes = 0
    first_queued_arrival_ms: float | None = None

    with socket.create_connection((args.server_host, args.tcp_port)) as tcp_connection:
        tcp_connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        experiment_start_time_ns = time.monotonic_ns()

        for frame_asset in frame_assets:
            scheduled_send_time_ns = experiment_start_time_ns + int(frame_asset.pts_ms * 1_000_000.0)
            sleep_until_ns(scheduled_send_time_ns)

            queued_frame_assets.append(frame_asset)
            queued_frame_rows.append(
                {
                    "display_deadline_ms": frame_asset.display_deadline_ms,
                    "key_frame": frame_asset.key_frame,
                    "frame_type": frame_asset.frame_type,
                }
            )
            queued_payload_bytes += frame_asset.payload_bytes
            current_time_ms = (time.monotonic_ns() - experiment_start_time_ns) / 1_000_000.0
            if first_queued_arrival_ms is None:
                first_queued_arrival_ms = current_time_ms

            batch_bytes, flush_interval_ms, immediate_flush = resolve_video_queue_policy(
                queue_rows=queued_frame_rows,
                playback_buffer_ms=float(args.playback_buffer_ms),
                transport_cfg=transport_config,
                frame_interval_ms=frame_interval_ms,
                now_ms=current_time_ms,
            )
            queue_age_ms = current_time_ms - first_queued_arrival_ms
            flush_due_to_size = queued_payload_bytes >= batch_bytes
            flush_due_to_time = flush_interval_ms >= 0.0 and queue_age_ms >= flush_interval_ms

            if immediate_flush or flush_due_to_size or flush_due_to_time:
                flush_heuristic_queue(
                    queued_frame_assets=queued_frame_assets,
                    client_events=client_events,
                    tcp_connection=tcp_connection,
                    experiment_start_time_ns=experiment_start_time_ns,
                    video_name=args.video_name,
                    policy_name=args.policy_name,
                )
                queued_frame_assets = []
                queued_frame_rows = []
                queued_payload_bytes = 0
                first_queued_arrival_ms = None

        if queued_frame_assets:
            flush_heuristic_queue(
                queued_frame_assets=queued_frame_assets,
                client_events=client_events,
                tcp_connection=tcp_connection,
                experiment_start_time_ns=experiment_start_time_ns,
                video_name=args.video_name,
                policy_name=args.policy_name,
            )

    return client_events


def run_frame_action_single_path_client(
    args: argparse.Namespace,
    frame_assets: list[VideoFrameAsset],
) -> list[ClientTransmissionEvent]:
    scorer = HeuristicImportanceScorer(playback_buffer_ms=float(args.playback_buffer_ms))
    client_events: list[ClientTransmissionEvent] = []

    with socket.create_connection((args.server_host, args.tcp_port)) as tcp_connection:
        tcp_connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            experiment_start_time_ns = time.monotonic_ns()

            for frame_asset in frame_assets:
                scheduled_send_time_ns = experiment_start_time_ns + int(frame_asset.pts_ms * 1_000_000.0)
                sleep_until_ns(scheduled_send_time_ns)

                current_time_ms = (time.monotonic_ns() - experiment_start_time_ns) / 1_000_000.0
                network_state = build_network_state(
                    round_trip_time_ms=float(args.round_trip_time_ms),
                    bandwidth_mbps=float(args.bandwidth_mbps),
                    loss_rate=float(args.loss_rate),
                    queued_payload_bytes=0,
                )
                frame_record = {
                    "frame_type": frame_asset.frame_type,
                    "payload_bytes": frame_asset.payload_bytes,
                    "display_deadline_ms": frame_asset.display_deadline_ms,
                    "event_time_ms": current_time_ms,
                    "key_frame": frame_asset.key_frame,
                }
                importance_score = scorer.score(frame_record, network_state)
                deadline_slack_ms = frame_asset.display_deadline_ms - current_time_ms
                selected_action = select_action(
                    importance_score=importance_score,
                    deadline_slack_ms=deadline_slack_ms,
                    network=network_state,
                    available_paths=1,
                    queue_bytes=0,
                    estimated_batch_gain=0.0,
                )

                if selected_action == FrameAction.RELIABLE_SINGLE:
                    send_start_time_ns = send_frame_over_tcp(tcp_connection, frame_asset)
                    client_events.append(
                        build_client_event(
                            experiment_start_time_ns=experiment_start_time_ns,
                            video_name=args.video_name,
                            policy_name=args.policy_name,
                            frame_asset=frame_asset,
                            selected_action_name=selected_action.name,
                            transport_protocol=TCP_PROTOCOL,
                            send_start_time_ns=send_start_time_ns,
                            dropped_by_policy=False,
                        )
                    )
                    continue

                if selected_action == FrameAction.UNRELIABLE:
                    send_start_time_ns = send_frame_over_udp(
                        udp_socket=udp_socket,
                        server_host=args.server_host,
                        udp_port=int(args.udp_port),
                        frame_asset=frame_asset,
                    )
                    client_events.append(
                        build_client_event(
                            experiment_start_time_ns=experiment_start_time_ns,
                            video_name=args.video_name,
                            policy_name=args.policy_name,
                            frame_asset=frame_asset,
                            selected_action_name=selected_action.name,
                            transport_protocol=UDP_PROTOCOL,
                            send_start_time_ns=send_start_time_ns,
                            dropped_by_policy=False,
                        )
                    )
                    continue

                if selected_action == FrameAction.DROP:
                    client_events.append(
                        build_client_event(
                            experiment_start_time_ns=experiment_start_time_ns,
                            video_name=args.video_name,
                            policy_name=args.policy_name,
                            frame_asset=frame_asset,
                            selected_action_name=selected_action.name,
                            transport_protocol="drop",
                            send_start_time_ns=time.monotonic_ns(),
                            dropped_by_policy=True,
                        )
                    )
                    continue

                raise RuntimeError(
                    f"Single-path experiment produced unsupported action: {selected_action.name}"
                )

    return client_events


def run_client(args: argparse.Namespace) -> None:
    frame_assets = load_video_frame_assets(
        video_path=Path(args.video_path).resolve(),
        playback_buffer_ms=float(args.playback_buffer_ms),
    )

    if args.policy_name == "heuristic_frame_aware":
        client_events = run_heuristic_frame_aware_client(args, frame_assets)
    elif args.policy_name == "frame_action_single_path":
        client_events = run_frame_action_single_path_client(args, frame_assets)
    else:
        raise ValueError(f"Unsupported policy: {args.policy_name}")

    write_client_events(client_events, Path(args.output_csv))
    Path(args.stop_flag_path).resolve().parent.mkdir(parents=True, exist_ok=True)
    Path(args.stop_flag_path).resolve().touch()
    logger.info("Client completed: policy=%s frames=%s", args.policy_name, len(client_events))


def run_server(args: argparse.Namespace) -> None:
    selector = selectors.DefaultSelector()
    server_events: list[ServerReceiveEvent] = []
    stop_flag_path = Path(args.stop_flag_path).resolve()
    stop_flag_path.parent.mkdir(parents=True, exist_ok=True)
    tcp_buffers: dict[socket.socket, bytearray] = {}
    last_receive_time_monotonic = time.monotonic()

    tcp_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        tcp_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_listener.bind((args.host, args.tcp_port))
        tcp_listener.listen(1)
        tcp_listener.setblocking(False)
        selector.register(tcp_listener, selectors.EVENT_READ, data="tcp_listener")

        udp_socket.bind((args.host, args.udp_port))
        udp_socket.setblocking(False)
        selector.register(udp_socket, selectors.EVENT_READ, data="udp_socket")

        while True:
            if stop_flag_path.exists() and (time.monotonic() - last_receive_time_monotonic) >= float(args.idle_timeout_seconds):
                break

            for key, _ in selector.select(timeout=0.25):
                socket_object = key.fileobj
                socket_role = key.data

                if socket_role == "tcp_listener":
                    tcp_connection, _ = tcp_listener.accept()
                    tcp_connection.setblocking(False)
                    tcp_buffers[tcp_connection] = bytearray()
                    selector.register(tcp_connection, selectors.EVENT_READ, data="tcp_connection")
                    continue

                if socket_role == "udp_socket":
                    packet_bytes, _ = udp_socket.recvfrom(2_097_152)
                    if len(packet_bytes) < FRAME_HEADER.size:
                        raise RuntimeError("Received truncated UDP packet.")
                    frame_index, payload_bytes = FRAME_HEADER.unpack(packet_bytes[: FRAME_HEADER.size])
                    payload = packet_bytes[FRAME_HEADER.size :]
                    if len(payload) != payload_bytes:
                        raise RuntimeError("UDP payload size mismatch.")
                    server_events.append(
                        ServerReceiveEvent(
                            frame_index=frame_index,
                            transport_protocol=UDP_PROTOCOL,
                            receive_time_ns=time.monotonic_ns(),
                            payload_bytes=payload_bytes,
                        )
                    )
                    last_receive_time_monotonic = time.monotonic()
                    continue

                if socket_role == "tcp_connection":
                    assert isinstance(socket_object, socket.socket)
                    chunk_bytes = socket_object.recv(2_097_152)
                    if not chunk_bytes:
                        selector.unregister(socket_object)
                        socket_object.close()
                        tcp_buffers.pop(socket_object, None)
                        continue

                    tcp_buffers[socket_object].extend(chunk_bytes)
                    buffer_bytes = tcp_buffers[socket_object]
                    while len(buffer_bytes) >= FRAME_HEADER.size:
                        frame_index, payload_bytes = FRAME_HEADER.unpack(buffer_bytes[: FRAME_HEADER.size])
                        expected_message_size = FRAME_HEADER.size + payload_bytes
                        if len(buffer_bytes) < expected_message_size:
                            break
                        del buffer_bytes[:expected_message_size]
                        server_events.append(
                            ServerReceiveEvent(
                                frame_index=frame_index,
                                transport_protocol=TCP_PROTOCOL,
                                receive_time_ns=time.monotonic_ns(),
                                payload_bytes=payload_bytes,
                            )
                        )
                        last_receive_time_monotonic = time.monotonic()

        write_server_events(server_events, Path(args.output_csv))
        logger.info("Server completed: received_frames=%s", len(server_events))
    finally:
        for registered_key in list(selector.get_map().values()):
            selector.unregister(registered_key.fileobj)
            registered_key.fileobj.close()
        selector.close()


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    if args.mode == "server":
        run_server(args)
        return
    run_client(args)


if __name__ == "__main__":
    main()
