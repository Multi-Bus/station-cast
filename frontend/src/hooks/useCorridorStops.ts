import { useEffect, useState } from "react";
import { getCongestion, getStops } from "../api/client";
import { NEARBY_STOPS } from "../data/mockStops";
import type { NearbyStop } from "../types/stop";

const PLACEHOLDER_ROUTES: string[] = [];
const PLACEHOLDER_DISTANCE_M = 0;

function congestionValueFromGrade(grade: string): number {
  if (grade === "혼잡") return 85;
  if (grade === "보통") return 55;
  return 15;
}

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
  usingMock: boolean;
} {
  const [stops, setStops] = useState<NearbyStop[]>([]);
  const [loading, setLoading] = useState(true);
  const [usingMock, setUsingMock] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        const { stops: apiStops } = await getStops();
        const built = await Promise.all(
          apiStops.map(async (s, index) => {
            const congestion = await getCongestion(s.stop_id);
            return {
              id: String(s.stop_id),
              name: s.name,
              arsNumber: s.ars_number,
              routes: PLACEHOLDER_ROUTES,
              distanceM: PLACEHOLDER_DISTANCE_M,
              waitEstimate: Math.round(congestion.estimated_wait),
              congestionValue: congestionValueFromGrade(congestion.grade),
              isTransferHub: false,
              isFavorite: false,
              mapPosition: placeholderMapPosition(index),
              latLng: { lat: s.lat, lng: s.lon },
            } satisfies NearbyStop;
          }),
        );
        if (!cancelled) {
          setStops(built);
          setUsingMock(false);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setStops(NEARBY_STOPS);
          setUsingMock(true);
          setLoading(false);
        }
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, []);

  return { stops, loading, usingMock };
}
