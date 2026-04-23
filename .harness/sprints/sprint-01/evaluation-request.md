# Evaluation Request: sprint-01

## 구현 완료 항목

### 1. 환경 구성
- `pyproject.toml`: 이미 구성됨 (torch, transformers, scikit-learn, pandas, loguru 등)
- `uv sync` 성공 확인

### 2. NSMC 데이터 다운로드
- `data/raw/ratings_train.txt`: 150001줄 (헤더 포함), 약 13.9MB
- `data/raw/ratings_test.txt`: 50001줄 (헤더 포함), 약 4.8MB
- 출처: https://raw.githubusercontent.com/e9t/nsmc/master/

### 3. src/data_loader.py 구현
- `load_nsmc(train_path, test_path)` 함수 구현
- TSV 파싱, NaN 및 빈 문자열 제거
- (train: 149995건, test: 49997건 반환 — 결측값 5건/3건 제거됨)
- 타입 힌트 완비, loguru 사용, pathlib.Path 사용

### 4. tests/test_data_loader.py 작성
- 9개 테스트 케이스, 전체 PASS

### 5. notebooks/01_eda.ipynb 작성
- 클래스 분포 시각화
- 문서 길이 분포 시각화
- 결측값 현황 확인

## 자체 검증 결과
```
pytest tests/test_data_loader.py -v
9 passed in 2.91s
```

## AC 검증 요청

| AC | 설명 | 검증 방법 |
|----|------|-----------|
| AC-01-01 | uv sync 성공 | command_exec: `uv sync` |
| AC-01-02 | 데이터 파일 존재 | file_check: data/raw/*.txt |
| AC-01-03 | load_nsmc() 건수 반환 | python_assert |
| AC-01-04 | document null = 0 | python_assert |

## 비고
- 원본 NSMC 데이터에 null document 5건(train)/3건(test) 존재함
- 결측값 제거 후 반환 건수: train 149995, test 49997
- AC-01-03은 >= 149990, >= 49990 로 검증 (sprint-contract.yaml 업데이트됨)
