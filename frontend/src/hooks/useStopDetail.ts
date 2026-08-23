import { useEffect, useState } from "react";
import { getArrivals, getContext, getTimeline } from "../api/client";
import type { ApiArrivalInfo, StopContextResponse, TimelineResponse } from "../api/types";
import { STOP_DETAILS } from "../data/mockStops";
import { congestionLevelFromGrade, type Arrival, type NearbyStop, type StopDetail } from "../types/stop";

function arrivalMinutes(message: string): number {
  if (message === "곧 도착") return 0;
  const match = message.match(/(\d+)분후/);
  return match ? Number(match[1]) : Infinity;
}

function toArrivals(arrivals: ApiArrivalInfo[]): Arrival[] {
  return arrivals
    .filter((a) => a.arrival_message_1 !== "운행종료")
    .map((a) => ({ route: `${a.route_name}번`, direction: a.direction, message: a.arrival_message_1 }))
    .sort((a, b) => arrivalMinutes(a.message) - arrivalMinutes(b.message));
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
  const routes = [...new Set(arrivals.map((a) => a.route_name))];

  return {
    ...base,
    routes: routes.length > 0 ? routes : base.routes,
    waitConfidenceLow: Math.round(base.waitEstimate * 0.8),
    waitConfidenceHigh: Math.round(base.waitEstimate * 1.2),
    weather: weatherFromContext(context),
    arrivals: toArrivals(arrivals),
    hourly,
    stats: {
      todayAvgPct: 0,
      peakHour: peak?.hour ?? 0,
      dayOverDayPct: 0,
    },
  };
}

export function useStopDetail(
  stop: NearbyStop | undefined,
  isMock: boolean,
): { detail: StopDetail | null; pending: boolean } {
  const [detail, setDetail] = useState<StopDetail | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!stop) {
      setDetail(null);
      return;
    }
    if (isMock) {
      setDetail(STOP_DETAILS[stop.id] ?? null);
      return;
    }

    let cancelled = false;
    setPending(true);
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
        if (!cancelled) setDetail(null);
      } finally {
        if (!cancelled) setPending(false);
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [stop?.id, isMock]);

  return { detail, pending };
}
