중간 보고 이후


after-mid-1의 연구 구성은 이렇습니다.

연구 주제: 실제 비디오 전송에서 콘텐츠 중요도와 전송 결정을 결합하는 cross-layer 적응 전송.

입력: 실제 MP4 원본 비디오와 원본에서 만든 frame/cache metadata.

정책 비교:

heuristic_frame_aware
frame_action_single_path
deadline_feasible_frame_action
실험 방식: Mininet에서 실제 TCP/UDP 전송을 수행하고, 실제 송신 시각·수신 시각·전송 바이트로 지표 계산.

평가 지표: late frame, keyframe late, decodable GOP, on-time goodput, wasted late bytes.

현재 핵심 쟁점은 deadline_feasible_frame_action이 낮은 RTT에서는 개선되지만, 1 Mbps / RTT 50 ms에서는 I-frame deadline miss 때문에 아직 baseline을 넘지 못한다는 점입니다.