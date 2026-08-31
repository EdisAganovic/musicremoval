import React, { useRef, useCallback } from "react";

export function MinimapScrollbar({
  zoomLevel,
  timelineContainerRef
}) {
  const isDraggingThumb = useRef(false);
  const startX = useRef(0);
  const startScrollLeft = useRef(0);

  const thumbWidthPct = Math.max(15, 100 / zoomLevel);

  const handleScrollbarMouseDown = useCallback((e) => {
    const container = timelineContainerRef.current;
    if (!container) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = clickX / rect.width;
    const maxScroll = container.scrollWidth - container.clientWidth;
    container.scrollLeft = ratio * maxScroll;
  }, [timelineContainerRef]);

  const handleThumbMouseDown = useCallback((e) => {
    e.stopPropagation();
    isDraggingThumb.current = true;
    startX.current = e.clientX;
    const container = timelineContainerRef.current;
    if (container) {
      startScrollLeft.current = container.scrollLeft;
    }

    const onMouseMove = (moveEvent) => {
      if (!isDraggingThumb.current || !timelineContainerRef.current) return;
      const dx = moveEvent.clientX - startX.current;
      const trackWidth = timelineContainerRef.current.clientWidth;
      const scrollRange = timelineContainerRef.current.scrollWidth - timelineContainerRef.current.clientWidth;
      const scrollDx = (dx / trackWidth) * scrollRange * zoomLevel;
      timelineContainerRef.current.scrollLeft = startScrollLeft.current + scrollDx;
    };

    const onMouseUp = () => {
      isDraggingThumb.current = false;
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, [timelineContainerRef, zoomLevel]);

  if (zoomLevel <= 1.05) return null;

  return (
    <div
      onMouseDown={handleScrollbarMouseDown}
      className="h-3 bg-[#060a14] border-t border-gray-800/80 relative cursor-pointer select-none px-56"
    >
      <div
        onMouseDown={handleThumbMouseDown}
        style={{
          width: `${thumbWidthPct}%`,
          left: `calc(14rem + 0px)`
        }}
        className="h-full bg-blue-600/40 hover:bg-blue-500/60 rounded-full border border-blue-400/40 cursor-grab active:cursor-grabbing transition-colors"
        title="Drag to scroll timeline view"
      />
    </div>
  );
}
