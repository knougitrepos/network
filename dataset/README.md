# dataset 사용 안내

- 원본 비디오는 `dataset/videos/`에 넣습니다.
- 프레임 트레이스 CSV는 `dataset/traces/`에 자동 생성됩니다.
- 중간보고용 노트북 `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb`는 이 경로를 기본 입력으로 사용합니다.

## 권장 파일명 형식

- `<group>_<name>_<resolution>_<bitrate>.mp4`
- 예: `animation_bbb_720p_2mbps.mp4`

## 최소 메타 정보

- group: 유사 계열 그룹명 (예: animation, nature, sports)
- video_name: 영상 식별명
- motion_level: low / medium / high
