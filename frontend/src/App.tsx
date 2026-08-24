import { useEffect, useMemo, useState } from "react";
import { BottomSheet } from "./components/BottomSheet";
import { ComingSoon } from "./components/ComingSoon";
import { MapScreen } from "./components/MapScreen";
import { NearbyStopsPanel } from "./components/NearbyStopsPanel";
import { StopDetailLoading } from "./components/StopDetailLoading";
import { StopDetailPending } from "./components/StopDetailPending";
import { StopDetailView } from "./components/StopDetailView";
import { TabBar, type TabKey } from "./components/TabBar";
import { useBottomSheet } from "./hooks/useBottomSheet";
import { useCorridorStops } from "./hooks/useCorridorStops";
import { useFavorites } from "./hooks/useFavorites";
import { useStopDetail } from "./hooks/useStopDetail";
import { useUserLocation } from "./hooks/useUserLocation";
import { applySearchQuery, applyStopFilters, type FilterKey } from "./types/stop";
import { haversineDistanceM } from "./utils/geo";

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("map");
  const [selectedStopId, setSelectedStopId] = useState<string | null>(null);
  const [activeFilters, setActiveFilters] = useState<Set<FilterKey>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const sheet = useBottomSheet("peek");
  const { favorites, toggle: toggleFavorite } = useFavorites([]);
  const { stops: corridorStops, loading: stopsLoading, usingMock } = useCorridorStops();
  const location = useUserLocation();

  const stops = useMemo(() => {
    const withFavorites = corridorStops.map((s) => ({ ...s, isFavorite: favorites.includes(s.id) }));
    if (!location.position) return withFavorites;
    const withDistance = withFavorites.map((s) => ({
      ...s,
      distanceM: haversineDistanceM(location.position!, s.latLng),
    }));
    return withDistance.sort((a, b) => a.distanceM - b.distanceM);
  }, [corridorStops, favorites, location.position]);

  // Filters live here, not inside MapScreen, so the sheet's list (screen ②)
  // and the map's markers can never disagree about which stops are shown.
  const visibleStops = useMemo(() => {
    const filtered = applyStopFilters(stops, activeFilters);
    return applySearchQuery(filtered, searchQuery);
  }, [stops, activeFilters, searchQuery]);

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

  function recenter() {
    setSelectedStopId(null);
    sheet.setSnap("peek");
    location.retry();
  }

  const selectedStop = selectedStopId ? stops.find((s) => s.id === selectedStopId) : undefined;
  const { detail: selectedDetail, pending: detailPending } = useStopDetail(selectedStop, usingMock);

  return (
    <>
      {activeTab === "map" && (
        <>
          <MapScreen
            stops={stops}
            visibleStops={visibleStops}
            activeFilters={activeFilters}
            onToggleFilter={toggleFilter}
            searchQuery={searchQuery}
            onSearchQueryChange={setSearchQuery}
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
            ) : selectedStop && detailPending ? (
              <StopDetailLoading
                stop={selectedStop}
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
                loading={stopsLoading}
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
