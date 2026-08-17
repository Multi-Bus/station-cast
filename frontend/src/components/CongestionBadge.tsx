import { CONGESTION_LABEL, type CongestionLevel } from "../types/stop";
import "./CongestionBadge.css";

export function CongestionBadge({ level }: { level: CongestionLevel }) {
  return <span className={`congestion-badge congestion-${level}`}>{CONGESTION_LABEL[level]}</span>;
}
