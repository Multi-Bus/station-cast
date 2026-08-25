# Station Cast

버스 정류장에 **지금 몇 명이 서서 기다리는지**를 공개 실데이터에서 역추정해 보여주는
오픈소스 서비스입니다. 2026 오픈소스 개발자대회 출품작입니다.

## 문제

버스 정류장에 몇 명이 서 있는지는 어떤 공개 데이터에도 없습니다. 공개된 것은 실제로
탄 사람(승차)뿐이고, 정류장에 남은 인원 수는 공개 데이터에 없습니다.

지도 앱이 보여주는 차내 혼잡도와는 다른 층위입니다. 차내 혼잡도는 버스 안을,
Station Cast는 정류장을 봅니다.

## 무엇을 제공하는가

서울 종로·명동·을지로 회랑의 **21개 정류장**에 대해:

| 엔드포인트 | 내용 |
|---|---|
| `GET /stops` | 정류장 목록·좌표·ARS번호 |
| `GET /stops/{id}/congestion` | 특정 시간대 대기인원 추정치 + 혼잡도 등급(여유/보통/혼잡) |
| `GET /stops/{id}/timeline` | 24시간 대기인원 곡선 |
| `GET /corridor` | 회랑 전체 정류장의 한 시간대 스냅샷 |
| `GET /stops/{id}/arrivals` | 실시간 버스 도착정보 (서울 TOPIS) |
| `GET /stops/{id}/context` | 날씨·요일 맥락과 혼잡도 보정 설명 |

여기에 모바일 웹 대시보드(React)가 붙습니다.

**대기인원은 끝까지 추정치로 표기합니다.** 실측이 불가능한 값이라 화면에도 "추정"
배지를 답니다. 행동 추천은 하지 않습니다 — 숫자를 보여주고 판단은 사용자가 합니다.

## 어떻게 추정하는가

노선별 실측 승차와 실측 배차간격에 Little's Law를 적용합니다. 

```
W(s,t) = Σ_r  B_r(s,t) × (headway_r / 2) × (1 + cv_r²) / 60
```

`B_r`(승차)과 `headway_r`(배차간격) 모두 공개 실데이터입니다. 검증 결과는 물리 제약
위반율 **0.0%**(비음수·용량), 승차 재현 MAPE **11.9%**(학습/검증 구간 분리)입니다.

자세한 근거와 대안 검토는 [ARCHITECTURE.md](./ARCHITECTURE.md)와
[docs/s3_validation_report.md](./docs/s3_validation_report.md)에 있습니다.

## 실행

### 0. 사전 준비

**Python 3.11이 필요합니다.** `pyproject.toml`의 `requires-python`이 `>=3.11,<3.12`입니다.

### 1. 설치

```bash
git clone https://github.com/Multi-Bus/station-cast.git
cd station-cast
python --version                              # Python 3.11.x
pip install -c constraints.txt -e ".[dev]"
pytest
```

`-c constraints.txt`는 CI·Dockerfile이 쓰는 것과 같은 의존성 버전 조합을 고정합니다.

### 2. API 키 발급 (선택)

**키가 없어도 대기인원 추정·혼잡도 등급 등 핵심 기능은 전부 동작합니다.** 그 중 세 가지만 비활성화됩니다.

