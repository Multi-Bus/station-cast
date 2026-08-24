import { Star } from "lucide-react";
import { CongestionBadge } from "./CongestionBadge";
import { EstimateBadge } from "./EstimateBadge";
import { congestionLevelFromValue, type NearbyStop } from "../types/stop";
import "./NearbyStopsPanel.css";

export function NearbyStopsPanel({
  stops,
  compact,
  loading,
  onSelectStop,
  onToggleFavorite,
}: {
  stops: NearbyStop[];
  compact: boolean;
  loading: boolean;
  onSelectStop: (id: string) => void;
  onToggleFavorite: (id: string) => void;
}) {
  if (compact) {
    const nearest = stops[0];
    return (
      <div className="nearby-peek">
        <p className="nearby-peek-title">
          {loading ? "정류장을 불러오는 중..." : `내 주변 정류장 ${stops.length}곳`}
        </p>
        {nearest && (
          <button className="nearby-peek-row" onClick={() => onSelectStop(nearest.id)}>
            가장 가까운 곳 · {nearest.name}
            {nearest.distanceM > 0 ? ` ${nearest.distanceM}m` : ""}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="nearby-list">
      <div className="nearby-list-header">
        <h2>내 주변 정류장</h2>
        <span className="nearby-sort">거리순 ⌄</span>
      </div>
      {stops.length === 0 && (
        <p className="nearby-empty">
          {loading ? "정류장을 불러오는 중..." : "필터 조건에 맞는 정류장이 없습니다."}
        </p>
      )}
      <ul className="nearby-rows">
        {stops.map((stop) => {
          const level = congestionLevelFromValue(stop.congestionValue);
          return (
            <li key={stop.id} className="nearby-row">
              {/* The star is a sibling, not a child: nesting a button inside a
                  button is invalid HTML and the inner one is unreachable by
                  keyboard. */}
              <button className="nearby-row-btn" onClick={() => onSelectStop(stop.id)}>
                <span className="nearby-row-main">
                  <span className="nearby-row-name">{stop.name}</span>
                  <span className="nearby-row-meta">
                    {[
                      stop.routes.length > 0 ? `${stop.routes.join(", ")}번` : null,
                      stop.distanceM > 0 ? `${stop.distanceM}m` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </span>
                <span className="nearby-row-side">
                  <CongestionBadge level={level} />
                  <span className="nearby-row-wait">
                    <EstimateBadge tone="surface" />
                    대기 약 {stop.waitEstimate}명
                  </span>
                </span>
              </button>
              <button
                className="nearby-row-star"
                aria-label={`${stop.name} 즐겨찾기`}
                aria-pressed={stop.isFavorite}
                onClick={() => onToggleFavorite(stop.id)}
              >
                <Star
                  size={16}
                  fill={stop.isFavorite ? "var(--color-favorite-star)" : "none"}
                  color={stop.isFavorite ? "var(--color-favorite-star)" : "var(--neutral-400)"}
                />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
