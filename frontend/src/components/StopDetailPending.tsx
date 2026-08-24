import { ChevronLeft, Star } from "lucide-react";
import { CongestionBadge } from "./CongestionBadge";
import type { NearbyStop } from "../types/stop";
// Shares StopDetailView's layout classes, so it must pull that stylesheet in
// itself rather than relying on the sibling happening to be imported first.
import "./StopDetailView.css";

/** design-data.md only has full detail sample data for one stop (강남역).
 * Other stops fall back to this instead of either fabricating detail
 * numbers or silently ignoring the tap. Still carries the same topbar
 * (back + favorite) as StopDetailView so favoriting works the same way
 * regardless of which stop the user opened. */
export function StopDetailPending({
  stop,
  onBack,
  onToggleFavorite,
}: {
  stop: NearbyStop;
  onBack: () => void;
  onToggleFavorite: (id: string) => void;
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
      <CongestionBadge level={stop.congestionLevel} />
      <p className="stop-disclaimer">이 정류장의 상세 데이터는 준비 중입니다.</p>
    </div>
  );
}
