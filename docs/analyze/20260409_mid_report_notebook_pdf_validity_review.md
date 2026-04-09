# 2026-04-09 중간보고서 제출용 PDF 대비 노트북 타당성 점검

작성일: 2026-04-09  
대상 브랜치: `mid-report-improvement`  
대상 노트북: `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb`  
대상 PDF: `중간보고서 제출용/1차_박동찬_[붙임1]구술평가2_논문양식.pdf`

## 총평

- **수치 정합성은 대체로 높다.**
  - PDF의 표 1, 표 2, 표 3 수치는 노트북 산출 CSV와 사실상 일치한다.
- **연구 방향 정합성도 대체로 맞다.**
  - Stage A 중요도 산정, Stage B 행동 선택, `late_frame_ratio` 중심 평가는 현재 코드와 부합한다.
- **하지만 구현 범위를 넘는 표현이 있다.**
  - 현재 코드는 실제 QUIC/MPR-QUIC 프로토콜 구현이 아니라, 프레임 행동을 반영한 시뮬레이션 근사 모델이다.
- **논문 양식 준수는 미흡하다.**
  - 표/그림 표기, 키워드 수, 일부 인용 표현은 양식 기준에서 바로 수정이 필요하다.

## 코드-문서 정합성

### 일치하는 부분

- Stage A 점수식
  - `policy/importance.py`에서 `0.45 * type_score + 0.40 * urgency + keyframe_bonus`로 계산한다.
- Stage B 행동 집합
  - `policy/action.py`에서 `RELIABLE_SINGLE`, `RELIABLE_MULTI`, `UNRELIABLE`, `DUPLICATE`, `DROP`을 정의한다.
- 실험 파라미터
  - 노트북은 `RTT=10ms`, `bandwidth=5Mbps`, `delayed_ack=40ms`로 설정한다.
- 핵심 지표
  - `late_frame_ratio`, `dropped_frame_ratio`, `useful_goodput_bytes`, `decodable_gop_ratio`를 실제로 집계한다.
- 표 수치
  - PDF 표 1, 2, 3 값은 `midreport_ipb_summary.csv`, `midreport_transport_efficiency.csv`의 집계와 일치한다.

### 불일치하거나 과장된 부분

- QUIC/MPR-QUIC 실제 구현처럼 보이게 쓰면 과장이다.
  - 실제 실행 경로는 `core/simulator.py`의 근사 completion 계산이며, `core/transport.py`의 QUIC 모델은 노트북 실험에 직접 쓰이지 않는다.
- `DUPLICATE` 행동은 코드에는 있으나 현재 결과에서는 한 번도 사용되지 않았다.
  - 즉, “다섯 행동을 모두 실험적으로 검증했다”는 식의 인상은 주면 안 된다.
- 다중경로도 실제 프로토콜 검증이 아니라, 이질 경로를 가정한 경량 시뮬레이션이다.

## 논문 양식 점검

### 미준수 또는 위험 항목

- 표 제목이 `Table 1.` 형식의 영문 캡션이 아니라 `표 1.` 형식이다.
- 그림/표 내용도 양식상 영문 표기를 원칙으로 요구하는데 현재 문서는 그렇지 않다.
- 키워드가 4개라서 양식의 `5-6개 내외` 요구에 못 미친다.
- `3.2`의 `HSDPA(3G) 14.4 Mbps [7]`는 참고문헌 [7]과 직접 대응되지 않아 인용 정합성이 약하다.
- `useful_goodput_bytes` 성격의 값을 표에서 비율처럼 읽히게 적은 부분은 표현 수정이 필요하다.

## 결론

- **타당성**: 현재 PDF의 핵심 결과 수치와 노트북 계산은 대체로 타당하다.
- **한계**: 다만 “실제 QUIC/MPR-QUIC 전송 구현 결과”처럼 읽히는 표현은 현재 코드 수준보다 강하다.
- **양식 준수**: 현재 상태를 엄격히 보면 **완전 준수는 아니다**. 표/그림 캡션, 키워드 수, 인용 표현은 수정 권장이다.
