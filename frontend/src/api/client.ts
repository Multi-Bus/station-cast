import type {
  ArrivalsResponse,
  CongestionResponse,
  StopContextResponse,
  StopsResponse,
  TimelineResponse,
} from "./types";

const BASE = "/api";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return (await res.json()) as T;
}

export function getStops(): Promise<StopsResponse> {
  return getJSON("/stops");
}

export function getCongestion(stopId: number): Promise<CongestionResponse> {
  return getJSON(`/stops/${stopId}/congestion`);
}

export function getTimeline(stopId: number): Promise<TimelineResponse> {
  return getJSON(`/stops/${stopId}/timeline`);
}

export function getContext(stopId: number): Promise<StopContextResponse> {
  return getJSON(`/stops/${stopId}/context`);
}

export function getArrivals(stopId: number): Promise<ArrivalsResponse> {
  return getJSON(`/stops/${stopId}/arrivals`);
}
