/** Congestion thresholds and colors are fixed design tokens (README §Design Tokens) --
 * v >= 70 -> heavy, v >= 40 -> moderate, else relaxed. */
export type CongestionLevel = "relaxed" | "moderate" | "heavy";

export const CONGESTION_LABEL: Record<CongestionLevel, string> = {
  relaxed: "여유",
  moderate: "보통",
  heavy: "혼잡",
};

export function congestionLevelFromValue(value: number): CongestionLevel {
  if (value >= 70) return "heavy";
  if (value >= 40) return "moderate";
  return "relaxed";
}

export type FilterKey = "heavy" | "transferHub";

/** Shared by MapScreen (markers) and NearbyStopsPanel (list) so the two
 * views can never show a different set of stops for the same filter state. */
export function applyStopFilters(stops: NearbyStop[], activeFilters: Set<FilterKey>): NearbyStop[] {
  return stops.filter((s) => {
    if (activeFilters.has("heavy") && congestionLevelFromValue(s.congestionValue) !== "heavy")
      return false;
    if (activeFilters.has("transferHub") && !s.isTransferHub) return false;
    return true;
  });
}

export interface NearbyStop {
  id: string;
  name: string;
  routes: string[];
  distanceM: number;
  waitEstimate: number;
  congestionValue: number;
  isTransferHub: boolean;
  isFavorite: boolean;
  /** Placeholder map position as a percentage of the map area (no real map SDK yet). */
  mapPosition: { xPct: number; yPct: number };
}

export interface Arrival {
  route: string;
  stopsAway: number;
  etaMin: number;
  inVehicleLevel: CongestionLevel;
}

export interface HourlyPoint {
  hour: number;
  value: number;
}

export interface StopDetail extends NearbyStop {
  waitConfidenceLow: number;
  waitConfidenceHigh: number;
  weather: {
    summary: string;
    note: string;
  };
  arrivals: Arrival[];
  hourly: HourlyPoint[];
  stats: {
    todayAvgPct: number;
    peakHour: number;
    dayOverDayPct: number;
  };
}
