import { useCallback, useEffect, useRef, useState } from "react";
import { haversineDistanceM } from "../utils/geo";

/** A high-accuracy fix wanders a few metres while the device sits still, and
 * publishing that would reshuffle the distance-sorted nearby list. */
const MIN_MOVE_M = 10;

export interface UserLocationState {
  position: { lat: number; lng: number } | null;
  status: "idle" | "pending" | "granted" | "unavailable";
  retry: () => void;
}

/** Watches the device position for as long as the app is mounted, so the map's
 * location dot tracks movement instead of freezing on the fix taken at startup.
 * Permission-denied or unsupported browsers fall back to status="unavailable"
 * (no distance shown, no sort change) rather than erroring. */
export function useUserLocation(): UserLocationState {
  const [position, setPosition] = useState<{ lat: number; lng: number } | null>(null);
  const [status, setStatus] = useState<UserLocationState["status"]>("idle");
  const watchId = useRef<number | null>(null);

  const request = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setStatus("unavailable");
      return;
    }
    if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
    setStatus("pending");
    watchId.current = navigator.geolocation.watchPosition(
      (pos) => {
        const next = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setPosition((prev) =>
          prev && haversineDistanceM(prev, next) < MIN_MOVE_M ? prev : next,
        );
        setStatus("granted");
      },
      () => setStatus("unavailable"),
      { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 },
    );
  }, []);

  useEffect(() => {
    request();
    return () => {
      if (watchId.current !== null) {
        navigator.geolocation.clearWatch(watchId.current);
        watchId.current = null;
      }
    };
  }, [request]);

  return { position, status, retry: request };
}
