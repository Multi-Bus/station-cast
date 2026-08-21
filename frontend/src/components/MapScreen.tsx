import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { Layers, Navigation, Search } from "lucide-react";
import { CustomOverlayMap, Map } from "react-kakao-maps-sdk";
import { congestionLevelFromValue, type FilterKey, type NearbyStop } from "../types/stop";
import "./MapScreen.css";

const KAKAO_MAP_KEY = import.meta.env.VITE_KAKAO_MAP_KEY;
const KAKAO_SCRIPT_ID = "kakao-maps-sdk";
type KakaoMapType = "ROADMAP" | "HYBRID";

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

function StopMarker({
  stop,
  selected,
  onSelectStop,
}: {
  stop: NearbyStop;
  selected: boolean;
  onSelectStop: (id: string) => void;
}) {
  const level = congestionLevelFromValue(stop.congestionValue);
  return (
    <button
      className={`map-marker ${selected ? "map-marker-selected" : ""}`}
      aria-pressed={selected}
      onClick={() => onSelectStop(stop.id)}
    >
      <span className="map-marker-label">{stop.name}</span>
      <span className={`map-marker-pin congestion-${level}`} />
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
  mapType,
}: {
  visibleStops: NearbyStop[];
  selectedStopId: string | null;
  onSelectStop: (id: string) => void;
  center: { lat: number; lng: number };
  mapType: KakaoMapType;
}) {
  const { ready, failed } = useKakaoScript(KAKAO_MAP_KEY);

  if (!ready || failed) {
    return <PlaceholderMap visibleStops={visibleStops} selectedStopId={selectedStopId} onSelectStop={onSelectStop} />;
  }

  return (
    <Map center={center} isPanto level={5} mapTypeId={mapType} style={{ position: "absolute", inset: 0 }}>
      {visibleStops.map((stop) => (
        <CustomOverlayMap key={stop.id} position={stop.latLng} clickable yAnchor={1}>
          <StopMarker stop={stop} selected={selectedStopId === stop.id} onSelectStop={onSelectStop} />
        </CustomOverlayMap>
      ))}
    </Map>
  );
}

export function MapScreen({
  stops,
  visibleStops,
  activeFilters,
  onToggleFilter,
  selectedStopId,
  sheetHeightPx,
  controlsHidden,
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
  selectedStopId: string | null;
  sheetHeightPx: number;
  controlsHidden: boolean;
  onSelectStop: (id: string) => void;
  onRecenter: () => void;
}) {
  const [center, setCenter] = useState(FALLBACK_CENTER);
  const [mapType, setMapType] = useState<KakaoMapType>("ROADMAP");
  const corridorCenter = useMemo(() => centroid(stops) ?? FALLBACK_CENTER, [stops]);
  const didInitialCenter = useRef(false);
  useEffect(() => {
    if (stops.length > 0 && !didInitialCenter.current) {
      setCenter(corridorCenter);
      didInitialCenter.current = true;
    }
  }, [stops, corridorCenter]);

  const heavyCount = stops.filter(
    (s) => congestionLevelFromValue(s.congestionValue) === "heavy",
  ).length;

  function handleRecenter() {
    setCenter(corridorCenter);
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
          mapType={mapType}
        />
      ) : (
        <PlaceholderMap visibleStops={visibleStops} selectedStopId={selectedStopId} onSelectStop={onSelectStop} />
      )}

      <div className="map-floating-top">
        <div className="search-bar">
          <Search size={15} color="var(--neutral-500)" />
          <span className="search-bar-placeholder">정류장, 노선, 주소 검색</span>
          <span className="search-bar-profile">SC</span>
        </div>
        <div className="filter-chip-row">
          <button
            className={`chip ${activeFilters.has("heavy") ? "chip-on" : ""}`}
            aria-pressed={activeFilters.has("heavy")}
            onClick={() => onToggleFilter("heavy")}
          >
            혼잡 {heavyCount}
          </button>
          <button
            className={`chip ${activeFilters.has("transferHub") ? "chip-on" : ""}`}
            aria-pressed={activeFilters.has("transferHub")}
            onClick={() => onToggleFilter("transferHub")}
          >
            환승 거점
          </button>
        </div>
      </div>

      <div className={`map-controls ${controlsHidden ? "map-controls-hidden" : ""}`}>
        <button
          className="map-control-btn"
          aria-label={mapType === "ROADMAP" ? "위성 지도로 보기" : "일반 지도로 보기"}
          aria-pressed={mapType === "HYBRID"}
          disabled={!KAKAO_MAP_KEY}
          onClick={() => setMapType((t) => (t === "ROADMAP" ? "HYBRID" : "ROADMAP"))}
        >
          <span className={`map-control-visual ${mapType === "HYBRID" ? "map-control-visual-active" : ""}`}>
            <Layers size={17} />
          </span>
        </button>
        <button className="map-control-btn" aria-label="내 위치로" onClick={handleRecenter}>
          <span className="map-control-visual map-control-visual-active">
            <Navigation size={17} />
          </span>
        </button>
      </div>
    </div>
  );
}
