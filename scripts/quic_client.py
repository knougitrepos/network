"""QUIC 기반 비디오 스트리밍 클라이언트.

aioquic 라이브러리를 사용하여 DATAGRAM 및 STREAM 수신을 지원한다.

주요 기능:
    - HTTP/3 기반 비디오 세그먼트 수신 (STREAM)
    - QUIC DATAGRAM을 통한 저지연 프레임 수신
    - 프레임 버퍼링 및 재생 시뮬레이션

사용 예시:
    python scripts/quic_client.py --server localhost:4433 \
        --frames 300 --output output/quic_test
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


logger = logging.getLogger(__name__)


# aioquic 임포트 (설치 필요)
try:
    from aioquic.asyncio import QuicConnectionProtocol, connect
    from aioquic.quic.configuration import QuicConfiguration
    from aioquic.quic.events import (
        ConnectionTerminated,
        DatagramFrameReceived,
        HandshakeCompleted,
        QuicEvent,
        StreamDataReceived,
    )
    from aioquic.h3.connection import H3_ALPN, H3Connection
    from aioquic.h3.events import (
        DataReceived,
        H3Event,
        HeadersReceived,
    )
    AIOQUIC_AVAILABLE = True
except ImportError:
    AIOQUIC_AVAILABLE = False
    logger.warning("aioquic가 설치되지 않았습니다. pip install aioquic")


@dataclass
class ReceivedFrame:
    """수신된 프레임."""
    index: int
    frame_type: str
    importance: float
    presentation_time_ms: float
    receive_time: float
    transport_mode: str  # "datagram" or "stream"
    data_size: int
    latency_ms: float = 0.0


@dataclass
class ClientStats:
    """클라이언트 통계."""
    frames_received: int = 0
    bytes_received: int = 0
    datagram_frames: int = 0
    stream_frames: int = 0
    lost_frames: int = 0
    start_time: float = field(default_factory=time.time)
    
    # 지연 시간 통계
    latencies: List[float] = field(default_factory=list)
    
    def add_latency(self, latency_ms: float) -> None:
        self.latencies.append(latency_ms)
    
    def to_dict(self) -> Dict[str, Any]:
        import numpy as np
        
        elapsed = time.time() - self.start_time
        latencies = self.latencies or [0]
        
        return {
            "frames_received": self.frames_received,
            "bytes_received": self.bytes_received,
            "datagram_frames": self.datagram_frames,
            "stream_frames": self.stream_frames,
            "lost_frames": self.lost_frames,
            "elapsed_seconds": elapsed,
            "throughput_mbps": (self.bytes_received * 8 / 1_000_000) / elapsed if elapsed > 0 else 0,
            "avg_latency_ms": float(np.mean(latencies)),
            "p95_latency_ms": float(np.percentile(latencies, 95)),
            "p99_latency_ms": float(np.percentile(latencies, 99)),
            "loss_ratio": self.lost_frames / (self.frames_received + self.lost_frames) if self.frames_received else 0,
        }


class FrameBuffer:
    """프레임 버퍼 (재생 시뮬레이션용)."""
    
    def __init__(self, buffer_target_ms: float = 500.0) -> None:
        self.buffer_target_ms = buffer_target_ms
        self.frames: Dict[int, ReceivedFrame] = {}
        self.next_play_index: int = 0
        self._lock = asyncio.Lock()
    
    async def add_frame(self, frame: ReceivedFrame) -> None:
        """프레임 추가."""
        async with self._lock:
            self.frames[frame.index] = frame
    
    async def get_next_frame(self) -> Optional[ReceivedFrame]:
        """다음 재생 프레임 가져오기."""
        async with self._lock:
            if self.next_play_index in self.frames:
                frame = self.frames.pop(self.next_play_index)
                self.next_play_index += 1
                return frame
            return None
    
    async def get_buffer_level(self) -> int:
        """버퍼에 있는 프레임 수."""
        async with self._lock:
            return len(self.frames)
    
    async def is_ready(self) -> bool:
        """재생 준비 완료 여부."""
        async with self._lock:
            return self.next_play_index in self.frames


if AIOQUIC_AVAILABLE:
    
    class VideoStreamingClientProtocol(QuicConnectionProtocol):
        """QUIC 비디오 스트리밍 클라이언트 프로토콜."""
        
        def __init__(
            self,
            *args,
            stats: ClientStats,
            frame_buffer: FrameBuffer,
            **kwargs
        ) -> None:
            super().__init__(*args, **kwargs)
            self.stats = stats
            self.frame_buffer = frame_buffer
            self._h3: Optional[H3Connection] = None
            self._pending_streams: Dict[int, Dict[str, Any]] = {}
            self._request_times: Dict[int, float] = {}
            
            # 완료 이벤트
            self._connected = asyncio.Event()
            self._done = asyncio.Event()
        
        def quic_event_received(self, event: QuicEvent) -> None:
            """QUIC 이벤트 처리."""
            if isinstance(event, HandshakeCompleted):
                logger.info("핸드셰이크 완료: ALPN=%s", event.alpn_protocol)
                if event.alpn_protocol in H3_ALPN:
                    self._h3 = H3Connection(self._quic, enable_webtransport=False)
                self._connected.set()
            
            elif isinstance(event, DatagramFrameReceived):
                self._handle_datagram(event.data)
            
            elif isinstance(event, StreamDataReceived):
                if self._h3 is not None:
                    for h3_event in self._h3.handle_event(event):
                        asyncio.create_task(self._handle_h3_event(h3_event))
            
            elif isinstance(event, ConnectionTerminated):
                logger.info("연결 종료: code=%d", event.error_code)
                self._done.set()
        
        def _handle_datagram(self, data: bytes) -> None:
            """DATAGRAM 프레임 처리."""
            receive_time = time.time()
            
            try:
                # 헤더와 페이로드 분리
                if b"\n" in data:
                    header_bytes, payload = data.split(b"\n", 1)
                else:
                    header_bytes = data
                    payload = b""
                
                header = json.loads(header_bytes.decode("utf-8"))
                
                if header.get("type") == "frame":
                    frame = ReceivedFrame(
                        index=header.get("index", 0),
                        frame_type=header.get("frame_type", "?"),
                        importance=header.get("importance", 0.0),
                        presentation_time_ms=header.get("pts_ms", 0.0),
                        receive_time=receive_time,
                        transport_mode="datagram",
                        data_size=len(payload),
                    )
                    
                    # 비동기 버퍼 추가
                    asyncio.create_task(self.frame_buffer.add_frame(frame))
                    
                    self.stats.frames_received += 1
                    self.stats.bytes_received += len(payload)
                    self.stats.datagram_frames += 1
                    
                    logger.debug(
                        "DATAGRAM 수신: frame=%d type=%s size=%d",
                        frame.index, frame.frame_type, len(payload)
                    )
                    
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.debug("DATAGRAM 파싱 실패: %s", e)
        
        async def _handle_h3_event(self, event: H3Event) -> None:
            """HTTP/3 이벤트 처리."""
            if isinstance(event, HeadersReceived):
                headers = dict(event.headers)
                stream_id = event.stream_id
                
                self._pending_streams[stream_id] = {
                    "headers": headers,
                    "data": bytearray(),
                }
            
            elif isinstance(event, DataReceived):
                stream_id = event.stream_id
                if stream_id in self._pending_streams:
                    self._pending_streams[stream_id]["data"].extend(event.data)
                    
                    if event.stream_ended:
                        await self._complete_stream(stream_id)
        
        async def _complete_stream(self, stream_id: int) -> None:
            """스트림 수신 완료 처리."""
            receive_time = time.time()
            pending = self._pending_streams.pop(stream_id, None)
            
            if pending is None:
                return
            
            headers = pending["headers"]
            data = bytes(pending["data"])
            
            # 프레임 메타데이터 추출
            frame_index = int(headers.get(b"x-frame-index", b"0").decode())
            frame_type = headers.get(b"x-frame-type", b"?").decode()
            importance = float(headers.get(b"x-importance", b"0").decode())
            pts_ms = float(headers.get(b"x-pts-ms", b"0").decode())
            
            # 지연 시간 계산
            request_time = self._request_times.pop(frame_index, receive_time)
            latency_ms = (receive_time - request_time) * 1000
            
            frame = ReceivedFrame(
                index=frame_index,
                frame_type=frame_type,
                importance=importance,
                presentation_time_ms=pts_ms,
                receive_time=receive_time,
                transport_mode="stream",
                data_size=len(data),
                latency_ms=latency_ms,
            )
            
            await self.frame_buffer.add_frame(frame)
            
            self.stats.frames_received += 1
            self.stats.bytes_received += len(data)
            self.stats.stream_frames += 1
            self.stats.add_latency(latency_ms)
            
            logger.debug(
                "STREAM 수신: frame=%d type=%s size=%d latency=%.1fms",
                frame.index, frame.frame_type, len(data), latency_ms
            )
        
        async def wait_connected(self, timeout: float = 10.0) -> bool:
            """연결 완료 대기."""
            try:
                await asyncio.wait_for(self._connected.wait(), timeout)
                return True
            except asyncio.TimeoutError:
                return False
        
        async def request_frame(self, frame_index: int) -> None:
            """프레임 요청."""
            if self._h3 is None:
                logger.warning("H3 연결 없음")
                return
            
            stream_id = self._quic.get_next_available_stream_id()
            self._request_times[frame_index] = time.time()
            
            headers = [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"localhost"),
                (b":path", f"/frame/{frame_index}".encode()),
            ]
            
            self._h3.send_headers(stream_id=stream_id, headers=headers, end_stream=True)
            self.transmit()
            
            logger.debug("프레임 요청: %d", frame_index)


class MockQuicClient:
    """[DEPRECATED] QUIC 클라이언트 모의 구현.
    
    ⚠️ 경고: 이 클래스는 실제 QUIC 통신을 하지 않고 합성 데이터를 생성합니다.
    실제 연구에는 적합하지 않습니다.
    
    실제 QUIC 통신을 위해서는 aioquic를 설치하세요:
        pip install aioquic
    """
    
    def __init__(self, server_host: str, server_port: int) -> None:
        import warnings
        warnings.warn(
            "MockQuicClient는 실제 QUIC 통신을 하지 않습니다. "
            "pip install aioquic 후 재실행하세요.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.server_host = server_host
        self.server_port = server_port
        self.stats = ClientStats()
        self.frame_buffer = FrameBuffer()
    
    async def run(self, num_frames: int) -> Dict[str, Any]:
        """클라이언트 실행 (모의)."""
        import numpy as np
        
        logger.error("=" * 60)
        logger.error("⚠️ 경고: aioquic 미설치 - 모의 클라이언트로 실행됩니다")
        logger.error("실제 QUIC 테스트를 위해 다음을 실행하세요:")
        logger.error("  pip install aioquic")
        logger.error("=" * 60)
        
        # 합성 데이터 생성
        for i in range(num_frames):
            # GOP 패턴: I P B B P B B ...
            gop_pos = i % 16
            if gop_pos == 0:
                frame_type = "I"
                importance = 1.0
                size = 50000
            elif gop_pos % 4 == 0:
                frame_type = "P"
                importance = 0.6
                size = 20000
            else:
                frame_type = "B"
                importance = 0.2
                size = 5000
            
            # 전송 방식 시뮬레이션
            if frame_type == "B" and importance < 0.3:
                transport_mode = "datagram"
                # DATAGRAM은 손실 가능
                if np.random.random() < 0.05:  # 5% 손실
                    self.stats.lost_frames += 1
                    continue
            else:
                transport_mode = "stream"
            
            # 합성 지연
            latency = np.random.exponential(20)  # 평균 20ms
            
            frame = ReceivedFrame(
                index=i,
                frame_type=frame_type,
                importance=importance,
                presentation_time_ms=i * 33.33,
                receive_time=time.time(),
                transport_mode=transport_mode,
                data_size=size,
                latency_ms=latency,
            )
            
            await self.frame_buffer.add_frame(frame)
            
            self.stats.frames_received += 1
            self.stats.bytes_received += size
            self.stats.add_latency(latency)
            
            if transport_mode == "datagram":
                self.stats.datagram_frames += 1
            else:
                self.stats.stream_frames += 1
            
            # 시뮬레이션 딜레이
            await asyncio.sleep(0.001)
        
        return self.stats.to_dict()


async def run_client(
    server_host: str,
    server_port: int,
    num_frames: int,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """QUIC 클라이언트 실행."""
    
    if not AIOQUIC_AVAILABLE:
        client = MockQuicClient(server_host, server_port)
        return await client.run(num_frames)
    
    # QUIC 설정
    configuration = QuicConfiguration(
        alpn_protocols=H3_ALPN,
        is_client=True,
        max_datagram_frame_size=65536,
    )
    
    # 자체 서명 인증서 허용
    configuration.verify_mode = False
    
    stats = ClientStats()
    frame_buffer = FrameBuffer()
    
    logger.info("QUIC 서버 연결: %s:%d", server_host, server_port)
    
    async with connect(
        server_host,
        server_port,
        configuration=configuration,
        create_protocol=lambda *args, **kwargs: VideoStreamingClientProtocol(
            *args, stats=stats, frame_buffer=frame_buffer, **kwargs
        ),
    ) as protocol:
        # 연결 대기
        if not await protocol.wait_connected():
            logger.error("연결 시간 초과")
            return stats.to_dict()
        
        logger.info("연결 완료, 프레임 요청 시작")
        
        # 프레임 요청
        for i in range(num_frames):
            await protocol.request_frame(i)
            await asyncio.sleep(0.033)  # 30 FPS 속도
        
        # 응답 대기
        await asyncio.sleep(2.0)
    
    result = stats.to_dict()
    
    # 결과 저장
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        with (output_dir / "client_stats.json").open("w") as f:
            json.dump(result, f, indent=2)
        logger.info("결과 저장: %s", output_dir / "client_stats.json")
    
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="QUIC 비디오 스트리밍 클라이언트")
    parser.add_argument("--server", default="localhost:4433", help="서버 주소 (host:port)")
    parser.add_argument("--frames", type=int, default=300, help="요청할 프레임 수")
    parser.add_argument("--output", default=None, help="결과 저장 디렉토리")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 로그")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    
    # 서버 주소 파싱
    if ":" in args.server:
        host, port = args.server.rsplit(":", 1)
        port = int(port)
    else:
        host = args.server
        port = 4433
    
    output_dir = Path(args.output) if args.output else None
    
    try:
        result = asyncio.run(run_client(host, port, args.frames, output_dir))
        
        print("\n=== 클라이언트 통계 ===")
        print(json.dumps(result, indent=2))
        
    except KeyboardInterrupt:
        logger.info("클라이언트 종료")


if __name__ == "__main__":
    main()
