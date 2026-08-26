# Station Cast Frontend

React + Vite + TypeScript. Station Cast의 모바일 웹 UI입니다.

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

지도는 **카카오맵 JS SDK**(`react-kakao-maps-sdk`)로 렌더링됩니다(issue #59, S4).
네이버 지도는 가입 시 결제수단 등록이 선행 조건이라 제외했습니다.

카카오맵 키 발급: [Kakao Developers](https://developers.kakao.com)에서 앱 생성 →
[제품 설정] > [카카오맵]에서 사용 설정 → [앱 설정] > [앱 키] > **JavaScript 키**
탭에서 키 확인 및 로컬/배포 도메인 등록(`http://localhost:5173` 등) -- 도메인을
안 넣으면 스크립트 요청이 401로 거부됩니다. `.env.example`을 `.env`로 복사해
`VITE_KAKAO_MAP_KEY`에 발급받은 키를 설정하세요(`.env`는 커밋하지
않습니다). **키가 없어도 앱은 기존 CSS 격자로 폴백 렌더링됩니다** -- 지도
SDK 하나가 없다고 나머지 화면까지 막히지 않도록 하기 위함입니다.

## 데이터

`src/hooks/useCorridorStops.ts`·`useStopDetail.ts`가 백엔드(`/stops`,
`/stops/{id}/congestion`, `/stops/{id}/timeline`, `/stops/{id}/context`,
`/stops/{id}/arrivals` -- `docs/openapi.json` 참고)를 실제로 호출해 코리더
21개 정류장을 채웁니다. 로컬 목데이터 폴백은 없습니다 -- 백엔드가 응답하지
않으면(서버 미기동 등) 재시도 버튼이 있는 에러 상태를 보여줍니다(issue #136).
프론트를 단독으로 재현하려면 백엔드(`uvicorn stationcast.api.main:app`)를
같이 띄워야 합니다.

백엔드에 아직 없는 값(사용자 위치 기반 거리, 지도·목록 화면의 정류장별 노선
목록)은 근사치로 채워 둡니다. 상세화면의 노선 목록만은 예외로, `/arrivals`
응답에서 실제 노선번호를 뽑아 씁니다. 실제 소스가 생기면 각 지점만
갈아끼우면 되도록 훅과 컴포넌트를 분리해 뒀습니다.
