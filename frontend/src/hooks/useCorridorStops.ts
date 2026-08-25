import { useEffect, useState } from "react";
import { getCorridor, getStops } from "../api/client";
import { congestionLevelFromGrade, type NearbyStop } from "../types/stop";

const PLACEHOLDER_ROUTES: string[] = [];
const PLACEHOLDER_DISTANCE_M = 0;

function placeholderMapPosition(index: number): { xPct: number; yPct: number } {
  const cols = 4;
  return {
    xPct: 15 + (index % cols) * 22,
    yPct: 15 + Math.floor(index / cols) * 18,
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
              routes: PLACEHOLDER_ROUTES,
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
