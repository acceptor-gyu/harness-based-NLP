# Evaluation Request — sprint-05

## 구현 완료 보고

### 구현 내용
- `src/evaluate.py`: Best 체크포인트 로드 → Test 추론 → 메트릭 계산 → 혼동 행렬 생성 → 오분류 분석 → 리포트 생성 전체 파이프라인 구현

### 주요 함수
- `find_best_checkpoint()`: artifacts/checkpoints/best_*.pt 자동 탐색
- `run_inference()`: Test 세트 전체 추론 (MPS 동기화 포함)
- `compute_metrics()`: accuracy / macro f1 / precision / recall 계산
- `save_confusion_matrix()`: matplotlib 기반 PNG 저장
- `extract_misclassified()`: confidence 내림차순 상위 20건 추출
- `enrich_misclassified_with_text()`: 원본 텍스트 보강
- `categorize_errors()`: 4개 카테고리 분류 (negation_confusion / short_text / slang_exclamation / high_confidence_error)
- `write_eval_report()`: eval_report.md 생성 (베이스라인 vs BERT 비교표 포함)

### 생성 산출물
- `artifacts/sprint-05_metrics.json`: test_accuracy, test_f1, test_precision, test_recall, accuracy, f1 키 포함
- `artifacts/confusion_matrix.png`: Confusion Matrix PNG
- `artifacts/eval_report.md`: 베이스라인 vs BERT 비교표 + 오분류 20건 분석 + 4개 카테고리

### 체크포인트 정보
- 사용 체크포인트: `artifacts/checkpoints/best_20260427T082245Z.pt`
- 모델: klue/roberta-base (val_accuracy=0.9025 at best_epoch=3)

## 평가 실행 방법
```bash
uv run python .harness/evaluator.py --sprint sprint-05 --json
```

## AC별 예상 판정
- AC-05-01 (Test Accuracy ≥ 0.90): metric_threshold — sprint-05_metrics.json["accuracy"] 확인
- AC-05-02 (Test Macro F1 ≥ 0.88): metric_threshold — sprint-05_metrics.json["f1"] 확인
- AC-05-03 (confusion_matrix.png 존재): file_check — artifacts/confusion_matrix.png 확인
- AC-05-04 (eval_report.md 비교표 포함): file_schema — "베이스라인", "BERT" 키워드 확인
- AC-05-05 (오분류 20건 + 3개 카테고리): semantic_eval — evaluator-llm 서브에이전트 위임

## 비고
- AC-05-05는 `semantic_eval` 타입으로 evaluator.py에서 SKIP 반환 → orchestrator가 evaluator-llm 서브에이전트로 판정 필요
- artifacts/eval_report.md에 4개 카테고리(negation_confusion, short_text, slang_exclamation, high_confidence_error)와 20건 샘플 목록 포함
