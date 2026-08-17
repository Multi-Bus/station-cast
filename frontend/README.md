# Station Cast Frontend

React + Vite + TypeScript. Mobile web UI implementing the design handoff in
`design_source/design_handoff_station_cast/`.

## 실행

```bash
npm install
npm run dev
```

`http://localhost:5173`. `npm run dev`는 `/api`를 `http://127.0.0.1:8000`(백엔드
FastAPI 서버)로 프록시합니다.

## 현재 범위

디자인 핸드오프의 11개 화면 중 핵심 루프만 구현되어 있습니다: 지도 화면 셸
(플로팅 검색바·필터칩·지도 컨트롤·탭바), 3단 스냅 바텀시트(Peek/Half/Full),
정류장 목록, 정류장 상세(혼잡도 히어로·날씨·도착정보·시간대 그래프·통계).
즐겨찾기/설정 탭, 검색 화면은 아직 자리표시자입니다.

디자인 핸드오프의 "회랑"(노선 전체 정류장 혼잡도 비교) 및 운영자 대시보드 화면은
이 앱에서 구현하지 않습니다 -- 운수업체 대상 뷰라 앱이 아닌 별도 웹으로 제공할
예정입니다.

지도는 디자인과 동일하게 CSS 격자 플레이스홀더입니다 -- 실제 지도는 **카카오맵 JS
SDK**로 교체할 예정입니다(issue #59, S4). 네이버 지도는 가입 시 결제수단 등록이
선행 조건이라 제외했습니다.

카카오맵 키 발급: [Kakao Developers](https://developers.kakao.com)에서 앱 생성 →
[제품 설정] > [카카오맵]에서 사용 설정 → [앱 설정] > [앱 키]에서 JavaScript 키 확인 →
플랫폼에 로컬/배포 도메인 등록. 발급받은 키는 `.env`의 `VITE_KAKAO_MAP_KEY`로 설정하며,
`.env`는 커밋하지 않습니다. **키가 없어도 앱은 기존 CSS 격자로 폴백 렌더링됩니다** --
재현성 검증(외부인 clone 시나리오)이 카카오 키 발급 여부에 좌우되지 않도록 하기 위함입니다.

## 데이터

`src/data/mockStops.ts`가 `design-data.md`의 샘플 데이터를 그대로 담고
있습니다. 백엔드에 `/stops`, `/stops/{id}/congestion`(등급 필드 포함, issue #57),
`/stops/{id}/timeline`, `/stops/{id}/context`(날씨·요일 보정, issue #47)가 이미
있지만(`docs/openapi.json` 참고), 이 화면이 쓰는 0-100 혼잡도 값·도착정보(issue #48
진행 중)는 아직 백엔드 소스가 없어서, 당분간 이 목데이터로 화면을 채워 둡니다.
실제 fetch로 바꾸는 작업은 각 데이터가 백엔드에 준비되는 대로 `src/data/`만
갈아끼우면 되도록 컴포넌트와 분리해 뒀습니다.
