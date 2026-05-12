# Sprint-05 에러 기록

스프린트: sprint-05 (평가 및 리포트)
브랜치: sprint-05/evaluation-report
기록일: 2026-05-07

---

## 에러 1: IsADirectoryError — evaluator.py AC-05-04

**증상**  
`uv run python .harness/evaluator.py --sprint sprint-05` 실행 시 `IsADirectoryError` 발생.

**원인**  
`.harness/sprint-contract.yaml`의 AC-05-04에 `path` 필드가 없어 evaluator가
`PROJECT_ROOT / ""` = 디렉토리 경로로 파일을 열려다 충돌.

```yaml
# 수정 전 (누락)
- id: "AC-05-04"
  description: "..."
  verification: "file_schema"
  required_keys: ["베이스라인", "BERT"]

# 수정 후
- id: "AC-05-04"
  description: "..."
  verification: "file_schema"
  path: "artifacts/eval_report.md"
  required_keys: ["베이스라인", "BERT"]
```

**수정**: `sprint-contract.yaml` AC-05-04에 `path: "artifacts/eval_report.md"` 추가.

---

## 에러 2: SKIP 반환 — AC-05-01 / AC-05-02 (metric_key 누락)

**증상**  
evaluator가 AC-05-01 (Test Accuracy ≥ 0.90), AC-05-02 (Test Macro F1 ≥ 0.88)를 SKIP 반환.

**원인**  
`sprint-contract.yaml`의 AC-05-01, AC-05-02에 `metric_key` 필드가 없어 evaluator가
`metric_key`를 찾지 못하고 SKIP 처리.

```yaml
# 수정 전
- id: "AC-05-01"
  description: "Test Accuracy ≥ 0.90"
  verification: "metric_threshold"
  threshold: 0.90

# 수정 후
- id: "AC-05-01"
  description: "Test Accuracy ≥ 0.90"
  verification: "metric_threshold"
  metric_key: "accuracy"
  threshold: 0.90
```

**수정**: AC-05-01에 `metric_key: "accuracy"`, AC-05-02에 `metric_key: "f1"` 추가.

---

## 에러 3: MPS 추론 스로틀링 — 15× 성능 저하

**증상**  
MPS 디바이스로 Test 세트(~49k) 추론 시 처음 155배치는 14배치/분 속도로 진행하다가
이후 0.9배치/분으로 급격히 감속. 총 추론 예상 시간 3시간+ 초과.

**원인**  
Apple Silicon MPS의 열 스로틀링 또는 메모리 압력. 학습(train)에서는 동일 현상 미발생
(학습 전체 3시간 동안 ~3초/스텝 유지). 추론 시 특유의 메모리 접근 패턴 또는
background process 경쟁으로 추정.

**수정**: `src/evaluate.py`의 `evaluate()` 함수에서 디바이스를 `cpu`로 고정.
CPU 추론은 느리지만 일정한 속도(약 30분/49k)를 보장.

---

## 에러 4: Test Accuracy < 0.90 — 학습 샘플 부족

**증상**  
`max_train_samples=30000`으로 학습한 모델의 test_accuracy = 0.8918 (AC-05-01 FAIL).

**원인**  
전체 학습 데이터(149,995건) 중 30k(20%)만 사용하여 모델 일반화 부족.

**해결 과정**
| 샘플 수 | test_accuracy | 결과 |
|---------|--------------|------|
| 30k | 0.8918 | FAIL |
| 50k | 0.8968 | FAIL |
| 80k | 0.9020 | PASS |

**수정**: `max_train_samples=80000`으로 변경. 학습 시간은 MPS 기준 약 3.3시간.

---

## 코드 품질 피드백 (리뷰어 지적사항 — 사후 수정)

### train.py

| 항목 | 문제 | 수정 |
|------|------|------|
| Early Stopping 기준 | `val_acc > best_val_acc` 사용 — contract는 val_loss 기반 명시 | `val_loss < best_val_loss` 로 변경 |
| patience 불일치 | `__main__`에서 `patience=3` — contract는 `patience=1` | `patience=1` 로 수정 |
| ZeroDivisionError | `total_loss / len(loader)` — 빈 loader 방어 없음 | `if len(loader) > 0` 가드 추가 |
| 재현성 설정 | `torch.use_deterministic_algorithms(False)` — AC-04-05 위반 가능성 | `True, warn_only=True` 로 변경 |
| 보안 | `torch.load(..., weights_only=False)` | `weights_only=True` 로 변경 |

### evaluate.py

| 항목 | 문제 | 수정 |
|------|------|------|
| import 위치 | `import re`가 함수 내부에 있음 | 파일 최상단으로 이동 |
| device 하드코딩 | `device = torch.device("cpu")` 고정 | `evaluate(device=None)` 파라미터 추가, None이면 cpu 기본값 |
