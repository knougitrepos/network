# 노트북 실행 결과 분석 리포트

작성일: 2026-03-31  
대상 파일: `output/jupyter-notebook/tcp-content-aware-batching.ipynb`  
검증 기준: 노트북 실행 산출물(`output/jupyter-notebook/assets/*.csv`)

## 1) 정상 작동 여부

결론: **정상 작동으로 판단됩니다.**

근거:
- `ml_label_model_comparison.csv`가 생성됨
- `policy_action_summary.csv`가 생성됨
- 비교 모델별 지표 값이 실제로 계산되어 저장됨
- 특히 `frame_action_ml_delta_qoe`는 다른 모델과 **다른 행동 분포**를 보임

즉, “모든 결과가 완전히 동일”한 상태는 현재 해소된 것으로 보입니다.

## 2) 핵심 결과 해석 (쉽게 설명)

## 2-1. 모델별 중요도 평균
- `frame_action_adaptive(heuristic)`: 약 **0.124**
- `frame_action_ml_bootstrap(ml)`: 약 **0.124**
- `frame_action_ml_delta_qoe(ml)`: 약 **0.0077**

해석:
- `delta_qoe` 모델은 프레임 중요도를 전체적으로 매우 낮게 평가합니다.
- 그래서 전송 행동을 더 보수적으로/차등적으로 선택하게 됩니다.

## 2-2. QoE 위험 지표 비교
- 지연 프레임 비율(`late_frame_ratio`)
  - heuristic / bootstrap: **0.0167**
  - delta_qoe: **0.0467** (상대적으로 높음)
- 드롭 비율(`dropped_frame_ratio`)
  - heuristic / bootstrap: **0.0067**
  - delta_qoe: **0.03** (상대적으로 높음)

해석:
- `delta_qoe` 모델은 행동을 더 공격적으로 바꾸는 대신, 지연/드롭이 다소 늘어났습니다.

## 2-3. 전송 행동 분포 비교

### heuristic / ml_bootstrap
- reliable_single: 1
- reliable_multi: 2
- unreliable: 295
- duplicate: 0
- drop: 2

### ml_delta_qoe
- reliable_single: 0
- reliable_multi: 137
- unreliable: 80
- duplicate: 74
- drop: 9

해석:
- `delta_qoe` 모델은 단순히 `unreliable`에 몰리지 않고,  
  `reliable_multi`, `duplicate`, `drop`까지 폭넓게 사용합니다.
- 즉, **행동 정책이 실제로 달라졌고**, 모델별 차이가 반영되고 있습니다.

## 3) 현재 상태 평가

- 장점
  - 모델별 행동 차이가 실제 수치로 나타남
  - 결과 파일/그래프 산출이 정상적으로 이뤄짐
- 점검 필요
  - `keyframe_late_ratio=1.0`, `decodable_gop_ratio=0.0`은 매우 불리한 상태를 의미하므로,
    시나리오/버퍼 파라미터/정책 가중치를 추가 점검할 필요가 있음

## 4) 최종 요약

현재 노트북은 **실행 파이프라인 자체는 정상**입니다.  
또한 모델 비교 결과도 실제로 분화되어, 이전의 “모두 동일한 결과” 문제는 개선된 상태입니다.  
다만 `delta_qoe` 모델은 현재 설정에서 지연/드롭이 증가하므로,  
추가 튜닝(임계값, 보상 가중치, 버퍼 관련 파라미터)이 다음 단계로 권장됩니다.
