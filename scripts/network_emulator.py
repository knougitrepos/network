"""Windows 호환 실제 네트워크 에뮬레이터.

asyncio 소켓 기반 실제 TCP/UDP 통신 + 지연/손실 시뮬레이션.
Mininet 없이도 Windows에서 실제 네트워크 조건을 테스트할 수 있다.

구성:
    - NetworkEmulator: 지연, 손실, 대역폭 제한을 적용하는 프록시 서버
    - EmulatedServer: 에뮬레이션이 적용된 서버
    - EmulatedClient: 에뮬레이션이 적용된 클라이언트
    - NetworkCondition: 네트워크 조건 설정

사용 예시:
    # 서버 실행
    python scripts/network_emulator.py server --port 8080 --profile wifi_congested

    # 클라이언트 실행
    python scripts/network_emulator.py client --server localhost:8080 --frames 100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import struct
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


logger = logging.getLogger(__name__)


@dataclass
class NetworkCondition:
    """네트워크 조건 설정.
    
    Attributes:
        name: 조건 이름
        bandwidth_mbps: 대역폭 (Mbps)
        rtt_ms: 왕복 지연 시간 (ms)
        loss_rate: 패킷 손실률 (0.0~1.0)
        jitter_ms: 지연 변동 (ms)
        queue_size: 버퍼 큐 크기 (패킷 수)
    """
    name: str = "default"
    bandwidth_mbps: float = 10.0
    rtt_ms: float = 50.0
    loss_rate: float = 0.01
    jitter_ms: float = 10.0
    queue_size: int = 100
    
    @property
    def one_way_delay_ms(self) -> float:
        return self.rtt_ms / 2.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "bandwidth_mbps": self.bandwidth_mbps,
            "rtt_ms": self.rtt_ms,
            "loss_rate": self.loss_rate,
            "jitter_ms": self.jitter_ms,
            "queue_size": self.queue_size,
        }


# 미리 정의된 네트워크 프로필 (실측 기반)
NETWORK_PROFILES: Dict[str, NetworkCondition] = {
    "wifi_good": NetworkCondition(
        name="wifi_good",
        bandwidth_mbps=50.0,
        rtt_ms=10.0,
        loss_rate=0.001,
        jitter_ms=2.0,
    ),
    "wifi_normal": NetworkCondition(
        name="wifi_normal",
        bandwidth_mbps=20.0,
        rtt_ms=30.0,
        loss_rate=0.005,
        jitter_ms=5.0,
    ),
    "wifi_congested": NetworkCondition(
        name="wifi_congested",
        bandwidth_mbps=5.0,
        rtt_ms=80.0,
        loss_rate=0.02,
        jitter_ms=20.0,
    ),
    "lte_good": NetworkCondition(
        name="lte_good",
        bandwidth_mbps=30.0,
        rtt_ms=40.0,
        loss_rate=0.002,
        jitter_ms=10.0,
    ),
    "lte_normal": NetworkCondition(
        name="lte_normal",
        bandwidth_mbps=10.0,
        rtt_ms=60.0,
        loss_rate=0.01,
        jitter_ms=15.0,
    ),
    "lte_poor": NetworkCondition(
        name="lte_poor",
        bandwidth_mbps=2.0,
        rtt_ms=150.0,
        loss_rate=0.05,
        jitter_ms=50.0,
    ),
    "3g": NetworkCondition(
        name="3g",
        bandwidth_mbps=1.0,
        rtt_ms=300.0,
        loss_rate=0.03,
        jitter_ms=100.0,
    ),
}


@dataclass
class PacketStats:
    """패킷 통계."""
    sent: int = 0
    received: int = 0
    lost: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    latencies: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sent": self.sent,
            "received": self.received,
            "lost": self.lost,
            "loss_ratio": self.lost / max(1, self.sent),
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "avg_latency_ms": float(np.mean(self.latencies)) if self.latencies else 0.0,
            "p95_latency_ms": float(np.percentile(self.latencies, 95)) if self.latencies else 0.0,
        }


class NetworkEmulator:
    """네트워크 조건 에뮬레이션.
    
    지연, 손실, 대역폭 제한을 asyncio 레벨에서 시뮬레이션한다.
    실제 소켓 통신을 사용하므로 Mock이 아닌 실제 네트워크 테스트다.
    """
    
    def __init__(self, condition: NetworkCondition) -> None:
        self.condition = condition
        self._last_send_time: float = 0.0
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=condition.queue_size)
        self._lock = asyncio.Lock()
    
    async def apply_delay(self) -> None:
        """지연 적용 (jitter 포함)."""
        base_delay = self.condition.one_way_delay_ms / 1000.0
        jitter = random.gauss(0, self.condition.jitter_ms / 1000.0 / 3)  # 3-sigma
        delay = max(0, base_delay + jitter)
        await asyncio.sleep(delay)
    
    def should_drop(self) -> bool:
        """패킷 손실 여부 결정."""
        return random.random() < self.condition.loss_rate
    
    async def apply_bandwidth_limit(self, data_size: int) -> None:
        """대역폭 제한 적용.
        
        토큰 버킷 알고리즘 기반으로 전송 속도를 제한한다.
        """
        bytes_per_second = self.condition.bandwidth_mbps * 1_000_000 / 8
        transmission_time = data_size / bytes_per_second
        
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_send_time
            wait_time = transmission_time - elapsed
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            self._last_send_time = time.time()
    
    async def send(self, data: bytes) -> Tuple[bool, float]:
        """데이터 전송 (에뮬레이션 적용).
        
        Returns:
            (성공 여부, 지연 시간 ms)
        """
        start_time = time.time()
        
        # 패킷 손실 체크
        if self.should_drop():
            return False, 0.0
        
        # 대역폭 제한 적용
        await self.apply_bandwidth_limit(len(data))
        
        # 지연 적용
        await self.apply_delay()
        
        elapsed_ms = (time.time() - start_time) * 1000
        return True, elapsed_ms


class FrameProtocol:
    """프레임 단위 전송 프로토콜.
    
    헤더 + 페이로드 구조:
    - 4바이트: 페이로드 길이 (big-endian)
    - N바이트: JSON 헤더 + 바이너리 페이로드
    """
    
    HEADER_SIZE = 4
    
    @staticmethod
    def pack(header: Dict[str, Any], payload: bytes = b"") -> bytes:
        """프레임 패킹."""
        header_json = json.dumps(header).encode("utf-8")
        header_with_separator = header_json + b"\n"
        full_payload = header_with_separator + payload
        length = len(full_payload)
        return struct.pack(">I", length) + full_payload
    
    @staticmethod
    async def unpack(reader: asyncio.StreamReader) -> Tuple[Dict[str, Any], bytes]:
        """프레임 언패킹."""
        length_bytes = await reader.readexactly(4)
        length = struct.unpack(">I", length_bytes)[0]
        
        data = await reader.readexactly(length)
        
        if b"\n" in data:
            header_json, payload = data.split(b"\n", 1)
        else:
            header_json = data
            payload = b""
        
        header = json.loads(header_json.decode("utf-8"))
        return header, payload


@dataclass
class VideoFrame:
    """비디오 프레임."""
    index: int
    frame_type: str  # "I", "P", "B"
    payload_size: int
    importance: float
    presentation_time_ms: float
    data: bytes = field(default_factory=bytes, repr=False)
    
    def to_header(self) -> Dict[str, Any]:
        return {
            "type": "frame",
            "index": self.index,
            "frame_type": self.frame_type,
            "payload_size": self.payload_size,
            "importance": self.importance,
            "pts_ms": self.presentation_time_ms,
        }


class EmulatedServer:
    """에뮬레이션이 적용된 비디오 스트리밍 서버."""
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        condition: NetworkCondition = None,
    ) -> None:
        self.host = host
        self.port = port
        self.condition = condition or NETWORK_PROFILES["wifi_normal"]
        self.emulator = NetworkEmulator(self.condition)
        self.stats = PacketStats()
        self._server: Optional[asyncio.Server] = None
        self._clients: List[asyncio.Task] = []
    
    def _generate_frame(self, index: int) -> VideoFrame:
        """GOP 패턴 기반 프레임 생성.
        
        실제 H.264 GOP 구조를 시뮬레이션:
        - GOP 크기: 16 프레임
        - 패턴: I B B P B B P B B P B B P B B P
        """
        gop_pos = index % 16
        
        if gop_pos == 0:
            frame_type = "I"
            importance = 1.0
            size = random.randint(40000, 60000)  # I-프레임: 40-60KB
        elif gop_pos % 4 == 0:
            frame_type = "P"
            importance = 0.5 + random.random() * 0.2
            size = random.randint(15000, 25000)  # P-프레임: 15-25KB
        else:
            frame_type = "B"
            importance = 0.1 + random.random() * 0.2
            size = random.randint(3000, 8000)  # B-프레임: 3-8KB
        
        return VideoFrame(
            index=index,
            frame_type=frame_type,
            payload_size=size,
            importance=importance,
            presentation_time_ms=index * 33.33,  # 30 FPS
            data=os.urandom(size),
        )
    
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """클라이언트 연결 처리."""
        addr = writer.get_extra_info("peername")
        logger.info("클라이언트 연결: %s", addr)
        
        try:
            while True:
                try:
                    header, _ = await asyncio.wait_for(
                        FrameProtocol.unpack(reader),
                        timeout=30.0,
                    )
                except asyncio.TimeoutError:
                    logger.debug("클라이언트 타임아웃: %s", addr)
                    break
                except asyncio.IncompleteReadError:
                    logger.debug("클라이언트 연결 종료: %s", addr)
                    break
                
                if header.get("type") == "request_frame":
                    frame_index = header.get("index", 0)
                    frame = self._generate_frame(frame_index)
                    
                    # 에뮬레이션 적용
                    packet = FrameProtocol.pack(frame.to_header(), frame.data)
                    success, latency = await self.emulator.send(packet)
                    
                    if success:
                        writer.write(packet)
                        await writer.drain()
                        
                        self.stats.sent += 1
                        self.stats.bytes_sent += len(packet)
                        self.stats.latencies.append(latency)
                        
                        logger.debug(
                            "프레임 전송: idx=%d type=%s size=%d latency=%.1fms",
                            frame_index, frame.frame_type, len(frame.data), latency,
                        )
                    else:
                        self.stats.lost += 1
                        logger.debug("프레임 손실: idx=%d", frame_index)
                
                elif header.get("type") == "get_stats":
                    stats_packet = FrameProtocol.pack({
                        "type": "stats",
                        "server_stats": self.stats.to_dict(),
                        "network_condition": self.condition.to_dict(),
                    })
                    writer.write(stats_packet)
                    await writer.drain()
                
                elif header.get("type") == "disconnect":
                    break
        
        except Exception as e:
            logger.error("클라이언트 처리 오류: %s - %s", addr, e)
        
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("클라이언트 연결 해제: %s", addr)
    
    async def start(self) -> None:
        """서버 시작."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        
        addrs = ", ".join(str(sock.getsockname()) for sock in self._server.sockets)
        logger.info("서버 시작: %s (조건: %s)", addrs, self.condition.name)
        
        async with self._server:
            await self._server.serve_forever()
    
    async def stop(self) -> None:
        """서버 종료."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()


class EmulatedClient:
    """에뮬레이션이 적용된 비디오 스트리밍 클라이언트."""
    
    def __init__(
        self,
        server_host: str = "localhost",
        server_port: int = 8080,
    ) -> None:
        self.server_host = server_host
        self.server_port = server_port
        self.stats = PacketStats()
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
    
    async def connect(self) -> bool:
        """서버 연결."""
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.server_host,
                self.server_port,
            )
            logger.info("서버 연결 성공: %s:%d", self.server_host, self.server_port)
            return True
        except Exception as e:
            logger.error("서버 연결 실패: %s", e)
            return False
    
    async def request_frame(self, index: int) -> Optional[Dict[str, Any]]:
        """프레임 요청."""
        if not self._writer or not self._reader:
            return None
        
        request = FrameProtocol.pack({"type": "request_frame", "index": index})
        send_time = time.time()
        
        self._writer.write(request)
        await self._writer.drain()
        self.stats.sent += 1
        
        try:
            header, payload = await asyncio.wait_for(
                FrameProtocol.unpack(self._reader),
                timeout=5.0,
            )
            
            latency = (time.time() - send_time) * 1000
            self.stats.received += 1
            self.stats.bytes_received += len(payload)
            self.stats.latencies.append(latency)
            
            return {
                "header": header,
                "payload_size": len(payload),
                "latency_ms": latency,
            }
        
        except asyncio.TimeoutError:
            self.stats.lost += 1
            logger.debug("프레임 수신 타임아웃: idx=%d", index)
            return None
    
    async def get_server_stats(self) -> Optional[Dict[str, Any]]:
        """서버 통계 조회."""
        if not self._writer or not self._reader:
            return None
        
        request = FrameProtocol.pack({"type": "get_stats"})
        self._writer.write(request)
        await self._writer.drain()
        
        try:
            header, _ = await asyncio.wait_for(
                FrameProtocol.unpack(self._reader),
                timeout=5.0,
            )
            return header
        except asyncio.TimeoutError:
            return None
    
    async def disconnect(self) -> None:
        """연결 종료."""
        if self._writer:
            try:
                request = FrameProtocol.pack({"type": "disconnect"})
                self._writer.write(request)
                await self._writer.drain()
            except Exception:
                pass
            
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        
        logger.info("연결 종료")
    
    async def run_experiment(
        self,
        num_frames: int,
        fps: float = 30.0,
    ) -> Dict[str, Any]:
        """실험 실행.
        
        Args:
            num_frames: 요청할 프레임 수
            fps: 초당 프레임 수
        
        Returns:
            실험 결과
        """
        if not await self.connect():
            return {"error": "connection_failed"}
        
        frame_interval = 1.0 / fps
        received_frames: List[Dict[str, Any]] = []
        
        start_time = time.time()
        
        for i in range(num_frames):
            frame_start = time.time()
            
            result = await self.request_frame(i)
            if result:
                received_frames.append(result)
            
            # FPS 유지
            elapsed = time.time() - frame_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        total_time = time.time() - start_time
        
        # 서버 통계 조회
        server_stats = await self.get_server_stats()
        
        await self.disconnect()
        
        # 결과 집계
        result = {
            "experiment": {
                "num_frames_requested": num_frames,
                "num_frames_received": len(received_frames),
                "total_time_seconds": total_time,
                "actual_fps": len(received_frames) / total_time,
            },
            "client_stats": self.stats.to_dict(),
            "server_stats": server_stats.get("server_stats") if server_stats else None,
            "network_condition": server_stats.get("network_condition") if server_stats else None,
        }
        
        return result


async def run_server(args: argparse.Namespace) -> None:
    """서버 실행."""
    condition = NETWORK_PROFILES.get(args.profile, NETWORK_PROFILES["wifi_normal"])
    
    if args.rtt:
        condition.rtt_ms = args.rtt
    if args.bandwidth:
        condition.bandwidth_mbps = args.bandwidth
    if args.loss:
        condition.loss_rate = args.loss / 100.0
    
    server = EmulatedServer(
        host=args.host,
        port=args.port,
        condition=condition,
    )
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("서버 종료 중...")
        await server.stop()


async def run_client(args: argparse.Namespace) -> None:
    """클라이언트 실행."""
    host, port = args.server.rsplit(":", 1)
    port = int(port)
    
    client = EmulatedClient(server_host=host, server_port=port)
    
    result = await client.run_experiment(
        num_frames=args.frames,
        fps=args.fps,
    )
    
    print("\n=== 실험 결과 ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 결과 저장
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\n결과 저장: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Windows 호환 실제 네트워크 에뮬레이터"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # 서버 서브커맨드
    server_parser = subparsers.add_parser("server", help="에뮬레이션 서버 실행")
    server_parser.add_argument("--host", default="0.0.0.0", help="바인드 호스트")
    server_parser.add_argument("--port", type=int, default=8080, help="바인드 포트")
    server_parser.add_argument(
        "--profile",
        choices=list(NETWORK_PROFILES.keys()),
        default="wifi_normal",
        help="네트워크 프로필",
    )
    server_parser.add_argument("--rtt", type=float, help="RTT 오버라이드 (ms)")
    server_parser.add_argument("--bandwidth", type=float, help="대역폭 오버라이드 (Mbps)")
    server_parser.add_argument("--loss", type=float, help="손실률 오버라이드 (%%)")
    
    # 클라이언트 서브커맨드
    client_parser = subparsers.add_parser("client", help="실험 클라이언트 실행")
    client_parser.add_argument("--server", default="localhost:8080", help="서버 주소")
    client_parser.add_argument("--frames", type=int, default=300, help="요청할 프레임 수")
    client_parser.add_argument("--fps", type=float, default=30.0, help="초당 프레임 수")
    client_parser.add_argument("--output", help="결과 저장 경로")
    
    # 프로필 목록 서브커맨드
    list_parser = subparsers.add_parser("list-profiles", help="네트워크 프로필 목록")
    
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 로그")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    
    if args.command == "server":
        asyncio.run(run_server(args))
    elif args.command == "client":
        asyncio.run(run_client(args))
    elif args.command == "list-profiles":
        print("사용 가능한 네트워크 프로필:\n")
        for name, cond in NETWORK_PROFILES.items():
            print(f"  {name}:")
            print(f"    대역폭: {cond.bandwidth_mbps} Mbps")
            print(f"    RTT: {cond.rtt_ms} ms")
            print(f"    손실률: {cond.loss_rate * 100:.1f}%")
            print(f"    지터: {cond.jitter_ms} ms")
            print()


if __name__ == "__main__":
    main()
