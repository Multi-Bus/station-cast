import { useEffect, useMemo, useState } from "react";
import { BottomSheet } from "./components/BottomSheet";
import { ComingSoon } from "./components/ComingSoon";
import { MapScreen } from "./components/MapScreen";
import { NearbyStopsPanel } from "./components/NearbyStopsPanel";
import { StopDetailPending } from "./components/StopDetailPending";
import { StopDetailView } from "./components/StopDetailView";
import { TabBar, type TabKey } from "./components/TabBar";
import { NEARBY_STOPS, STOP_DETAILS } from "./data/mockStops";
import { useBottomSheet } from "./hooks/useBottomSheet";
import { useFavorites } from "./hooks/useFavorites";
import { applyStopFilters, type FilterKey } from "./types/stop";

const DEFAULT_FAVORITES = NEARBY_STOPS.filter((s) => s.isFavorite).map((s) => s.id);

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("map");
  const [selectedStopId, setSelectedStopId] = useState<string | null>(null);
  const [activeFilters, setActiveFilters] = useState<Set<FilterKey>>(new Set());
  const sheet = useBottomSheet("peek");
  const { favorites, toggle: toggleFavorite } = useFavorites(DEFAULT_FAVORITES);

  const stops = useMemo(
    () => NEARBY_STOPS.map((s) => ({ ...s, isFavorite: favorites.includes(s.id) })),
    [favorites],
  );

  // Filters live here, not inside MapScreen, so the sheet's list (screen ②)
  // and the map's markers can never disagree about which stops are shown.
  const visibleStops = useMemo(
    () => applyStopFilters(stops, activeFilters),
    [stops, activeFilters],
  );

  function toggleFilter(key: FilterKey) {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // Peek is the "내 주변" summary, so dragging a detail sheet all the way down
  // dismisses it -- otherwise the detail sits cropped in a 120px window that
  // cannot scroll. Driven by an effect because the drag settles inside the hook.
  useEffect(() => {
    if (sheet.snap === "peek") setSelectedStopId(null);
  }, [sheet.snap]);

  // Resetting here rather than in an effect on activeTab: the reset belongs to
  // the act of switching tabs, and an effect would also fire on mount.
  function changeTab(tab: TabKey) {
    setActiveTab(tab);
    setSelectedStopId(null);
    sheet.setSnap("peek");
  }

  function selectStop(id: string) {
    setSelectedStopId(id);
    sheet.setSnap("half");
  }

  function backToList() {
    setSelectedStopId(null);
    sheet.setSnap("half");
  }

  /** Placeholder map has no camera, so "내 위치" returns to the surroundings
   * view: drop the selection and collapse back to the peek summary. */
  function recenter() {
    setSelectedStopId(null);
    sheet.setSnap("peek");
  }

  const selectedStop = selectedStopId ? stops.find((s) => s.id === selectedStopId) : undefined;
  const selectedDetail = selectedStopId ? STOP_DETAILS[selectedStopId] : undefined;

  return (
    <>
      {activeTab === "map" && (
        <>
          <MapScreen
            stops={stops}
            visibleStops={visibleStops}
            activeFilters={activeFilters}
            onToggleFilter={toggleFilter}
            selectedStopId={selectedStopId}
            sheetHeightPx={sheet.heightPx}
            controlsHidden={sheet.snap === "full"}
            onSelectStop={selectStop}
            onRecenter={recenter}
          />
          <BottomSheet sheet={sheet}>
            {selectedDetail && selectedStop ? (
              <StopDetailView
                stop={{ ...selectedDetail, isFavorite: selectedStop.isFavorite }}
                onBack={backToList}
                onToggleFavorite={toggleFavorite}
              />
            ) : selectedStop ? (
              <StopDetailPending
                stop={selectedStop}
                onBack={backToList}
                onToggleFavorite={toggleFavorite}
              />
            ) : (
              <NearbyStopsPanel
                stops={visibleStops}
                compact={sheet.snap === "peek"}
                onSelectStop={selectStop}
                onToggleFavorite={toggleFavorite}
              />
            )}
          </BottomSheet>
        </>
      )}
      {activeTab === "favorites" && <ComingSoon label="즐겨찾기" />}
      {activeTab === "settings" && <ComingSoon label="설정" />}

      <TabBar active={activeTab} onChange={changeTab} />
    </>
  );
}
