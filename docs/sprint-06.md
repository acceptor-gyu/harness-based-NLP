# Sprint-06: Gradio UI

## 개요

| 항목 | 내용 |
|------|------|
| 스프린트 | sprint-06 |
| 제목 | Gradio UI (선택) |
| 브랜치 | `sprint-06/gradio-ui` |
| 완료일 | 2026-05-12 |
| 판정 | **PASS** (AC-06-01, AC-06-02, AC-06-03 전체 PASS) |

## 목표

klue/roberta-base 파인튜닝 모델을 Gradio Interface로 서빙한다.
- 텍스트 입력 → 긍정/부정 + 신뢰도 출력
- 모델 로딩은 앱 시작 시 1회 (캐시)
- 배포 스크립트 제공

## 구현 내용

### src/serve.py

Gradio UI 서빙 모듈. 주요 구성 요소:

| 컴포넌트 | 역할 |
|----------|------|
| `_ModelCache` | 전역 모델+토크나이저 캐시. `load()` 최초 1회 호출 후 재사용 |
| `predict(text)` | 텍스트 전처리 → 토크나이즈 → 추론. `(label, confidence, elapsed)` 반환 |
| `_gradio_predict(text)` | Gradio Label 컴포넌트용 래퍼. `{label: confidence}` 딕셔너리 반환 |
| `build_interface()` | Gradio Interface 빌드 (텍스트 입력 → Label 출력, 예시 포함) |
| `main()` | 서버 기동 엔트리포인트 (host=0.0.0.0, port=7860) |

**실행 방법:**
```bash
uv run python -m src.serve
# 또는
bash scripts/serve.sh
```

### scripts/serve.sh

배포 스크립트. `uv sync` → `uv run python -m src.serve` 순으로 실행.

```bash
bash scripts/serve.sh               # 기본 (localhost:7860)
bash scripts/serve.sh --port 7861   # 포트 변경
bash scripts/serve.sh --share       # Gradio 공개 링크 생성
```

## Acceptance Criteria 판정

| AC | 설명 | 판정 | 근거 |
|----|------|------|------|
| AC-06-01 | 로컬 실행 시 Gradio Interface 빌드 가능 | PASS | `build_interface()` 정상 호출 확인 |
| AC-06-02 | '이 영화 정말 재미있어요!' → 긍정 (신뢰도 > 0.9) | PASS | confidence=0.9804 |
| AC-06-03 | 단일 요청 응답 시간 < 1초 (CPU 기준) | PASS | elapsed=0.026s (워밍업 후) |

## 성능

| 지표 | 값 |
|------|-----|
| 예측 신뢰도 ('이 영화 정말 재미있어요!') | 0.9804 |
| 응답 시간 (워밍업 후) | 0.026s |
| 모델 | klue/roberta-base (best_20260507T122610Z.pt) |
| Gradio 버전 | 6.13.0 |
| 서빙 디바이스 | MPS (Apple Silicon) |

## 의존성 변경

`gradio>=4.44.0` 추가 (`uv add "gradio>=4.44.0"`, 실제 설치: gradio==6.13.0)

## 전체 프로젝트 완료

sprint-06은 한국어 감성 분석기 프로젝트의 마지막 스프린트입니다. 모든 6개 스프린트가 PASS 판정을 받았습니다.

| 스프린트 | 제목 | 판정 |
|----------|------|------|
| sprint-01 | 환경 세팅 및 데이터 로드 | PASS |
| sprint-02 | 전처리 파이프라인 | PASS |
| sprint-03 | 베이스라인 모델 (TF-IDF + LogReg) | PASS |
| sprint-04 | BERT 파인튜닝 | PASS |
| sprint-05 | 평가 및 리포트 | PASS |
| sprint-06 | Gradio UI (선택) | PASS |
