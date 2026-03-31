"""Mininet 기반 반복실험 자동화 러너.

토폴로지와 네트워크 프로파일 조합으로 실험을 반복 실행하고
결과를 수집한다.

사용 예시 (Linux, root 권한 필요):
    sudo python scripts/emulation_runner.py \\
        --iterations 10 \\
        --profiles wifi_good wifi_congested lte_normal \\
        --output output/emulation_results.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


logger = logging.getLogger(__name__)


# 타입 힌트를 위한 forward reference
try:
    from scripts.emulation_topology import (
        VideoStreamingTopology,
        NetworkProfile,
        NETWORK_PRESETS,
    )
except ImportError:
    VideoStreamingTopology = Any
    NetworkProfile = Any
    NETWORK_PRESETS = {}


@dataclass
class ExperimentConfig:
    """단일 실험 설정."""
    profile_name: str
    iteration: int
    seed: int
    video_path: Optional[str] = None
    duration_seconds: float = 30.0
    extra_params: Dict[str, object] = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """단일 실험 결과."""
    config: ExperimentConfig
    start_time: datetime
    end_time: datetime
    success: bool
    
    # 네트워크 지표
    rtt_min_ms: float = 0.0
    rtt_avg_ms: float = 0.0
    rtt_max_ms: float = 0.0
    packet_loss_pct: float = 0.0
    
    # 전송 지표
    throughput_mbps: float = 0.0
    goodput_mbps: float = 0.0
    
    # QoE 지표 (시뮬레이션 연동 시)
    late_frame_ratio: float = 0.0
    rebuffer_ratio: float = 0.0
    vmaf_score: float = 0.0
    
    # 에러 정보
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, object]:
        """딕셔너리로 변환."""
        return {
            "profile_name": self.config.profile_name,
            "iteration": self.config.iteration,
            "seed": self.config.seed,
            "duration_seconds": self.config.duration_seconds,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "elapsed_seconds": (self.end_time - self.start_time).total_seconds(),
            "success": self.success,
            "rtt_min_ms": self.rtt_min_ms,
            "rtt_avg_ms": self.rtt_avg_ms,
            "rtt_max_ms": self.rtt_max_ms,
            "packet_loss_pct": self.packet_loss_pct,
            "throughput_mbps": self.throughput_mbps,
            "goodput_mbps": self.goodput_mbps,
            "late_frame_ratio": self.late_frame_ratio,
            "rebuffer_ratio": self.rebuffer_ratio,
            "vmaf_score": self.vmaf_score,
            "error_message": self.error_message,
        }


class ExperimentRunner:
    """에뮬레이션 실험 러너.
    
    토폴로지 생성, 실험 실행, 결과 수집을 관리한다.
    """
    
    def __init__(
        self,
        output_dir: Path,
        seed_base: int = 20260331,
    ) -> None:
        """러너 초기화.
        
        Args:
            output_dir: 결과 저장 디렉토리
            seed_base: 시드 기본값
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.seed_base = seed_base
        self.results: List[ExperimentResult] = []
    
    def _create_config(
        self,
        profile_name: str,
        iteration: int,
        **kwargs: Any,
    ) -> ExperimentConfig:
        """실험 설정 생성."""
        seed = self.seed_base + iteration
        return ExperimentConfig(
            profile_name=profile_name,
            iteration=iteration,
            seed=seed,
            **kwargs,
        )
    
    def _run_ping_test(
        self,
        topology: VideoStreamingTopology,
        count: int = 20,
    ) -> Dict[str, float]:
        """Ping 테스트 실행."""
        return topology.ping_test(count=count)
    
    def _run_iperf_test(
        self,
        topology: VideoStreamingTopology,
        duration_seconds: float = 10.0,
    ) -> Dict[str, float]:
        """iperf3로 throughput 측정.
        
        서버에서 iperf3 서버 시작 → 클라이언트에서 테스트 실행.
        """
        result = {"throughput_mbps": 0.0, "goodput_mbps": 0.0}
        
        # 서버 시작
        server_stdout, _, _ = topology.run_command(
            "server",
            "iperf3 -s -D -1"  # daemon mode, one-off
        )
        time.sleep(1)  # 서버 시작 대기
        
        # 클라이언트 테스트
        client_stdout, stderr, rc = topology.run_command(
            "client0",
            f"iperf3 -c {topology.server_ip} -t {int(duration_seconds)} -J"
        )
        
        if rc != 0:
            logger.warning("iperf3 테스트 실패: %s", stderr)
            return result
        
        try:
            iperf_result = json.loads(client_stdout)
            # bits_per_second → Mbps
            result["throughput_mbps"] = iperf_result.get("end", {}).get(
                "sum_sent", {}
            ).get("bits_per_second", 0) / 1_000_000
            result["goodput_mbps"] = iperf_result.get("end", {}).get(
                "sum_received", {}
            ).get("bits_per_second", 0) / 1_000_000
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("iperf3 결과 파싱 실패: %s", e)
        
        return result
    
    def run_single_experiment(
        self,
        config: ExperimentConfig,
        with_streaming: bool = False,
    ) -> ExperimentResult:
        """단일 실험 실행.
        
        Args:
            config: 실험 설정
            with_streaming: 스트리밍 테스트 포함 여부
            
        Returns:
            ExperimentResult
        """
        start_time = datetime.now()
        
        try:
            from scripts.emulation_topology import VideoStreamingTopology, NETWORK_PRESETS
            
            profile = NETWORK_PRESETS.get(config.profile_name)
            if profile is None:
                raise ValueError(f"Unknown profile: {config.profile_name}")
            
            with VideoStreamingTopology(n_clients=1, profile=profile) as topology:
                # Ping 테스트
                ping_result = self._run_ping_test(topology)
                
                # Throughput 테스트
                iperf_result = self._run_iperf_test(
                    topology,
                    duration_seconds=min(config.duration_seconds, 10.0),
                )
                
                end_time = datetime.now()
                
                return ExperimentResult(
                    config=config,
                    start_time=start_time,
                    end_time=end_time,
                    success=True,
                    rtt_min_ms=ping_result.get("min_ms", 0.0),
                    rtt_avg_ms=ping_result.get("avg_ms", 0.0),
                    rtt_max_ms=ping_result.get("max_ms", 0.0),
                    packet_loss_pct=ping_result.get("loss_pct", 0.0),
                    throughput_mbps=iperf_result.get("throughput_mbps", 0.0),
                    goodput_mbps=iperf_result.get("goodput_mbps", 0.0),
                )
                
        except Exception as e:
            end_time = datetime.now()
            logger.error("실험 실패: %s", e)
            return ExperimentResult(
                config=config,
                start_time=start_time,
                end_time=end_time,
                success=False,
                error_message=str(e),
            )
    
    def run_experiments(
        self,
        profile_names: List[str],
        n_iterations: int = 10,
        duration_seconds: float = 30.0,
    ) -> pd.DataFrame:
        """여러 프로파일/반복으로 실험 실행.
        
        Args:
            profile_names: 테스트할 네트워크 프로파일 이름 목록
            n_iterations: 각 프로파일당 반복 횟수
            duration_seconds: 각 실험 지속 시간
            
        Returns:
            DataFrame: 실험 결과
        """
        self.results.clear()
        total_experiments = len(profile_names) * n_iterations
        completed = 0
        
        logger.info(
            "실험 시작: %d profiles × %d iterations = %d experiments",
            len(profile_names), n_iterations, total_experiments
        )
        
        for profile_name in profile_names:
            for iteration in range(n_iterations):
                config = self._create_config(
                    profile_name=profile_name,
                    iteration=iteration,
                    duration_seconds=duration_seconds,
                )
                
                logger.info(
                    "실험 %d/%d: profile=%s, iteration=%d",
                    completed + 1, total_experiments, profile_name, iteration
                )
                
                result = self.run_single_experiment(config)
                self.results.append(result)
                completed += 1
                
                # 중간 저장
                if completed % 5 == 0:
                    self._save_intermediate_results()
        
        # 최종 결과 저장
        df = self._save_final_results()
        logger.info("실험 완료: %d/%d 성공", sum(r.success for r in self.results), len(self.results))
        
        return df
    
    def _save_intermediate_results(self) -> None:
        """중간 결과 저장."""
        path = self.output_dir / "intermediate_results.csv"
        df = pd.DataFrame([r.to_dict() for r in self.results])
        df.to_csv(path, index=False)
    
    def _save_final_results(self) -> pd.DataFrame:
        """최종 결과 저장."""
        df = pd.DataFrame([r.to_dict() for r in self.results])
        
        # CSV 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = self.output_dir / f"emulation_results_{timestamp}.csv"
        df.to_csv(csv_path, index=False)
        logger.info("결과 저장: %s", csv_path)
        
        # 요약 통계 저장
        summary = df.groupby("profile_name").agg({
            "success": "mean",
            "rtt_avg_ms": ["mean", "std"],
            "packet_loss_pct": ["mean", "std"],
            "throughput_mbps": ["mean", "std"],
        }).round(3)
        
        summary_path = self.output_dir / f"emulation_summary_{timestamp}.csv"
        summary.to_csv(summary_path)
        logger.info("요약 저장: %s", summary_path)
        
        return df
    
    def generate_report(self) -> str:
        """결과 리포트 생성."""
        if not self.results:
            return "결과 없음"
        
        df = pd.DataFrame([r.to_dict() for r in self.results])
        
        lines = [
            "# 에뮬레이션 실험 리포트",
            "",
            f"- 총 실험 수: {len(self.results)}",
            f"- 성공률: {df['success'].mean() * 100:.1f}%",
            "",
            "## 프로파일별 결과",
            "",
        ]
        
        for profile_name in df["profile_name"].unique():
            profile_df = df[df["profile_name"] == profile_name]
            lines.extend([
                f"### {profile_name}",
                f"- RTT (avg): {profile_df['rtt_avg_ms'].mean():.2f} ± {profile_df['rtt_avg_ms'].std():.2f} ms",
                f"- Packet Loss: {profile_df['packet_loss_pct'].mean():.2f}%",
                f"- Throughput: {profile_df['throughput_mbps'].mean():.2f} ± {profile_df['throughput_mbps'].std():.2f} Mbps",
                "",
            ])
        
        return "\n".join(lines)


