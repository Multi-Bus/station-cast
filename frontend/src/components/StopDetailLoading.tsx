import { CaretLeft, Star } from "@phosphor-icons/react";
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
          <CaretLeft size={16} /> 목록
        </button>
        <div className="stop-detail-topbar-actions">
          <button aria-pressed={stop.isFavorite} onClick={() => onToggleFavorite(stop.id)}>
            <Star
              size={14}
              weight={stop.isFavorite ? "fill" : "regular"}
              color={stop.isFavorite ? "var(--color-favorite-star)" : "currentColor"}
            />{" "}
            즐겨찾기
          </button>
        </div>
      </div>
      <h1 className="stop-detail-title">{stop.name}</h1>
      {/* Shaped like the hero it is standing in for, so the layout does not
          jump when the reading arrives. */}
      <div className="stop-detail-skeleton" role="status" aria-label="혼잡도 정보를 불러오는 중" />
    </div>
  );
}
