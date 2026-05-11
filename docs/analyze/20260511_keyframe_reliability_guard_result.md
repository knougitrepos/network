# keyframe reliability guard 재실험 결과

작성일: 2026-05-11

## 실험 조건

- video: `archive_popeye_512kb`
- policy: `deadline_feasible_frame_action`
- bandwidth: `1 Mbps`
- RTT: `50 ms`
- loss: `0%`
- repeat: `3`
- 실행 경로: WSL2 Ubuntu Mininet actual experiment

## 확인된 결과

`keyframe reliable 보호 정책 추가` 커밋 이후 동일 조건을 재실험했다. 산출물은 `output/mininet_actual_experiment/archive_popeye_512kb/deadline_feasible_frame_action/1mbps_rtt50ms_loss0pct/` 아래에 생성되었다.

요약 지표는 다음과 같다.

- late frame: `2873/33294`
- late frame ratio: `0.08629182435273623`
- keyframe late ratio: `0.7091891891891892`
- decodable GOP ratio: `0.2897297297297297`
- on-time goodput ratio: `0.7497654412217709`
- wasted late bytes ratio: `0.25023455877822914`
- reliable single count: `2775`
- unreliable count: `30495`
- drop count: `24`
- reliable single late count: `1968`
- unreliable late count: `881`

반복별 로그에서 client는 각 repeat마다 `11098` 프레임 처리를 완료했고, server는 각 repeat마다 `11090` 프레임 수신을 완료했다. repeat별 keyframe late ratio와 decodable GOP ratio는 모두 동일하게 각각 `0.7091891891891892`, `0.2897297297297297`로 나타났다.

## 해석

hard keyframe guard는 RTT `50 ms`, bandwidth `1 Mbps` 조건에서 개선이 아니라 회귀를 만들었다. I-frame 전체가 `RELIABLE_SINGLE`로 이동했지만, TCP 지연 때문에 keyframe deadline miss가 증가했고 GOP 복호 가능성도 낮아졌다.

따라서 다음 수정은 keyframe을 무조건 reliable로 고정하는 방식이 아니라 deadline-aware keyframe guard로 바꾸는 것이 타당하다. keyframe도 deadline 내 도착 가능성이 낮으면 TCP 고집을 줄이고, UDP best-effort 또는 후속 FEC 조합 후보로 넘겨야 한다.
