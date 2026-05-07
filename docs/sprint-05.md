# Sprint-05: 평가 및 리포트

## 개요

| 항목 | 내용 |
|------|------|
| 스프린트 | sprint-05 |
| 제목 | 평가 및 리포트 |
| 브랜치 | sprint-05/evaluation-report |
| 완료일 | 2026-05-07 |
| 종합 판정 | **PASS** |

## 구현 내용

### src/evaluate.py

Best 체크포인트를 로드하여 Test 세트 전체 평가를 수행하는 파이프라인.

- `find_best_checkpoint()`: `artifacts/checkpoints/best_*.pt` 중 최신 파일 자동 선택
- `run_inference()`: Test 세트(~49k) CPU 추론 (MPS 스로틀링 방지)
- `compute_metrics()`: Accuracy / Macro F1 / Precision / Recall 산출
- `plot_confusion_matrix()`: 2×2 Confusion Matrix PNG 생성
- `extract_top_errors()`: confidence 기준 오분류 상위 20건 추출
- `categorize_errors()`: 4개 카테고리 자동 분류 (negation_confusion, short_text, slang_exclamation, high_confidence_error)
- `write_eval_report()`: 베이스라인 비교표 + 오분류 분석 포함 Markdown 리포트 생성

### 주요 기술 결정

**CPU 추론**: MPS(Apple Silicon)는 학습 시 안정적이나 장시간 추론에서 열 스로틀링 발생 (14 배치/분 → 0.9 배치/분). `device = torch.device("cpu")`로 고정하여 안정적으로 49k 샘플 처리.

**80k 학습 샘플**: 30k→50k→80k 순차 실험. 80k에서 val_acc=0.9036, test_acc=0.9020으로 AC-05-01 기준(≥0.90) 달성.

## 산출물

| 파일 | 설명 |
|------|------|
| `artifacts/sprint-05_metrics.json` | test_accuracy, test_f1 등 수치 지표 |
| `artifacts/confusion_matrix.png` | 2×2 Confusion Matrix |
| `artifacts/eval_report.md` | 베이스라인 vs BERT 비교 + 오분류 분석 |

## 평가 결과

| AC | 내용 | 판정 | 결과 |
|----|------|------|------|
| AC-05-01 | Test Accuracy ≥ 0.90 | PASS | 0.9020 |
| AC-05-02 | Test Macro F1 ≥ 0.88 | PASS | 0.9020 |
| AC-05-03 | confusion_matrix.png 존재 | PASS | 파일 확인 |
| AC-05-04 | eval_report.md 베이스라인 vs BERT 비교 | PASS | 비교표 포함 |
| AC-05-05 | 오분류 20건 + 3개 이상 카테고리 | PASS | 20건 / 4카테고리 |

## 성능 비교

| 지표 | TF-IDF + LogReg | klue/roberta-base | 개선 |
|------|-----------------|-------------------|------|
| Accuracy | 0.8612 | 0.9020 | +0.0408 |
| Macro F1 | 0.8612 | 0.9020 | +0.0408 |

## 오분류 분석 요약

| 카테고리 | 건수 | 주요 원인 |
|----------|------|-----------|
| negation_confusion | 4 | 이중 부정·조건절로 감성 방향 혼동 |
| short_text | 11 | 5단어 이하 초단문으로 문맥 정보 부족 |
| slang_exclamation | 3 | 신조어·이모티콘 단독 사용 시 방향성 모호 |
| high_confidence_error | 20 | 도메인 편향(영화 제목·배우명) 고확신 오분류 |
