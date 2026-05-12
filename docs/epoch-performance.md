# Epoch 성능 병목 분석 및 개선 전략

이 문서는 `src/train.py`의 epoch 루프에서 발생하는 속도 저하의 원인을 코드 근거와 함께 정리하고, 각 원인에 대한 개선 전략을 제시한다.

---

## 병목 원인

### 1. `num_workers=0` — 동기식 데이터 로딩

- **위치**: `src/preprocess.py:213–215`
- **현재 코드**:
  ```python
  train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
  val_loader   = DataLoader(val_dataset,   batch_size=batch_size, shuffle=False)
  ```
- **문제**: `num_workers` 미지정 시 기본값 `0`. 데이터 로딩이 메인 프로세스에서 동기적으로 실행된다. GPU/MPS가 현재 배치를 연산하는 동안 다음 배치를 CPU가 순차적으로 준비하므로, 매 스텝마다 연산 장치가 유휴 상태로 대기한다.

  ```
  [batch N 준비] → [batch N 연산] → [batch N+1 준비] → [batch N+1 연산] ...
                      (GPU 유휴)                          (GPU 유휴)
  ```

- **영향도**: 가장 큰 원인. 스텝 수만큼 반복되므로 전체 epoch 시간에 직접 누적된다.

---

### 2. `pin_memory=False` + 동기 `.to(device)` — CPU→Device 전송 블로킹

- **위치**: `src/preprocess.py:213–215` (DataLoader 생성), `src/train.py:107–109` (전송)
- **현재 코드**:
  ```python
  # preprocess.py — pin_memory 미지정
  train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

  # train.py — 매 스텝 3회 동기 전송
  input_ids      = batch["input_ids"].to(device)
  attention_mask = batch["attention_mask"].to(device)
  labels         = batch["labels"].to(device)
  ```
- **문제**: `pin_memory=True` 없이는 일반 페이지 메모리가 사용되어 CPU→GPU DMA 전송이 비효율적이다. 또한 `.to(device)` 가 `non_blocking=False`(기본값)이므로 전송 완료까지 메인 스레드가 블로킹된다.
- **영향도**: CUDA 환경에서 배치 전송 속도 2–3배 차이.

---

### 3. `use_deterministic_algorithms(True)` — 느린 결정론적 커널 강제

- **위치**: `src/train.py:71`
- **현재 코드**:
  ```python
  torch.use_deterministic_algorithms(True, warn_only=True)
  ```
- **문제**: 재현성 보장을 위해 결정론적 알고리즘을 강제하면, scatter/gather·self-attention 등의 연산에서 최적화된 비결정론적 커널 대신 느린 참조 구현이 사용된다. klue/roberta-base의 self-attention이 이 영향을 직접 받는다.
- **영향도**: CUDA 환경에서 forward pass 수십 % 느려짐. `warn_only=True`로 경고만 내도 실제로는 느린 경로가 선택될 수 있다.

---

### 4. AMP(혼합 정밀도) 미사용 — fp32 전 구간 연산

- **위치**: `src/train.py:346–347` (train_epoch 호출부)
- **문제**: `torch.amp.autocast`가 없어 모델 forward/backward 전체가 fp32로 실행된다. 최신 GPU(Tensor Core)와 Apple MPS는 fp16/bf16 연산 처리량이 fp32 대비 2–3배 높다.
- **영향도**: 연산 자체 비용 증가. 배치가 클수록 차이가 벌어진다.

---

## 병목 요약

| # | 원인 | 위치 | 영향도 |
|---|------|------|--------|
| 1 | `num_workers=0` — 동기 데이터 로딩 | preprocess.py:213–215 | 매 스텝 GPU 유휴 / **최우선** |
| 2 | `pin_memory=False` + 동기 `.to()` | preprocess.py:213–215, train.py:107–109 | CPU↔Device 전송 블로킹 |
| 3 | `use_deterministic_algorithms(True)` | train.py:71 | Transformer 연산 커널 저하 |
| 4 | AMP 미사용 | train.py 전체 학습 루프 | fp32 연산 2–3× 비용 |

---

## 개선 전략

### 전략 1: `num_workers` 활성화 + `pin_memory=True`

