import { Star } from "lucide-react";
import { CongestionBadge } from "./CongestionBadge";
import { EstimateBadge } from "./EstimateBadge";
import type { NearbyStop } from "../types/stop";
import "./NearbyStopsPanel.css";

export function NearbyStopsPanel({
  stops,
  compact,
  loading,
  error,
  emptyReason,
  onSelectStop,
  onToggleFavorite,
  onRetry,
}: {
  stops: NearbyStop[];
  compact: boolean;
  loading: boolean;
  error: boolean;
  /** Why `stops` (the already filtered+searched list) is empty, when it's not
   * loading or errored -- lets the message say which of "필터"/"검색" is
   * responsible instead of one sentence covering both plus API failure. */
  emptyReason: "filter" | "search" | null;
  onSelectStop: (id: string) => void;
  onToggleFavorite: (id: string) => void;
  onRetry: () => void;
}) {
  const emptyMessage = loading
    ? "정류장을 불러오는 중..."
    : error
      ? "정류장 정보를 불러오지 못했습니다."
      : emptyReason === "search"
        ? "검색 결과가 없습니다."
        : "필터 조건에 맞는 정류장이 없습니다.";

  if (compact) {
    const nearest = stops[0];
    return (
      <div className="nearby-peek">
        <p className="nearby-peek-title">
          {loading
            ? "정류장을 불러오는 중..."
            : error
              ? "정류장 정보를 불러오지 못했습니다."
              : `내 주변 정류장 ${stops.length}곳`}
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
        <div className="nearby-empty">
          <p>{emptyMessage}</p>
          {!loading && error && (
            <button className="nearby-empty-retry" onClick={onRetry}>
              다시 시도
            </button>
          )}
        </div>
      )}
      <ul className="nearby-rows">
        {stops.map((stop) => {
          const level = stop.congestionLevel;
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
