import { useState } from "react";
import { ChevronLeft, Cloud, CloudRain, CloudSnow, Share2, Star, Sun } from "lucide-react";
import { EstimateBadge } from "./EstimateBadge";
import { CONGESTION_LABEL, type CongestionLevel, type StopDetail } from "../types/stop";
import "./StopDetailView.css";

const BAR_COLOR: Record<CongestionLevel, string> = {
  heavy: "var(--congestion-heavy-bg)",
  moderate: "var(--congestion-moderate-bg)",
  relaxed: "var(--congestion-relaxed-bg)",
};

function WeatherIcon({ sky }: { sky: string }) {
  if (sky.includes("눈")) return <CloudSnow size={20} />;
  if (sky.includes("비")) return <CloudRain size={20} />;
  if (sky === "맑음") return <Sun size={20} />;
  return <Cloud size={20} />;
}

async function shareStop(stop: StopDetail): Promise<"shared" | "copied" | "failed"> {
  const text = `${stop.name} - 현재 ${CONGESTION_LABEL[stop.congestionLevel]}, 대기 약 ${stop.waitEstimate}명`;
  const url = window.location.href;

  if (navigator.share) {
    try {
      await navigator.share({ title: stop.name, text, url });
      return "shared";
    } catch {
      return "failed";
    }
  }
  try {
    await navigator.clipboard.writeText(`${text}\n${url}`);
    return "copied";
  } catch {
    return "failed";
  }
}

export function StopDetailView({
  stop,
  onBack,
  onToggleFavorite,
}: {
  stop: StopDetail;
  onBack: () => void;
  onToggleFavorite: (id: string) => void;
}) {
  const level = stop.congestionLevel;
  const peakBarValue = Math.max(...stop.hourly.map((h) => h.value));
  const [shareStatus, setShareStatus] = useState<"idle" | "copied">("idle");

  async function handleShare() {
    const result = await shareStop(stop);
    if (result === "copied") {
      setShareStatus("copied");
      setTimeout(() => setShareStatus("idle"), 2000);
    }
  }

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
          <button aria-label="정류장 정보 공유" onClick={handleShare}>
            <Share2 size={14} /> {shareStatus === "copied" ? "복사됨" : "공유"}
          </button>
        </div>
      </div>

      <h1 className="stop-detail-title">
        {stop.name}
        {stop.arsNumber && <span className="stop-detail-ars-number">{stop.arsNumber}</span>}
      </h1>

      <section className={`stop-hero congestion-${level}`}>
        <div className="stop-hero-top">
          <span className="stop-hero-label">{CONGESTION_LABEL[level]}</span>
          <EstimateBadge />
        </div>
        <p className="stop-hero-body">대기 약 {stop.waitEstimate}명</p>
      </section>

      <section className="card stop-weather">
        <WeatherIcon sky={stop.weather.sky} />
        <div>
          <p className="stop-weather-summary">
            {stop.weather.summary}
            {stop.weather.isForecast && <span className="forecast-badge">예보</span>}
          </p>
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
          <span className="stop-stat-label">최고 혼잡</span>
          <span className="stop-stat-value">{stop.stats.peakHour}시</span>
        </div>
      </section>

      <p className="stop-disclaimer">
        대기인원은 승·하차 실측 데이터에 큐 수지 모델을 적용한 추정치입니다. 출처: 서울 열린데이터광장
        OA-12913
      </p>
    </div>
  );
}
