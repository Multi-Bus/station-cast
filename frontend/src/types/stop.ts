/** The level always comes from the backend's own grade (congestion.py's W/capacity
 * ratio, via congestionLevelFromGrade) or is set directly in mock data -- there is
 * no client-side numeric threshold any more (issue #111). */
export type CongestionLevel = "relaxed" | "moderate" | "heavy";

export const CONGESTION_LABEL: Record<CongestionLevel, string> = {
  relaxed: "여유",
  moderate: "보통",
  heavy: "혼잡",
};

export function congestionLevelFromGrade(grade: string): CongestionLevel {
  if (grade === "혼잡") return "heavy";
  if (grade === "보통") return "moderate";
  return "relaxed";
}

export type FilterKey = "heavy";

/** Shared by MapScreen (markers) and NearbyStopsPanel (list) so the two
 * views can never show a different set of stops for the same filter state. */
export function applyStopFilters(stops: NearbyStop[], activeFilters: Set<FilterKey>): NearbyStop[] {
  return stops.filter((s) => {
    if (activeFilters.has("heavy") && s.congestionLevel !== "heavy") return false;
    return true;
  });
}

/** Name-only: per-stop route lists aren't available from the backend for the
 * full corridor (only for a selected stop's live arrivals), so route-number
 * search isn't feasible here. */
export function applySearchQuery(stops: NearbyStop[], query: string): NearbyStop[] {
  const trimmed = query.trim();
  if (!trimmed) return stops;
  return stops.filter((s) => s.name.includes(trimmed));
}

export interface NearbyStop {
  id: string;
  name: string;
  arsNumber?: string;
  routes: string[];
  distanceM: number;
  waitEstimate: number;
  congestionLevel: CongestionLevel;
  isFavorite: boolean;
  mapPosition: { xPct: number; yPct: number };
  latLng: { lat: number; lng: number };
}

export interface Arrival {
  route: string;
  direction: string;
  message: string;
}

export interface HourlyPoint {
  hour: number;
  value: number;
  level: CongestionLevel;
}

export interface StopDetail extends NearbyStop {
  weather: {
    summary: string;
    note: string;
    sky: string;
    isForecast: boolean;
  };
  arrivals: Arrival[];
  hourly: HourlyPoint[];
  stats: {
    peakHour: number;
  };
}
