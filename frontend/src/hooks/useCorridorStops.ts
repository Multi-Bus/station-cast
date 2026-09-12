import { useEffect, useState } from "react";
import { getCorridor, getStops } from "../api/client";
import { congestionLevelFromGrade, type NearbyStop } from "../types/stop";

const PLACEHOLDER_DISTANCE_M = 0;

/** Grid for the no-Kakao-key fallback map. Spacing is sized so the whole
 *  corridor lands inside 0-100% -- the old 18% row pitch pushed the last rows
 *  past the bottom edge, where they were clipped and unreachable. */
function placeholderMapPosition(index: number): { xPct: number; yPct: number } {
  const cols = 4;
  return {
    xPct: 14 + (index % cols) * 24,
    // Starts below the search bar and filter chips, ends above the peeking
    // sheet, so no marker is born underneath a piece of chrome.
    yPct: 21 + Math.floor(index / cols) * 12,
  };
}

export function useCorridorStops(): {
  stops: NearbyStop[];
  loading: boolean;
  error: boolean;
  retry: () => void;
} {
  const [stops, setStops] = useState<NearbyStop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);

    async function run() {
      try {
        const [{ stops: apiStops }, { stops: snapshots }] = await Promise.all([
          getStops(),
          getCorridor(),
        ]);
        const snapshotByStopId = new Map(snapshots.map((s) => [s.stop_id, s]));

        const built = apiStops.flatMap((s, index) => {
          const snapshot = snapshotByStopId.get(s.stop_id);
          if (!snapshot) return [];
          return [
            {
              id: String(s.stop_id),
              name: s.name,
              arsNumber: s.ars_number,
              distanceM: PLACEHOLDER_DISTANCE_M,
              waitEstimate: Math.round(snapshot.estimated_wait),
              congestionLevel: congestionLevelFromGrade(snapshot.grade),
              isFavorite: false,
              mapPosition: placeholderMapPosition(index),
              latLng: { lat: s.lat, lng: s.lon },
            } satisfies NearbyStop,
          ];
        });
        if (!cancelled) {
          setStops(built);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setStops([]);
          setError(true);
          setLoading(false);
        }
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  return { stops, loading, error, retry: () => setReloadKey((k) => k + 1) };
}
