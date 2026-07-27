# 라이선스 정책

2026 오픈소스 개발자대회 운영규정 제8조를 근거로, 우리 프로젝트는 라이선스를 **두 층위**로
구분해서 다룬다.

| 층위 | 근거 | 대상 | 조치 |
|---|---|---|---|
| **① 규정 위반 (절대 금지)** | 제8조①②③ — 직접 작성한 소스코드에는 **OSI 인증** 라이선스 적용 의무. 비상업 조건이 포함된 라이선스는 OSI 인증이 아니므로 원칙적으로 사용 불가 | SSPL, RSALv2, ELv2, BUSL, CC-BY-NC 등 **non-OSI** | CI가 PR **차단** |
| **② 자체 호환성 정책 (우리 선택)** | 2차 라이선스 검증(5점)의 "서로 다른 라이선스 조합·소스코드 간 결합 이슈" 회피 | GPL / AGPL / LGPL 등 copyleft | CI가 PR **차단**, 단 규정 위반은 아님 |

## 왜 이렇게 나누는가

운영규정 제8조①은 대표적인 OSI 인증 라이선스 예시로 **"MIT, Apache 2.0, GPL-2.0/3.0, LGPL,
BSD 등"**을 명시한다. 즉 **GPL·LGPL은 규정상 허용된다.** 우리가 이들을 프로젝트에서
배제하는 것은 Apache-2.0으로 배포하는 우리 산출물과의 결합 이슈(라이선스 전염, 재배포 조건
충돌)를 원천적으로 피하려는 **팀의 선택**이지, 대회 규정이 요구하는 바가 아니다.

## 금지 목록 (예시)

| 라이선스 | 층위 | 비고 |
|---|---|---|
| SSPL | ① | MongoDB, Redis 7.4+ 등에서 사용. OSI 미승인 |
| RSALv2 | ① | Redis 7.4+ |
| Elastic License v2 (ELv2) | ① | Elasticsearch, Kibana 7.11+ |
| BUSL | ① | 일부 상용 오픈코어 제품 |
| CC-BY-NC 계열 | ① | 비상업 조건 |
| GPL-2.0 / GPL-3.0 | ② | 프로젝트 전체가 GPL 조건을 상속받을 위험 |
| AGPL-3.0 | ② | 네트워크 사용도 배포로 간주 — SaaS 배포와 상충 |
| LGPL | ② | 동적 링크는 상대적으로 안전하지만, 명확성을 위해 배제 |

## 대체재

| 피할 것 | 문제 | 대체 |
|---|---|---|
| Redis 7.4+ | RSALv2/SSPL | **Valkey** (BSD-3) |
| MongoDB | SSPL | PostgreSQL |
| Elasticsearch 7.11+ | SSPL/ELv2 | OpenSearch (Apache-2.0) |
| psycopg2/3 | LGPL-3.0 | **asyncpg** (Apache-2.0) |
| mysqlclient | GPL-2.0 | (PostgreSQL 사용) |
| Grafana 9+ | AGPL-3.0 | MVP 미사용 |
| Docker Desktop | 상용 라이선스 | Docker Engine / Podman |

## 새 의존성을 추가할 때

1. PyPI/npm 등에서 라이선스를 확인한다.
2. 위 표에 없는 라이선스라면 [choosealicense.com](https://choosealicense.com) 또는 SPDX
   목록에서 OSI 승인 여부를 확인한다.
3. CI의 라이선스 스캔(S1에서 FOSSLight/ScanCode 도입 예정)이 자동으로 차단하지만,
   추가 전에 이 문서에 없는 신규 라이브러리는 PR 설명에 라이선스를 명시한다.
