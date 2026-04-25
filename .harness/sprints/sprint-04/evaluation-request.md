# Sprint-04 Evaluation Request

## 구현 완료 항목

### 파일
- `src/train.py` — AutoModelForSequenceClassification 기반 BERT 파인튜닝 전체 파이프라인
- `tests/test_train.py` — 7개 단위 테스트 (전체 40개 PASS)

### 구현 사항
1. **모델**: `klue/roberta-base` + `AutoModelForSequenceClassification` (num_labels=2)
2. **옵티마이저**: AdamW (lr=2e-5, weight_decay=0.01)
3. **스케줄러**: Linear Warmup (warmup_ratio=0.1)
4. **학습 설정**: epoch=3, batch_size=32, max_length=128, random_seed=42
5. **Early Stopping**: patience=1, val_loss 기준
6. **체크포인트**: `artifacts/checkpoints/best_<timestamp>.pt`
7. **로그**: `logs/training_<timestamp>.json` (epoch별 train_loss/val_loss/val_acc)
8. **메트릭**: `artifacts/sprint-04_metrics.json` (val_accuracy, best_val_loss, epoch_logs 포함)
9. **디바이스**: cuda → mps → cpu 우선순위

### 브랜치
`sprint-04/bert-finetuning`

## 평가 명령

```bash
uv run python .harness/evaluator.py --sprint sprint-04 --json
```

## AC 판정 기준

| AC | 검증 방식 | 기준 |
|----|----------|------|
| AC-04-01 | metric_threshold | val_accuracy >= 0.90 (artifacts/sprint-04_metrics.json) |
| AC-04-02 | log_schema | train_loss, val_loss, val_acc 필드 존재 확인 |
| AC-04-03 | command_exec | 체크포인트 파일 존재 및 로드 가능 |
| AC-04-04 | log_schema | epoch_logs, best_epoch 필드 존재 확인 |
| AC-04-05 | metric_threshold | val_accuracy >= 0.89 (재현성 하한) |
