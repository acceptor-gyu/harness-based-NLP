# harness-based-NLP
하네스 기반 NLP 프로젝트

# sentiment-analyzer

한국어 영화 리뷰(NSMC) 감성 분석기. Planner-Generator-Evaluator 3단계 하네스 기반으로 스프린트 단위 개발.

## 구조

```
sentiment-analyzer/
├── AGENTS.md                 # 하네스 가이드 (에이전트 자동 주입)
├── PLAN.md                   # 전체 개발 계획 (6 스프린트)
├── pyproject.toml            # uv 기반 의존성
├── .harness/
│   ├── sprint-contract.yaml  # 스프린트 계약 (SSOT)
│   ├── claude-progress.txt   # 진행 상태
│   ├── runner.py             # Stop Condition 관리자
│   ├── evaluator.py          # 자동 평가 스크립트
│   └── sprints/              # 스프린트별 핸드오프 아티팩트
├── src/                      # 소스 코드
├── data/                     # NSMC 원본/전처리
├── artifacts/                # 체크포인트, 메트릭, 리포트
├── notebooks/                # EDA
└── tests/
```

## 시작 가이드

```bash
# 1) 의존성 설치
uv sync

# 2) 현재 스프린트 실행 (Generator가 구현)
#    에이전트가 .harness/sprint-contract.yaml을 읽고 작업 수행

# 3) 스프린트 평가 (자동)
uv run python .harness/runner.py --sprint sprint-01

# 4) 보고서 확인
cat .harness/sprints/sprint-01/evaluation-report.md
```

## 하네스 흐름

1. **Planner (1회)** — `sprint-contract.yaml` 생성 완료
2. **Generator (스프린트별)** — 코드 구현 → `evaluation-request.md` 작성
3. **Evaluator (자동)** — `evaluator.py` 실행 → `evaluation-report.md` 생성
4. **Runner** — PASS → 다음 스프린트 / FAIL → 최대 3회 재시도 / 초과 → 에스컬레이션

## 문서

- [개발 계획 상세](PLAN.md)
- [하네스 가이드](AGENTS.md)
- [스프린트 계약](.harness/sprint-contract.yaml)
