# dataset 안내

## 목적

- `dataset/videos/`는 실제 실험 입력인 원본 MP4를 보관한다.
- `dataset/traces/`는 원본 비디오에서 생성한 trace CSV 캐시를 보관한다.

## 규칙

- 실제 비디오가 없는 trace CSV 단독 실험은 허용하지 않는다.
- trace CSV는 `scripts/video_trace_prepare.py`로만 생성한다.
- synthetic payload나 임의 생성 비디오 데이터는 두지 않는다.

## 현재 기본 대상

- `archive_popeye_512kb.mp4`
- `echo_mediaelement.mp4`
- `w3c_movie_300.mp4`
