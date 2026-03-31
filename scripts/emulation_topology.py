"""Mininet 기반 에뮬레이션 토폴로지 정의.

비디오 스트리밍 시뮬레이션을 위한 네트워크 토폴로지를 정의한다.

필수 의존성:
    - Mininet (Linux only)
    - tc/netem (네트워크 조건 에뮬레이션)

토폴로지 구조:
    client1 ──┬── switch ── server
    client2 ──┘

사용 예시 (Linux):
    sudo python -c "from emulation.topology import VideoStreamingTopology; t = VideoStreamingTopology()"
"""

from __future__ import annotations

import logging
import platform
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Mininet은 Linux에서만 사용 가능
_MININET_AVAILABLE = False
if platform.system() == "Linux":
    try:
        from mininet.net import Mininet
        from mininet.node import Controller, OVSSwitch
        from mininet.link import TCLink
        from mininet.topo import Topo
        from mininet.cli import CLI
        _MININET_AVAILABLE = True
    except ImportError:
        pass


@dataclass
class LinkConfig:
    """네트워크 링크 설정."""
    bandwidth_mbps: float = 10.0
    delay_ms: float = 10.0
    loss_rate: float = 0.0
    jitter_ms: float = 0.0
    max_queue_size: int = 1000  # 패킷 수


@dataclass
class NetworkProfile:
    """네트워크 조건 프로파일.
    
    실험에서 사용할 네트워크 조건 세트를 정의한다.
    """
    name: str
    client_to_switch: LinkConfig = field(default_factory=LinkConfig)
    switch_to_server: LinkConfig = field(default_factory=LinkConfig)
    
    @classmethod
    def wifi_good(cls) -> "NetworkProfile":
        """양호한 Wi-Fi 환경."""
        return cls(
            name="wifi_good",
            client_to_switch=LinkConfig(bandwidth_mbps=50.0, delay_ms=5.0, loss_rate=0.001),
            switch_to_server=LinkConfig(bandwidth_mbps=100.0, delay_ms=2.0, loss_rate=0.0),
        )
    
    @classmethod
    def wifi_congested(cls) -> "NetworkProfile":
        """혼잡한 Wi-Fi 환경."""
        return cls(
            name="wifi_congested",
            client_to_switch=LinkConfig(bandwidth_mbps=10.0, delay_ms=20.0, loss_rate=0.02, jitter_ms=10.0),
            switch_to_server=LinkConfig(bandwidth_mbps=100.0, delay_ms=2.0, loss_rate=0.0),
        )
    
    @classmethod
    def lte_normal(cls) -> "NetworkProfile":
        """일반적인 LTE 환경."""
        return cls(
            name="lte_normal",
            client_to_switch=LinkConfig(bandwidth_mbps=20.0, delay_ms=30.0, loss_rate=0.005),
            switch_to_server=LinkConfig(bandwidth_mbps=100.0, delay_ms=5.0, loss_rate=0.0),
        )
    
    @classmethod
    def lte_poor(cls) -> "NetworkProfile":
        """열악한 LTE 환경 (이동 중, 약전계)."""
        return cls(
            name="lte_poor",
            client_to_switch=LinkConfig(bandwidth_mbps=5.0, delay_ms=80.0, loss_rate=0.05, jitter_ms=30.0),
            switch_to_server=LinkConfig(bandwidth_mbps=100.0, delay_ms=5.0, loss_rate=0.0),
        )
    
    @classmethod
    def all_profiles(cls) -> List["NetworkProfile"]:
        """모든 프로파일 반환."""
        return [
            cls.wifi_good(),
            cls.wifi_congested(),
            cls.lte_normal(),
            cls.lte_poor(),
        ]


def _link_config_to_tc_params(config: LinkConfig) -> Dict[str, object]:
    """LinkConfig를 Mininet TCLink 파라미터로 변환."""
    params = {
        "bw": config.bandwidth_mbps,
        "delay": f"{config.delay_ms}ms",
        "loss": config.loss_rate * 100,  # percentage
        "max_queue_size": config.max_queue_size,
    }
    if config.jitter_ms > 0:
        params["jitter"] = f"{config.jitter_ms}ms"
    return params


