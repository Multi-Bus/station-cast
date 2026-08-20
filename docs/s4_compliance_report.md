# S4 컴플라이언스 리포트 — FOSSLight/ScanCode 최종 스캔 (issue #25)

`main`(`f8675e0`) 기준 최신 CI `license` job 실행 결과([run 32271204144](https://github.com/Multi-Bus/station-cast/actions/runs/32271204144))다. CI가 매 push/PR마다 자동으로 실행하는 스캔과 동일하며, 이 리포트는 S4 시점 스냅샷을 기록한다.

## 1. FOSSLight — 의존성 라이선스 스캔

`docs/LICENSE_POLICY.md`의 금지 키워드(`scripts/check_licenses.py`: SSPL, RSAL, Elastic License, BUSL, CC-BY-NC, GPL/LGPL/AGPL 등)를 기준으로 스캔했다.

| 대상 | 스캔 방식 | 의존성 수 | 금지 라이선스 | 라이선스 미확인 |
|---|---|---|---|---|
| Python (`pyproject.toml`) | `fosslight_dependency -m pypi` | 43 | 0건 | 0건 |
| npm (`frontend/package.json`) | `fosslight_dependency -m npm` | 6 (직접 의존성) | 0건 | 0건 |

npm 스캐너는 전이 의존성 전체를 훑지 않고 `package.json`의 직접 의존성만 다룬다 — 전체 `node_modules`(72개 패키지) 수동 확인은 `ci.yml`의 `license` job에 이미 기록돼 있듯 이 스캔 단계 도입 시점에 완료했고, 이번 스캔에서도 직접 의존성 6개 전부 이상 없음을 재확인했다.

## 2. ScanCode — 소스 파일 임베디드 라이선스 스캔

우리가 직접 작성한 소스 파일에 타 라이선스 텍스트가 섞여 들어왔는지 확인한다.

| 대상 | 스캔 파일 수 | 임베디드 라이선스 검출 |
|---|---|---|
| `src/` | 22 | 0건 |
| `scripts/`* | 2 | 0건 |
| `tests/` | 18 | 0건 |

\* `scripts/check_licenses.py`는 스캔 대상에서 제외한다 — 이 스크립트 자체가 금지 라이선스 이름을 문자열 리터럴(`FORBIDDEN_KEYWORDS`)로 갖고 있어 ScanCode 텍스트 매처가 항상 오탐하기 때문(`ci.yml` 주석 참고). 실제 임베디드 라이선스 텍스트가 아니다.

## 3. 결론

**FOSSLight·ScanCode 모두 이슈 0건.** S4 시점 기준 라이선스 컴플라이언스는 깨끗한 상태이며, 별도 조치가 필요한 항목은 없다.
