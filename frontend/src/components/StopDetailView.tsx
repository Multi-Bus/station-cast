import { ChevronLeft, CloudRain, Share2, Star } from "lucide-react";
import { EstimateBadge } from "./EstimateBadge";
import {
  CONGESTION_LABEL,
  congestionLevelFromValue,
  type CongestionLevel,
  type StopDetail,
} from "../types/stop";
import "./StopDetailView.css";

const BAR_COLOR: Record<CongestionLevel, string> = {
  heavy: "var(--congestion-heavy-bg)",
  moderate: "var(--congestion-moderate-bg)",
  relaxed: "var(--congestion-relaxed-bg)",
};

export function StopDetailView({
  stop,
  onBack,
  onToggleFavorite,
}: {
  stop: StopDetail;
  onBack: () => void;
  onToggleFavorite: (id: string) => void;
}) {
  const level = congestionLevelFromValue(stop.congestionValue);
  const peakBarValue = Math.max(...stop.hourly.map((h) => h.value));

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
          <span aria-hidden="true">·</span>
          <button aria-label="공유 (준비 중)" disabled>
            <Share2 size={14} /> 공유
          </button>
        </div>
      </div>

      {stop.isTransferHub && <p className="stop-detail-routes">환승 거점</p>}
      <h1 className="stop-detail-title">
        {stop.name}
        {stop.arsNumber && <span className="stop-detail-ars-number">{stop.arsNumber}</span>}
      </h1>

      <section className={`stop-hero congestion-${level}`}>
        <div className="stop-hero-top">
          <span className="stop-hero-label">{CONGESTION_LABEL[level]}</span>
          <EstimateBadge />
        </div>
        <p className="stop-hero-body">
          대기 약 {stop.waitEstimate}명 · 신뢰구간 {stop.waitConfidenceLow}–{stop.waitConfidenceHigh}명
        </p>
      </section>

      <section className="card stop-weather">
        <CloudRain size={20} />
        <div>
          <p className="stop-weather-summary">{stop.weather.summary}</p>
          <p className="stop-weather-note">{stop.weather.note}</p>
        </div>
      </section>

      <section className="card stop-arrivals">
        <h3 className="section-header">버스 도착 정보</h3>
        {stop.arrivals.map((a) => (
          <div key={`${a.route}-${a.direction}`} className="stop-arrival-row">
            <span className="stop-arrival-route">{a.route}</span>
            <span className="stop-arrival-meta">{a.direction}행</span>
            <span className="stop-arrival-eta">{a.message}</span>
          </div>
        ))}
      </section>

      <section className="stop-hourly">
        <h3 className="section-header">시간대별 예상 대기인원</h3>
        <div
          className="stop-hourly-bars"
          role="img"
          aria-label={`시간대별 예상 대기인원. ${stop.hourly
            .map((h) => `${h.hour}시 ${h.value}`)
            .join(", ")}`}
        >
          {stop.hourly.map((h) => (
            <div key={h.hour} className="stop-hourly-bar-col">
              <div
                className="stop-hourly-bar"
                style={{
                  height: `${Math.max(4, (h.value / peakBarValue) * 100)}%`,
                  background: BAR_COLOR[h.level],
                }}
              />
              <span className="stop-hourly-hour">{h.hour}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="stop-stats">
        <div className="stop-stat card">
          <span className="stop-stat-label">오늘 평균</span>
          <span className="stop-stat-value">{stop.stats.todayAvgPct}%</span>
        </div>
        <div className="stop-stat card">
          <span className="stop-stat-label">최고 혼잡</span>
          <span className="stop-stat-value">{stop.stats.peakHour}시</span>
        </div>
        <div className="stop-stat card">
          <span className="stop-stat-label">전일 대비</span>
          <span className="stop-stat-value">
            {stop.stats.dayOverDayPct > 0 ? "+" : ""}
            {stop.stats.dayOverDayPct}%
          </span>
        </div>
      </section>

      <p className="stop-disclaimer">
        대기인원은 승·하차 실측 데이터에 큐 수지 모델을 적용한 추정치입니다. 출처: 서울 열린데이터광장
        OA-12913
      </p>
    </div>
  );
}
