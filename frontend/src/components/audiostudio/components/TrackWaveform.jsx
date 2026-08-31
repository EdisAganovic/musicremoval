import React, { useRef, useEffect } from "react";
import { Scissors, Trash2, VolumeX } from "lucide-react";
import { roundTo } from "../utils/audioMath";

export function TrackWaveform({
  track,
  duration,
  currentTime,
  peakData,
  selectedCut,
  setSelectedCut,
  dragSelection,
  setDragSelection,
  fadeOutDurationMs,
  fadeInDurationMs,
  handleTrackMouseDown,
  handleSelectionFadeHandleMouseDown,
  handleSelectionEdgeMouseDown,
  handleFadeHandleMouseDown,
  handleCutResizeMouseDown,
  removeCut,
  applyDeleteCut,
  applySilenceCut
}) {
  const canvasRef = useRef(null);

  // Render Canvas Waveform
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const activePeaks = (peakData && peakData.min && peakData.min.length > 0)
      ? peakData
      : (track.peaks && track.peaks.min && track.peaks.min.length > 0
          ? {
              min: new Float32Array(track.peaks.min),
              max: new Float32Array(track.peaks.max)
            }
          : null);

    if (!activePeaks || !activePeaks.min || activePeaks.min.length === 0) {
      // Background grid lines
      ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
      ctx.lineWidth = 1;
      for (let x = 0; x < width; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      return;
    }

    const { min: minPeaks, max: maxPeaks } = activePeaks;
    const numPeaks = minPeaks.length;
    const midY = height / 2;
    const trackColor = track.color || "#3b82f6";

    // Draw waveform bars
    ctx.fillStyle = trackColor;
    const barWidth = Math.max(1, width / numPeaks);

    for (let i = 0; i < numPeaks; i++) {
      const x = (i / numPeaks) * width;
      const minVal = minPeaks[i];
      const maxVal = maxPeaks[i];
      const topY = midY - maxVal * (height * 0.44);
      const bottomY = midY - minVal * (height * 0.44);
      const barHeight = Math.max(1, bottomY - topY);

      ctx.fillRect(x, topY, barWidth, barHeight);
    }
  }, [peakData, track.peaks, track.color]);

  return (
    <div
      onMouseDown={(e) => handleTrackMouseDown(e, track.id)}
      className="waveform-lane flex-1 relative bg-[#040814] h-28 overflow-visible select-none cursor-crosshair border-b border-gray-800/60"
    >
      {/* Waveform Canvas */}
      <canvas ref={canvasRef} className="w-full h-full block pointer-events-none" />

      {/* AI Bleed Highlight Regions */}
      {track.bleed_regions?.map((b, idx) => {
        const leftPct = (b.start / (duration || 30)) * 100;
        const widthPct = ((b.end - b.start) / (duration || 30)) * 100;
        return (
          <div
            key={idx}
            className="absolute top-0 bottom-0 bg-amber-500/20 border-x border-amber-500/50 pointer-events-none z-10 flex items-start p-1"
            style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
            title={`AI Detected Music Bleed (${roundTo(b.start, 1)}s - ${roundTo(b.end, 1)}s)`}
          >
            <span className="text-[8px] font-mono text-amber-300 bg-black/80 px-1 rounded">
              Bleed
            </span>
          </div>
        );
      })}

      {/* Applied Cut / Silence / Deleted Overlays */}
      {track.cuts?.map((cut) => {
        const leftPct = (cut.start / (duration || 30)) * 100;
        const widthPct = ((cut.end - cut.start) / (duration || 30)) * 100;
        const isSelected = selectedCut?.cutId === cut.id;
        const isDeleted = cut.deleted || cut.cut_type === 'delete';
        const cutDur = Math.max(0.01, cut.end - cut.start);
        const fadeOutSec = Math.min(cutDur * 0.48, Math.max(0.01, (cut.fade_out_ms ?? 100) / 1000));
        const fadeInSec = Math.min(cutDur * 0.48, Math.max(0.01, (cut.fade_in_ms ?? 100) / 1000));
        const fadeOutWidthPct = (fadeOutSec / cutDur) * 100;
        const fadeInWidthPct = (fadeInSec / cutDur) * 100;

        if (isDeleted) {
          return (
            <div
              key={cut.id}
              onClick={(e) => {
                e.stopPropagation();
                setSelectedCut({ trackId: track.id, cutId: cut.id });
              }}
              onMouseDown={(e) => e.stopPropagation()}
              className={`absolute top-0 bottom-0 bg-[repeating-linear-gradient(45deg,#3b0712,#3b0712_10px,#1f0409_10px,#1f0409_20px)] border-y border-dashed border-rose-500/50 shadow-2xl flex items-center justify-between z-20 group/cut select-none transition-all ${
                isSelected ? 'ring-2 ring-amber-400 border-x-2 border-amber-400' : 'border-x-2 border-rose-600'
              }`}
              style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
            >
              <div
                onMouseDown={(e) => handleCutResizeMouseDown(e, track.id, cut.id, 'start')}
                className="absolute top-0 bottom-0 left-0 w-3 cursor-ew-resize hover:bg-rose-400/40 flex items-center justify-center z-30 group/handle"
                title="Adjust start time of deleted region"
              >
                <div className="w-0.5 h-7 bg-rose-300/80 rounded-full group-hover/handle:bg-white group-hover/handle:w-1 transition-all" />
              </div>

              <div
                onMouseDown={(e) => e.stopPropagation()}
                className="absolute inset-0 flex items-center justify-center px-1 pointer-events-none z-20"
              >
                <div className="pointer-events-auto max-w-[calc(100%-16px)] flex items-center gap-1.5 bg-[#0a0204]/95 border border-rose-600/80 rounded-full px-2.5 py-1 shadow-2xl backdrop-blur-md text-[9px] font-mono select-none">
                  <Trash2 className="w-3 h-3 text-rose-400 shrink-0" />
                  <span className="text-rose-200 font-bold whitespace-nowrap" title={`Deleted audio segment: ${roundTo(cut.end - cut.start, 2)}s`}>
                    Deleted ({roundTo(cut.end - cut.start, 1)}s)
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeCut(track.id, cut.id);
                    }}
                    className="px-1.5 py-0.5 bg-rose-500/20 hover:bg-rose-500/40 text-rose-200 hover:text-white rounded text-[8px] font-bold border border-rose-500/40 transition-all hover:scale-105 active:scale-95 cursor-pointer ml-0.5"
                    title="Restore this deleted audio segment"
                  >
                    Restore
                  </button>
                </div>
              </div>

              <div
                onMouseDown={(e) => handleCutResizeMouseDown(e, track.id, cut.id, 'end')}
                className="absolute top-0 bottom-0 right-0 w-3 cursor-ew-resize hover:bg-rose-400/40 flex items-center justify-center z-30 group/handle"
                title="Adjust end time of deleted region"
              >
                <div className="w-0.5 h-7 bg-rose-300/80 rounded-full group-hover/handle:bg-white group-hover/handle:w-1 transition-all" />
              </div>
            </div>
          );
        }

        return (
          <div
            key={cut.id}
            onClick={(e) => {
              e.stopPropagation();
              setSelectedCut({ trackId: track.id, cutId: cut.id });
            }}
            onMouseDown={(e) => e.stopPropagation()}
            className={`absolute top-0 bottom-0 bg-rose-950/80 border-y border-rose-500/30 shadow-2xl flex items-center justify-between z-20 group/cut select-none transition-all ${
              isSelected ? 'ring-2 ring-amber-400 border-x-2 border-amber-400' : 'border-x-2 border-rose-500'
            }`}
            style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
          >
            {/* Left Fade-Out SVG Curve */}
            <div
              className="absolute top-0 bottom-0 left-0 pointer-events-none overflow-hidden"
              style={{ width: `${fadeOutWidthPct}%` }}
            >
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full">
                <defs>
                  <linearGradient id={`grad_out_${cut.id}`} x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.45" />
                    <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.05" />
                  </linearGradient>
                </defs>
                <path d="M 0 0 C 45 0, 55 100, 100 100 L 0 100 Z" fill={`url(#grad_out_${cut.id})`} />
                <path d="M 0 0 C 45 0, 55 100, 100 100" fill="none" stroke="#f43f5e" strokeWidth="2.5" />
              </svg>
              <div className="absolute top-0 bottom-0 right-0 border-r border-dashed border-rose-400/50" />
            </div>

            {/* Left DAW Fade-Out Drag Handle (Elevated above track) */}
            <div
              onMouseDown={(e) => handleFadeHandleMouseDown(e, track.id, cut.id, 'fade_out')}
              style={{ left: `${fadeOutWidthPct}%` }}
              className="absolute -top-3 -translate-x-1/2 w-5 h-5 bg-rose-500 hover:bg-rose-400 border-2 border-white rounded-full shadow-[0_0_12px_rgba(244,63,94,1)] cursor-ew-resize hover:scale-125 transition-transform z-50 flex items-center justify-center group/fadeout pointer-events-auto"
              title={`Fade Out: ${cut.fade_out_ms ?? 100}ms (Drag horizontally)`}
            >
              <div className="w-1.5 h-1.5 bg-white rounded-full pointer-events-none" />
              <span className="opacity-0 group-hover/fadeout:opacity-100 absolute -top-6 left-1/2 -translate-x-1/2 bg-black/95 text-rose-300 text-[10px] font-mono font-bold px-2 py-0.5 rounded shadow-xl whitespace-nowrap pointer-events-none border border-rose-500/50 z-50">
                Fade Out: {cut.fade_out_ms ?? 100}ms
              </span>
            </div>

            {/* Right Fade-In SVG Curve */}
            <div
              className="absolute top-0 bottom-0 right-0 pointer-events-none overflow-hidden"
              style={{ width: `${fadeInWidthPct}%` }}
            >
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full">
                <defs>
                  <linearGradient id={`grad_in_${cut.id}`} x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.45" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0.05" />
                  </linearGradient>
                </defs>
                <path d="M 0 100 C 45 100, 55 0, 100 0 L 100 100 Z" fill={`url(#grad_in_${cut.id})`} />
                <path d="M 0 100 C 45 100, 55 0, 100 0" fill="none" stroke="#10b981" strokeWidth="2.5" />
              </svg>
              <div className="absolute top-0 bottom-0 left-0 border-l border-dashed border-emerald-400/50" />
            </div>

            {/* Right DAW Fade-In Drag Handle (Elevated above track) */}
            <div
              onMouseDown={(e) => handleFadeHandleMouseDown(e, track.id, cut.id, 'fade_in')}
              style={{ right: `${fadeInWidthPct}%` }}
              className="absolute -top-3 translate-x-1/2 w-5 h-5 bg-emerald-500 hover:bg-emerald-400 border-2 border-white rounded-full shadow-[0_0_12px_rgba(16,185,129,1)] cursor-ew-resize hover:scale-125 transition-transform z-50 flex items-center justify-center group/fadein pointer-events-auto"
              title={`Fade In: ${cut.fade_in_ms ?? 100}ms (Drag horizontally)`}
            >
              <div className="w-1.5 h-1.5 bg-white rounded-full pointer-events-none" />
              <span className="opacity-0 group-hover/fadein:opacity-100 absolute -top-6 left-1/2 -translate-x-1/2 bg-black/95 text-emerald-300 text-[10px] font-mono font-bold px-2 py-0.5 rounded shadow-xl whitespace-nowrap pointer-events-none border border-emerald-500/50 z-50">
                Fade In: {cut.fade_in_ms ?? 100}ms
              </span>
            </div>

            {/* Left Resize Handle */}
            <div
              onMouseDown={(e) => handleCutResizeMouseDown(e, track.id, cut.id, 'start')}
              className="absolute top-0 bottom-0 left-0 w-3 cursor-ew-resize hover:bg-rose-400/40 flex items-center justify-center z-30 group/handle"
              title="Drag left/right to adjust cut start time"
            >
              <div className="w-0.5 h-7 bg-rose-300/80 rounded-full group-hover/handle:bg-white group-hover/handle:w-1 transition-all" />
            </div>

            {/* Center Clean Cut Pill */}
            <div
              onMouseDown={(e) => e.stopPropagation()}
              className="absolute inset-0 flex items-center justify-center px-1 pointer-events-none z-20"
            >
              <div className="pointer-events-auto max-w-[calc(100%-20px)] flex items-center gap-1.5 bg-[#060b18]/95 border border-rose-500/60 rounded-full px-2.5 py-1 shadow-2xl backdrop-blur-md text-[10px] font-mono select-none">
                <Scissors className="w-3 h-3 text-rose-400 shrink-0" />
                <span className="text-rose-200 font-bold whitespace-nowrap" title={`Silenced region: ${roundTo(cut.end - cut.start, 2)}s`}>
                  {roundTo(cut.end - cut.start, 1)}s
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeCut(track.id, cut.id);
                  }}
                  className="text-rose-300 hover:text-white p-0.5 hover:bg-rose-600 rounded-full shadow transition-all hover:scale-110 active:scale-95 cursor-pointer shrink-0 ml-0.5"
                  title="Delete Silenced Region (Del)"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>

            {/* Right Resize Handle */}
            <div
              onMouseDown={(e) => handleCutResizeMouseDown(e, track.id, cut.id, 'end')}
              className="absolute top-0 bottom-0 right-0 w-3 cursor-ew-resize hover:bg-rose-400/40 flex items-center justify-center z-30 group/handle"
              title="Drag left/right to adjust cut end time"
            >
              <div className="w-0.5 h-7 bg-rose-300/80 rounded-full group-hover/handle:bg-white group-hover/handle:w-1 transition-all" />
            </div>
          </div>
        );
      })}

      {/* Interactive Drag Selection Box */}
      {dragSelection && dragSelection.trackId === track.id && (() => {
        const selStart = Math.min(dragSelection.start, dragSelection.end);
        const selEnd = Math.max(dragSelection.start, dragSelection.end);
        const selDur = Math.max(0.01, selEnd - selStart);
        const selFadeOutSec = Math.min(selDur * 0.48, Math.max(0.01, (fadeOutDurationMs ?? 100) / 1000));
        const selFadeInSec = Math.min(selDur * 0.48, Math.max(0.01, (fadeInDurationMs ?? 100) / 1000));
        const selFadeOutWidthPct = (selFadeOutSec / selDur) * 100;
        const selFadeInWidthPct = (selFadeInSec / selDur) * 100;

        return (
          <div
            className="absolute top-0 bottom-0 bg-amber-400/20 border-y-2 border-amber-400/90 shadow-[0_0_20px_rgba(251,191,36,0.25)] z-30 pointer-events-none ring-1 ring-amber-300/40"
            style={{
              left: `${(selStart / (duration || 30)) * 100}%`,
              width: `${Math.max(0.2, ((selDur / (duration || 30)) * 100))}%`
            }}
          >
            {/* Left Fade-Out SVG Curve */}
            <div
              className="absolute top-0 bottom-0 left-0 pointer-events-none overflow-hidden"
              style={{ width: `${selFadeOutWidthPct}%` }}
            >
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full">
                <defs>
                  <linearGradient id="grad_out_sel" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.45" />
                    <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.05" />
                  </linearGradient>
                </defs>
                <path d="M 0 0 C 45 0, 55 100, 100 100 L 0 100 Z" fill="url(#grad_out_sel)" />
                <path d="M 0 0 C 45 0, 55 100, 100 100" fill="none" stroke="#f43f5e" strokeWidth="2.5" />
              </svg>
              <div className="absolute top-0 bottom-0 right-0 border-r border-dashed border-rose-400/60" />
            </div>

            {/* Left Fade-Out Handle (Elevated above track) */}
            <div
              onMouseDown={(e) => handleSelectionFadeHandleMouseDown(e, 'fade_out')}
              style={{ left: `${selFadeOutWidthPct}%` }}
              className="absolute -top-3 -translate-x-1/2 w-5 h-5 bg-rose-500 hover:bg-rose-400 border-2 border-white rounded-full shadow-[0_0_12px_rgba(244,63,94,1)] cursor-ew-resize hover:scale-125 transition-transform z-50 flex items-center justify-center group/fadeout pointer-events-auto"
              title={`Fade Out: ${fadeOutDurationMs}ms (Drag horizontally)`}
            >
              <div className="w-1.5 h-1.5 bg-white rounded-full pointer-events-none" />
              <span className="opacity-0 group-hover/fadeout:opacity-100 absolute -top-6 left-1/2 -translate-x-1/2 bg-black/95 text-rose-300 text-[10px] font-mono font-bold px-2 py-0.5 rounded shadow-xl whitespace-nowrap pointer-events-none border border-rose-500/50 z-50">
                Fade Out: {fadeOutDurationMs}ms
              </span>
            </div>

            {/* Right Fade-In SVG Curve */}
            <div
              className="absolute top-0 bottom-0 right-0 pointer-events-none overflow-hidden"
              style={{ width: `${selFadeInWidthPct}%` }}
            >
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full">
                <defs>
                  <linearGradient id="grad_in_sel" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.45" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0.05" />
                  </linearGradient>
                </defs>
                <path d="M 0 100 C 45 100, 55 0, 100 0 L 100 100 Z" fill="url(#grad_in_sel)" />
                <path d="M 0 100 C 45 100, 55 0, 100 0" fill="none" stroke="#10b981" strokeWidth="2.5" />
              </svg>
              <div className="absolute top-0 bottom-0 left-0 border-l border-dashed border-emerald-400/60" />
            </div>

            {/* Right Fade-In Handle (Elevated above track) */}
            <div
              onMouseDown={(e) => handleSelectionFadeHandleMouseDown(e, 'fade_in')}
              style={{ right: `${selFadeInWidthPct}%` }}
              className="absolute -top-3 translate-x-1/2 w-5 h-5 bg-emerald-500 hover:bg-emerald-400 border-2 border-white rounded-full shadow-[0_0_12px_rgba(16,185,129,1)] cursor-ew-resize hover:scale-125 transition-transform z-50 flex items-center justify-center group/fadein pointer-events-auto"
              title={`Fade In: ${fadeInDurationMs}ms (Drag horizontally)`}
            >
              <div className="w-1.5 h-1.5 bg-white rounded-full pointer-events-none" />
              <span className="opacity-0 group-hover/fadein:opacity-100 absolute -top-6 left-1/2 -translate-x-1/2 bg-black/95 text-emerald-300 text-[10px] font-mono font-bold px-2 py-0.5 rounded shadow-xl whitespace-nowrap pointer-events-none border border-emerald-500/50 z-50">
                Fade In: {fadeInDurationMs}ms
              </span>
            </div>

            {/* Left Selection Trim Handle */}
            <div
              onMouseDown={(e) => handleSelectionEdgeMouseDown(e, 'start')}
              className="absolute top-0 bottom-0 left-0 w-3.5 -translate-x-1/2 cursor-ew-resize hover:bg-amber-400/50 flex items-center justify-center z-40 group/edge pointer-events-auto"
              title="Drag to trim selection start time"
            >
              <div className="w-1 h-8 bg-amber-400 rounded-full shadow-[0_0_8px_rgba(251,191,36,1)] group-hover/edge:scale-125 transition-transform" />
            </div>

            {/* Centered Floating Action Toolbar */}
            <div
              onMouseDown={(e) => e.stopPropagation()}
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-[#080e22]/95 border border-amber-400/80 rounded-2xl px-3 py-1.5 flex flex-col items-center justify-center gap-1.5 shadow-2xl backdrop-blur-xl ring-2 ring-black/80 z-40 max-w-full w-fit pointer-events-auto select-none"
            >
              {/* 1st Line: Centered Seconds Badge */}
              <div className="flex items-center gap-1 text-amber-300 font-black text-xs">
                <Scissors className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                <span>{roundTo(selDur, 2)}s</span>
              </div>

              {/* 2nd Line: Centered Action Icons */}
              <div className="flex items-center gap-1.5">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    applyDeleteCut(dragSelection.trackId, selStart, selEnd);
                  }}
                  className="p-1.5 bg-rose-600 hover:bg-rose-500 text-white rounded-lg shadow-lg flex items-center justify-center transition-all hover:scale-110 active:scale-95 cursor-pointer"
                  title="Delete Audio Segment (Del / Backspace / X)"
                >
                  <Trash2 className="w-3.5 h-3.5 text-white" />
                </button>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    applySilenceCut();
                  }}
                  className="p-1.5 bg-amber-500 hover:bg-amber-400 text-black rounded-lg shadow-lg flex items-center justify-center transition-all hover:scale-110 active:scale-95 cursor-pointer"
                  title="Silence Region (Z)"
                >
                  <VolumeX className="w-3.5 h-3.5 text-black" />
                </button>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setDragSelection(null);
                  }}
                  className="p-1 text-gray-400 hover:text-white rounded-lg hover:bg-white/10 cursor-pointer text-xs"
                  title="Cancel Selection (Esc)"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Right Selection Trim Handle */}
            <div
              onMouseDown={(e) => handleSelectionEdgeMouseDown(e, 'end')}
              className="absolute top-0 bottom-0 right-0 w-3.5 translate-x-1/2 cursor-ew-resize hover:bg-amber-400/50 flex items-center justify-center z-40 group/edge pointer-events-auto"
              title="Drag to trim selection end time"
            >
              <div className="w-1 h-8 bg-amber-400 rounded-full shadow-[0_0_8px_rgba(251,191,36,1)] group-hover/edge:scale-125 transition-transform" />
            </div>

            {/* Bottom Region Boundaries Badge */}
            <div className="absolute bottom-1 left-1/2 -translate-x-1/2 flex items-center justify-center text-[8px] font-mono text-amber-300 bg-black/90 px-2 py-0.5 rounded border border-amber-400/50 shadow-lg whitespace-nowrap pointer-events-none z-30">
              <span>{roundTo(selStart, 2)}s ➔ {roundTo(selEnd, 2)}s</span>
            </div>
          </div>
        );
      })()}

      {/* Master Playhead Needle */}
      <div
        className="absolute top-0 bottom-0 w-0.5 bg-cyan-400 shadow-[0_0_10px_rgba(6,182,212,1)] z-40 pointer-events-none"
        style={{ left: `${(currentTime / (duration || 30)) * 100}%` }}
      />
    </div>
  );
}
