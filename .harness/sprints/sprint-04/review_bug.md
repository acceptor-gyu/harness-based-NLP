# Bug Review — sprint-04

## 발견된 이슈

### 1. Early Stopping 로직의 치명적 버그
**심각도:** 높음 (CRITICAL)

**위치:** `src/train.py` 라인 363-389

**문제:**
Early Stopping 기준이 스프린트 계약(sprint-contract.yaml 라인 139, 164)과 **불일치**한다.
- sprint-contract.yaml AC-04-04: "Val loss 상승 시 Early Stopping 정상 동작"
- 실제 구현 (라인 363): `if val_acc > best_val_acc:` — **Accuracy 기반**

스프린트 계약상 **"Val loss 기반"** Early Stopping이어야 하는데, 현재는 val_acc 최대화 기준으로 동작한다.

**구체적 오류 시나리오:**
- Epoch 2: train_loss=0.25, val_loss=0.30, val_acc=0.91 → Best 저장
- Epoch 3: train_loss=0.20, val_loss=0.45, val_acc=0.92 → Best 갱신 (val_acc > 0.91)
- Epoch 4: train_loss=0.18, val_loss=0.60, val_acc=0.92 → patience++ (val_acc 미개선)
  
**실제 결과:** Epoch 3에서 val_loss가 극적으로 악화(0.30→0.45)했지만 val_acc가 향상(0.91→0.92)되었으므로 Early Stopping 발동 안 함.
**요구사항:** Epoch 3의 val_loss 상승만으로 Early Stopping 발동해야 함.

또한, val_acc 동일할 때 val_loss로 tie-break하는 로직이 없음.

---

### 2. 초기화 로직: best_epoch = -1 의미 불명확
**심각도:** 중간 (불명확성)

**위치:** `src/train.py` 라인 336

**문제:**
`best_epoch: int = -1`로 초기화되어, 학습 중 최소 1 에폭도 개선이 없으면 `best_epoch=-1`이 최종 값이 된다.
메트릭 저장 시 (라인 399) `"best_epoch": best_epoch`로 -1이 기록된다.

이 경우:
- 첫 에폭도 "best"로 갱신되지 않은 시나리오 가능 (patience가 0이면 첫 에폭부터 early stop 가능, 하지만 patience 기본값은 1이므로 최소 2 에폭은 실행)
- 하지만 논리상 첫 에폭이 val_acc < 0.0이 될 수 없으므로 실제로는 항상 `best_epoch >= 1`

**리스크:** 테스트가 없으므로, 향후 patience 로직 변경 시 best_epoch=-1 상태가 나올 수 있다.

---

### 3. load_checkpoint에서 예외 처리 불충분
**심각도:** 중간 (견고성)

**위치:** `src/train.py` 라인 188-209

**문제:**
`checkpoint.get("model_state_dict")` 호출 전에 체크가 없다 (라인 206).
- 만약 이전 버전의 체크포인트에서 `"model_state_dict"` 키가 없으면, `KeyError` 발생.
- 라인 198-199에서 파일 존재 여부만 확인하고, 파일 내용의 유효성은 미검증.

**시나리오:**
```
checkpoint = {"metrics": {...}}  # model_state_dict 없음
model.load_state_dict(checkpoint["model_state_dict"])  # KeyError
```

---

### 4. 0 배치 시 eval_epoch의 동작
**심각도:** 낮음 (edge case)

**위치:** `src/train.py` 라인 157-158

**문제:**
```python
val_acc = correct / total if total > 0 else 0.0
```
val_loss는 `total_loss / len(loader)`로 계산되므로, 만약 loader가 비어있으면 `ZeroDivisionError` 발생.
val_acc는 방어했지만, val_loss는 미방어.

**현실성:** 실제로는 build_dataloaders()가 보장하겠지만, 이 함수는 독립적으로도 호출 가능 (테스트에서 _make_tiny_loader 사용).

---

### 5. save_checkpoint 중복 호출 리스크
**심각도:** 낮음 (비효율)

**위치:** `src/train.py` 라인 368-377

**문제:**
매 에폭마다 save_checkpoint()를 호출하면 동일 timestamp로 여러 파일이 생성된다 (아니, 동일 timestamp 내 1개만 생성, 하지만 매번 덮어쓰지는 않음 — 정정: 파일명에 timestamp가 있으므로 에폭당 다른 파일이 아니라 **같은 파일명**).

