import { type CSSProperties, useState } from "react";
import { ChevronLeft, Cloud, CloudRain, CloudSnow, Share2, Star, Sun } from "lucide-react";
import { EstimateBadge } from "./EstimateBadge";
import { CONGESTION_LABEL, type StopDetail } from "../types/stop";
import "./StopDetailView.css";

function WeatherIcon({ sky }: { sky: string }) {
  if (sky.includes("눈")) return <CloudSnow size={18} strokeWidth={2} />;
  if (sky.includes("비")) return <CloudRain size={18} strokeWidth={2} />;
  if (sky === "맑음") return <Sun size={18} strokeWidth={2} />;
  return <Cloud size={18} strokeWidth={2} />;
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
  const [shareStatus, setShareStatus] = useState<"idle" | "copied" | "failed">("idle");

  async function handleShare() {
    const result = await shareStop(stop);
    if (result === "shared") return;
    setShareStatus(result === "copied" ? "copied" : "failed");
    setTimeout(() => setShareStatus("idle"), 2000);
  }

  return (
    <div className="stop-detail">
      <div className="stop-detail-topbar">
        <button className="stop-detail-back" onClick={onBack}>
          <ChevronLeft size={16} strokeWidth={2} /> 목록
        </button>
        <div className="stop-detail-topbar-actions">
          <button aria-pressed={stop.isFavorite} onClick={() => onToggleFavorite(stop.id)}>
            <Star
              size={14}
              strokeWidth={2}
              fill={stop.isFavorite ? "var(--color-favorite-star)" : "none"}
              color={stop.isFavorite ? "var(--color-favorite-star)" : "currentColor"}
            />{" "}
            즐겨찾기
          </button>
          <button aria-label="정류장 정보 공유" onClick={handleShare}>
            <Share2 size={14} strokeWidth={2} />{" "}
            <span aria-live="polite">
              {shareStatus === "copied" ? "복사됨" : shareStatus === "failed" ? "공유 실패" : "공유"}
            </span>
          </button>
        </div>
      </div>

      <h1 className="stop-detail-title">
        {stop.name}
        {stop.arsNumber && (
          <>
            <span className="sr-only"> </span>
            <span className="stop-detail-ars-number">{stop.arsNumber}</span>
          </>
        )}
      </h1>

      {/* The wait count is the whole product, so it is the largest thing on the
          screen and the only saturated surface in the app. */}
      <section className="stop-hero" data-level={level}>
        <p className="stop-hero-figure">
          <span className="stop-hero-count figure">{stop.waitEstimate}</span>
          <span className="stop-hero-unit">명 대기</span>
        </p>
        <div className="stop-hero-side">
          <EstimateBadge />
          <span className="stop-hero-label">{CONGESTION_LABEL[level]}</span>
        </div>
      </section>

      <section className="stop-weather">
        <WeatherIcon sky={stop.weather.sky} />
        <div>
          <p className="stop-weather-summary">
            {stop.weather.summary}
            {stop.weather.isForecast && (
              <>
                <span className="sr-only"> </span>
                <span className="forecast-badge">예보</span>
              </>
            )}
          </p>
          <p className="stop-weather-note">{stop.weather.note}</p>
        </div>
      </section>

      <section className="stop-section">
        <h2 className="section-header">버스 도착 정보</h2>
        <div>
          {stop.arrivals.map((a) => (
            <div key={`${a.route}-${a.direction}`} className="stop-arrival-row">
              <span className="stop-arrival-route">{a.route}</span>
              <span className="stop-arrival-meta">{a.direction}행</span>
              <span className="stop-arrival-when">
                <span className="stop-arrival-eta">{a.eta}</span>
                {a.stopsAway && <span className="stop-arrival-away">{a.stopsAway}</span>}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="stop-section">
        <h2 className="section-header">
          시간대별 예상 대기인원{" "}
          <span className="stop-hourly-peak">
            가장 붐비는 시간 <span className="figure">{stop.stats.peakHour}</span>시
          </span>
        </h2>
        <div>
          <div
            className="stop-hourly-bars"
            role="img"
            aria-label={`시간대별 예상 대기인원. ${stop.hourly
              .map((h) => `${h.hour}시 ${h.value}명`)
              .join(", ")}`}
          >
            {stop.hourly.map((h, index) => (
              <div key={h.hour} className="stop-hourly-bar-col">
                <div
                  className="stop-hourly-bar"
                  data-level={h.level}
                  data-peak={h.hour === stop.stats.peakHour || undefined}
                  style={
                    {
                      height: `${Math.max(3, (h.value / peakBarValue) * 100)}%`,
                      "--bar-index": index,
                    } as CSSProperties
                  }
                />
              </div>
            ))}
          </div>
          <div className="stop-hourly-axis" aria-hidden="true">
            <span>0시</span>
            <span>6시</span>
            <span>12시</span>
            <span>18시</span>
            <span>23시</span>
          </div>
        </div>
      </section>

      <p className="stop-disclaimer">
        대기인원은 노선별 실측 승차와 배차간격에 Little&apos;s Law를 적용한 추정치입니다. 실제로 센
        값이 아닙니다. 출처: 서울 열린데이터광장 OA-12913
      </p>
    </div>
  );
}
