# Test Review — sprint-04

## 테스트 실행 결과

✅ **모든 테스트 통과**

```
============================= test session starts ==============================
platform darwin -- Python 3.12.2, pytest-9.0.3, pluggy-1.6.0
collected 7 items

tests/test_train.py::test_set_seed_reproducibility PASSED                [ 14%]
tests/test_train.py::test_get_device_returns_torch_device PASSED         [ 28%]
tests/test_train.py::test_train_epoch_returns_float PASSED               [ 42%]
tests/test_train.py::test_eval_epoch_returns_loss_and_acc PASSED         [ 57%]
tests/test_train.py::test_save_and_load_checkpoint PASSED                [ 71%]
tests/test_train.py::test_save_metrics_creates_json PASSED               [ 85%]
tests/test_train.py::test_save_training_log_schema PASSED                [100%]

============================== 7 passed in 3.35s =======================================
```

## 커버리지 평가

### 긍정적 평가

1. **Core Utility Functions** (매우 좋음)
   - `set_seed()`: 재현성 테스트 (동일 시드 결과 검증) ✓
   - `get_device()`: 타입 및 유효한 device 반환 검증 ✓
   - `save_checkpoint()`: 경로 생성 및 state_dict 저장 검증 ✓
   - `save_metrics()`: JSON 파일 생성 및 파싱 검증 ✓
   - `save_training_log()`: 스키마 및 필드 검증 ✓

2. **Training Loop Functions** (기본적)
   - `train_epoch()`: float loss 반환 타입 검증 ✓
   - `eval_epoch()`: (val_loss, val_acc) 튜플 및 범위 검증 ✓

3. **Mock & Fixture 활용**
   - `_make_tiny_model()`: transformers 호환 모델 흉내 사용
   - `_make_tiny_loader()`: 작은 배치 DataLoader 생성
   - `tmp_path` fixture: 임시 디렉토리 테스트 격리

### 부정적 평가 (누락 & 약점)

## 누락된 테스트

### 1. **Main Training Pipeline (`train()` 함수) 미테스트** (심각)
- `train()` 함수는 가장 중요한 통합 기능인데 **단위 테스트 전무**
- 에폭 루프, Early Stopping, 메트릭 저장 등 핵심 로직이 검증되지 않음
- AC-04-01 (Best checkpoint val_acc 기반 선택) 검증 불가능

### 2. **`load_checkpoint()` 함수 미테스트**
- `save_checkpoint()` 반대 작업이지만 테스트 없음
- transformers 모델 로드 (GPU 의존) 때문에 skip되는 것 같음
- `FileNotFoundError` 예외 처리 미검증

### 3. **Edge Cases & Error Handling 미흡**
- `eval_epoch()`: `total=0` 조건 (empty loader) 미테스트
- `train_epoch()`: gradient clipping 효과 미검증
- `save_checkpoint()`: 디렉토리 생성 실패 시나리오 미테스트
- JSON 파일 쓰기 실패/권한 문제 미검증

### 4. **하이퍼파라미터 조합 테스트 미흡**
- 서로 다른 `num_epochs`, `batch_size`, `max_length` 조합 미테스트
- `warmup_ratio`, `weight_decay` 영향 미검증

### 5. **Early Stopping 로직 미테스트**
- `patience_counter` 증감 미검증
- 조기 종료 조건 (`patience >= patience_counter`) 미검증
- 최대 에폭 도달 시 종료 미검증

### 6. **Logging & Side Effects 미검증**
- `logger` 호출 검증 없음 (loguru 심화 테스트)
- 체크포인트 저장 후 파일 권한/크기 검증 없음

### 7. **데이터 로더 통합 테스트 미흡**
- `build_dataloaders()` 반환 loader 실제 통합 테스트 없음
- 진정한 NSMC 데이터 로드 파이프라인 미테스트

### 8. **Device 이동 검증 미흡**
- 모든 테스트가 CPU 고정 (`device = torch.device("cpu")`)
- CUDA/MPS 디바이스 통합 테스트 없음

### 9. **모델 상태 검증 미흡**
- `model.train()` / `model.eval()` 전환 미검증
- Dropout, BatchNorm 등 training mode 의존성 미검증

### 10. **타임스탬프 형식 미검증**
- `save_checkpoint()`, `save_training_log()` 타임스탬프 형식 미검증
- ISO 8601 format 준수 미확인

## 결론

**NEEDS_FIX**

### 근거

1. **Critical**: `train()` 함수 (가장 핵심 기능) 완전 미테스트
   - Sprint contract AC-04-01 (Best checkpoint 선택) 검증 불가능
   - Early Stopping 로직 미검증

2. **High**: 핵심 함수 `load_checkpoint()` 미테스트
   - 에러 처리 (`FileNotFoundError`) 미검증
   - 모델 로드 후 상태 미검증

3. **Medium**: Edge cases & error handling 부족
   - Empty loader, 권한 오류, 디렉토리 생성 실패 등 미검증
   - 로깅 및 파일 I/O 견고성 미검증

4. **Test Coverage**: 7개 테스트 중 대부분 "happy path" 타입
   - 실제 데이터 파이프라인 없이 toy model 사용
   - 통합 테스트 부재

### 권장사항

1. **즉시 추가**: `test_train()` 함수 (작은 데이터셋으로 end-to-end)
2. **즉시 추가**: `test_load_checkpoint()` (FileNotFoundError 포함)
3. **추가**: Early Stopping 로직 유닛 테스트
4. **추가**: `test_train_epoch_gradient_clipping()` (grad norm 검증)
5. **고려**: 실제 NSMC 데이터 작은 샘플로 통합 테스트

### 현재 상태

- ✅ 단위 테스트 기본 구조 양호
- ✅ Mock 활용 및 tmp_path fixture 적절
- ❌ 통합 테스트 부재
- ❌ 핵심 함수 (`train`, `load_checkpoint`) 미테스트
- ❌ Edge cases 및 에러 처리 검증 미흡
