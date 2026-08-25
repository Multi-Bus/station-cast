# Station Cast

버스 정류장별 대기 혼잡도를 공개 실데이터에서 역추정하여 대시보드로 제공하는 오픈소스 서비스입니다.

2026 오픈소스 개발자대회 출품 프로젝트이며, 개발 초기 단계입니다.

## 문제

버스 정류장에 몇 명이 서서 기다리고 있는지는 어떤 공개 데이터에도 없습니다. 공개된 것은
실제로 탄 사람(승차)뿐입니다. Station Cast는 이 승차 실데이터와 노선별 배차간격으로부터
대기인원을 역추정합니다(Little's Law 기반).

문제 정의와 접근 방식은 [ARCHITECTURE.md](./ARCHITECTURE.md)에 정리했습니다.

## 실행

**Python 3.11이 필요합니다.** `pyproject.toml`의 `requires-python`이 `>=3.11,<3.12`이며,
3.12 이상에서는 설치 단계에서 막힙니다. CI와 Docker 이미지도 3.11로 고정돼 있습니다.

```bash
git clone https://github.com/Multi-Bus/station-cast.git
cd station-cast
python --version                              # Python 3.11.x
pip install -c constraints.txt -e ".[dev]"
pytest
```

`-c constraints.txt`는 CI·Dockerfile이 쓰는 것과 같은 의존성 버전 조합을 고정합니다.

### 데이터 파이프라인 재현 (issue #20)

`data/processed/`의 parquet은 커밋되지 않으므로(용량·라이선스), 각자 로컬에서 재생성합니다.
원본 CSV/XLSX는 기상청 로그인·공공데이터포털 인증키가 필요해 자동화할 수 없으니, 먼저
[`data/README.md`](./data/README.md) §1~§7을 보고 `data/raw/`에 내려받습니다. 그 다음:

```bash
python scripts/build_processed.py
```

`ingest/`·`features/` 산출물(정류장·노선별 승하차, 날씨, 공휴일, 요일×날씨×기온 보정계수)이
한 번에 만들어집니다. 원본이 빠져 있으면 어떤 파일이 왜 필요한지 먼저 알려주고 멈춥니다.

이어서 대기인원 추정치(`corridor_wait.parquet`, API가 서빙하는 `W(s,t)`)를 만듭니다.

```bash
python -m stationcast.estimator.wait_population
```

두 단계를 마치면 API 서버를 띄울 수 있습니다.

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
