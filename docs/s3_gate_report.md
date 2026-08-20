# S3 GATE — 성능표 확보 (issue #21, B트랙)

B트랙(추정·검증, issue #16·#17)에서 확보한 실측 수치를 정리한 최종 성능표다.

## 최종 수치표

| 지표 | 실측치 | 근거 |
|---|---|---|
| 비음수 위반율 | 0.0% | `docs/s3_validation_report.md` §1 |
| 용량 위반율 (버스 정원 46명 가정) | 0.0% | `docs/s3_validation_report.md` §1 |
| 승차 재현 MAPE — 코리더 평균 (요일+날씨+기온 보정, held-out 1년) | 11.9% | `docs/s3_validation_report.md` §3~4 |
| 승차 재현 MAPE — 보정 효과 (무보정 → 보정 후) | 26.1% → 11.9% (14.2%p 개선) | `docs/s3_validation_report.md` §3~4 |
| 승차 재현 MAPE — 정류장별 범위 (21개 정류장) | 9.5%(롯데백화점) ~ 18.5%(광화문역), 중앙값 11.4% | `docs/s3_validation_report.md` §3~4 "정류장별 상세" |
| 정류장별 대기인원 W(s,t) 시각화 | 21개 정류장 전체 확보 | `docs/wait_curves/overview.png` |

## 측정 불가 항목

이전 큐 수지 모델의 "일 마감 조건"(W(s, 막차) ≈ 0)은 `estimator/wait_population.py`가 이월(reservoir) 항 자체를 갖지 않는 구조로 바뀌면서 개념이 성립하지 않게 됐다. 미달이 아니라 이 모델에서는 애초에 정의되지 않는 항목이라 표에서 제외했다(`docs/s3_validation_report.md` §2, `physical_constraints.py` 모듈 docstring 참고).

## 참고 자료

- 승차 재현 MAPE 산출 방법(train/test 분리 등): `docs/s3_validation_report.md`
- 정류장별 W(s,t) 곡선: `docs/wait_curves/overview.png`
- 배차 불규칙성 보정(cv) 반영: issue #82
