# Evaluation Report: sprint-02
평가 일시: 2026-04-23T11:31:00+00:00
평가자: Orchestrator (수동 재검증)

## 종합 판정: **PASS**

## AC별 판정 결과

| AC | 판정 | 근거 |
|----|------|------|
| AC-02-01 | PASS | over_ratio=0.00% (threshold < 5%) |
| AC-02-02 | PASS | val_ratio=10.00% (범위 9~11%) |
| AC-02-03 | PASS | 레이블 분포 편차=0.46%p (threshold < 2%p) |
| AC-02-04 | PASS | DataLoader 배치 키: {input_ids, attention_mask, labels} |

## 상세 수치

- AC-02-01: 토큰 길이 mean=19.6, max=120, 128 초과=0건 (0.00%)
- AC-02-02: total=199992, val=20000, val_ratio=0.1000
- AC-02-03: train_pos=49.88%, val_pos=49.89%, test_pos=50.35%, max_diff=0.46%p
- AC-02-04: input_ids shape=(32,128), attention_mask shape=(32,128), labels shape=(32,)

## 비고
evaluator.py의 metric_threshold 타입이 metric_key 기반 판정으로 동작하여 AC-02-01~04 모두 SKIP 처리됨.
Orchestrator가 evaluation-request.md의 python_assert 스크립트를 직접 실행하여 재검증 완료.
