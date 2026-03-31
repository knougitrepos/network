"""QUIC 기반 비디오 스트리밍 서버.

aioquic 라이브러리를 사용하여 DATAGRAM 및 STREAM 전송을 지원한다.

주요 기능:
    - HTTP/3 기반 비디오 세그먼트 전송 (STREAM)
    - QUIC DATAGRAM을 통한 저지연 프레임 전송
    - cross-layer 적응 전송: 중요도 기반 전송 방식 결정

사용 예시:
    python scripts/quic_server.py --host 0.0.0.0 --port 4433 \
        --cert certs/server.crt --key certs/server.key
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
    from aioquic.asyncio import QuicConnectionProtocol, serve
    from aioquic.asyncio.server import QuicServer
    from aioquic.quic.configuration import QuicConfiguration
    from aioquic.quic.connection import QuicConnection
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
        PushPromiseReceived,
    )
    AIOQUIC_AVAILABLE = True
except ImportError:
    AIOQUIC_AVAILABLE = False
    logger.warning("aioquic가 설치되지 않았습니다. pip install aioquic")


@dataclass
class FrameInfo:
    """프레임 정보."""
    index: int
    frame_type: str  # "I", "P", "B"
    payload_size: int
    importance: float = 0.0
    presentation_time_ms: float = 0.0
    data: bytes = field(default_factory=bytes, repr=False)


@dataclass
class ServerStats:
    """서버 통계."""
    total_frames_sent: int = 0
    total_bytes_sent: int = 0
    datagram_frames: int = 0
    stream_frames: int = 0
    connections: int = 0
    start_time: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time
        return {
            "total_frames_sent": self.total_frames_sent,
            "total_bytes_sent": self.total_bytes_sent,
            "datagram_frames": self.datagram_frames,
            "stream_frames": self.stream_frames,
            "connections": self.connections,
            "elapsed_seconds": elapsed,
            "throughput_mbps": (self.total_bytes_sent * 8 / 1_000_000) / elapsed if elapsed > 0 else 0,
        }


# 중요도 기반 전송 방식 결정
_HIGH_IMPORTANCE = 0.75
_LOW_IMPORTANCE = 0.30


def decide_transport_mode(frame: FrameInfo) -> str:
    """프레임 중요도에 따른 전송 방식 결정.
    
    Args:
        frame: 프레임 정보
    
    Returns:
        str: "datagram" (저지연, 비신뢰) 또는 "stream" (신뢰, 순서보장)
    """
    # I-프레임 또는 높은 중요도 → STREAM (신뢰 전송)
    if frame.frame_type == "I" or frame.importance >= _HIGH_IMPORTANCE:
        return "stream"
    
    # B-프레임이고 낮은 중요도 → DATAGRAM (저지연, 손실 허용)
    if frame.frame_type == "B" and frame.importance < _LOW_IMPORTANCE:
        return "datagram"
    
    # 기본: STREAM
    return "stream"


if AIOQUIC_AVAILABLE:
    
    class VideoStreamingProtocol(QuicConnectionProtocol):
        """QUIC 비디오 스트리밍 프로토콜."""
        
        def __init__(self, *args, stats: ServerStats, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.stats = stats
            self._h3: Optional[H3Connection] = None
            self._pending_requests: Dict[int, bytes] = {}
            
            stats.connections += 1
            logger.info("새 연결 수립")
        
        def quic_event_received(self, event: QuicEvent) -> None:
            """QUIC 이벤트 처리."""
            if isinstance(event, HandshakeCompleted):
                logger.info("핸드셰이크 완료: ALPN=%s", event.alpn_protocol)
                if event.alpn_protocol in H3_ALPN:
                    self._h3 = H3Connection(self._quic, enable_webtransport=False)
            
            elif isinstance(event, DatagramFrameReceived):
                self._handle_datagram(event.data)
            
            elif isinstance(event, StreamDataReceived):
                if self._h3 is not None:
                    for h3_event in self._h3.handle_event(event):
                        self._handle_h3_event(h3_event)
            
            elif isinstance(event, ConnectionTerminated):
                logger.info("연결 종료: code=%d, reason=%s", event.error_code, event.reason_phrase)
        
        def _handle_datagram(self, data: bytes) -> None:
            """DATAGRAM 프레임 처리."""
            try:
                # 프레임 요청 메시지 파싱
                message = json.loads(data.decode("utf-8"))
                if message.get("type") == "frame_request":
                    frame_index = message.get("frame_index", 0)
                    logger.debug("DATAGRAM 프레임 요청: %d", frame_index)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.debug("DATAGRAM 파싱 실패: %s", e)
        
        def _handle_h3_event(self, event: H3Event) -> None:
            """HTTP/3 이벤트 처리."""
            if isinstance(event, HeadersReceived):
                headers = dict(event.headers)
                path = headers.get(b":path", b"/").decode()
                method = headers.get(b":method", b"GET").decode()
                
                logger.debug("HTTP/3 요청: %s %s", method, path)
                
                if path.startswith("/frame/"):
                    self._handle_frame_request(event.stream_id, path)
                elif path == "/stats":
                    self._handle_stats_request(event.stream_id)
                else:
                    self._send_404(event.stream_id)
        
        def _handle_frame_request(self, stream_id: int, path: str) -> None:
            """프레임 요청 처리."""
            try:
                frame_index = int(path.split("/")[-1])
            except ValueError:
                self._send_400(stream_id, "Invalid frame index")
                return
            
            # 더미 프레임 생성 (실제로는 비디오 소스에서 가져옴)
            frame = self._generate_dummy_frame(frame_index)
            
            # 전송 방식 결정
            transport_mode = decide_transport_mode(frame)
            
            if transport_mode == "datagram" and self._quic.configuration.max_datagram_frame_size:
                self._send_frame_via_datagram(frame)
            else:
                self._send_frame_via_stream(stream_id, frame)
        
        def _generate_dummy_frame(self, index: int) -> FrameInfo:
            """더미 프레임 생성 (테스트용)."""
            # GOP 패턴: I P B B P B B P B B P B B P B B (16 프레임)
            gop_pos = index % 16
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
            
            return FrameInfo(
                index=index,
                frame_type=frame_type,
                payload_size=size,
                importance=importance,
                presentation_time_ms=index * 33.33,  # 30 FPS
                data=os.urandom(size),
            )
        
        def _send_frame_via_datagram(self, frame: FrameInfo) -> None:
            """DATAGRAM으로 프레임 전송."""
            # 헤더 + 페이로드
            header = json.dumps({
                "type": "frame",
                "index": frame.index,
                "frame_type": frame.frame_type,
                "importance": frame.importance,
                "pts_ms": frame.presentation_time_ms,
            }).encode()
            
            # DATAGRAM은 크기 제한이 있으므로 분할 필요
            max_size = self._quic.configuration.max_datagram_frame_size or 1200
            
            # 간단한 구현: 헤더만 DATAGRAM, 큰 페이로드는 스트림
            if len(frame.data) <= max_size - len(header) - 10:
                self._quic.send_datagram_frame(header + b"\n" + frame.data)
                self.stats.datagram_frames += 1
            else:
                # 크기 초과시 스트림으로 폴백
                logger.debug("DATAGRAM 크기 초과, 스트림으로 전환")
                # 새 스트림 생성
                stream_id = self._quic.get_next_available_stream_id()
                self._send_frame_via_stream(stream_id, frame)
                return
            
            self.stats.total_frames_sent += 1
            self.stats.total_bytes_sent += len(frame.data)
            
            logger.debug(
                "DATAGRAM 전송: frame=%d type=%s size=%d",
                frame.index, frame.frame_type, len(frame.data)
            )
        
        def _send_frame_via_stream(self, stream_id: int, frame: FrameInfo) -> None:
            """STREAM으로 프레임 전송 (HTTP/3)."""
            response_headers = [
                (b":status", b"200"),
                (b"content-type", b"application/octet-stream"),
                (b"x-frame-index", str(frame.index).encode()),
                (b"x-frame-type", frame.frame_type.encode()),
                (b"x-importance", f"{frame.importance:.2f}".encode()),
                (b"x-pts-ms", f"{frame.presentation_time_ms:.2f}".encode()),
            ]
            
            self._h3.send_headers(stream_id=stream_id, headers=response_headers)
            self._h3.send_data(stream_id=stream_id, data=frame.data, end_stream=True)
            
            self.stats.total_frames_sent += 1
            self.stats.total_bytes_sent += len(frame.data)
            self.stats.stream_frames += 1
            
            # 전송 버퍼 플러시
            self.transmit()
            
            logger.debug(
                "STREAM 전송: frame=%d type=%s size=%d",
                frame.index, frame.frame_type, len(frame.data)
            )
        
        def _handle_stats_request(self, stream_id: int) -> None:
            """서버 통계 요청 처리."""
            stats_json = json.dumps(self.stats.to_dict()).encode()
            
            response_headers = [
                (b":status", b"200"),
                (b"content-type", b"application/json"),
            ]
            
            self._h3.send_headers(stream_id=stream_id, headers=response_headers)
            self._h3.send_data(stream_id=stream_id, data=stats_json, end_stream=True)
            self.transmit()
        
        def _send_404(self, stream_id: int) -> None:
            """404 응답 전송."""
            response_headers = [
                (b":status", b"404"),
            ]
            self._h3.send_headers(stream_id=stream_id, headers=response_headers, end_stream=True)
            self.transmit()
        
        def _send_400(self, stream_id: int, message: str) -> None:
            """400 응답 전송."""
            response_headers = [
                (b":status", b"400"),
                (b"content-type", b"text/plain"),
            ]
            self._h3.send_headers(stream_id=stream_id, headers=response_headers)
            self._h3.send_data(stream_id=stream_id, data=message.encode(), end_stream=True)
            self.transmit()


class MockQuicServer:
    """[DEPRECATED] QUIC 서버 모의 구현.
    
    ⚠️ 경고: 이 클래스는 실제 QUIC 통신을 하지 않습니다. 실제 연구에는 적합하지 않습니다.
    
    실제 QUIC 통신을 위해서는 aioquic를 설치하세요:
        pip install aioquic
    
    인증서 생성:
        openssl req -x509 -newkey rsa:2048 -keyout certs/server.key -out certs/server.crt -days 365 -nodes
    """
    
    def __init__(self, host: str, port: int) -> None:
        import warnings
        warnings.warn(
            "MockQuicServer는 실제 QUIC 통신을 하지 않습니다. "
            "pip install aioquic 후 재실행하세요.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.host = host
        self.port = port
        self.stats = ServerStats()
        self._running = False
    
    async def run(self) -> None:
        """서버 실행 (모의)."""
        logger.error("=" * 60)
        logger.error("⚠️ 경고: aioquic 미설치 - 모의 서버로 실행됩니다")
        logger.error("실제 QUIC 테스트를 위해 다음을 실행하세요:")
        logger.error("  pip install aioquic")
        logger.error("=" * 60)
        self._running = True
        
        while self._running:
            await asyncio.sleep(1)
            logger.debug("MockQuicServer 대기 중...")
    
    def stop(self) -> None:
        """서버 종료."""
        self._running = False


async def run_server(
    host: str,
    port: int,
    cert_path: Path,
    key_path: Path,
) -> None:
    """QUIC 서버 실행."""
    
    if not AIOQUIC_AVAILABLE:
        server = MockQuicServer(host, port)
        await server.run()
        return
    
    # QUIC 설정
    configuration = QuicConfiguration(
        alpn_protocols=H3_ALPN,
        is_client=False,
        max_datagram_frame_size=65536,
    )
    
    # 인증서 로드
    if cert_path.exists() and key_path.exists():
        configuration.load_cert_chain(str(cert_path), str(key_path))
    else:
        logger.error("인증서 파일이 없습니다: %s, %s", cert_path, key_path)
        logger.info("테스트용 인증서 생성:")
        logger.info("  openssl req -x509 -newkey rsa:2048 -keyout server.key -out server.crt -days 365 -nodes")
        return
    
    stats = ServerStats()
    
    # 프로토콜 팩토리
    def create_protocol(*args, **kwargs):
        return VideoStreamingProtocol(*args, stats=stats, **kwargs)
    
    logger.info("QUIC 서버 시작: %s:%d", host, port)
    
    await serve(
        host=host,
        port=port,
        configuration=configuration,
        create_protocol=create_protocol,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="QUIC 비디오 스트리밍 서버")
    parser.add_argument("--host", default="0.0.0.0", help="바인드 호스트")
    parser.add_argument("--port", type=int, default=4433, help="바인드 포트")
    parser.add_argument("--cert", default="certs/server.crt", help="서버 인증서 경로")
    parser.add_argument("--key", default="certs/server.key", help="개인키 경로")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 로그")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    
    cert_path = Path(args.cert)
    key_path = Path(args.key)
    
    try:
        asyncio.run(run_server(args.host, args.port, cert_path, key_path))
    except KeyboardInterrupt:
        logger.info("서버 종료")


if __name__ == "__main__":
    main()
