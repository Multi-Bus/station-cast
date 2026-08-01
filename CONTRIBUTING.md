# Contributing to Station Cast

## 기본 원칙

- `main` 브랜치에 직접 push 하지 않습니다. 모든 변경은 Issue → 브랜치 → PR → 리뷰(작성자를
  제외한 팀원 전원 승인) → merge 순서를 따릅니다.
- 모든 PR은 CI(ruff, mypy, pytest, 라이선스 스캔)를 통과해야 merge할 수 있습니다.
- 페어로 작업한 경우 커밋 메시지에 `Co-authored-by:` 트레일러를 추가해 두 사람의 기여를
  모두 남깁니다.

## 브랜치 이름

```
<type>/<short-description>
```

예: `feat/oa12913-collector`, `fix/queue-balance-negative`, `docs/architecture`

## 커밋 메시지 — Conventional Commits

```
<type>(<scope>): <description>

feat(ingest): add OA-12913 monthly collector
fix(estimator): clamp negative queue values before optimization
docs(readme): add 5-minute quickstart
```

type: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`

## PR 절차

1. 관련 Issue를 먼저 만들거나 기존 Issue에 연결합니다.
2. 브랜치를 파고 작업합니다. 커밋은 작고 의미 단위로 나눕니다.
3. PR을 열 때 템플릿의 체크리스트를 채웁니다 (테스트 방법, 관련 Issue 등).
4. PR 작성자를 제외한 팀원 전원의 리뷰 승인을 받습니다.
5. CI green 확인 후 merge (squash 또는 merge commit, 팀 합의에 따름).

## 의존성 추가 시

새 라이브러리를 추가하는 PR은 CI의 라이선스 스캔을 통과해야 합니다. non-OSI 라이선스
(SSPL, RSALv2, ELv2 등)와 copyleft 계열(GPL, AGPL, LGPL)은 기본적으로 차단됩니다.
자세한 기준은 [docs/LICENSE_POLICY.md](./docs/LICENSE_POLICY.md)를 참고하세요.

## 로컬 개발 환경

```bash
pip install -e ".[dev]"
pre-commit install
pytest
```
