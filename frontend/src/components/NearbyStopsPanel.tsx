import type { CSSProperties } from "react";
import { ChevronRight, Star } from "lucide-react";
import { CongestionBadge } from "./CongestionBadge";
import type { NearbyStop } from "../types/stop";
import "./NearbyStopsPanel.css";

/** Distance is only known once geolocation is granted, so the ARS number is
 * what the line falls back to rather than leaving it blank. */
function stopMeta(stop: NearbyStop): string {
  return [stop.arsNumber, stop.distanceM > 0 ? `${stop.distanceM}m` : null]
    .filter(Boolean)
    .join(" · ");
}

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
        <div className="nearby-peek-head">
          <p className="nearby-peek-title">
            {loading
              ? "정류장을 불러오는 중..."
              : error
                ? "정류장 정보를 불러오지 못했습니다."
                : `내 주변 정류장 ${stops.length}곳`}
          </p>
          {nearest && <span className="nearby-sort-note">가장 가까운 곳</span>}
        </div>
        {/* Peek is the state the app sits in, so it carries the reading itself
            rather than only naming the stop: the question is "is my stop busy",
            and answering it should not cost a tap. */}
        {nearest && (
          <button
            className="nearby-peek-row"
            onClick={() => onSelectStop(nearest.id)}
            aria-label={`가장 가까운 정류장 ${nearest.name}, 대기 약 ${nearest.waitEstimate}명`}
          >
            <span className="nearby-row-main">
              <span className="nearby-row-name">{nearest.name}</span>
              <span className="nearby-row-meta figure">{stopMeta(nearest)}</span>
            </span>
            <span className="nearby-row-wait">
              <span className="figure">{nearest.waitEstimate}</span>
              <span className="nearby-row-wait-unit">명</span>
            </span>
            <CongestionBadge level={nearest.congestionLevel} />
            <ChevronRight
              size={16}
              strokeWidth={2}
              color="var(--color-text-faint)"
              aria-hidden="true"
            />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="nearby-list">
      <div className="nearby-list-header">
        <h2>내 주변 정류장</h2>
        <span className="nearby-sort-note">가까운 순</span>
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
        {stops.map((stop, index) => {
          const level = stop.congestionLevel;
          return (
            <li
              key={stop.id}
              className="nearby-row"
              style={{ "--row-index": index } as CSSProperties}
            >
              {/* The star is a sibling, not a child: nesting a button inside a
                  button is invalid HTML and the inner one is unreachable by
                  keyboard. */}
              <button className="nearby-row-btn" onClick={() => onSelectStop(stop.id)}>
                <span className="nearby-row-main">
                  <span className="nearby-row-name">{stop.name}</span>
                  {/* The corridor has several pairs of stops sharing a name --
                      opposite sides of the same street. The ARS number is what
                      tells them apart, and it is what is printed on the pole. */}
                  <span className="nearby-row-meta figure">{stopMeta(stop)}</span>
                </span>
                <span className="nearby-row-side">
                  <span className="nearby-row-wait">
                    <span className="figure">{stop.waitEstimate}</span>
                    <span className="nearby-row-wait-unit">명</span>
                  </span>
                  <CongestionBadge level={level} />
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
                  strokeWidth={2}
                  fill={stop.isFavorite ? "var(--color-favorite-star)" : "none"}
                  color={stop.isFavorite ? "var(--color-favorite-star)" : "var(--color-text-faint)"}
                />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
