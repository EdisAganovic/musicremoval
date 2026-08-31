import React from "react";
import {
  Volume2,
  VolumeX,
  Radio,
  Gauge,
  Sparkles,
  Edit3,
  Check,
  Trash2,
  SlidersHorizontal
} from "lucide-react";

export function TrackControls({
  track,
  editingTrackId,
  setEditingTrackId,
  editingName,
  setEditingName,
  handleRenameTrack,
  toggleMute,
  toggleSolo,
  setTrackVolume,
  setTrackPan,
  handleNormalizeTrack,
  handleScanBleed,
  handleDeleteTrack
}) {
  const isEditing = editingTrackId === track.id;

  return (
    <div className="w-56 bg-[#080d1a] border-r border-gray-800 p-2.5 flex flex-col justify-between shrink-0 select-none">
      {/* Top: Track Name & Stem Type Tag */}
      <div>
        <div className="flex items-center justify-between gap-1 mb-1">
          <div className="flex items-center gap-1.5 min-w-0 flex-1">
            <div
              className="w-2.5 h-2.5 rounded-full shrink-0 shadow-sm"
              style={{ backgroundColor: track.color || "#3b82f6" }}
            />
            {isEditing ? (
              <div className="flex items-center gap-1 w-full">
                <input
                  type="text"
                  value={editingName}
                  onChange={(e) => setEditingName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleRenameTrack(track.id);
                    if (e.key === "Escape") setEditingTrackId(null);
                  }}
                  autoFocus
                  className="bg-[#11192e] border border-blue-500 rounded px-1.5 py-0.5 text-xs text-white w-full focus:outline-none"
                />
                <button
                  onClick={() => handleRenameTrack(track.id)}
                  className="p-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-[10px]"
                >
                  <Check className="w-3 h-3" />
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-between w-full min-w-0 group/title">
                <span
                  onDoubleClick={() => {
                    setEditingTrackId(track.id);
                    setEditingName(track.name);
                  }}
                  className="text-xs font-bold text-gray-200 truncate cursor-text"
                  title="Double click to rename"
                >
                  {track.name}
                </span>
                <button
                  onClick={() => {
                    setEditingTrackId(track.id);
                    setEditingName(track.name);
                  }}
                  className="opacity-0 group-hover/title:opacity-100 p-0.5 text-gray-500 hover:text-gray-300 rounded transition"
                  title="Rename Track"
                >
                  <Edit3 className="w-2.5 h-2.5" />
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Stem Badge */}
        <div className="flex items-center gap-1">
          <span className="px-1.5 py-0.2 text-[8px] font-mono font-bold uppercase rounded bg-gray-800/80 text-gray-400 border border-gray-700/60">
            {track.model || "Source"}
          </span>
          {track.stem_type && (
            <span className="px-1.5 py-0.2 text-[8px] font-mono font-semibold rounded bg-blue-950/40 text-blue-300 border border-blue-800/30">
              {track.stem_type}
            </span>
          )}
        </div>
      </div>

      {/* Middle: Mute / Solo Buttons & Actions */}
      <div className="flex items-center justify-between gap-1.5 my-2">
        <div className="flex items-center gap-1">
          {/* Mute */}
          <button
            onClick={() => toggleMute(track.id)}
            className={`px-2 py-0.5 rounded text-[10px] font-bold transition ${
              track.muted
                ? "bg-rose-600 text-white shadow-sm"
                : "bg-gray-800 text-gray-400 hover:text-white"
            }`}
            title="Mute Track (M)"
          >
            M
          </button>

          {/* Solo */}
          <button
            onClick={() => toggleSolo(track.id)}
            className={`px-2 py-0.5 rounded text-[10px] font-bold transition ${
              track.solo
                ? "bg-amber-500 text-black shadow-sm"
                : "bg-gray-800 text-gray-400 hover:text-white"
            }`}
            title="Solo Track (S)"
          >
            S
          </button>
        </div>

        <div className="flex items-center gap-1">
          {/* Normalize Volume */}
          <button
            onClick={() => handleNormalizeTrack(track.id)}
            className="p-1 text-gray-400 hover:text-cyan-300 rounded hover:bg-cyan-950/30 transition"
            title="EBU R128 Peak Normalization (N)"
          >
            <Gauge className="w-3.5 h-3.5" />
          </button>

          {/* Scan Bleed */}
          <button
            onClick={() => handleScanBleed(track.id)}
            className="p-1 text-gray-400 hover:text-amber-300 rounded hover:bg-amber-950/30 transition"
            title="AI Scan Music Bleed in Vocals"
          >
            <Sparkles className="w-3.5 h-3.5" />
          </button>

          {/* Delete Track */}
          <button
            onClick={() => handleDeleteTrack(track.id)}
            className="p-1 text-gray-500 hover:text-rose-400 rounded hover:bg-rose-950/30 transition"
            title="Delete Stem Track"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Bottom: Volume & Pan Sliders */}
      <div className="space-y-1 pt-1 border-t border-gray-800/60">
        {/* Volume */}
        <div className="flex items-center gap-1.5 text-[9px] font-mono text-gray-400">
          <Volume2 className="w-3 h-3 shrink-0 text-gray-500" />
          <input
            type="range"
            min="0"
            max="1.5"
            step="0.05"
            value={track.volume ?? 1.0}
            onChange={(e) => setTrackVolume(track.id, Number(e.target.value))}
            className="w-full accent-blue-500 cursor-pointer h-1"
            title={`Track Volume: ${Math.round((track.volume ?? 1.0) * 100)}%`}
          />
          <span className="w-6 text-right text-[8px]">
            {Math.round((track.volume ?? 1.0) * 100)}%
          </span>
        </div>

        {/* Pan */}
        <div className="flex items-center gap-1.5 text-[9px] font-mono text-gray-400">
          <span className="w-3 text-center text-gray-500 font-bold">P</span>
          <input
            type="range"
            min="-1.0"
            max="1.0"
            step="0.1"
            value={track.pan ?? 0.0}
            onChange={(e) => setTrackPan(track.id, Number(e.target.value))}
            className="w-full accent-cyan-500 cursor-pointer h-1"
            title={`Track Pan: ${track.pan > 0 ? `R${Math.round(track.pan * 100)}` : track.pan < 0 ? `L${Math.round(Math.abs(track.pan) * 100)}` : 'Center'}`}
          />
          <span className="w-6 text-right text-[8px]">
            {track.pan > 0 ? `R${Math.round(track.pan * 10)}` : track.pan < 0 ? `L${Math.round(Math.abs(track.pan) * 10)}` : 'C'}
          </span>
        </div>
      </div>
    </div>
  );
}
