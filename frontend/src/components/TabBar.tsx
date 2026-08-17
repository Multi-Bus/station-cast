import { MapIcon, Settings, Star } from "lucide-react";
import "./TabBar.css";

export type TabKey = "map" | "favorites" | "settings";

const TABS: { key: TabKey; label: string; Icon: typeof MapIcon }[] = [
  { key: "map", label: "지도", Icon: MapIcon },
  { key: "favorites", label: "즐겨찾기", Icon: Star },
  { key: "settings", label: "설정", Icon: Settings },
];

export function TabBar({
  active,
  onChange,
}: {
  active: TabKey;
  onChange: (tab: TabKey) => void;
}) {
  return (
    <nav className="tabbar">
      {TABS.map(({ key, label, Icon }) => (
        <button
          key={key}
          className={`tabbar-item ${active === key ? "tabbar-item-active" : ""}`}
          onClick={() => onChange(key)}
          aria-current={active === key ? "page" : undefined}
        >
          <Icon size={20} strokeWidth={active === key ? 2.5 : 2} />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}
