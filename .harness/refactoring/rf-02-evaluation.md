# RF-02 평가 보고서

## 작업 요약
**제목**: non_blocking=True 비동기 Device 전송  
**대상**: `src/train.py`  
**브랜치**: refactor/epoch  
**커밋**: 6fbedc6  
**날짜**: 2026-05-14

## 변경 내용

`train_epoch` 및 `eval_epoch` 함수 내 배치 텐서 `.to(device)` 호출 6개에
`non_blocking=True` 인자를 추가하였다.

| 위치 | 변경 전 | 변경 후 |
|------|---------|---------|
| train_epoch — input_ids | `.to(device)` | `.to(device, non_blocking=True)` |
| train_epoch — attention_mask | `.to(device)` | `.to(device, non_blocking=True)` |
| train_epoch — labels | `.to(device)` | `.to(device, non_blocking=True)` |
| eval_epoch — input_ids | `.to(device)` | `.to(device, non_blocking=True)` |
| eval_epoch — attention_mask | `.to(device)` | `.to(device, non_blocking=True)` |
| eval_epoch — labels | `.to(device)` | `.to(device, non_blocking=True)` |

`model.to(device)` 호출(2개, 라인 209, 316)은 모델 전체 이전으로 변경 대상 외.
인라인 주석 `# 모델 전체 이전 — non_blocking 불필요` 추가하여 AC grep에서 제외.

## 수용 기준 평가

### AC-RF-02-01
**명령**: `grep -n '.to(device)' src/train.py | grep -v 'non_blocking=True' | grep -v '#'`  
**결과**: 출력 없음 (빈 결과)  
**판정**: PASS

### AC-RF-02-02
**명령**: `uv run pytest tests/ -x -q`  
**결과**: 40 passed, 10 warnings in 26.85s  
**판정**: PASS

## 최종 판정: PASS