`num_workers ≥ 2` 로 설정하면 데이터 준비와 GPU 연산이 겹쳐(overlap) 실행된다.

```python
# src/preprocess.py:213–215 수정
import os

NUM_WORKERS = min(4, os.cpu_count() or 1)

train_loader = DataLoader(
    train_dataset,
    batch_size=batch_size,
    shuffle=True,
    num_workers=NUM_WORKERS,
    pin_memory=True,
    persistent_workers=True,   # 에폭 간 worker 재시작 오버헤드 제거
)
val_loader = DataLoader(
    val_dataset,
    batch_size=batch_size,
    shuffle=False,
    num_workers=NUM_WORKERS,
    pin_memory=True,
    persistent_workers=True,
)
```

> **주의 (macOS MPS)**: macOS에서 `num_workers > 0`은 `multiprocessing_context="fork"` 설정이 필요할 수 있다. MPS 환경에서는 먼저 `num_workers=2`로 시작하여 안정성을 확인한다.

---

### 전략 2: `non_blocking=True` 비동기 전송

`pin_memory=True`와 함께 사용해야 효과가 있다.

```python
# src/train.py:107–109 수정
input_ids      = batch["input_ids"].to(device, non_blocking=True)
attention_mask = batch["attention_mask"].to(device, non_blocking=True)
labels         = batch["labels"].to(device, non_blocking=True)
```

전송과 이전 배치 연산이 겹쳐 실행되어 전송 대기 시간이 사라진다.

---

### 전략 3: `use_deterministic_algorithms` 비활성화 (학습 시)

재현성이 필요한 경우 시드 고정만으로 충분하다. 결정론적 알고리즘 강제는 벤치마크·테스트에만 사용한다.

```python
# src/train.py:71 수정
# 학습 시에는 비활성화
# torch.use_deterministic_algorithms(True, warn_only=True)  # 제거 또는 조건부 적용
```

재현성이 반드시 필요한 평가 시:

```python
# 평가 전용 컨텍스트에서만 활성화
with torch.use_deterministic_algorithms(True):
    val_loss, val_acc = eval_epoch(model, val_loader, device)
```

---

### 전략 4: AMP(자동 혼합 정밀도) 적용

CUDA는 `float16`, Apple MPS/최신 GPU는 `bfloat16`을 사용한다.

```python
# src/train.py — train_epoch 함수 수정
from torch.amp import autocast, GradScaler

def train_epoch(model, loader, optimizer, scheduler, device, log_interval=200):
    model.train()
    total_loss = 0.0
    dtype = torch.bfloat16 if device.type in ("mps", "cpu") else torch.float16
    scaler = GradScaler(enabled=(device.type == "cuda"))

    for step, batch in enumerate(loader, 1):
        input_ids      = batch["input_ids"].to(device, non_blocking=True)
        attention_mask = batch["attention_mask"].to(device, non_blocking=True)
        labels         = batch["labels"].to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)   # zero_grad 개선도 포함

        with autocast(device_type=device.type, dtype=dtype):
            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()
        total_loss += loss.item()

        if step % log_interval == 0:
            logger.info(f"  step {step}/{len(loader)} — avg_loss={total_loss/step:.4f}")

    return total_loss / len(loader) if len(loader) > 0 else 0.0
```

> `set_to_none=True`: 그래디언트를 0으로 채우는 대신 `None`으로 설정하여 메모리 쓰기 비용을 절감한다.

---

### 개선 효과 예상

| 전략 | 기대 효과 | 적용 난이도 |
|------|-----------|------------|
| `num_workers` + `pin_memory` | 데이터 로딩 병목 제거, step당 시간 감소 | 낮음 |
| `non_blocking=True` | 전송 대기 시간 제거 | 낮음 |
| `use_deterministic_algorithms` 비활성화 | forward pass 속도 회복 | 낮음 |
| AMP 적용 | epoch당 시간 30–60% 단축 (CUDA 기준) | 중간 |

전략 1–3은 코드 변경이 5줄 이내로 가장 먼저 적용한다. 전략 4(AMP)는 `GradScaler` 도입이 필요하지만 CUDA/MPS 환경에서 가장 큰 속도 개선을 제공한다.