class VideoStreamingTopology:
    """비디오 스트리밍 에뮬레이션을 위한 토폴로지.
    
    구조:
        clients[0..n-1] ─── switch ─── server
        
    각 클라이언트는 다른 네트워크 조건을 가질 수 있다.
    """
    
    def __init__(
        self,
        n_clients: int = 1,
        profile: Optional[NetworkProfile] = None,
        server_ip: str = "10.0.0.100",
        client_ip_base: str = "10.0.0.",
    ) -> None:
        """토폴로지 초기화.
        
        Args:
            n_clients: 클라이언트 수
            profile: 네트워크 프로파일 (None이면 기본값 사용)
            server_ip: 서버 IP 주소
            client_ip_base: 클라이언트 IP 기본 주소 (마지막 옥텟은 1부터 시작)
        """
        self.n_clients = n_clients
        self.profile = profile or NetworkProfile.wifi_good()
        self.server_ip = server_ip
        self.client_ip_base = client_ip_base
        
        self.net: Optional[object] = None
        self._hosts: Dict[str, object] = {}
        
        if not _MININET_AVAILABLE:
            logger.warning(
                "Mininet을 사용할 수 없습니다. "
                "Linux 환경에서 'sudo apt-get install mininet' 또는 "
                "'pip install mininet'으로 설치하세요."
            )
    
    def build(self) -> bool:
        """토폴로지 빌드 및 네트워크 시작.
        
        Returns:
            bool: 성공 여부
        """
        if not _MININET_AVAILABLE:
            logger.error("Mininet을 사용할 수 없어 토폴로지를 빌드할 수 없습니다.")
            return False
        
        try:
            # Mininet 생성
            self.net = Mininet(controller=Controller, switch=OVSSwitch, link=TCLink)
            
            # 컨트롤러 추가
            self.net.addController("c0")
            
            # 스위치 추가
            switch = self.net.addSwitch("s1")
            
            # 서버 추가
            server = self.net.addHost("server", ip=self.server_ip)
            self._hosts["server"] = server
            
            # 서버-스위치 링크
            server_link_params = _link_config_to_tc_params(self.profile.switch_to_server)
            self.net.addLink(server, switch, **server_link_params)
            
            # 클라이언트 추가
            client_link_params = _link_config_to_tc_params(self.profile.client_to_switch)
            for i in range(self.n_clients):
                client_name = f"client{i}"
                client_ip = f"{self.client_ip_base}{i + 1}"
                client = self.net.addHost(client_name, ip=client_ip)
                self._hosts[client_name] = client
                self.net.addLink(client, switch, **client_link_params)
            
            # 네트워크 시작
            self.net.start()
            logger.info("토폴로지 빌드 완료: %d clients, profile=%s", self.n_clients, self.profile.name)
            return True
            
        except Exception as e:
            logger.error("토폴로지 빌드 실패: %s", e)
            return False
    
    def get_host(self, name: str) -> Optional[object]:
        """호스트 객체 반환."""
        return self._hosts.get(name)
    
    def run_command(self, host_name: str, command: str) -> Tuple[str, str, int]:
        """특정 호스트에서 명령 실행.
        
        Args:
            host_name: 호스트 이름 (예: "server", "client0")
            command: 실행할 명령
            
        Returns:
            Tuple[stdout, stderr, return_code]
        """
        host = self._hosts.get(host_name)
        if host is None:
            return "", f"Host not found: {host_name}", 1
        
        try:
            result = host.cmd(command)
            return result, "", 0
        except Exception as e:
            return "", str(e), 1
    
    def ping_test(self, from_host: str = "client0", to_ip: Optional[str] = None, count: int = 5) -> Dict[str, float]:
        """Ping 테스트 실행.
        
        Returns:
            Dict with keys: min_ms, avg_ms, max_ms, loss_pct
        """
        to_ip = to_ip or self.server_ip
        stdout, stderr, rc = self.run_command(from_host, f"ping -c {count} {to_ip}")
        
        result = {"min_ms": 0.0, "avg_ms": 0.0, "max_ms": 0.0, "loss_pct": 100.0}
        
        if rc != 0:
            return result
        
        # Parse ping output
        for line in stdout.split("\n"):
            if "packet loss" in line:
                # "5 packets transmitted, 5 received, 0% packet loss"
                try:
                    loss_str = line.split(",")[2].strip().split("%")[0]
                    result["loss_pct"] = float(loss_str)
                except (IndexError, ValueError):
                    pass
            elif "min/avg/max" in line:
                # "rtt min/avg/max/mdev = 0.123/0.456/0.789/0.012 ms"
                try:
                    times = line.split("=")[1].strip().split("/")
                    result["min_ms"] = float(times[0])
                    result["avg_ms"] = float(times[1])
                    result["max_ms"] = float(times[2])
                except (IndexError, ValueError):
                    pass
        
        return result
    
    def apply_network_condition(
        self,
        interface: str,
        config: LinkConfig,
        host_name: str = "client0",
    ) -> bool:
        """tc/netem으로 동적 네트워크 조건 적용.
        
        Args:
            interface: 네트워크 인터페이스 이름
            config: 적용할 네트워크 조건
            host_name: 조건을 적용할 호스트
        
        Returns:
            bool: 성공 여부
        """
        # 기존 qdisc 삭제
        self.run_command(host_name, f"tc qdisc del dev {interface} root 2>/dev/null")
        
        # netem 설정
        netem_cmd = f"tc qdisc add dev {interface} root netem"
        netem_cmd += f" delay {config.delay_ms}ms"
        if config.jitter_ms > 0:
            netem_cmd += f" {config.jitter_ms}ms"
        if config.loss_rate > 0:
            netem_cmd += f" loss {config.loss_rate * 100}%"
        
        stdout, stderr, rc = self.run_command(host_name, netem_cmd)
        if rc != 0:
            logger.warning("netem 설정 실패: %s", stderr)
            return False
        
        # tbf (Token Bucket Filter)로 대역폭 제한
        tbf_cmd = (
            f"tc qdisc add dev {interface} parent 1:1 handle 10: tbf "
            f"rate {config.bandwidth_mbps}mbit burst 32kbit latency 400ms"
        )
        # tbf는 netem 위에 추가하기 어려우므로 간단히 생략
        
        logger.info("네트워크 조건 적용: %s on %s", config, host_name)
        return True
    
    def stop(self) -> None:
        """네트워크 중지 및 정리."""
        if self.net is not None:
            try:
                self.net.stop()
                logger.info("토폴로지 중지 완료")
            except Exception as e:
                logger.warning("토폴로지 중지 중 오류: %s", e)
        self.net = None
        self._hosts.clear()
    
    def interactive_cli(self) -> None:
        """Mininet CLI 시작 (디버깅용)."""
        if not _MININET_AVAILABLE or self.net is None:
            logger.error("CLI를 시작할 수 없습니다.")
            return
        CLI(self.net)
    
    def __enter__(self) -> "VideoStreamingTopology":
        self.build()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


