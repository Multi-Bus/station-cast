/** Sample data from design_source/design_handoff_station_cast/design-data.md.
 * Used by useCorridorStops/useStopDetail as the offline fallback when the
 * backend is unreachable. */
import type { CongestionLevel, NearbyStop, StopDetail } from "../types/stop";

export const NEARBY_STOPS: NearbyStop[] = [
  {
    id: "gangnam",
    name: "강남역 정류장",
    routes: ["146", "402"],
    distanceM: 120,
    waitEstimate: 42,
    congestionLevel: "heavy",
    isFavorite: true,
    mapPosition: { xPct: 52, yPct: 44 },
    latLng: { lat: 37.4979, lng: 127.0276 },
  },
  {
    id: "yeoksam-post",
    name: "역삼동 우체국",
    routes: ["340"],
    distanceM: 280,
    waitEstimate: 14,
    congestionLevel: "moderate",
    isFavorite: false,
    mapPosition: { xPct: 30, yPct: 60 },
    latLng: { lat: 37.5007, lng: 127.0364 },
  },
  {
    id: "seocho-office",
    name: "서초구청",
    routes: ["740", "641"],
    distanceM: 410,
    waitEstimate: 46,
    congestionLevel: "heavy",
    isFavorite: true,
    mapPosition: { xPct: 68, yPct: 70 },
    latLng: { lat: 37.4836, lng: 127.0326 },
  },
  {
    id: "seoul-natl-univ-of-edu",
    name: "교대역 6번 출구",
    routes: ["405"],
    distanceM: 560,
    waitEstimate: 5,
    congestionLevel: "relaxed",
    isFavorite: false,
    mapPosition: { xPct: 40, yPct: 22 },
    latLng: { lat: 37.4935, lng: 127.0144 },
  },
];

const HOURLY_VALUES: [number, number, CongestionLevel][] = [
  [7, 60, "moderate"],
  [8, 88, "heavy"],
  [9, 95, "heavy"],
  [10, 55, "moderate"],
  [11, 40, "moderate"],
  [12, 58, "moderate"],
  [13, 45, "moderate"],
  [14, 38, "relaxed"],
  [15, 42, "moderate"],
  [16, 60, "moderate"],
  [17, 80, "heavy"],
  [18, 98, "heavy"],
  [19, 90, "heavy"],
  [20, 65, "moderate"],
  [21, 48, "moderate"],
  [22, 30, "relaxed"],
];

export const STOP_DETAILS: Record<string, StopDetail> = {
  gangnam: {
    ...NEARBY_STOPS[0],
    weather: {
      summary: "비 · 평일 · 21°C",
      note: "비 오는 평일 저녁은 평소보다 대기 인원이 12% 늘어나는 경향이 있습니다.",
      sky: "비",
      isForecast: false,
    },
    arrivals: [
      { route: "146번", direction: "청계산입구", message: "3분후[2번째 전]" },
      { route: "402번", direction: "염곡동", message: "8분후[5번째 전]" },
      { route: "740번", direction: "국민대", message: "12분후[8번째 전]" },
    ],
    hourly: HOURLY_VALUES.map(([hour, value, level]) => ({
      hour,
      value,
      level,
    })),
    stats: { peakHour: 18 },
  },
};
