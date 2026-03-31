"""실환경(Wi-Fi + LTE/5G) 측정 하네스.

timestamp 동기화, 전송 로그, 재생 로그, 네트워크 로그를 통합 수집한다.

구성:
    - RealworldLogger: 통합 로그 수집기
    - TimestampSync: NTP 기반 시간 동기화
    - NetworkMonitor: 네트워크 상태 모니터링
    - PlaybackLogger: 재생 버퍼 이벤트 로깅

사용 예시:
    from scripts.realworld_harness import RealworldExperiment
    
    exp = RealworldExperiment(
        output_dir="output/realworld",
        server_url="http://server:8080",
    )
    exp.run(video_path="data/videos/test.mp4", duration_seconds=60)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


logger = logging.getLogger(__name__)


# NTP 서버 목록
NTP_SERVERS = [
    "time.google.com",
    "time.cloudflare.com",
    "pool.ntp.org",
    "time.windows.com",
]


@dataclass
class TimestampedEvent:
    """타임스탬프가 포함된 이벤트."""
    timestamp_utc: datetime
    timestamp_local: datetime
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "timestamp_local": self.timestamp_local.isoformat(),
            "event_type": self.event_type,
            **self.data,
        }


class TimestampSync:
    """NTP 기반 시간 동기화.
    
    클라이언트-서버 간 시간 동기화를 위한 오프셋 계산.
    """
    
    def __init__(self, ntp_servers: Optional[List[str]] = None) -> None:
        self.ntp_servers = ntp_servers or NTP_SERVERS
        self.offset_ms: float = 0.0
        self.last_sync: Optional[datetime] = None
        self._lock = threading.Lock()
    
    def sync(self) -> bool:
        """NTP 서버와 동기화하여 오프셋 계산.
        
        Returns:
            bool: 동기화 성공 여부
        """
        try:
            import ntplib
            client = ntplib.NTPClient()
            
            for server in self.ntp_servers:
                try:
                    response = client.request(server, version=3, timeout=5)
                    with self._lock:
                        self.offset_ms = response.offset * 1000.0
                        self.last_sync = datetime.now(timezone.utc)
                    logger.info(
                        "NTP 동기화 성공: server=%s, offset=%.3f ms",
                        server, self.offset_ms
                    )
                    return True
                except Exception as e:
                    logger.debug("NTP 서버 %s 실패: %s", server, e)
                    continue
            
            logger.warning("모든 NTP 서버 동기화 실패")
            return False
            
        except ImportError:
            logger.warning("ntplib가 설치되지 않았습니다. pip install ntplib")
            return False
    
    def get_synced_time(self) -> datetime:
        """동기화된 현재 시간 반환."""
        now = datetime.now(timezone.utc)
        with self._lock:
            offset_seconds = self.offset_ms / 1000.0
        # 오프셋을 적용한 시간 반환
        from datetime import timedelta
        return now + timedelta(seconds=offset_seconds)
    
    def get_offset_ms(self) -> float:
        """현재 오프셋 반환 (ms)."""
        with self._lock:
            return self.offset_ms


class NetworkMonitor:
    """네트워크 상태 모니터링.
    
    RTT, 패킷 손실, 대역폭을 주기적으로 측정한다.
    """
    
    def __init__(
        self,
        target_host: str,
        interval_seconds: float = 1.0,
    ) -> None:
        self.target_host = target_host
        self.interval_seconds = interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._measurements: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
    
    def start(self) -> None:
        """모니터링 시작."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("네트워크 모니터링 시작: target=%s", self.target_host)
    
    def stop(self) -> None:
        """모니터링 중지."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("네트워크 모니터링 중지")
    
    def _monitor_loop(self) -> None:
        """모니터링 루프."""
        while self._running:
            try:
                measurement = self._measure()
                with self._lock:
                    self._measurements.append(measurement)
            except Exception as e:
                logger.debug("측정 실패: %s", e)
            time.sleep(self.interval_seconds)
    
    def _measure(self) -> Dict[str, Any]:
        """단일 측정 수행."""
        timestamp = datetime.now(timezone.utc)
        result = {
            "timestamp": timestamp.isoformat(),
            "target": self.target_host,
            "rtt_ms": None,
            "packet_loss": None,
            "interface": None,
            "rx_bytes": None,
            "tx_bytes": None,
        }
        
        # Ping RTT 측정
        rtt = self._ping()
        if rtt is not None:
            result["rtt_ms"] = rtt
        
        # 인터페이스 통계 (Linux)
        if platform.system() == "Linux":
            stats = self._get_interface_stats()
            result.update(stats)
        
        return result
    
    def _ping(self, count: int = 1, timeout: float = 1.0) -> Optional[float]:
        """Ping으로 RTT 측정."""
        system = platform.system()
        if system == "Windows":
            cmd = ["ping", "-n", str(count), "-w", str(int(timeout * 1000)), self.target_host]
        else:
            cmd = ["ping", "-c", str(count), "-W", str(int(timeout)), self.target_host]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            output = result.stdout
            
            # RTT 파싱
            if system == "Windows":
                # "평균 = 10ms" 또는 "Average = 10ms"
                for line in output.split("\n"):
                    if "=" in line and "ms" in line.lower():
                        try:
                            parts = line.split("=")
                            for part in parts:
                                if "ms" in part.lower():
                                    rtt_str = part.strip().replace("ms", "").strip()
                                    return float(rtt_str)
                        except ValueError:
                            pass
            else:
                # "time=10.5 ms"
                for line in output.split("\n"):
                    if "time=" in line:
                        try:
                            time_part = line.split("time=")[1].split()[0]
                            return float(time_part)
                        except (IndexError, ValueError):
                            pass
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
        
        return None
    
    def _get_interface_stats(self) -> Dict[str, Any]:
        """Linux 네트워크 인터페이스 통계."""
        result = {}
        
        try:
            # 기본 인터페이스 찾기
            with open("/proc/net/route") as f:
                for line in f:
                    fields = line.strip().split()
                    if len(fields) >= 2 and fields[1] == "00000000":
                        interface = fields[0]
                        result["interface"] = interface
                        break
            
            if "interface" in result:
                interface = result["interface"]
                # RX/TX 바이트
                rx_path = f"/sys/class/net/{interface}/statistics/rx_bytes"
                tx_path = f"/sys/class/net/{interface}/statistics/tx_bytes"
                
                if os.path.exists(rx_path):
                    with open(rx_path) as f:
                        result["rx_bytes"] = int(f.read().strip())
                if os.path.exists(tx_path):
                    with open(tx_path) as f:
                        result["tx_bytes"] = int(f.read().strip())
        except Exception as e:
            logger.debug("인터페이스 통계 읽기 실패: %s", e)
        
        return result
    
    def get_measurements(self) -> List[Dict[str, Any]]:
        """수집된 측정값 반환."""
        with self._lock:
            return list(self._measurements)
    
    def get_summary(self) -> Dict[str, float]:
        """측정값 요약 통계."""
        with self._lock:
            measurements = list(self._measurements)
        
        if not measurements:
            return {}
        
        rtt_values = [m["rtt_ms"] for m in measurements if m["rtt_ms"] is not None]
        
        return {
            "rtt_min_ms": min(rtt_values) if rtt_values else 0.0,
            "rtt_avg_ms": np.mean(rtt_values) if rtt_values else 0.0,
            "rtt_max_ms": max(rtt_values) if rtt_values else 0.0,
            "rtt_std_ms": np.std(rtt_values) if rtt_values else 0.0,
            "measurement_count": len(measurements),
            "rtt_count": len(rtt_values),
        }


@dataclass
class PlaybackEvent:
    """재생 이벤트."""
    timestamp: datetime
    event_type: str  # "buffer_empty", "buffer_full", "stall_start", "stall_end", "frame_displayed", "frame_late"
    buffer_level_ms: float = 0.0
    frame_index: int = -1
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "buffer_level_ms": self.buffer_level_ms,
            "frame_index": self.frame_index,
            **self.extra,
        }


class PlaybackLogger:
    """재생 버퍼 이벤트 로거.
    
    비디오 재생 중 버퍼 상태와 스톨 이벤트를 기록한다.
    """
    
    def __init__(self) -> None:
        self.events: List[PlaybackEvent] = []
        self._lock = threading.Lock()
    
    def log_event(
        self,
        event_type: str,
        buffer_level_ms: float = 0.0,
        frame_index: int = -1,
        **extra: Any,
    ) -> None:
        """이벤트 기록."""
        event = PlaybackEvent(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            buffer_level_ms=buffer_level_ms,
            frame_index=frame_index,
            extra=extra,
        )
        with self._lock:
            self.events.append(event)
    
    def log_stall_start(self, buffer_level_ms: float = 0.0) -> None:
        """버퍼링 시작 (스톨)."""
        self.log_event("stall_start", buffer_level_ms=buffer_level_ms)
    
    def log_stall_end(self, buffer_level_ms: float, stall_duration_ms: float) -> None:
        """버퍼링 종료."""
        self.log_event("stall_end", buffer_level_ms=buffer_level_ms, stall_duration_ms=stall_duration_ms)
    
    def log_frame(self, frame_index: int, on_time: bool, buffer_level_ms: float) -> None:
        """프레임 표시 이벤트."""
        event_type = "frame_displayed" if on_time else "frame_late"
        self.log_event(event_type, buffer_level_ms=buffer_level_ms, frame_index=frame_index)
    
    def get_events(self) -> List[Dict[str, Any]]:
        """모든 이벤트 반환."""
        with self._lock:
            return [e.to_dict() for e in self.events]
    
    def get_summary(self) -> Dict[str, float]:
        """재생 품질 요약."""
        with self._lock:
            events = list(self.events)
        
        if not events:
            return {}
        
        stall_count = sum(1 for e in events if e.event_type == "stall_start")
        total_stall_duration_ms = sum(
            e.extra.get("stall_duration_ms", 0.0)
            for e in events if e.event_type == "stall_end"
        )
        
        frame_events = [e for e in events if e.event_type in ("frame_displayed", "frame_late")]
        late_count = sum(1 for e in events if e.event_type == "frame_late")
        
        return {
            "stall_count": stall_count,
            "total_stall_duration_ms": total_stall_duration_ms,
            "frame_count": len(frame_events),
            "late_frame_count": late_count,
            "late_frame_ratio": late_count / len(frame_events) if frame_events else 0.0,
        }


@dataclass
class TransmissionEvent:
    """전송 이벤트."""
    timestamp: datetime
    event_type: str  # "send", "ack", "loss", "retransmit"
    sequence_number: int
    payload_bytes: int
    frame_index: int = -1
    latency_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "sequence_number": self.sequence_number,
            "payload_bytes": self.payload_bytes,
            "frame_index": self.frame_index,
            "latency_ms": self.latency_ms,
        }


class TransmissionLogger:
    """전송 이벤트 로거.
    
    패킷 송신, ACK, 손실, 재전송 이벤트를 기록한다.
    """
    
    def __init__(self) -> None:
        self.events: List[TransmissionEvent] = []
        self._lock = threading.Lock()
        self._send_times: Dict[int, datetime] = {}
    
    def log_send(
        self,
        sequence_number: int,
        payload_bytes: int,
        frame_index: int = -1,
    ) -> None:
        """패킷 송신 이벤트."""
        timestamp = datetime.now(timezone.utc)
        self._send_times[sequence_number] = timestamp
        
        event = TransmissionEvent(
            timestamp=timestamp,
            event_type="send",
            sequence_number=sequence_number,
            payload_bytes=payload_bytes,
            frame_index=frame_index,
        )
        with self._lock:
            self.events.append(event)
    
    def log_ack(self, sequence_number: int) -> None:
        """ACK 수신 이벤트."""
        timestamp = datetime.now(timezone.utc)
        send_time = self._send_times.pop(sequence_number, None)
        latency_ms = (timestamp - send_time).total_seconds() * 1000 if send_time else 0.0
        
        event = TransmissionEvent(
            timestamp=timestamp,
            event_type="ack",
            sequence_number=sequence_number,
            payload_bytes=0,
            latency_ms=latency_ms,
        )
        with self._lock:
            self.events.append(event)
    
    def log_loss(self, sequence_number: int) -> None:
        """손실 감지 이벤트."""
        event = TransmissionEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="loss",
            sequence_number=sequence_number,
            payload_bytes=0,
        )
        with self._lock:
            self.events.append(event)
    
    def get_events(self) -> List[Dict[str, Any]]:
        """모든 이벤트 반환."""
        with self._lock:
            return [e.to_dict() for e in self.events]
    
    def get_summary(self) -> Dict[str, float]:
        """전송 통계 요약."""
        with self._lock:
            events = list(self.events)
        
        send_count = sum(1 for e in events if e.event_type == "send")
        ack_count = sum(1 for e in events if e.event_type == "ack")
        loss_count = sum(1 for e in events if e.event_type == "loss")
        
        ack_events = [e for e in events if e.event_type == "ack"]
        latencies = [e.latency_ms for e in ack_events if e.latency_ms > 0]
        
        total_bytes = sum(e.payload_bytes for e in events if e.event_type == "send")
        
        return {
            "send_count": send_count,
            "ack_count": ack_count,
            "loss_count": loss_count,
            "loss_ratio": loss_count / send_count if send_count else 0.0,
            "total_bytes": total_bytes,
            "avg_latency_ms": np.mean(latencies) if latencies else 0.0,
            "p95_latency_ms": np.percentile(latencies, 95) if latencies else 0.0,
        }


class RealworldExperiment:
    """실환경 실험 통합 관리자.
    
    네트워크 모니터링, 전송 로깅, 재생 로깅을 통합 관리한다.
    """
    
    def __init__(
        self,
        output_dir: Path,
        server_host: str = "localhost",
        sync_ntp: bool = True,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.server_host = server_host
        
        # 컴포넌트 초기화
        self.timestamp_sync = TimestampSync()
        self.network_monitor = NetworkMonitor(server_host)
        self.playback_logger = PlaybackLogger()
        self.transmission_logger = TransmissionLogger()
        
        # NTP 동기화
        if sync_ntp:
            self.timestamp_sync.sync()
        
        self.experiment_id: Optional[str] = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
    
    def start(self, experiment_id: Optional[str] = None) -> None:
        """실험 시작."""
        self.experiment_id = experiment_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.start_time = datetime.now(timezone.utc)
        
        # 네트워크 모니터링 시작
        self.network_monitor.start()
        
        logger.info("실험 시작: id=%s", self.experiment_id)
    
    def stop(self) -> None:
        """실험 종료 및 결과 저장."""
        self.end_time = datetime.now(timezone.utc)
        
        # 네트워크 모니터링 중지
        self.network_monitor.stop()
        
        # 결과 저장
        self._save_results()
        
        logger.info("실험 종료: id=%s", self.experiment_id)
    
    def _save_results(self) -> None:
        """모든 로그 저장."""
        exp_dir = self.output_dir / self.experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        
        # 메타데이터
        metadata = {
            "experiment_id": self.experiment_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "server_host": self.server_host,
            "ntp_offset_ms": self.timestamp_sync.get_offset_ms(),
            "platform": platform.platform(),
        }
        with (exp_dir / "metadata.json").open("w") as f:
            json.dump(metadata, f, indent=2)
        
        # 네트워크 측정
        network_df = pd.DataFrame(self.network_monitor.get_measurements())
        if not network_df.empty:
            network_df.to_csv(exp_dir / "network_measurements.csv", index=False)
        
        # 전송 이벤트
        transmission_df = pd.DataFrame(self.transmission_logger.get_events())
        if not transmission_df.empty:
            transmission_df.to_csv(exp_dir / "transmission_events.csv", index=False)
        
        # 재생 이벤트
        playback_df = pd.DataFrame(self.playback_logger.get_events())
        if not playback_df.empty:
            playback_df.to_csv(exp_dir / "playback_events.csv", index=False)
        
        # 요약 통계
        summary = {
            "network": self.network_monitor.get_summary(),
            "transmission": self.transmission_logger.get_summary(),
            "playback": self.playback_logger.get_summary(),
        }
        with (exp_dir / "summary.json").open("w") as f:
            json.dump(summary, f, indent=2)
        
        logger.info("결과 저장: %s", exp_dir)
    
    def get_summary(self) -> Dict[str, Any]:
        """실험 요약 반환."""
        return {
            "experiment_id": self.experiment_id,
            "network": self.network_monitor.get_summary(),
            "transmission": self.transmission_logger.get_summary(),
            "playback": self.playback_logger.get_summary(),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="실환경 측정 하네스 테스트")
    parser.add_argument("--server", default="8.8.8.8", help="대상 서버 호스트")
    parser.add_argument("--duration", type=float, default=30.0, help="측정 시간 (초)")
    parser.add_argument("--output", default="output/realworld", help="결과 저장 디렉토리")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    
    output_dir = Path(args.output)
    
    experiment = RealworldExperiment(
        output_dir=output_dir,
        server_host=args.server,
    )
    
    try:
        experiment.start()
        logger.info("측정 중... (%.1f초)", args.duration)
        time.sleep(args.duration)
    finally:
        experiment.stop()
    
    # 요약 출력
    summary = experiment.get_summary()
    print("\n=== 실험 요약 ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