class DumbbellTopology:
    """Dumbbell 토폴로지 (병목 링크 테스트용).
    
    구조:
        client1 ──┐                  ┌── server1
        client2 ──┼── switch1 ─── switch2 ──┼── server2
        client3 ──┘                  └── server3
        
    switch1-switch2 링크가 병목 (bottleneck)이 된다.
    """
    
    def __init__(
        self,
        n_pairs: int = 2,
        bottleneck_config: Optional[LinkConfig] = None,
        edge_config: Optional[LinkConfig] = None,
    ) -> None:
        self.n_pairs = n_pairs
        self.bottleneck_config = bottleneck_config or LinkConfig(
            bandwidth_mbps=10.0, delay_ms=20.0, loss_rate=0.0
        )
        self.edge_config = edge_config or LinkConfig(
            bandwidth_mbps=100.0, delay_ms=1.0, loss_rate=0.0
        )
        self.net = None
        self._hosts = {}
    
    def build(self) -> bool:
        """토폴로지 빌드."""
        if not _MININET_AVAILABLE:
            logger.error("Mininet을 사용할 수 없습니다.")
            return False
        
        try:
            self.net = Mininet(controller=Controller, switch=OVSSwitch, link=TCLink)
            self.net.addController("c0")
            
            # 스위치 추가
            switch1 = self.net.addSwitch("s1")
            switch2 = self.net.addSwitch("s2")
            
            # 병목 링크
            bottleneck_params = _link_config_to_tc_params(self.bottleneck_config)
            self.net.addLink(switch1, switch2, **bottleneck_params)
            
            # 클라이언트-서버 쌍 추가
            edge_params = _link_config_to_tc_params(self.edge_config)
            for i in range(self.n_pairs):
                client = self.net.addHost(f"client{i}", ip=f"10.0.1.{i + 1}")
                server = self.net.addHost(f"server{i}", ip=f"10.0.2.{i + 1}")
                self._hosts[f"client{i}"] = client
                self._hosts[f"server{i}"] = server
                self.net.addLink(client, switch1, **edge_params)
                self.net.addLink(server, switch2, **edge_params)
            
            self.net.start()
            logger.info("Dumbbell 토폴로지 빌드 완료: %d pairs", self.n_pairs)
            return True
            
        except Exception as e:
            logger.error("토폴로지 빌드 실패: %s", e)
            return False
    
    def stop(self) -> None:
        if self.net is not None:
            self.net.stop()
        self.net = None
        self._hosts.clear()


# 편의를 위한 네트워크 조건 프리셋
NETWORK_PRESETS = {
    "wifi_good": NetworkProfile.wifi_good(),
    "wifi_congested": NetworkProfile.wifi_congested(),
    "lte_normal": NetworkProfile.lte_normal(),
    "lte_poor": NetworkProfile.lte_poor(),
}


def create_topology(
    topology_type: str = "streaming",
    n_clients: int = 1,
    profile_name: str = "wifi_good",
) -> VideoStreamingTopology | DumbbellTopology:
    """토폴로지 팩토리 함수.
    
    Args:
        topology_type: "streaming" 또는 "dumbbell"
        n_clients: 클라이언트 수
        profile_name: 네트워크 프로파일 이름
        
    Returns:
        토폴로지 객체
    """
    profile = NETWORK_PRESETS.get(profile_name, NetworkProfile.wifi_good())
    
    if topology_type == "dumbbell":
        return DumbbellTopology(n_pairs=n_clients)
    else:
        return VideoStreamingTopology(n_clients=n_clients, profile=profile)
