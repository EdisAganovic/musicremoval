import React, { useRef, useCallback } from "react";
import { formatTime, snapToGrid } from "../utils/audioMath";

export function TimelineRuler({
  duration,
  currentTime,
  zoomLevel,
  snapGrid,
  hoverTime,
  setHoverTime,
  seekTo,
  activeTracks,
  timelineRulerRef
}) {
  const isScrubbingRef = useRef(false);

  const handleRulerMouseDown = useCallback((e) => {
    e.preventDefault();
    isScrubbingRef.current = true;
    const ruler = timelineRulerRef.current;
    if (!ruler) return;
    const rect = ruler.getBoundingClientRect();

    const updateTimeFromEvent = (event) => {
      const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
      const rawTime = (x / rect.width) * (duration || 30);
      const snapped = snapToGrid(rawTime, snapGrid);
      seekTo(snapped, activeTracks);
    };

    updateTimeFromEvent(e);

    const onMouseMove = (moveEvent) => {
      if (isScrubbingRef.current) {
        updateTimeFromEvent(moveEvent);
      }
    };

    const onMouseUp = () => {
      isScrubbingRef.current = false;
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, [duration, snapGrid, seekTo, activeTracks, timelineRulerRef]);

  const handleMouseMove = useCallback((e) => {
    const ruler = timelineRulerRef.current;
    if (!ruler) return;
    const rect = ruler.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const t = (x / rect.width) * (duration || 30);
    setHoverTime(t);
  }, [duration, setHoverTime, timelineRulerRef]);

  // Generate dynamic ruler ticks based on duration and zoom
  const numMajorTicks = Math.max(4, Math.min(40, Math.round(10 * zoomLevel)));
  const ticks = Array.from({ length: numMajorTicks + 1 }, (_, i) => {
    const t = (i / numMajorTicks) * (duration || 30);
    const pct = (i / numMajorTicks) * 100;
    return { time: t, pct };
  });

  return (
    <div
      ref={timelineRulerRef}
      onMouseDown={handleRulerMouseDown}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => setHoverTime(null)}
      className="relative h-7 bg-[#090f20] border-b border-gray-800/90 cursor-pointer select-none overflow-hidden"
      title="Click or drag to scrub playhead"
    >
      {/* Ticks */}
      {ticks.map((tick, idx) => (
        <div
          key={idx}
          className="absolute top-0 bottom-0 flex flex-col justify-between pointer-events-none"
          style={{ left: `${tick.pct}%` }}
        >
          <span className="text-[9px] font-mono font-semibold text-gray-400 pl-1">
            {formatTime(tick.time)}
          </span>
          <div className="w-px h-2 bg-gray-700 self-start" />
        </div>
      ))}

      {/* Hover Needle */}
      {hoverTime !== null && (
        <div
          className="absolute top-0 bottom-0 w-px bg-cyan-400/50 pointer-events-none z-10"
          style={{ left: `${(hoverTime / (duration || 30)) * 100}%` }}
        >
          <span className="absolute -top-0.5 left-1 bg-black/90 text-cyan-300 text-[8px] font-mono px-1 rounded shadow">
            {formatTime(hoverTime)}
          </span>
        </div>
      )}

      {/* Master Playhead Indicator Needle */}
      <div
        className="absolute top-0 bottom-0 w-0.5 bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,1)] pointer-events-none z-20"
        style={{ left: `${(currentTime / (duration || 30)) * 100}%` }}
      >
        <div className="w-2.5 h-2.5 -translate-x-[4px] -top-1 bg-cyan-400 rotate-45 rounded-sm shadow-md" />
      </div>
    </div>
  );
}
