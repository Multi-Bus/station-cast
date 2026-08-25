import { AlertCircle, ChevronLeft, Star } from "lucide-react";
import type { NearbyStop } from "../types/stop";
// Shares StopDetailView's layout classes, so it must pull that stylesheet in
// itself rather than relying on the sibling happening to be imported first.
import "./StopDetailView.css";

/** Shown when the stop detail fetch (timeline/arrivals/context) fails --
 * there's no local fallback data any more (issue #136), so a failed fetch is
 * always a backend problem, not a "not implemented yet" state. Still carries
 * the same topbar (back + favorite) as StopDetailView so favoriting works
 * the same way regardless of which stop the user opened. */
export function StopDetailError({
  stop,
  onBack,
  onToggleFavorite,
  onRetry,
}: {
  stop: NearbyStop;
  onBack: () => void;
  onToggleFavorite: (id: string) => void;
  onRetry: () => void;
}) {
  return (
    <div className="stop-detail">
      <div className="stop-detail-topbar">
        <button className="stop-detail-back" onClick={onBack}>
          <ChevronLeft size={16} /> 목록
        </button>
        <div className="stop-detail-topbar-actions">
          <button aria-pressed={stop.isFavorite} onClick={() => onToggleFavorite(stop.id)}>
            <Star
              size={14}
              fill={stop.isFavorite ? "var(--color-favorite-star)" : "none"}
              color={stop.isFavorite ? "var(--color-favorite-star)" : "currentColor"}
            />{" "}
            즐겨찾기
          </button>
        </div>
      </div>
      <h1 className="stop-detail-title">{stop.name}</h1>
      <div className="stop-detail-error">
        <AlertCircle size={22} />
        <span>정류장 정보를 불러오지 못했습니다.</span>
        <button className="stop-detail-error-retry" onClick={onRetry}>
          다시 시도
        </button>
      </div>
    </div>
  );
}
