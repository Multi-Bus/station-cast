import { useCallback, useEffect, useState } from "react";

export interface UserLocationState {
  position: { lat: number; lng: number } | null;
  status: "idle" | "pending" | "granted" | "unavailable";
  retry: () => void;
}

/** One-shot on mount; permission-denied or unsupported browsers fall back to
 * status="unavailable" (no distance shown, no sort change) rather than erroring. */
export function useUserLocation(): UserLocationState {
  const [position, setPosition] = useState<{ lat: number; lng: number } | null>(null);
  const [status, setStatus] = useState<UserLocationState["status"]>("idle");

  const request = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setStatus("unavailable");
      return;
    }
    setStatus("pending");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPosition({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setStatus("granted");
      },
      () => setStatus("unavailable"),
      { timeout: 5000 },
    );
  }, []);

  useEffect(() => {
    request();
  }, [request]);

  return { position, status, retry: request };
}
