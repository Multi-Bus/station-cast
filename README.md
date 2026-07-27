# Station Cast

버스 정류장별 **대기 혼잡도**를 공개 실데이터에서 역추정하여 대시보드로 제공하는 오픈소스 서비스.

> 🚧 개발 초기 단계입니다 (2026 오픈소스 개발자대회 출품 프로젝트). 이 문서는 스프린트가
> 진행되며 계속 채워집니다.

## 문제

버스 정류장에 몇 명이 **서서 기다리고 있는지**는 어떤 공개 데이터에도 없습니다.
공개된 것은 실제로 탄 사람(승차)과 내린 사람(하차)뿐입니다. Station Cast는 이 승하차
실데이터로부터 대기인원을 역추정하는 **큐 수지(queue balance) 방정식**을 사용합니다.

자세한 문제 정의와 접근 방식은 [ARCHITECTURE.md](./ARCHITECTURE.md)를 참고하세요. *(작성 중)*

## 5분 실행

```bash
git clone https://github.com/Multi-Bus/station-cast.git
cd station-cast
pip install -e ".[dev]"
pytest
```

*(API 서버 실행 방법은 `api/` 구현 완료 후 이 절에 추가됩니다 — S2 목표)*

## 디렉터리 구조

```
station-cast/
  src/stationcast/
    ingest/       # 공개 데이터 수집 (서울 열린데이터광장 OA-12913 등)
    features/     # λ(도착률)·환승률 추정, 날씨·공휴일 피처
    estimator/    # 큐 수지 방정식 — 대기인원 W(s,t) 추정
    validate/     # 물리 제약 검증 (비음수·마감조건·용량·환승 정합성)
    api/          # FastAPI 서비스
  tests/
  docs/           # AI_USAGE.md, LICENSE_POLICY.md 등
  data/           # raw/processed (커밋되지 않음, .gitkeep만 추적)
```

## 기여하기

[CONTRIBUTING.md](./CONTRIBUTING.md)를 참고하세요. 모든 변경은 Issue → 브랜치 → PR → 리뷰
→ merge 절차를 따릅니다. `main`에 직접 push하지 않습니다.

## 로드맵

[ROADMAP.md](./ROADMAP.md) *(S4에서 작성)*

## 라이선스

[Apache License 2.0](./LICENSE). 서드파티 라이선스 고지는 [NOTICE](./NOTICE)를 참고하세요.
이 저장소는 [2026 오픈소스 개발자대회](https://www.oss.kr) 출품작으로, 수상 시
운영규정에 따라 **5년간 Public 상태로 유지**됩니다.
