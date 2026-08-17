import { type CSSProperties } from "react";
import { Layers, Navigation, Search } from "lucide-react";
import { CONGESTION_LABEL, congestionLevelFromValue, type FilterKey, type NearbyStop } from "../types/stop";
import "./MapScreen.css";

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
  const heavyCount = stops.filter(
    (s) => congestionLevelFromValue(s.congestionValue) === "heavy",
  ).length;

  return (
    <div
      className="map-screen"
      style={{ "--sheet-height": `${sheetHeightPx}px` } as CSSProperties}
    >
      <div className="map-placeholder">
        <div className="user-dot" aria-hidden="true" />
        {visibleStops.map((stop) => {
          const level = congestionLevelFromValue(stop.congestionValue);
          return (
            <button
              key={stop.id}
              className={`map-marker ${selectedStopId === stop.id ? "map-marker-selected" : ""}`}
              style={{ left: `${stop.mapPosition.xPct}%`, top: `${stop.mapPosition.yPct}%` }}
              aria-pressed={selectedStopId === stop.id}
              onClick={() => onSelectStop(stop.id)}
            >
              {/* Label uses the theme text color, not the level color: the
                  level colors are tuned for the pin's white-on-fill contrast,
                  not for small text on the light floating background (several
                  fall below WCAG AA at this size). The colored pin below
                  still carries the at-a-glance color cue. */}
              <span className="map-marker-label">
                {stop.name} · {CONGESTION_LABEL[level]}
              </span>
              <span className={`map-marker-pin congestion-${level}`} />
            </button>
          );
        })}
      </div>

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
        {/* No layer data to switch between yet -- disabled rather than left as a
            button that looks live and does nothing. */}
        <button className="map-control-btn" aria-label="지도 레이어 (준비 중)" disabled>
          <span className="map-control-visual">
            <Layers size={17} />
          </span>
        </button>
        <button className="map-control-btn" aria-label="내 위치로" onClick={onRecenter}>
          <span className="map-control-visual map-control-visual-active">
            <Navigation size={17} />
          </span>
        </button>
      </div>
    </div>
  );
}
