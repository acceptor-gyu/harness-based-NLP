# Sprint-02 평가 요청

## 스프린트 정보
- ID: sprint-02
- 제목: 전처리 파이프라인
- 브랜치: sprint-02/preprocessing-pipeline

## 구현 완료 사항
- `src/preprocess.py`: 정규화, 클리닝, 불용어 제거, 토크나이저 적용, 분할, DataLoader 생성
- `tests/test_preprocess.py`: 15개 테스트 작성 (전체 PASS 확인)

## 자체 검증 결과
```
pytest tests/test_preprocess.py -v
15 passed in 51.13s
```

## AC별 검증 방법

### AC-02-01: 토큰 길이 128 초과 비율 < 5%
```python
from transformers import AutoTokenizer
from src.data_loader import load_nsmc
from src.preprocess import clean_text, compute_token_length_stats
tokenizer = AutoTokenizer.from_pretrained("klue/roberta-base")
train_df, _ = load_nsmc()
texts = train_df["document"].apply(lambda x: clean_text(x)).tolist()
stats = compute_token_length_stats(texts, tokenizer, max_length=128)
assert stats["over_ratio"] < 0.05
```

### AC-02-02: Val 크기가 전체의 10% ± 1%
```python
from src.data_loader import load_nsmc
from src.preprocess import split_dataframe
train_df, test_df = load_nsmc()
total = len(train_df) + len(test_df)
_, val_split, _ = split_dataframe(train_df, test_df)
val_ratio = len(val_split) / total
assert 0.09 <= val_ratio <= 0.11
```

### AC-02-03: 레이블 분포 편차 < 2%p
```python
from src.data_loader import load_nsmc
from src.preprocess import split_dataframe
train_df, test_df = load_nsmc()
train_split, val_split, test_split = split_dataframe(train_df, test_df)
def pos_ratio(df): return float((df["label"] == 1).mean())
ratios = [pos_ratio(train_split), pos_ratio(val_split), pos_ratio(test_split)]
assert max(ratios) - min(ratios) < 0.02
```

### AC-02-04: DataLoader 배치 형식
```python
from src.data_loader import load_nsmc
from src.preprocess import build_dataloaders
train_df, test_df = load_nsmc()
train_loader, val_loader, test_loader = build_dataloaders(train_df, test_df)
batch = next(iter(train_loader))
assert set(batch.keys()) == {"input_ids", "attention_mask", "labels"}
```

## 비고
- evaluator.py의 metric_threshold 타입은 metric_key 기반으로 판정하므로,
  sprint-02 AC들은 python_assert 방식으로 직접 실행해야 합니다.
