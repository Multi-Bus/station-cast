# Station Cast

버스 정류장별 대기 혼잡도를 공개 실데이터에서 역추정하여 대시보드로 제공하는 오픈소스 서비스입니다.

2026 오픈소스 개발자대회 출품 프로젝트이며, 개발 초기 단계입니다.

## 문제

버스 정류장에 몇 명이 서서 기다리고 있는지는 어떤 공개 데이터에도 없습니다. 공개된 것은
실제로 탄 사람(승차)뿐입니다. Station Cast는 이 승차 실데이터와 노선별 배차간격으로부터
대기인원을 역추정합니다(Little's Law 기반).

문제 정의와 접근 방식은 [ARCHITECTURE.md](./ARCHITECTURE.md)에 정리합니다. 작성 중입니다.

## 실행

```bash
git clone https://github.com/Multi-Bus/station-cast.git
cd station-cast
pip install -e ".[dev]"
pytest
```

데이터 파이프라인(`ingest/`, `features/`, `estimator/`)을 먼저 로컬에서 실행해
`data/processed/`를 채운 뒤(각 모듈의 `if __name__ == "__main__"` 참고), API 서버를 띄웁니다.

```bash
uvicorn stationcast.api.main:app --reload
```

`http://127.0.0.1:8000/docs`에서 Swagger UI로 확인할 수 있습니다. 응답 스키마는
[`docs/openapi.json`](./docs/openapi.json)에 freeze되어 있으며(issue #14),
`api/main.py`·`api/schemas.py` 변경 시 `python scripts/export_openapi.py`로
재생성해야 CI가 통과합니다.

### 프론트엔드 (issue #56)

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173`. 목데이터로 동작하며(백엔드 fetch 연동은 각 데이터가
준비되는 대로 진행), API 서버를 같이 띄우면 `/api`가 프록시됩니다. 자세한 범위는
[`frontend/README.md`](./frontend/README.md) 참고.

## 디렉터리 구조

```
station-cast/
  src/stationcast/
    ingest/       # 공개 데이터 수집 (서울 열린데이터광장 OA-12913 등)
    features/     # 날씨·공휴일 피처
    estimator/    # 대기인원 추정 (Little's Law 기반) — 정류장 대기인원 W(s,t)
    validate/     # 물리 제약 검증 (비음수·용량)
    api/          # FastAPI 서비스
  frontend/       # React + Vite + TypeScript 모바일 웹 UI
  design_source/  # 디자인 핸드오프 원본 (frontend/README.md 참고)
  tests/
  docs/           # LICENSE_POLICY.md 등
  data/           # raw/processed (커밋되지 않음, .gitkeep만 추적)
```

## 기여

[CONTRIBUTING.md](./CONTRIBUTING.md)를 참고하세요. 모든 변경은 Issue → 브랜치 → PR → 리뷰 →
merge 순서를 따릅니다. `main`에 직접 push하지 않습니다.

## 로드맵

[ROADMAP.md](./ROADMAP.md) (S4에서 작성)

## 라이선스

[Apache License 2.0](./LICENSE)이며, 서드파티 라이선스 고지는 [NOTICE](./NOTICE)를 참고하세요.

이 저장소는 [2026 오픈소스 개발자대회](https://www.oss.kr) 출품작으로, 수상 시 운영규정에
따라 5년간 Public 상태로 유지됩니다.
