<div align="center">

# Station Cast

**버스 정류장에서 지금 몇 명이 기다리는지를 공개 데이터로 역추정해 보여주는 오픈소스 서비스.**

![Python](https://img.shields.io/badge/Python-3.11-3776AB)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)
![React](https://img.shields.io/badge/React-Vite%20%2B%20TS-61DAFB)
![License](https://img.shields.io/badge/License-Apache--2.0-blue)

</div>

2026 오픈소스 개발자대회(제20회) 출품작이다. 팀 Multi-Bus.

공개 데이터에는 정류장에 남은 인원이 없다. 있는 것은 실제로 탄 사람(승차)과 배차간격뿐이다. Station Cast는 이 두 값으로 대기 인원을 추정한다. 추정치는 끝까지 추정으로 표기한다.

## 목차

- [기능](#기능)
- [동작 방식](#동작-방식)
- [빠른 시작](#빠른-시작)
- [사용 흐름](#사용-흐름)
- [API](#api)
- [설정](#설정)
- [검증](#검증)
- [한계](#한계)
- [내부 구조](#내부-구조)
- [개발](#개발)
- [라이선스](#라이선스)

## 기능

서울 종로, 명동, 을지로 회랑의 정류장 21개를 대상으로 한다(기본 `demo` 범위).

| 기능 | 내용 |
|---|---|
| 정류장 목록 | 정류장 ID, 좌표, ARS 번호를 반환한다 |
| 대기 인원 추정 | 특정 시간대의 대기 인원과 혼잡도 등급(여유, 보통, 혼잡)을 반환한다 |
| 24시간 곡선 | 정류장별 대기 인원 추정 곡선을 반환한다 |
| 회랑 스냅샷 | 회랑 전체 정류장의 한 시간대 값을 반환한다 |
| 실시간 도착 | 서울시 TOPIS 도착 정보를 매 요청마다 조회한다(키가 있을 때) |
| 날씨 맥락 | 날씨와 요일을 반영한 보정 설명을 반환한다(오늘·미래 날짜는 키가 있을 때) |
| 모바일 웹 UI | 지도, 정류장 목록, 정류장 상세 화면을 제공한다 |

## 동작 방식

노선별 실측 승차와 배차간격에 Little's Law를 적용한다.

```
W(s,t) = Σ_r  B_r(s,t) × (headway_r / 2) × (1 + cv_r²) / 60
```

- `B_r(s,t)`는 노선 `r`의 정류장 `s`, 시간 `t` 승차 인원이다. 서울 열린데이터광장 OA-12913의 2025-07~2026-06 12개월치를 일평균으로 합친 값이다.
- `headway_r`은 배차간격이다.
- `cv_r`은 배차 변동 계수다.

`/api/stops/{id}/congestion`은 조회 날짜의 요일, 날씨, 기온 보정계수를 곱해 그날 조건에 맞춘 값을 낸다(`features/demand_factors.py`).

검증 지표는 두 개다. 둘 다 회랑 21개 정류장 기준이다. 물리 제약(비음수, 용량) 위반율은 0.0%다. 보정계수가 일별 승차를 재현하는 MAPE는 12.1%다(무보정 25.3%). 자세한 근거는 [ARCHITECTURE.md](ARCHITECTURE.md)와 [검증](#검증)에 있다.

## 빠른 시작

요구 환경은 Python 3.11이다(`requires-python = ">=3.11,<3.12"`).

```bash
git clone https://github.com/Multi-Bus/station-cast.git
cd station-cast
pip install -c constraints.txt -e ".[dev]"
pytest
```

`constraints.txt`는 CI와 Dockerfile이 쓰는 버전 조합이다.

### 데이터 준비

`data/processed/`의 산출물은 저장소에 없다. 원본 데이터를 내려받아 파이프라인을 돌려야 API가 데이터를 낸다.

1. [`data/README.md`](data/README.md)의 §1~§7을 보고 원본을 `data/raw/`에 내려받는다. 기상청 ASOS 일자료만 회원가입과 로그인이 필요하다.
2. 파이프라인을 실행한다.

```bash
python scripts/build_processed.py                  # 기본: 회랑 21개 정류장(demo)
STATIONCAST_SCOPE=seoul python scripts/build_processed.py   # 서울 전체(정류장 12,537개, 약 5분, 산출물 158MB)
```

원본이 빠져 있으면 어떤 파일이 왜 필요한지 알려주고 멈춘다.

원본 없이 기동만 확인하려면 `python scripts/build_smoke_data.py`로 가짜 데이터를 만든다. 이 데이터는 실데이터가 아니다.

### API 실행

```bash
uvicorn stationcast.api.main:app --reload
```

`http://127.0.0.1:8000/docs`에서 Swagger UI를 볼 수 있다. 데이터 API는 모두 `/api` 아래에 있고, 루트에는 `/health`만 있다.

### 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173`에서 열린다. `/api`는 `http://127.0.0.1:8000`으로 프록시되므로 백엔드를 먼저 띄워야 정류장 데이터가 보인다. 백엔드가 응답하지 않으면 재시도 버튼이 있는 오류 화면이 뜬다.

### Docker 실행

```bash
docker compose up --build
```

`http://localhost:8000`에서 웹 UI와 `/api`가 함께 뜬다. 이미지는 빌드 시점의 `data/processed/`를 담는다. 데이터 없이 빌드하면 `/health`는 응답하지만 데이터 경로는 503을 낸다.

## 사용 흐름

1. 정류장 목록을 `GET /api/stops`로 받는다.
2. 정류장 하나를 고르고 `GET /api/stops/{id}/congestion?hour=...`로 시간대별 추정치를 본다. `hour`를 생략하면 현재값을 낸다.
3. `GET /api/stops/{id}/timeline`으로 하루 곡선을 보고, `GET /api/stops/{id}/arrivals`로 실시간 도착을 본다.
4. 웹 UI에서는 같은 흐름을 지도와 바텀시트로 한다. 즐겨찾기는 브라우저 로컬 저장소에 둔다.

행동 추천은 하지 않는다. 숫자를 보여주고 판단은 사용자가 한다.

## API

| 엔드포인트 | 내용 |
|---|---|
| `GET /api/stops` | 정류장 목록, 좌표, ARS 번호 |
| `GET /api/stops/{id}/congestion` | 시간대별 대기 인원 추정과 혼잡도 등급 |
| `GET /api/stops/{id}/timeline` | 24시간 대기 인원 곡선 |
| `GET /api/corridor` | 회랑 전체 정류장의 한 시간대 스냅샷 |
| `GET /api/stops/{id}/arrivals` | 실시간 버스 도착 정보(TOPIS) |
| `GET /api/stops/{id}/context` | 날씨, 요일 맥락과 보정 설명 |
| `GET /health` | 상태 확인. 루트에 있고 `/api` 접두사가 없다 |

응답 스키마는 [`docs/openapi.json`](docs/openapi.json)에 고정되어 있다. `api/main.py`나 `api/schemas.py`를 바꾸면 `python scripts/export_openapi.py`로 다시 생성해야 CI가 통과한다. 요청이 3초를 넘기면 504를 반환한다.

## 설정

키가 없어도 대기 인원 추정과 혼잡도 등급은 동작한다. 키가 없으면 아래 세 기능만 빠진다.

| 환경변수 | 발급처 | 없을 때 |
|---|---|---|
| `SEOUL_BUS_API_KEY` | 공공데이터포털 15000314 (서울시 버스도착정보조회) | `/api/stops/{id}/arrivals`가 `available: false`로 응답 |
| `KMA_FORECAST_API_KEY` | 공공데이터포털 15084084 (기상청 단기예보) | `/context`는 과거 날짜만 응답. `/congestion`은 날씨 보정 없이 응답 |
| `VITE_KAKAO_MAP_KEY` | Kakao Developers JavaScript 키 | 지도가 CSS 격자로 대체된다 |

두 공공데이터 키는 활용신청 후 자동 승인된다. 키는 퍼센트 인코딩된 상태로 붙여넣어도 `unquote()`로 디코딩된다.

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

`.env`는 `.gitignore`에 있다. Vite는 지도 키를 빌드 시점에 넣으므로 Docker에서는 `docker compose build --build-arg VITE_KAKAO_MAP_KEY=<키>`로 준다.

## 검증

| 항목 | 결과 | 비고 |
|---|---|---|
| 승차 재현 MAPE | 12.1% | 요일·날씨·기온 보정계수가 일별 승차를 재현하는 오차. 회랑 21개 정류장, 무보정은 25.3%. 보정계수는 2023-07~2025-06로 맞추고 2025-07~2026-06에서 쟀다 |
| 물리 제약 위반율 | 0.0% | 비음수, 용량 기준. 회랑 21개 정류장 기준이며 서울 전체는 용량 위반이 0.001%(13/948,384행) |
| 테스트 | `pytest` | CI 구성은 [개발](#개발) |

12.1%는 대기 인원 추정의 오차가 아니다. 대기 인원은 실측이 없어 오차를 잴 수 없다.

재현 명령:

```bash
python -m stationcast.validate.boarding_reproduction
python -m stationcast.validate.physical_constraints
```

## 한계

- 대기 인원은 실측이 아니라 추정이다. 화면에 "추정" 배지를 붙인다.
- 승차와 배차간격은 과거 데이터의 평균이다. 현재값도 실시간이 아니라 고정된 과거 파일을 읽는다. 실시간 승하차 소스는 아직 없다.
- 날씨와 요일 보정은 과거 평균을 조정하는 방식이다. 당일 실제 혼잡을 반영하지 않는다.
- 대상은 서울 회랑 21개 정류장이다. 다른 도시는 `ingest/` 어댑터를 새로 짜야 한다.
- 로그인과 계정 시스템은 없다. 즐겨찾기는 브라우저 로컬 저장소에만 남는다.
- 프론트엔드에서 즐겨찾기 추가는 되지만 즐겨찾기 탭, 설정 탭, 검색 화면은 자리표시자다. 사용자 위치 기반 거리와 목록 화면의 노선 목록도 근사치다.
- 운수업체용 노선별 집계 뷰는 아직 없다. 로드맵에만 있다.

<details>
<summary>미확인·제외 항목</summary>

미확인:

- 위 검증 수치(MAPE, 위반율)는 이 문서를 쓰면서 다시 돌려 확인하지 않았다.
- 테스트 통과 여부, Docker 빌드, 실제 API 응답은 실행해서 확인하지 않았다.
- 대회 결과와 본선 진출 여부는 확인하지 않았다.
- 프론트엔드의 화면 범위(회랑 비교 없음, 운영자 대시보드 없음)는 프론트 코드를 전부 읽지 않고 `frontend/README.md` 기준으로 적었다.

제외:

- 행동 추천은 만들지 않는다.
- 로그인과 계정은 만들지 않는다.
- 회랑 비교 화면과 운영자 대시보드는 이 앱에 없다.

</details>

## 내부 구조

<details>
<summary>계층과 디렉터리</summary>

```
station-cast/
  src/stationcast/
    ingest/       공개 데이터 수집 (OA-12913, OA-12912, 노선 배차, 날씨 예보, 공휴일, TOPIS)
    features/     날씨, 공휴일 피처와 보정계수
    estimator/    대기 인원 추정(Little's Law), 혼잡도 등급
    validate/     물리 제약 검증(비음수, 용량), 승차 재현 검증, 시각화
    api/          FastAPI 서비스
  frontend/       React + Vite + TypeScript 모바일 웹 UI
  scripts/        파이프라인, 가짜 데이터, OpenAPI 내보내기
  tests/          pytest
  docs/           openapi.json, LICENSE_POLICY.md
```

데이터 흐름은 `ingest → features → estimator → validate → api → frontend` 순서다.

</details>

<details>
<summary>CI와 기여 규칙</summary>

- CI는 `ruff check`, `mypy src`, `pytest`, OpenAPI 고정 검사를 돌린다.
- Docker 작업은 데이터 없이 가짜 데이터로 이미지를 검사한다.
- `main`에 직접 push하지 않는다. Issue, 브랜치, PR, 리뷰, merge 순서다.
- 커밋 메시지는 Conventional Commits를 따른다.
- 새 의존성은 OSI 승인 permissive 라이선스만 허용한다. GPL, AGPL, LGPL 계열은 CI가 막는다.

</details>

## 개발

```bash
pip install -c constraints.txt -e ".[dev]"
ruff check .
mypy src
pytest
```

브랜치 이름 규칙과 PR 절차는 [CONTRIBUTING.md](CONTRIBUTING.md)에 있다.

## 라이선스

[Apache License 2.0](LICENSE). 서드파티 고지는 [NOTICE](NOTICE)에 있다.