실제로 확인: 파일명 = `best_{timestamp}.pt` → 동일 실행 내 timestamp는 고정이므로 **항상 같은 파일에 덮어쓴다**.

실제 동작: 매 에폭마다 동일 경로에 덮어쓰므로, 최종적으로 best 모델이 저장되는 것은 맞다. 하지만 "체크포인트 저장"을 여러 번 로깅하는 것은 오도할 수 있다.

**결론:** 구현상 문제는 아니지만, 명확성을 위해 "best 갱신"이라고 로깅하는 게 더 나을 것.

---

### 6. 무시된 유형 오류: 배치 dict 구조 가정
**심각도:** 낮음 (타입 안정성)

**위치:** `src/train.py` 라인 107-109, 143-145

**문제:**
batch가 dict 형식이라고 가정하지만, 타입 힌트가 `DataLoader[Any]`로 불명확.
만약 build_dataloaders()가 다른 형식의 배치를 반환하면 runtime error.

테스트에서는 _make_tiny_loader()가 dict를 반환하므로 패스.

---

## 권장 수정

### 1. Early Stopping 기준 명확히 (우선도 높음)
스프린트 계약이 "Val loss 기반"이라면, 다음과 같이 수정:

```python
# Before (라인 363)
if val_acc > best_val_acc:

# After (loss 기반)
if val_loss < best_val_loss:
    # 또는 val_acc 동일할 때 loss로 tie-break
    # (현재 주석: AC-04-01에서 val_acc 최대화 기준이라고 명시되어 있으므로, 
    #  실제로는 val_acc 기반이 맞을 수 있음 — 재확인 필요)
```

**주의:** 코드 라인 362 주석이 "AC-04-01" 참조하므로, sprint-contract.yaml 확인 필수.

---

### 2. load_checkpoint에 방어 코드 추가

```python
def load_checkpoint(ckpt_path: Path, device: torch.device) -> nn.Module:
    if not ckpt_path.exists():
        raise FileNotFoundError(f"체크포인트 없음: {ckpt_path}")
    checkpoint = torch.load(ckpt_path, map_location=device, weights_only=False)
    
    # 필수 키 검증
    if "model_state_dict" not in checkpoint:
        raise ValueError(f"유효하지 않은 체크포인트 형식: {ckpt_path}")
    
    model_name = checkpoint.get("model_name", MODEL_NAME)
    num_labels = checkpoint.get("num_labels", NUM_LABELS)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=num_labels
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    logger.info(f"체크포인트 로드 완료: {ckpt_path} (metrics={checkpoint.get('metrics')})")
    return model
```

---

### 3. eval_epoch에 loader 검증

```python
def eval_epoch(
    model: nn.Module,
    loader: DataLoader[Any],
    device: torch.device,
) -> tuple[float, float]:
    """평가 실행 후 (val_loss, val_acc) 반환."""
    if not loader:
        logger.warning("빈 DataLoader로 eval_epoch 호출됨")
        return 0.0, 0.0
    
    model.eval()
    # ... 이하 동일
```

---

### 4. best_epoch 초기값 개선 (선택사항)

```python
# Before
best_epoch: int = -1

# After
best_epoch: int = 0  # 또는 None, 타입 변경 필요
```

또는, 첫 에폭이 항상 best가 되도록 보장:
```python
best_val_acc: float = -1.0  # 0.0 대신 음수로 초기화
```

---

## 결론

**NEEDS_FIX**

**주요 이유:**
1. Early Stopping 기준 (val_loss vs val_acc) 불일치는 재확인 필수 (AC-04-01 검토 필요)
2. load_checkpoint에 필수 키 검증 없음 (runtime safety)
3. eval_epoch에서 빈 loader 미처리 가능 (edge case)

테스트는 모두 통과하지만, 통합 테스트(실제 데이터 + 모델)가 없으므로 런타임 오류 가능성 있음.

**필수 조치:**
- sprint-contract.yaml에서 AC-04-01 기준 재확인 (Early Stopping: loss vs accuracy)
- load_checkpoint에 유효성 검증 추가
- eval_epoch에 loader 상태 검증 추가
