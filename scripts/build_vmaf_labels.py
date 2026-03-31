"""실측 VMAF/SSIM 기반 ΔQoE 라벨 생성 스크립트.

FFmpeg + libvmaf를 활용하여 프레임 drop 시 실제 품질 저하를 측정한다.
각 프레임을 drop했을 때의 VMAF/SSIM 차이를 계산하여 중요도 라벨로 사용한다.

사용 예시:
    python scripts/build_vmaf_labels.py \\
        --input data/videos/bbb_720p.mp4 \\
        --output data/video-traces/bbb_720p_vmaf_labels.csv

필수 의존성:
    - FFmpeg (libvmaf 포함)
    - PyAV (선택: 프레임 조작용)
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


logger = logging.getLogger(__name__)


@dataclass
class FrameInfo:
    """프레임 메타데이터."""
    frame_idx: int
    pts_ms: float
    duration_ms: float
    frame_type: str
    key_frame: int
    gop_id: int
    payload_bytes: int


@dataclass
class QualityMetrics:
    """VMAF/SSIM 품질 지표."""
    vmaf: float
    ssim: float
    psnr: float


def _check_ffmpeg_vmaf() -> bool:
    """FFmpeg VMAF 지원 여부 확인."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True,
            text=True,
            check=False,
        )
        return "libvmaf" in result.stdout
    except FileNotFoundError:
        return False


def _probe_frames(video_path: Path) -> List[Dict[str, Any]]:
    """ffprobe로 프레임 정보 추출."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_frames",
        "-show_entries",
        "frame=best_effort_timestamp_time,pkt_pts_time,pkt_dts_time,"
        "pkt_duration_time,pict_type,pkt_size,key_frame",
        "-of", "json",
        str(video_path),
    ]
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    return list(payload.get("frames", []))


def _float_or_default(value: Any, default: float = 0.0) -> float:
    """값을 float으로 변환, 실패 시 기본값 반환."""
    if value in (None, "", "N/A"):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_frame_info(frames: List[Dict[str, Any]]) -> List[FrameInfo]:
    """프레임 정보를 FrameInfo 객체로 변환."""
    result = []
    gop_id = -1
    
    # 프레임 간격 추정 (duration이 없는 경우 대비)
    pts_values = []
    for frame in frames:
        for key in ("best_effort_timestamp_time", "pkt_pts_time", "pkt_dts_time"):
            val = _float_or_default(frame.get(key), -1)
            if val >= 0:
                pts_values.append(val * 1000.0)
                break
    
    if len(pts_values) >= 2:
        diffs = [pts_values[i+1] - pts_values[i] for i in range(len(pts_values)-1) if pts_values[i+1] > pts_values[i]]
        fallback_duration_ms = float(np.median(diffs)) if diffs else 33.333
    else:
        fallback_duration_ms = 33.333
    
    for idx, frame in enumerate(frames):
        # PTS 추출
        pts_ms = -1.0
        for key in ("best_effort_timestamp_time", "pkt_pts_time", "pkt_dts_time"):
            val = _float_or_default(frame.get(key), -1)
            if val >= 0:
                pts_ms = val * 1000.0
                break
        if pts_ms < 0:
            pts_ms = idx * fallback_duration_ms
        
        # Duration 추출
        duration = _float_or_default(frame.get("pkt_duration_time"), -1)
        duration_ms = duration * 1000.0 if duration > 0 else fallback_duration_ms
        
        # 프레임 타입
        frame_type = str(frame.get("pict_type", "P")).upper()
        if frame_type not in ("I", "P", "B"):
            frame_type = "P"
        
        key_frame = int(frame.get("key_frame", 0))
        if frame_type == "I":
            gop_id += 1
        elif gop_id < 0:
            gop_id = 0
        
        payload_bytes = int(frame.get("pkt_size") or 0)
        
        result.append(FrameInfo(
            frame_idx=idx,
            pts_ms=pts_ms,
            duration_ms=duration_ms,
            frame_type=frame_type,
            key_frame=key_frame,
            gop_id=gop_id,
            payload_bytes=payload_bytes,
        ))
    
    return result


def _compute_vmaf_ssim(
    reference_path: Path,
    distorted_path: Path,
    vmaf_model: str = "vmaf_v0.6.1",
) -> QualityMetrics:
    """FFmpeg libvmaf를 사용하여 VMAF/SSIM/PSNR 계산.
    
    Args:
        reference_path: 원본 비디오 경로
        distorted_path: 비교 비디오 경로 (프레임 drop된 버전)
        vmaf_model: VMAF 모델 (vmaf_v0.6.1 또는 vmaf_4k_v0.6.1)
    
    Returns:
        QualityMetrics: VMAF, SSIM, PSNR 값
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        log_path = Path(tmp.name)
    
    try:
        # libvmaf 필터로 VMAF/SSIM/PSNR 동시 계산
        filter_complex = (
            f"[0:v][1:v]libvmaf=model=version={vmaf_model}:"
            f"log_path={log_path}:log_fmt=json:feature=name=psnr|name=ssim"
        )
        
        cmd = [
            "ffmpeg",
            "-i", str(distorted_path),
            "-i", str(reference_path),
            "-lavfi", filter_complex,
            "-f", "null", "-",
        ]
        
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        
        # 결과 파싱
        with log_path.open("r") as f:
            vmaf_result = json.load(f)
        
        pooled = vmaf_result.get("pooled_metrics", {})
        vmaf_score = pooled.get("vmaf", {}).get("mean", 0.0)
        ssim_score = pooled.get("ssim", {}).get("mean", 0.0)
        psnr_score = pooled.get("psnr", {}).get("mean", 0.0)
        
        # SSIM이 pooled_metrics에 없으면 frames에서 추출
        if ssim_score == 0.0:
            frames_data = vmaf_result.get("frames", [])
            if frames_data:
                ssim_values = [f.get("metrics", {}).get("ssim", 0.0) for f in frames_data]
                ssim_score = float(np.mean(ssim_values)) if ssim_values else 0.0
        
        return QualityMetrics(
            vmaf=float(vmaf_score),
            ssim=float(ssim_score),
            psnr=float(psnr_score),
        )
    
    finally:
        if log_path.exists():
            log_path.unlink()


