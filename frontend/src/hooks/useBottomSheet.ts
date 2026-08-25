import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";

export type SheetSnap = "peek" | "half" | "full";

const PEEK_PX = 120;
const HALF_RATIO = 0.54;

/** Resolves --tabbar-total (tokens.css: 56px tab bar + safe-area-inset-bottom)
 * to an actual pixel number. A custom property can't be read directly via
 * getComputedStyle -- calc()/env() inside one are only resolved once the
 * property is applied to a real layout property, so a throwaway probe
 * element is the standard way to get the number out.
 *
 * Reading the token here (rather than re-deriving 56 + inset separately)
 * keeps this in sync with BottomSheet.css's `bottom: var(--tabbar-total)`
 * by construction -- the two drifting apart is exactly how issue #142
 * happened (JS hardcoded 56, CSS also added the inset). */
function readTabbarTotalPx(): number {
  const probe = document.createElement("div");
  probe.style.position = "absolute";
  probe.style.visibility = "hidden";
  probe.style.height = "var(--tabbar-total)";
  document.body.appendChild(probe);
  const px = probe.getBoundingClientRect().height;
  document.body.removeChild(probe);
  return px;
}

function computeAnchors(viewportH: number) {
  const containerH = viewportH - readTabbarTotalPx();
  return { peek: PEEK_PX, half: Math.round(containerH * HALF_RATIO), full: containerH };
}

/** Drag-to-snap bottom sheet (README "바텀시트 3단 스냅"): tracks pointer
 * delta as a live height while dragging, then on release jumps to whichever
 * of peek/half/full is nearest and lets CSS transition the rest of the way. */
export function useBottomSheet(initial: SheetSnap = "peek") {
  const [snap, setSnap] = useState<SheetSnap>(initial);
  const [dragHeight, setDragHeight] = useState<number | null>(null);
  // Anchors live in state, not a ref: a ref would be mutated on resize without
  // re-rendering, leaving the sheet sized to the old viewport until something
  // else happened to render.
  const [anchors, setAnchors] = useState(() => computeAnchors(window.innerHeight));
  const dragStart = useRef<{ y: number; height: number } | null>(null);

  useEffect(() => {
    const onResize = () => setAnchors(computeAnchors(window.innerHeight));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const onPointerDown = useCallback(
    (e: ReactPointerEvent) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      dragStart.current = { y: e.clientY, height: anchors[snap] };
    },
    [anchors, snap],
  );

  const onPointerMove = useCallback(
    (e: ReactPointerEvent) => {
      if (!dragStart.current) return;
      const delta = e.clientY - dragStart.current.y;
      setDragHeight(
        Math.min(anchors.full, Math.max(anchors.peek, dragStart.current.height - delta)),
      );
    },
    [anchors],
  );

  // Always clears dragHeight, even when no drag was in progress. Bailing out
  // early on a missing dragStart (a cancelled or never-delivered pointerdown)
  // used to strand a stale dragHeight, which pins heightPx and makes the sheet
  // ignore every later snap change.
  const endDrag = useCallback(() => {
    const started = dragStart.current !== null;
    dragStart.current = null;

    if (started && dragHeight !== null) {
      const nearest = (
        [
          ["peek", Math.abs(dragHeight - anchors.peek)],
          ["half", Math.abs(dragHeight - anchors.half)],
          ["full", Math.abs(dragHeight - anchors.full)],
        ] as [SheetSnap, number][]
      ).sort((a, b) => a[1] - b[1])[0][0];
      setSnap(nearest);
    }
    setDragHeight(null);
  }, [anchors, dragHeight]);

  return {
    snap,
    setSnap,
    heightPx: dragHeight ?? anchors[snap],
    isDragging: dragHeight !== null,
    handlers: {
      onPointerDown,
      onPointerMove,
      onPointerUp: endDrag,
      onPointerCancel: endDrag,
    },
  };
}