| 환경변수 | 발급처 | 승인 | 없으면 |
|---|---|---|---|
| `SEOUL_BUS_API_KEY` | [공공데이터포털 15000314](https://www.data.go.kr/data/15000314/openapi.do) — 서울시 버스도착정보조회 | 자동승인(즉시) | `/arrivals`가 `available: false`로 응답 |
| `KMA_FORECAST_API_KEY` | [공공데이터포털 15084084](https://www.data.go.kr/data/15084084/openapi.do) — 기상청 단기예보 | 자동승인(즉시) | `/context`가 과거 날짜만 응답, 오늘·미래는 404 |
| `VITE_KAKAO_MAP_KEY` | [Kakao Developers](https://developers.kakao.com) JavaScript 키 | 즉시 | 지도가 CSS 격자 플레이스홀더로 폴백 |

위 두가지는 data.go.kr 로그인 후 **활용신청 → 자동승인**이라 대기 없이 바로 받습니다.
카카오맵은 Kakao Developers에 가입하여 카카오맵 사용 버튼을 누른 뒤, JavaScripts 키를 발급 받습니다.

```bash
cp .env.example .env                 # 백엔드 키 2개
cp frontend/.env.example frontend/.env   # 카카오 지도 키
```

`.env`는 `.gitignore`에 있습니다. 포털이 주는 키가 퍼센트 인코딩(`%2F`, `%3D` 등)돼
있어도 그대로 붙여넣으면 됩니다 — 코드가 `unquote()`로 디코딩합니다.

### 3. 원본 데이터 내려받기

`data/processed/`의 parquet은 커밋되지 않으므로(용량·라이선스), 각자 로컬에서 재생성합니다.
원본 CSV/XLSX는 기상청 로그인·공공데이터포털 인증키가 필요해 자동화할 수 없으니, 먼저
[`data/README.md`](./data/README.md) §1~§7을 보고 `data/raw/`에 내려받습니다.

대부분은 **인증키 없이** 받을 수 있습니다(서울 열린데이터광장 CSV 3종, 서울시 버스운행노선
XLSX). 기상청 ASOS 일자료만 회원가입·로그인이 필요하고, 특일정보(공휴일)는 위 2번과 같은
방식의 오픈API 키를 씁니다.

### 4. 파이프라인 실행

```bash
python scripts/build_processed.py
```

`ingest/`·`features/` 산출물(정류장·노선별 승하차, 날씨, 공휴일, 요일×날씨×기온 보정계수)이
한 번에 만들어집니다. 원본이 빠져 있으면 어떤 파일이 왜 필요한지 먼저 알려주고 멈춥니다.

이어서 대기인원 추정치(`corridor_wait.parquet`, API가 서빙하는 `W(s,t)`)를 만듭니다.

```bash
python -m stationcast.estimator.wait_population
```

### 5. API 서버

```bash
uvicorn stationcast.api.main:app --reload
```

`http://127.0.0.1:8000/docs`에서 Swagger UI로 확인할 수 있습니다. 응답 스키마는
[`docs/openapi.json`](./docs/openapi.json)에 freeze되어 있으며(issue #14),
`api/main.py`·`api/schemas.py` 변경 시 `python scripts/export_openapi.py`로
재생성해야 CI가 통과합니다.

### 6. 프론트엔드 (issue #56)

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173`. `/api`가 API 서버(`http://127.0.0.1:8000`)로
프록시되므로 백엔드를 같이 띄워야 정류장 데이터가 뜹니다 -- 백엔드가 응답하지
않으면 재시도 버튼이 있는 에러 상태가 표시됩니다(목데이터 폴백 없음, issue
#136). 자세한 범위는 [`frontend/README.md`](./frontend/README.md) 참고.

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

## 규칙

- `main`에 직접 push하지 않습니다. 모든 변경은 Issue → 브랜치 → PR → 리뷰 → merge를 거칩니다.
- 커밋 메시지는 Conventional Commits(`<type>(<scope>): <description>`)를 따릅니다.
- 새 의존성은 OSI 승인 permissive 라이선스만 허용합니다. GPL·AGPL·LGPL 계열은 CI가
  차단합니다([docs/LICENSE_POLICY.md](./docs/LICENSE_POLICY.md)).

브랜치명 규칙과 PR 절차는 [CONTRIBUTING.md](./CONTRIBUTING.md)에 있습니다.

## 로드맵

MVP 이후 방향(실시간 연동, 타 도시 확장, 운수업체 배차 분석)은 [ROADMAP.md](./ROADMAP.md)에 정리했습니다.

## 라이선스

[Apache License 2.0](./LICENSE)이며, 서드파티 라이선스 고지는 [NOTICE](./NOTICE)를 참고하세요.

