# 라이선스 정책

새 의존성의 라이선스를 두 층위로 구분해서 다룬다.

| 층위 | 이유 | 대상 | 조치 |
|---|---|---|---|
| ① OSI 미승인 (절대 금지) | 비상업 조건 등이 포함돼 OSI 승인 오픈소스 정의를 충족하지 않음 | SSPL, RSALv2, ELv2, BUSL, CC-BY-NC 등 non-OSI | PR 리뷰에서 차단 |
| ② copyleft 회피 (팀 정책) | Apache-2.0 배포물과의 결합 이슈(라이선스 전염, 재배포 조건 충돌)를 피하기 위한 선택 | GPL / AGPL / LGPL 등 copyleft | PR 리뷰에서 차단, 단 라이선스 자체의 결함은 아님 |

## 왜 이렇게 나누는가

MIT, Apache 2.0, GPL-2.0/3.0, LGPL, BSD 등은 전부 OSI 승인 라이선스다. 즉 GPL·LGPL은
그 자체로 문제가 아니다. 이들을 프로젝트에서 배제하는 것은 Apache-2.0으로 배포하는
산출물과의 결합 이슈를 피하려는 팀의 선택이지, 라이선스 자체의 결함 때문이 아니다.

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
| Redis 7.4+ | RSALv2/SSPL | Valkey (BSD-3) |
| MongoDB | SSPL | PostgreSQL |
| Elasticsearch 7.11+ | SSPL/ELv2 | OpenSearch (Apache-2.0) |
| psycopg2/3 | LGPL-3.0 | asyncpg (Apache-2.0) |
| mysqlclient | GPL-2.0 | (PostgreSQL 사용) |
| Grafana 9+ | AGPL-3.0 | MVP 미사용 |
| Docker Desktop | 상용 라이선스 | Docker Engine / Podman |

## 새 의존성을 추가할 때

1. PyPI/npm 등에서 라이선스를 확인한다.
2. 위 표에 없는 라이선스라면 [choosealicense.com](https://choosealicense.com) 또는 SPDX
   목록에서 OSI 승인 여부를 확인한다.
3. 위 표에 없는 신규 라이브러리는 PR 설명에 라이선스를 명시해 리뷰어가 확인할 수 있게 한다.