class MockRunner:
    """[DEPRECATED] Mininet 없이 테스트용 모의 러너.
    
    ⚠️ 경고: 이 클래스는 가짜 데이터를 생성합니다. 실제 연구에는 적합하지 않습니다.
    
    Windows에서 실제 네트워크 테스트가 필요하면 다음을 사용하세요:
        - scripts/network_emulator.py (실제 TCP 소켓 통신 + 지연/손실 시뮬레이션)
    
    사용 예시:
        py -3 scripts/network_emulator.py server --port 8080 --profile wifi_congested
        py -3 scripts/network_emulator.py client --server localhost:8080 --frames 300
    """
    
    def __init__(self, output_dir: Path) -> None:
        import warnings
        warnings.warn(
            "MockRunner는 가짜 데이터를 생성합니다. "
            "실제 테스트는 scripts/network_emulator.py를 사용하세요.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def run_mock_experiments(
        self,
        profile_names: List[str],
        n_iterations: int = 10,
    ) -> pd.DataFrame:
        """모의 실험 데이터 생성."""
        rng = np.random.default_rng(20260331)
        
        rows = []
        for profile_name in profile_names:
            # 프로파일별 기본 특성
            if "wifi_good" in profile_name:
                base_rtt, rtt_std = 10.0, 2.0
                base_loss = 0.1
                base_throughput = 40.0
            elif "wifi_congested" in profile_name:
                base_rtt, rtt_std = 30.0, 15.0
                base_loss = 2.0
                base_throughput = 8.0
            elif "lte_normal" in profile_name:
                base_rtt, rtt_std = 40.0, 10.0
                base_loss = 0.5
                base_throughput = 15.0
            else:  # lte_poor
                base_rtt, rtt_std = 100.0, 40.0
                base_loss = 5.0
                base_throughput = 3.0
            
            for i in range(n_iterations):
                rows.append({
                    "profile_name": profile_name,
                    "iteration": i,
                    "seed": 20260331 + i,
                    "success": True,
                    "rtt_min_ms": max(1.0, base_rtt - rtt_std + rng.normal(0, rtt_std * 0.5)),
                    "rtt_avg_ms": max(1.0, base_rtt + rng.normal(0, rtt_std)),
                    "rtt_max_ms": max(1.0, base_rtt + rtt_std + rng.normal(0, rtt_std * 0.5)),
                    "packet_loss_pct": max(0.0, base_loss + rng.normal(0, base_loss * 0.3)),
                    "throughput_mbps": max(0.1, base_throughput + rng.normal(0, base_throughput * 0.2)),
                    "goodput_mbps": max(0.1, base_throughput * 0.95 + rng.normal(0, base_throughput * 0.2)),
                })
        
        df = pd.DataFrame(rows)
        
        # 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = self.output_dir / f"mock_emulation_results_{timestamp}.csv"
        df.to_csv(csv_path, index=False)
        logger.info("모의 결과 저장: %s", csv_path)
        
        return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Mininet 에뮬레이션 실험 러너")
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["wifi_good", "wifi_congested", "lte_normal", "lte_poor"],
        help="테스트할 네트워크 프로파일 목록",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="각 프로파일당 반복 횟수",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="각 실험 지속 시간 (초)",
    )
    parser.add_argument(
        "--output",
        default="output/emulation",
        help="결과 저장 디렉토리",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Mininet 없이 모의 데이터 생성 (테스트용)",
    )
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    
    output_dir = Path(args.output)
    
    if args.mock:
        logger.info("모의 실험 모드 (Mininet 없음)")
        runner = MockRunner(output_dir)
        df = runner.run_mock_experiments(args.profiles, args.iterations)
    else:
        # root 권한 확인
        if os.geteuid() != 0:
            logger.error("Mininet 실험은 root 권한이 필요합니다. 'sudo'를 사용하세요.")
            sys.exit(1)
        
        runner = ExperimentRunner(output_dir)
        df = runner.run_experiments(
            profile_names=args.profiles,
            n_iterations=args.iterations,
            duration_seconds=args.duration,
        )
        
        print("\n" + runner.generate_report())
    
    print(f"\n결과 저장 위치: {output_dir}")


if __name__ == "__main__":
    main()