def _compute_ssim_only(
    reference_path: Path,
    distorted_path: Path,
) -> float:
    """SSIM만 계산 (VMAF 없이)."""
    cmd = [
        "ffmpeg",
        "-i", str(distorted_path),
        "-i", str(reference_path),
        "-lavfi", "ssim=stats_file=-",
        "-f", "null", "-",
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    
    # stderr에서 SSIM 추출
    for line in result.stderr.split("\n"):
        if "All:" in line:
            # 예: "SSIM All:0.982345 (17.952)"
            try:
                ssim_str = line.split("All:")[1].split()[0]
                return float(ssim_str)
            except (IndexError, ValueError):
                pass
    
    return 0.0


def _create_dropped_frame_video(
    input_path: Path,
    output_path: Path,
    drop_frame_idx: int,
    frame_count: int,
) -> bool:
    """특정 프레임을 drop한 비디오 생성.
    
    drop된 프레임은 이전 프레임으로 대체 (freeze frame 효과).
    I-frame drop 시 해당 GOP 전체에 영향을 줄 수 있음.
    """
    # select 필터로 프레임 선택/복제
    # drop된 프레임 위치에 이전 프레임을 반복
    if drop_frame_idx == 0:
        # 첫 프레임 drop: 두 번째 프레임으로 대체
        select_expr = f"'if(eq(n,0),0,if(lt(n,{drop_frame_idx+1}),n,n))'"
    else:
        # 이전 프레임으로 대체
        select_expr = f"'if(eq(n,{drop_frame_idx}),{drop_frame_idx-1},n)'"
    
    # 더 간단한 접근: 프레임 drop 후 이전 프레임 복사
    # select 필터로 특정 프레임 제외 후 setpts로 타임스탬프 재조정
    filter_complex = f"select='not(eq(n\\,{drop_frame_idx}))',setpts=N/FRAME_RATE/TB"
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-vf", filter_complex,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "18",
        "-an",
        str(output_path),
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.warning("프레임 %d drop 비디오 생성 실패: %s", drop_frame_idx, e.stderr)
        return False


def _create_freeze_frame_video(
    input_path: Path,
    output_path: Path,
    freeze_frame_idx: int,
    frames_info: List[FrameInfo],
) -> bool:
    """특정 프레임 위치에서 이전 프레임을 freeze하는 비디오 생성.
    
    더 현실적인 drop 시뮬레이션: 해당 프레임이 도착하지 않으면
    이전 프레임이 표시됨 (freeze).
    """
    if freeze_frame_idx == 0:
        # 첫 프레임은 drop 시뮬레이션이 어려움
        return False
    
    # freeze_frame_idx 위치의 프레임을 이전 프레임으로 대체
    # 방법: 프레임을 추출하고 재조합
    
    # 간단한 접근: select 필터로 프레임 선택 조작
    # eq(n,X) 위치에서 이전 프레임(X-1) 표시
    
    # FFmpeg 표현식: 프레임 N에서 N-1의 프레임을 사용
    # 이를 위해 tpad나 loop 사용이 복잡하므로,
    # 실제로는 프레임을 제외하고 fps 유지하는 방식 사용
    
    filter_expr = (
        f"select='if(eq(n\\,{freeze_frame_idx})\\,0\\,1)',"
        f"setpts=N/FRAME_RATE/TB"
    )
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-vf", filter_expr,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "18",
        "-an",
        str(output_path),
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.warning("프레임 %d freeze 비디오 생성 실패: %s", freeze_frame_idx, e.stderr)
        return False


def compute_frame_importance_vmaf(
    video_path: Path,
    frames_info: List[FrameInfo],
    sample_ratio: float = 1.0,
    use_vmaf: bool = True,
) -> pd.DataFrame:
    """각 프레임의 중요도를 VMAF/SSIM 기반으로 계산.
    
    Args:
        video_path: 입력 비디오 경로
        frames_info: 프레임 정보 리스트
        sample_ratio: 샘플링 비율 (1.0 = 전체, 0.1 = 10%)
        use_vmaf: VMAF 사용 여부 (False면 SSIM만 사용)
    
    Returns:
        DataFrame: 프레임별 중요도 라벨
    """
    # 먼저 baseline 품질 계산
    logger.info("Baseline 품질 계산 중...")
    
    has_vmaf = _check_ffmpeg_vmaf()
    if use_vmaf and not has_vmaf:
        logger.warning("FFmpeg에 libvmaf가 없습니다. SSIM만 사용합니다.")
        use_vmaf = False
    
    # 샘플링할 프레임 선택
    n_frames = len(frames_info)
    if sample_ratio < 1.0:
        n_samples = max(1, int(n_frames * sample_ratio))
        # I-frame은 반드시 포함, 나머지는 균등 샘플링
        i_frame_indices = [f.frame_idx for f in frames_info if f.frame_type == "I"]
        other_indices = [f.frame_idx for f in frames_info if f.frame_type != "I"]
        
        # I-frame 외 나머지에서 균등 샘플링
        n_others = n_samples - len(i_frame_indices)
        if n_others > 0 and other_indices:
            step = max(1, len(other_indices) // n_others)
            sampled_others = other_indices[::step][:n_others]
        else:
            sampled_others = []
        
        sample_indices = set(i_frame_indices + sampled_others)
    else:
        sample_indices = set(range(n_frames))
    
    logger.info("총 %d개 프레임 중 %d개 샘플링", n_frames, len(sample_indices))
    
    # 각 프레임 drop 시 품질 저하 계산
    results = []
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        for frame in frames_info:
            idx = frame.frame_idx
            
            # 기본값으로 초기화
            row = {
                "frame_idx": idx,
                "pts_ms": frame.pts_ms,
                "duration_ms": frame.duration_ms,
                "frame_type": frame.frame_type,
                "key_frame": frame.key_frame,
                "gop_id": frame.gop_id,
                "payload_bytes": frame.payload_bytes,
                "delta_vmaf": 0.0,
                "delta_ssim": 0.0,
                "delta_qoe": 0.0,
                "sampled": idx in sample_indices,
            }
            
            if idx not in sample_indices:
                # 샘플링되지 않은 프레임: 같은 타입의 평균으로 나중에 보간
                results.append(row)
                continue
            
            # Drop 비디오 생성
            dropped_path = tmpdir_path / f"dropped_{idx}.mp4"
            success = _create_freeze_frame_video(
                video_path,
                dropped_path,
                idx,
                frames_info,
            )
            
            if not success:
                logger.debug("프레임 %d skip (비디오 생성 실패)", idx)
                results.append(row)
                continue
            
            # 품질 비교
            try:
                if use_vmaf:
                    metrics = _compute_vmaf_ssim(video_path, dropped_path)
                    # baseline은 100 (완벽한 품질), drop 시 저하량 계산
                    # 여기서는 단순화: drop된 비디오 vs 원본의 차이
                    row["delta_vmaf"] = 100.0 - metrics.vmaf
                    row["delta_ssim"] = 1.0 - metrics.ssim
                else:
                    ssim = _compute_ssim_only(video_path, dropped_path)
                    row["delta_ssim"] = 1.0 - ssim
                    row["delta_vmaf"] = row["delta_ssim"] * 100.0  # 근사값
                
                # 통합 QoE (VMAF 기반, 0-100 스케일)
                row["delta_qoe"] = row["delta_vmaf"]
                
            except Exception as e:
                logger.warning("프레임 %d 품질 계산 실패: %s", idx, e)
            
            results.append(row)
            
            if (idx + 1) % 50 == 0:
                logger.info("진행: %d/%d 프레임", idx + 1, n_frames)
    
    df = pd.DataFrame(results)
    
    # 샘플링되지 않은 프레임 보간 (같은 타입의 평균으로)
    if sample_ratio < 1.0:
        for frame_type in ["I", "P", "B"]:
            mask_sampled = (df["frame_type"] == frame_type) & (df["sampled"])
            mask_not_sampled = (df["frame_type"] == frame_type) & (~df["sampled"])
            
            if mask_sampled.any() and mask_not_sampled.any():
                avg_delta_vmaf = df.loc[mask_sampled, "delta_vmaf"].mean()
                avg_delta_ssim = df.loc[mask_sampled, "delta_ssim"].mean()
                avg_delta_qoe = df.loc[mask_sampled, "delta_qoe"].mean()
                
                df.loc[mask_not_sampled, "delta_vmaf"] = avg_delta_vmaf
                df.loc[mask_not_sampled, "delta_ssim"] = avg_delta_ssim
                df.loc[mask_not_sampled, "delta_qoe"] = avg_delta_qoe
    
    # 정규화: delta_qoe_norm (0-1 스케일)
    max_delta = df["delta_qoe"].max()
    if max_delta > 0:
        df["delta_qoe_norm"] = df["delta_qoe"] / max_delta
    else:
        df["delta_qoe_norm"] = 0.0
    
    # 라벨 모드 표시
    df["label_mode"] = "vmaf_ssim_v1" if use_vmaf else "ssim_only_v1"
    
    return df


def build_vmaf_labels(
    video_path: Path,
    output_path: Path,
    sample_ratio: float = 1.0,
    use_vmaf: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """VMAF/SSIM 기반 라벨 생성 메인 함수.
    
    Args:
        video_path: 입력 비디오 경로
        output_path: 출력 CSV 경로
        sample_ratio: 프레임 샘플링 비율
        use_vmaf: VMAF 사용 여부
    
    Returns:
        Tuple[DataFrame, DataFrame]: (라벨 데이터, 요약 통계)
    """
    # 프레임 정보 추출
    logger.info("프레임 정보 추출 중: %s", video_path)
    raw_frames = _probe_frames(video_path)
    if not raw_frames:
        raise ValueError(f"비디오에서 프레임을 추출할 수 없습니다: {video_path}")
    
    frames_info = _parse_frame_info(raw_frames)
    logger.info("추출된 프레임 수: %d", len(frames_info))
    
    # VMAF/SSIM 기반 중요도 계산
    labels_df = compute_frame_importance_vmaf(
        video_path,
        frames_info,
        sample_ratio=sample_ratio,
        use_vmaf=use_vmaf,
    )
    
    # 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    labels_df.to_csv(output_path, index=False)
    logger.info("라벨 저장 완료: %s (%d rows)", output_path, len(labels_df))
    
    # 요약 통계
    summary_df = (
        labels_df.groupby("frame_type", sort=False)["delta_qoe_norm"]
        .agg(["count", "mean", "median", "max", "std"])
        .reset_index()
    )
    
    return labels_df, summary_df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VMAF/SSIM 기반 실측 ΔQoE 라벨 생성"
    )
    parser.add_argument("--input", required=True, help="입력 비디오 경로")
    parser.add_argument("--output", required=True, help="출력 라벨 CSV 경로")
    parser.add_argument(
        "--sample-ratio",
        type=float,
        default=1.0,
        help="프레임 샘플링 비율 (0.0-1.0, 기본: 1.0)",
    )
    parser.add_argument(
        "--no-vmaf",
        action="store_true",
        help="VMAF 대신 SSIM만 사용",
    )
    parser.add_argument(
        "--trace-output",
        default="",
        help="프레임 trace CSV 출력 경로 (선택)",
    )
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    
    video_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    
    if not video_path.exists():
        raise FileNotFoundError(f"비디오 파일을 찾을 수 없습니다: {video_path}")
    
    # FFmpeg 확인
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("FFmpeg가 설치되어 있지 않습니다.")
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe가 설치되어 있지 않습니다.")
    
    labels_df, summary_df = build_vmaf_labels(
        video_path=video_path,
        output_path=output_path,
        sample_ratio=args.sample_ratio,
        use_vmaf=not args.no_vmaf,
    )
    
    logger.info("라벨 요약 (frame_type별):\n%s", summary_df.to_string(index=False))
    
    # trace 출력 (선택)
    if args.trace_output:
        trace_path = Path(args.trace_output).resolve()
        trace_df = labels_df[[
            "frame_idx", "pts_ms", "duration_ms", "frame_type",
            "payload_bytes", "key_frame", "gop_id",
        ]].copy()
        trace_df["importance_rank"] = trace_df["frame_type"].map({"I": 0, "P": 1, "B": 2})
        trace_df["display_deadline_ms"] = trace_df["pts_ms"] + trace_df["duration_ms"] + 50.0
        trace_df = trace_df.rename(columns={"frame_idx": "event_idx"})
        trace_df.to_csv(trace_path, index=False)
        logger.info("Trace 저장 완료: %s", trace_path)


if __name__ == "__main__":
    main()
