# Sprint-03 Evaluation Request

## 구현 완료 항목

### 파일 목록
- `src/baseline.py`: TF-IDF + LogisticRegression 베이스라인 구현
- `tests/test_baseline.py`: 베이스라인 테스트 (단위 6개 + 통합 3개)
- `artifacts/baseline_metrics.json`: 평가 메트릭 저장
- `pyproject.toml`: `slow` 마크 등록 추가

### 구현 세부사항
- **TF-IDF**: word n-gram(1,2) max_features=20000 + char n-gram(2,4) FeatureUnion (한국어 형태소 미사용 보완)
- **LogisticRegression**: C=1.0, max_iter=1000, solver=lbfgs
- **전처리**: HTML 태그 제거 + 기본 구두점 보존 경량 클리닝 (TF-IDF 전용)

## 자체 테스트 결과

```
uv run pytest tests/test_baseline.py -v
```

```
9 passed in 50.28s
```

## 성능 결과

```json
{
  "accuracy": 0.8612,
  "precision": 0.8613,
  "recall": 0.8613,
  "f1": 0.8612
}
```

## AC 자체 판정

| AC | 기준 | 결과 | 판정 |
|----|------|------|------|
| AC-03-01 | Test Accuracy ≥ 0.85 | 0.8612 | PASS |
| AC-03-02 | Test Macro F1 ≥ 0.83 | 0.8612 | PASS |
| AC-03-03 | baseline_metrics.json에 accuracy/precision/recall/f1 저장 | 확인됨 | PASS |
| AC-03-04 | pytest tests/test_baseline.py 전체 통과 | 9/9 PASS | PASS |

## 주의사항
- Generator 완료 선언 금지. Evaluator가 최종 판정.
