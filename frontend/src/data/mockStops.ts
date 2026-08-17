/** Sample data from design_source/design_handoff_station_cast/design-data.md.
 * Real /stops, /stops/{id}/congestion (grade included, issue #57),
 * /stops/{id}/timeline, /stops/{id}/context (weather, issue #47) all exist,
 * but the design's 0-100 congestion value and arrivals (issue #48, in
 * progress) have no backend source yet -- so this screen runs on the
 * design's own sample data until those land. Swapping to real fetches only
 * touches this file. */
import type { NearbyStop, StopDetail } from "../types/stop";

export const NEARBY_STOPS: NearbyStop[] = [
  {
    id: "gangnam",
    name: "강남역 정류장",
    routes: ["146", "402"],
    distanceM: 120,
    waitEstimate: 42,
    congestionValue: 82,
    isTransferHub: true,
    isFavorite: true,
    mapPosition: { xPct: 52, yPct: 44 },
  },
  {
    id: "yeoksam-post",
    name: "역삼동 우체국",
    routes: ["340"],
    distanceM: 280,
    waitEstimate: 14,
    congestionValue: 54,
    isTransferHub: false,
    isFavorite: false,
    mapPosition: { xPct: 30, yPct: 60 },
  },
  {
    id: "seocho-office",
    name: "서초구청",
    routes: ["740", "641"],
    distanceM: 410,
    waitEstimate: 46,
    congestionValue: 91,
    isTransferHub: false,
    isFavorite: true,
    mapPosition: { xPct: 68, yPct: 70 },
  },
  {
    id: "seoul-natl-univ-of-edu",
    name: "교대역 6번 출구",
    routes: ["405"],
    distanceM: 560,
    waitEstimate: 5,
    congestionValue: 23,
    isTransferHub: false,
    isFavorite: false,
    mapPosition: { xPct: 40, yPct: 22 },
  },
];

const HOURLY_VALUES: [number, number][] = [
  [7, 60],
  [8, 88],
  [9, 95],
  [10, 55],
  [11, 40],
  [12, 58],
  [13, 45],
  [14, 38],
  [15, 42],
  [16, 60],
  [17, 80],
  [18, 98],
  [19, 90],
  [20, 65],
  [21, 48],
  [22, 30],
];

export const STOP_DETAILS: Record<string, StopDetail> = {
  gangnam: {
    ...NEARBY_STOPS[0],
    waitConfidenceLow: 34,
    waitConfidenceHigh: 51,
    weather: {
      summary: "비 · 평일 · 21°C",
      note: "비 오는 평일 저녁은 평소보다 대기 인원이 12% 늘어나는 경향이 있습니다.",
    },
    arrivals: [
      { route: "146번", stopsAway: 2, etaMin: 3, inVehicleLevel: "heavy" },
      { route: "402번", stopsAway: 5, etaMin: 8, inVehicleLevel: "moderate" },
      { route: "740번", stopsAway: 8, etaMin: 12, inVehicleLevel: "relaxed" },
    ],
    hourly: HOURLY_VALUES.map(([hour, value]) => ({ hour, value })),
    stats: { todayAvgPct: 63, peakHour: 18, dayOverDayPct: 9 },
  },
};
