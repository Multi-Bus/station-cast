import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { Navigation, Search, Star } from "lucide-react";
import { CustomOverlayMap, Map } from "react-kakao-maps-sdk";
import type { UserLocationState } from "../hooks/useUserLocation";
import type { FilterKey, NearbyStop } from "../types/stop";
import "./MapScreen.css";

const KAKAO_MAP_KEY = import.meta.env.VITE_KAKAO_MAP_KEY;
const KAKAO_SCRIPT_ID = "kakao-maps-sdk";

function useKakaoScript(appkey: string | undefined): { ready: boolean; failed: boolean } {
  const [state, setState] = useState(() => ({
    ready: typeof window !== "undefined" && !!window.kakao?.maps?.Map,
    failed: false,
  }));

  useEffect(() => {
    if (!appkey || state.ready) return;

    function onLoad() {
      window.kakao.maps.load(() => setState({ ready: true, failed: false }));
    }
    function onError() {
      setState({ ready: false, failed: true });
    }

    const existing = document.getElementById(KAKAO_SCRIPT_ID);
    if (existing) {
      existing.addEventListener("load", onLoad);
      existing.addEventListener("error", onError);
      return () => {
        existing.removeEventListener("load", onLoad);
        existing.removeEventListener("error", onError);
      };
    }

    const script = document.createElement("script");
    script.id = KAKAO_SCRIPT_ID;
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${appkey}&autoload=false`;
    script.addEventListener("load", onLoad);
    script.addEventListener("error", onError);
    document.head.appendChild(script);
    return () => {
      script.removeEventListener("load", onLoad);
      script.removeEventListener("error", onError);
    };
  }, [appkey, state.ready]);

  return state;
}
const FALLBACK_CENTER = { lat: 37.5665, lng: 126.978 };

function centroid(stops: NearbyStop[]): { lat: number; lng: number } | null {
  if (stops.length === 0) return null;
  const lat = stops.reduce((sum, s) => sum + s.latLng.lat, 0) / stops.length;
  const lng = stops.reduce((sum, s) => sum + s.latLng.lng, 0) / stops.length;
  return { lat, lng };
}

const LEVEL_RANK: Record<NearbyStop["congestionLevel"], number> = {
  relaxed: 0,
  moderate: 1,
  heavy: 2,
};

// Circles this close together on screen visually merge no matter how they're
// sized, so grouping them into one marker is the fix, not a smaller circle.
// 50px covers the largest single-stop disc (52px) with a little room.
const CLUSTER_CELL_PX = 50;

type MarkerGroup =
  | { kind: "single"; stop: NearbyStop }
  | { kind: "cluster"; key: string; stops: NearbyStop[]; lat: number; lng: number };

/** Buckets stops into screen-space grid cells at the map's current zoom, so
 * markers that would overlap on screen combine into one. Recomputed on every
 * render; cheap at the corridor's stop count and always reflects the
 * projection at call time, so the caller just needs to re-render after pan
 * or zoom rather than keep this in step itself. */
function buildMarkerGroups(
  map: kakao.maps.Map,
  stops: NearbyStop[],
  selectedStopId: string | null,
): MarkerGroup[] {
  const projection = map.getProjection();
  // globalThis.Map, not the react-kakao-maps-sdk `Map` component imported above.
  const buckets = new globalThis.Map<string, NearbyStop[]>();
  const groups: MarkerGroup[] = [];

  for (const stop of stops) {
    // The selected stop is never folded into a cluster -- it was just panned
    // into view on purpose, so it has to stay a marker you can see and tap.
    if (stop.id === selectedStopId) {
      groups.push({ kind: "single", stop });
      continue;
    }
    const point = projection.pointFromCoords(new window.kakao.maps.LatLng(stop.latLng.lat, stop.latLng.lng));
    const key = `${Math.round(point.x / CLUSTER_CELL_PX)}:${Math.round(point.y / CLUSTER_CELL_PX)}`;
    const bucket = buckets.get(key);
    if (bucket) bucket.push(stop);
    else buckets.set(key, [stop]);
  }

  for (const [key, bucketStops] of buckets) {
    if (bucketStops.length === 1) {
      groups.push({ kind: "single", stop: bucketStops[0] });
      continue;
    }
    groups.push({
      kind: "cluster",
      key,
      stops: bucketStops,
      lat: bucketStops.reduce((sum, s) => sum + s.latLng.lat, 0) / bucketStops.length,
      lng: bucketStops.reduce((sum, s) => sum + s.latLng.lng, 0) / bucketStops.length,
    });
  }
  return groups;
}

function ClusterMarker({ stops, onExpand }: { stops: NearbyStop[]; onExpand: () => void }) {
  // Coloured by the worst reading inside, same as a single marker would be --
  // the group is exactly as alarming as its most crowded member.
  const worstLevel = stops.reduce(
    (worst, s) => (LEVEL_RANK[s.congestionLevel] > LEVEL_RANK[worst] ? s.congestionLevel : worst),
    stops[0].congestionLevel,
  );
  return (
    <button
      className="map-marker"
      data-level={worstLevel}
      onClick={onExpand}
      aria-label={`이 근처 정류장 ${stops.length}곳, 눌러서 펼치기`}
    >
      <span
        className="map-dot map-dot-cluster"
        style={{ "--wait": stops.length * 5 } as CSSProperties}
      >
        <span className="map-dot-value figure">{stops.length}</span>
      </span>
    </button>
  );
}

function StopMarker({
  stop,
  selected,
  onSelectStop,
}: {
  stop: NearbyStop;
  selected: boolean;
  onSelectStop: (id: string) => void;
}) {
  return (
    <button
      className="map-marker"
      data-level={stop.congestionLevel}
      data-selected={selected || undefined}
      aria-pressed={selected}
      aria-label={`${stop.name}, 대기 약 ${stop.waitEstimate}명`}
      onClick={() => onSelectStop(stop.id)}
    >
      {/* The reading sits inside the marker instead of behind a tap. Fill
          colour, diameter and the number itself all carry congestion, so the
          map still parses with colour vision that cannot separate the fills. */}
      <span className="map-dot" style={{ "--wait": stop.waitEstimate } as CSSProperties}>
        <span className="map-dot-value figure">{stop.waitEstimate}</span>
      </span>
      <span className="map-dot-label">{stop.name}</span>
    </button>
  );
}

function PlaceholderMap({
  visibleStops,
  selectedStopId,
  onSelectStop,
}: {
  visibleStops: NearbyStop[];
  selectedStopId: string | null;
  onSelectStop: (id: string) => void;
}) {
  return (
    <div className="map-placeholder">
      <div className="user-dot" aria-hidden="true" />
      {visibleStops.map((stop) => (
        <div
          key={stop.id}
          className="map-marker-anchor"
          style={{ left: `${stop.mapPosition.xPct}%`, top: `${stop.mapPosition.yPct}%` }}
        >
          <StopMarker stop={stop} selected={selectedStopId === stop.id} onSelectStop={onSelectStop} />
        </div>
      ))}
    </div>
  );
}

function KakaoStopsMap({
  visibleStops,
  selectedStopId,
  onSelectStop,
  center,
  userPosition,
  sheetHeightPx,
}: {
  visibleStops: NearbyStop[];
  selectedStopId: string | null;
  onSelectStop: (id: string) => void;
  center: { lat: number; lng: number };
  userPosition: { lat: number; lng: number } | null;
  sheetHeightPx: number;
}) {
  const { ready, failed } = useKakaoScript(KAKAO_MAP_KEY);
  const mapRef = useRef<kakao.maps.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const selected = visibleStops.find((s) => s.id === selectedStopId);
  const selectedLat = selected?.latLng.lat;
  const selectedLng = selected?.latLng.lng;

  // buildMarkerGroups reads the map's live projection, which only changes via
  // Kakao's own pan/zoom internals -- nothing React knows about. This just
  // forces a re-render after each one settles so the groups it computes stay
  // current; it holds no state of its own.
  const [, forceRegroup] = useState(0);
  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    const bump = () => forceRegroup((n) => n + 1);
    window.kakao.maps.event.addListener(map, "idle", bump);
    return () => window.kakao.maps.event.removeListener(map, "idle", bump);
  }, [mapReady]);

  // Tapping a marker opens the sheet over the bottom half of the map, which is
  // usually where the marker just was. Push the map down by half the sheet so
  // the stop you picked stays in the strip you can still see.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || selectedLat === undefined || selectedLng === undefined) return;

    const projection = map.getProjection();
    const point = projection.pointFromCoords(
      new window.kakao.maps.LatLng(selectedLat, selectedLng),
    );
    point.y += sheetHeightPx / 2;
    const target = projection.coordsFromPoint(point);

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) map.setCenter(target);
    else map.panTo(target);
    // sheetHeightPx is read but not depended on: it changes on every drag frame,
    // and re-panning mid-drag would fight the user.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedLat, selectedLng]);

  if (!ready || failed) {
    return <PlaceholderMap visibleStops={visibleStops} selectedStopId={selectedStopId} onSelectStop={onSelectStop} />;
  }

  return (
    <Map
      center={center}
      isPanto
      level={5}
      style={{ position: "absolute", inset: 0 }}
      onCreate={(map) => {
        mapRef.current = map;
        setMapReady(true);
      }}
    >
      {userPosition && (
        <CustomOverlayMap position={userPosition}>
          <div className="user-location-dot" aria-label="내 위치" role="img" />
        </CustomOverlayMap>
      )}
      {(mapReady && mapRef.current
        ? buildMarkerGroups(mapRef.current, visibleStops, selectedStopId)
        : visibleStops.map((stop): MarkerGroup => ({ kind: "single", stop }))
      ).map((group) =>
        group.kind === "single" ? (
          <CustomOverlayMap key={group.stop.id} position={group.stop.latLng} clickable yAnchor={0.5}>
            <StopMarker
              stop={group.stop}
              selected={selectedStopId === group.stop.id}
              onSelectStop={onSelectStop}
            />
          </CustomOverlayMap>
        ) : (
          <CustomOverlayMap key={group.key} position={{ lat: group.lat, lng: group.lng }} clickable yAnchor={0.5}>
            <ClusterMarker
              stops={group.stops}
              onExpand={() => {
                const map = mapRef.current;
                if (!map) return;
                map.setLevel(map.getLevel() - 1, {
                  anchor: new window.kakao.maps.LatLng(group.lat, group.lng),
                });
              }}
            />
          </CustomOverlayMap>
        ),
      )}
    </Map>
  );
}

export function MapScreen({
  stops,
  visibleStops,
  activeFilters,
  onToggleFilter,
  searchQuery,
  onSearchQueryChange,
  selectedStopId,
  sheetHeightPx,
  controlsHidden,
  userPosition,
  locationStatus,
  onSelectStop,
  onRecenter,
}: {
  /** Full set, unaffected by filters -- only used for the "혼잡 N" chip count. */
  stops: NearbyStop[];
  /** Filtered set actually rendered as markers; kept in sync with the sheet's
   * list by the parent so map and list never disagree. */
  visibleStops: NearbyStop[];
  activeFilters: Set<FilterKey>;
  onToggleFilter: (key: FilterKey) => void;
  searchQuery: string;
  onSearchQueryChange: (query: string) => void;
  selectedStopId: string | null;
  sheetHeightPx: number;
  controlsHidden: boolean;
  userPosition: { lat: number; lng: number } | null;
  locationStatus: UserLocationState["status"];
  onSelectStop: (id: string) => void;
  onRecenter: () => void;
}) {
  const [center, setCenter] = useState(FALLBACK_CENTER);
  const corridorCenter = useMemo(() => centroid(stops) ?? FALLBACK_CENTER, [stops]);
  const didInitialCenter = useRef(false);
  useEffect(() => {
    if (stops.length > 0 && !didInitialCenter.current) {
      setCenter(corridorCenter);
      didInitialCenter.current = true;
    }
  }, [stops, corridorCenter]);

  const heavyCount = stops.filter((s) => s.congestionLevel === "heavy").length;
  const favoriteCount = stops.filter((s) => s.isFavorite).length;

  // Gating on "granted" is load-bearing: retry() flips the status to "pending"
  // first, and reading that as an answer would end the wait before the fix lands.
  const awaitingFix = useRef(false);
  useEffect(() => {
    if (!awaitingFix.current) return;
    if (locationStatus === "granted" && userPosition) {
      setCenter(userPosition);
      awaitingFix.current = false;
    } else if (locationStatus === "unavailable") {
      setCenter(corridorCenter);
      awaitingFix.current = false;
    }
  }, [userPosition, locationStatus, corridorCenter]);

  function handleRecenter() {
    if (userPosition) setCenter(userPosition);
    awaitingFix.current = true;
    onRecenter();
  }

  return (
    <div
      className="map-screen"
      style={{ "--sheet-height": `${sheetHeightPx}px` } as CSSProperties}
    >
      {KAKAO_MAP_KEY ? (
        <KakaoStopsMap
          visibleStops={visibleStops}
          selectedStopId={selectedStopId}
          onSelectStop={onSelectStop}
          center={center}
          userPosition={userPosition}
          sheetHeightPx={sheetHeightPx}
        />
      ) : (
        <PlaceholderMap visibleStops={visibleStops} selectedStopId={selectedStopId} onSelectStop={onSelectStop} />
      )}

      <div className="map-floating-top">
        <div className="search-bar">
          <Search size={16} strokeWidth={2} color="var(--color-text-faint)" />
          <input
            className="search-bar-input"
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchQueryChange(e.target.value)}
            placeholder="정류장 이름 검색"
            aria-label="정류장 이름 검색"
          />
        </div>
        <div className="filter-chip-row">
          {heavyCount > 0 && (
            <button
              className="chip"
              aria-pressed={activeFilters.has("heavy")}
              onClick={() => onToggleFilter("heavy")}
            >
              혼잡 <span className="chip-count figure">{heavyCount}</span>
            </button>
          )}
          {/* Hidden rather than disabled at zero: a permanently greyed-out
              control is just clutter until the user has starred something. */}
          {favoriteCount > 0 && (
            <button
              className="chip"
              aria-pressed={activeFilters.has("favorite")}
              onClick={() => onToggleFilter("favorite")}
            >
              <Star size={12} strokeWidth={2} aria-hidden="true" /> 즐겨찾기{" "}
              <span className="chip-count figure">{favoriteCount}</span>
            </button>
          )}
        </div>
      </div>

      <div className={`map-controls ${controlsHidden ? "map-controls-hidden" : ""}`}>
        <button className="map-control-btn" aria-label="내 위치로" onClick={handleRecenter}>
          <span className="map-control-visual">
            <Navigation size={17} strokeWidth={2} />
          </span>
        </button>
      </div>
    </div>
  );
}
