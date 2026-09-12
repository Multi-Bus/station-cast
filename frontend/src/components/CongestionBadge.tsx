import { CONGESTION_LABEL, type CongestionLevel } from "../types/stop";
import "./CongestionBadge.css";

export function CongestionBadge({ level }: { level: CongestionLevel }) {
  return (
    <span className="congestion-badge" data-level={level}>
      <span className="congestion-badge-mark" aria-hidden="true" />
      {CONGESTION_LABEL[level]}
    </span>
  );
}
