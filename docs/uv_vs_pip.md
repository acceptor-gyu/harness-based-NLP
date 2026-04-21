# uv vs pip install 차이

## 한 줄 요약

`pip`은 패키지를 설치하는 도구이고, `uv`는 패키지 설치부터 가상환경, 의존성 잠금, 스크립트 실행까지 아우르는 Python 프로젝트 전체 관리 도구다.

---

## 핵심 차이 비교

| 항목 | pip | uv |
|------|-----|----|
| 구현 언어 | Python | Rust |
| 속도 | 기준 | 10~100배 빠름 |
| 가상환경 관리 | 별도 `venv` 필요 | `uv venv` 내장 |
| 의존성 잠금 | `pip freeze > requirements.txt` (수동) | `uv.lock` 자동 생성/관리 |
| 재현 가능 설치 | `pip install -r requirements.txt` | `uv sync` (lock 파일 기준) |
| 프로젝트 메타데이터 | `setup.py` / `setup.cfg` 별도 | `pyproject.toml` 단일 파일 |
| 스크립트 실행 | 가상환경 활성화 후 실행 | `uv run <script>` |
| Python 버전 관리 | 미지원 | `uv python install` 내장 |
| 전이 의존성 해석 | 설치 시점에 결정 (비결정적) | SAT Solver로 결정적 해석 |

---

## 의존성 잠금: 가장 중요한 차이

### pip의 문제

```bash
pip install torch transformers
pip freeze > requirements.txt
```

`requirements.txt`에는 직접 설치한 패키지뿐 아니라 전이 의존성까지 모두 고정되지만, **누가 직접 요청한 것인지 알 수 없다.** 다른 머신에서 `pip install -r requirements.txt`를 실행하면 패키지 순서나 환경에 따라 미묘하게 다른 결과가 나올 수 있다.

### uv의 방식

```bash
uv add torch transformers
```

- `pyproject.toml`에 **직접 의존성만** 기록 (사람이 관리)
- `uv.lock`에 전이 의존성을 포함한 **전체 해결 결과**를 SHA 해시와 함께 잠금 (자동 관리)

```bash
uv sync          # uv.lock 기준으로 정확히 동일한 환경 재현
uv sync --frozen # lock 파일 변경 없이 설치만 (CI 환경에 적합)
```

`uv.lock`은 git에 커밋해야 하고, 직접 편집하지 않는다.

---

## 속도 차이가 나는 이유

`uv`는 Rust로 작성되어 있고 다음 최적화를 적용한다:

1. **전역 캐시**: 한 번 다운로드한 패키지를 머신 전체에서 재사용. 같은 패키지를 여러 프로젝트에서 설치해도 다운로드는 1회.
2. **병렬 다운로드/설치**: 패키지를 동시에 처리.
3. **Copy-on-Write / 하드링크**: 캐시에서 가상환경으로 파일을 복사할 때 실제 복사 없이 링크.

---

## 스크립트 실행: `uv run`

가상환경을 직접 활성화하지 않아도 된다.

```bash
# pip 방식
source .venv/bin/activate
python src/train.py

# uv 방식 (가상환경 활성화 불필요)
uv run python src/train.py
uv run pytest tests/ -x -q
```

`uv run`은 실행 전 자동으로 `uv sync`를 수행해 환경이 항상 `uv.lock`과 일치함을 보장한다.

---

## 이 프로젝트에서 uv를 사용하는 이유

1. **재현성**: `uv.lock`이 있으면 어느 머신에서도 `uv sync` 한 번으로 동일한 환경을 얻는다.
2. **명시적 의존성 관리**: `pyproject.toml`에는 직접 의존성만 있어 프로젝트 의도가 명확하다.
3. **하네스 실행 일관성**: `uv run python .harness/orchestrator.py`처럼 쓰면 환경 활성화 없이 항상 올바른 인터프리터로 실행된다.
4. **속도**: BERT 파인튜닝 환경처럼 무거운 의존성도 재설치 시 캐시로 빠르게 복원된다.

---

## 명령어 대응표

| 목적 | pip | uv |
|------|-----|----|
| 패키지 설치 | `pip install torch` | `uv add torch` |
| 개발 의존성 설치 | `pip install pytest` | `uv add --dev pytest` |
| 환경 전체 재현 | `pip install -r requirements.txt` | `uv sync` |
| 패키지 제거 | `pip uninstall torch` | `uv remove torch` |
| 스크립트 실행 | `python script.py` (활성화 후) | `uv run python script.py` |
| 현재 설치 목록 | `pip list` | `uv pip list` |
| 가상환경 생성 | `python -m venv .venv` | `uv venv` |
