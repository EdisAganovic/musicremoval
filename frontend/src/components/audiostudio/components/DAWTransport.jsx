import React from "react";
import {
  Play,
  Pause,
  Square,
  Volume2,
  Scissors,
  VolumeX,
  MousePointer,
  RotateCcw,
  ZoomIn,
  ZoomOut,
  Magnet
} from "lucide-react";
import { formatTime } from "../utils/audioMath";
import { VuMeter } from "./VuMeter";

export function DAWTransport({
  isPlaying,
  startPlayback,
  pausePlayback,
  stopPlayback,
  currentTime,
  duration,
  isLooping,
  setIsLooping,
  zoomLevel,
  setZoomLevel,
  snapGrid,
  setSnapGrid,
  activeTool,
  setActiveTool,
  masterVolume,
  setMasterVolume,
  vuLevelsRef,
  activeTracks
}) {
  return (
    <div className="px-5 py-2 bg-[#0d1326] border-b border-gray-800/80 flex flex-wrap items-center justify-between gap-4 select-none">
      {/* Left: Transport Controls & Time Display */}
      <div className="flex items-center gap-3">
        {/* Play / Pause */}
        <button
          onClick={() => {
            if (isPlaying) {
              pausePlayback();
            } else {
              startPlayback(activeTracks);
            }
          }}
          className={`p-2 rounded-xl text-white font-bold transition shadow-lg flex items-center justify-center ${
            isPlaying
              ? "bg-amber-600 hover:bg-amber-500 shadow-amber-600/30"
              : "bg-blue-600 hover:bg-blue-500 shadow-blue-600/30"
          }`}
          title="Play / Pause (Spacebar)"
        >
          {isPlaying ? <Pause className="w-4 h-4 fill-white" /> : <Play className="w-4 h-4 fill-white translate-x-0.5" />}
        </button>

        {/* Stop */}
        <button
          onClick={stopPlayback}
          className="p-2 bg-[#172038] hover:bg-gray-800 text-gray-300 hover:text-white rounded-xl transition border border-gray-700/60"
          title="Stop & Reset to Start (0:00)"
        >
          <Square className="w-4 h-4" />
        </button>

        {/* Loop Toggle */}
        <button
          onClick={() => setIsLooping(!isLooping)}
          className={`p-2 rounded-xl transition border ${
            isLooping
              ? "bg-blue-600/20 text-blue-400 border-blue-500/50 shadow-sm"
              : "bg-[#172038] text-gray-400 hover:text-white border-gray-700/60"
          }`}
          title="Toggle Timeline Loop Playback"
        >
          <RotateCcw className="w-4 h-4" />
        </button>

        {/* Digital Timecode Display */}
        <div className="bg-black/70 border border-gray-800 px-3 py-1.5 rounded-xl font-mono flex items-center gap-1.5 shadow-inner">
          <span className="text-blue-400 font-bold text-sm tracking-wider">
            {formatTime(currentTime)}
          </span>
          <span className="text-gray-600 text-xs">/</span>
          <span className="text-gray-400 text-xs">
            {formatTime(duration)}
          </span>
        </div>
      </div>

      {/* Center: Tools, Snap Grid & Zoom */}
      <div className="flex items-center gap-3">
        {/* Tool Mode Buttons */}
        <div className="flex items-center bg-[#172038] p-0.5 rounded-xl border border-gray-700/60">
          <button
            onClick={() => setActiveTool("select")}
            className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1 transition ${
              activeTool === "select"
                ? "bg-blue-600 text-white shadow-sm"
                : "text-gray-400 hover:text-white"
            }`}
            title="Range Selection Tool (V)"
          >
            <MousePointer className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Select</span>
          </button>
          <button
            onClick={() => setActiveTool("cut")}
            className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1 transition ${
              activeTool === "cut"
                ? "bg-rose-600 text-white shadow-sm"
                : "text-gray-400 hover:text-white"
            }`}
            title="Razor Split Tool (C)"
          >
            <Scissors className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Split</span>
          </button>
          <button
            onClick={() => setActiveTool("silence")}
            className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1 transition ${
              activeTool === "silence"
                ? "bg-amber-600 text-white shadow-sm"
                : "text-gray-400 hover:text-white"
            }`}
            title="Silence Region Tool (Z)"
          >
            <VolumeX className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Silence</span>
          </button>
        </div>

        {/* Snap Grid */}
        <div className="flex items-center gap-1.5 bg-[#172038] px-2.5 py-1 rounded-xl border border-gray-700/60 text-xs">
          <Magnet className="w-3.5 h-3.5 text-gray-400" />
          <select
            value={snapGrid}
            onChange={(e) => setSnapGrid(Number(e.target.value))}
            className="bg-transparent text-gray-200 text-xs font-semibold focus:outline-none cursor-pointer"
            title="Snap Playhead & Cuts to Time Grid"
          >
            <option value={0} className="bg-[#0f172a]">Snap: Off</option>
            <option value={0.1} className="bg-[#0f172a]">Snap: 0.1s</option>
            <option value={0.5} className="bg-[#0f172a]">Snap: 0.5s</option>
            <option value={1.0} className="bg-[#0f172a]">Snap: 1.0s</option>
          </select>
        </div>

        {/* Timeline Zoom */}
        <div className="flex items-center gap-1 bg-[#172038] px-1.5 py-0.5 rounded-xl border border-gray-700/60">
          <button
            onClick={() => setZoomLevel(prev => Math.max(1.0, prev - 0.5))}
            className="p-1 text-gray-400 hover:text-white rounded hover:bg-white/5 transition"
            title="Zoom Out Timeline"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="text-[11px] font-mono font-bold text-gray-300 px-1 min-w-[28px] text-center">
            {zoomLevel.toFixed(1)}x
          </span>
          <button
            onClick={() => setZoomLevel(prev => Math.min(5.0, prev + 0.5))}
            className="p-1 text-gray-400 hover:text-white rounded hover:bg-white/5 transition"
            title="Zoom In Timeline"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Right: Master Volume & Stereo VU Meter */}
      <div className="flex items-center gap-3">
        {/* Master Volume */}
        <div className="flex items-center gap-2 bg-[#172038] px-2.5 py-1 rounded-xl border border-gray-700/60">
          <Volume2 className="w-3.5 h-3.5 text-gray-400" />
          <input
            type="range"
            min="0"
            max="1.5"
            step="0.05"
            value={masterVolume}
            onChange={(e) => setMasterVolume(Number(e.target.value))}
            className="w-16 accent-blue-500 cursor-pointer h-1.5"
            title={`Master Volume: ${Math.round(masterVolume * 100)}%`}
          />
          <span className="text-[10px] font-mono text-gray-300 w-7 text-right">
            {Math.round(masterVolume * 100)}%
          </span>
        </div>

        {/* VU Meter */}
        <VuMeter levelsRef={vuLevelsRef} />
      </div>
    </div>
  );
}
