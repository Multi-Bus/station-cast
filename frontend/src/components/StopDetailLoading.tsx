import { ChevronLeft, LoaderCircle, Star } from "lucide-react";
import type { NearbyStop } from "../types/stop";
import "./StopDetailView.css";

export function StopDetailLoading({
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
      <div className="stop-detail-loading">
        <LoaderCircle className="stop-detail-loading-spinner" size={22} />
        <span>혼잡도 정보를 불러오는 중...</span>
      </div>
    </div>
  );
}
