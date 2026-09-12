import { useEffect, useState } from "react";
import { getArrivals, getContext, getTimeline } from "../api/client";
import type { ApiArrivalInfo, StopContextResponse, TimelineResponse } from "../api/types";
import { congestionLevelFromGrade, type Arrival, type NearbyStop, type StopDetail } from "../types/stop";

/** Sort key. Runs on the normalised eta ("8분 후"), not on TOPIS's raw string. */
function arrivalMinutes(eta: string): number {
  if (eta === "곧 도착") return 0;
  const match = eta.match(/(\d+)분/);
  return match ? Number(match[1]) : Infinity;
}

/** TOPIS returns one packed string, e.g. "8분후[2번째 전]". Split it so the
 *  minutes can be the number the rider acts on and the position can sit beside
 *  it as context, instead of shipping the raw bracket notation to the screen. */
function parseArrivalMessage(message: string): { eta: string; stopsAway: string | null } {
  const match = message.match(/^(\d+)분\s*(\d+초)?후\s*\[(\d+)번째\s*전\]$/);
  if (match) return { eta: `${match[1]}분 후`, stopsAway: `${match[3]}정거장 전` };

  const minutesOnly = message.match(/^(\d+)분\s*(?:\d+초)?후/);
  if (minutesOnly) return { eta: `${minutesOnly[1]}분 후`, stopsAway: null };

  return { eta: message, stopsAway: null };
}

function toArrivals(arrivals: ApiArrivalInfo[]): Arrival[] {
  return arrivals
    .filter((a) => a.arrival_message_1 !== "운행종료")
    .map((a) => ({
      route: `${a.route_name}번`,
      direction: a.direction,
      ...parseArrivalMessage(a.arrival_message_1),
    }))
    .sort((a, b) => arrivalMinutes(a.eta) - arrivalMinutes(b.eta));
}

function weatherFromContext(context: StopContextResponse | null): StopDetail["weather"] {
  if (!context) {
    return { summary: "날씨 정보 없음", note: "이 날짜의 날씨 데이터가 아직 없습니다.", sky: "맑음", isForecast: false };
  }
  const sky =
    context.precipitation_type ??
    (context.precipitation > 0 ? "비" : context.snowfall > 0 ? "눈" : "맑음");
  return {
    summary: `${sky} · ${context.day_type} · ${Math.round(context.temperature)}°C`,
    note: context.congestion_note,
    sky,
    isForecast: context.is_forecast ?? false,
  };
}

function buildStopDetail(
  base: NearbyStop,
  timeline: TimelineResponse,
  arrivals: ApiArrivalInfo[],
  context: StopContextResponse | null,
): StopDetail {
  const hourly = timeline.timeline.map((t) => ({
    hour: t.hour,
    value: t.estimated_wait,
    level: congestionLevelFromGrade(t.grade),
  }));
  const peak = hourly.reduce((max, h) => (h.value > max.value ? h : max), hourly[0]);

  return {
    ...base,
    weather: weatherFromContext(context),
    arrivals: toArrivals(arrivals),
    hourly,
    stats: {
      peakHour: peak?.hour ?? 0,
    },
  };
}

export function useStopDetail(
  stop: NearbyStop | undefined,
): { detail: StopDetail | null; pending: boolean; error: boolean; retry: () => void } {
  const [detail, setDetail] = useState<StopDetail | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!stop) {
      setDetail(null);
      setError(false);
      return;
    }

    let cancelled = false;
    setPending(true);
    setError(false);
    setDetail(null);

    async function run() {
      try {
        const stopId = Number(stop!.id);
        const [timeline, arrivalsRes, context] = await Promise.all([
          getTimeline(stopId),
          getArrivals(stopId).catch(() => null),
          getContext(stopId).catch(() => null),
        ]);
        if (cancelled) return;
        setDetail(buildStopDetail(stop!, timeline, arrivalsRes?.arrivals ?? [], context));
      } catch {
        if (!cancelled) setError(true);
      } finally {
        if (!cancelled) setPending(false);
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [stop?.id, reloadKey]);

  return { detail, pending, error, retry: () => setReloadKey((k) => k + 1) };
}
