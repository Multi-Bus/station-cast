import type { ReactNode } from "react";
import type { useBottomSheet } from "../hooks/useBottomSheet";
import "./BottomSheet.css";

export function BottomSheet({
  sheet,
  children,
}: {
  sheet: ReturnType<typeof useBottomSheet>;
  children: ReactNode;
}) {
  const { snap, setSnap, heightPx, isDragging, handlers } = sheet;

  return (
    <div
      className="bottom-sheet"
      style={{
        height: heightPx,
        transition: isDragging
          ? "none"
          : "height var(--sheet-snap-duration) var(--sheet-snap-ease)",
      }}
    >
      <div className="bottom-sheet-grabber-row" {...handlers}>
        {/* Dragging is pointer-driven, so the sheet also needs a plain
            activatable control to be reachable by keyboard. */}
        <button
          className="bottom-sheet-grabber"
          aria-label={snap === "full" ? "시트 접기" : "시트 펼치기"}
          aria-expanded={snap !== "peek"}
          onClick={() => setSnap(snap === "full" ? "peek" : "full")}
        />
      </div>
      <div className={`bottom-sheet-content ${snap === "peek" ? "bottom-sheet-content-locked" : ""}`}>
        {children}
      </div>
    </div>
  );
}
