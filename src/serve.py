"""Gradio UI 서빙 모듈 — sprint-06.

klue/roberta-base 파인튜닝 모델을 Gradio Interface로 제공한다.

- 텍스트 입력 → 긍정/부정 + 신뢰도 출력
- 모델은 앱 시작 시 1회 로드 후 캐시 (전역 상태)
- 기본 실행: uv run python -m src.serve
- 포트: 7860 (Gradio 기본)
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import torch
from loguru import logger
from transformers import AutoTokenizer, PreTrainedTokenizerBase

from src.evaluate import find_best_checkpoint
from src.preprocess import clean_text, MAX_LENGTH, MODEL_NAME
from src.train import get_device, load_checkpoint

# ──────────────────────────────────────────────
# 경로 상수
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent

# ──────────────────────────────────────────────
# 레이블 매핑
# ──────────────────────────────────────────────
LABEL_MAP: dict[int, str] = {0: "부정 (Negative)", 1: "긍정 (Positive)"}


# ──────────────────────────────────────────────
# 모델 & 토크나이저 캐시 (앱 시작 시 1회 로드)
# ──────────────────────────────────────────────

class _ModelCache:
    """단일 인스턴스 모델 캐시. 최초 접근 시 로드한다."""

    def __init__(self) -> None:
        self._model: Any | None = None
        self._tokenizer: PreTrainedTokenizerBase | None = None
        self._device: torch.device | None = None

    def load(self) -> None:
        """체크포인트와 토크나이저를 로드한다."""
        if self._model is not None:
            return  # 이미 로드됨

        ckpt_path = find_best_checkpoint()
        self._device = get_device()
        logger.info(f"서빙 디바이스: {self._device}")

        logger.info("토크나이저 로드 중...")
        self._tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

        logger.info(f"모델 로드 중: {ckpt_path.name}")
        self._model = load_checkpoint(ckpt_path, self._device)
        self._model.eval()
        logger.info("모델 로드 완료 — 서빙 준비")

    @property
    def model(self) -> Any:
        if self._model is None:
            raise RuntimeError("모델이 로드되지 않았습니다. load()를 먼저 호출하세요.")
        return self._model

    @property
    def tokenizer(self) -> PreTrainedTokenizerBase:
        if self._tokenizer is None:
            raise RuntimeError("토크나이저가 로드되지 않았습니다. load()를 먼저 호출하세요.")
        return self._tokenizer

    @property
    def device(self) -> torch.device:
        if self._device is None:
            raise RuntimeError("디바이스가 설정되지 않았습니다. load()를 먼저 호출하세요.")
        return self._device


_CACHE = _ModelCache()


# ──────────────────────────────────────────────
# 추론 함수
# ──────────────────────────────────────────────

def predict(text: str) -> tuple[str, float, float]:
    """단일 텍스트에 대해 긍/부정 예측과 신뢰도를 반환한다.

    Args:
        text: 입력 한국어 텍스트.

    Returns:
        (label_str, confidence, elapsed_sec) 튜플.
    """
    t0 = time.perf_counter()

    # 1. 전처리
    cleaned = clean_text(text)
    if not cleaned.strip():
        return "입력 없음", 0.0, 0.0

    # 2. 토크나이즈
    encoding = _CACHE.tokenizer(
        cleaned,
        truncation=True,
        padding="max_length",
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    input_ids = encoding["input_ids"].to(_CACHE.device)
    attention_mask = encoding["attention_mask"].to(_CACHE.device)

    # 3. 추론
    with torch.inference_mode():
        outputs = _CACHE.model(input_ids=input_ids, attention_mask=attention_mask)
        logits = outputs.logits.cpu()
        probs = torch.softmax(logits, dim=-1).squeeze()
        pred_idx = int(logits.argmax(dim=-1).item())
        confidence = float(probs[pred_idx].item())

    elapsed = time.perf_counter() - t0
    label_str = LABEL_MAP[pred_idx]
    logger.debug(f"예측: {label_str} ({confidence:.4f}) / {elapsed:.3f}s")
    return label_str, confidence, elapsed


# ──────────────────────────────────────────────
# Gradio 인터페이스
# ──────────────────────────────────────────────

def _gradio_predict(text: str) -> dict[str, float]:
    """Gradio Label 컴포넌트용 래퍼. 긍정/부정 두 클래스의 확률을 딕셔너리로 반환."""
    if not text or not text.strip():
        return {"입력 없음": 1.0}
    label, confidence, elapsed = predict(text)
    logger.info(f"요청 처리 완료 — label={label}, confidence={confidence:.4f}, elapsed={elapsed:.3f}s")
    other_label = LABEL_MAP[0] if label == LABEL_MAP[1] else LABEL_MAP[1]
    return {
        label: round(confidence, 6),
        other_label: round(1.0 - confidence, 6),
    }


def build_interface() -> Any:
    """Gradio Interface를 빌드하고 반환한다."""
    try:
        import gradio as gr
    except ImportError as e:
        raise ImportError(
            "gradio 패키지가 없습니다. `uv add gradio` 또는 `uv sync --extra serve`로 설치하세요."
        ) from e

    examples = [
        ["이 영화 정말 재미있어요!"],
        ["시간 낭비였습니다. 최악의 영화."],
        ["배우들의 연기가 훌륭하고 스토리도 탄탄해요."],
        ["별로였어요. 기대에 못 미쳤습니다."],
        ["감동적인 작품입니다. 강력 추천!"],
    ]

    iface = gr.Interface(
        fn=_gradio_predict,
        inputs=gr.Textbox(
            label="리뷰 텍스트 입력",
            placeholder="영화 리뷰를 입력하세요...",
            lines=3,
        ),
        outputs=gr.Label(
            label="감성 분류 결과",
            num_top_classes=2,
        ),
        title="한국어 감성 분석기 (NSMC + klue/roberta-base)",
        description=(
            "영화 리뷰 텍스트를 입력하면 긍정/부정 감성과 신뢰도를 출력합니다.\n"
            "모델: klue/roberta-base 파인튜닝 (NSMC Test Accuracy ≈ 0.90)"
        ),
        examples=examples,
        flagging_mode="never",
    )
    return iface


# ──────────────────────────────────────────────
# 엔트리포인트
# ──────────────────────────────────────────────

def main(
    host: str = "0.0.0.0",
    port: int = 7860,
    share: bool = False,
) -> None:
    """Gradio 앱을 시작한다."""
    logger.info("=== sprint-06 Gradio 서버 시작 ===")

    # 모델 & 토크나이저 사전 로드 (앱 시작 시 1회)
    _CACHE.load()

    import gradio as gr

    iface = build_interface()
    iface.launch(
        server_name=host,
        server_port=port,
        share=share,
        show_error=True,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="한국어 감성 분석기 Gradio 서버")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="바인딩 호스트 (기본: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7860, help="서버 포트 (기본: 7860)")
    parser.add_argument("--share", action="store_true", help="Gradio 공개 링크 생성")
    args = parser.parse_args()

    main(host=args.host, port=args.port, share=args.share)
