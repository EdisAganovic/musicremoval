import React from "react";
import { Mic, FileAudio } from "lucide-react";

export function ImportTrackModal({
  show,
  onClose,
  importFile,
  setImportFile,
  importTrackName,
  setImportTrackName,
  handleImportTrack,
  loading
}) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-[#0f172a] border border-emerald-500/40 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-5 text-gray-200 animate-in fade-in zoom-in duration-200">
        <div className="flex justify-between items-center border-b border-gray-800 pb-3">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Mic className="w-5 h-5 text-emerald-400" /> Import Voiceover / Translated Dub Track
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">✕</button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-gray-400 block mb-1">Track Label Name</label>
            <input
              type="text"
              value={importTrackName}
              onChange={(e) => setImportTrackName(e.target.value)}
              className="w-full bg-[#1e293b] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
              placeholder="e.g. 🎙️ Translated Spanish Voiceover"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-400 block mb-1">Upload Audio File (.wav, .mp3, .aac, .flac, .m4a)</label>
            <input
              type="file"
              accept="audio/*"
              onChange={(e) => setImportFile(e.target.files[0])}
              className="w-full text-xs text-gray-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-600 file:text-white hover:file:bg-emerald-500 cursor-pointer"
            />
          </div>

          <div className="p-3 bg-emerald-950/20 border border-emerald-900/40 rounded-xl text-xs text-emerald-300">
            💡 The audio track will be loaded directly into your DAW multi-track timeline, with full volume, pan, mute, solo, and region cutting support.
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition"
          >
            Cancel
          </button>
          <button
            onClick={handleImportTrack}
            disabled={loading || !importFile}
            className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium rounded-lg text-sm flex items-center gap-2 shadow-lg shadow-emerald-600/20 transition"
          >
            {loading ? "Importing Track..." : "Import Track"}
          </button>
        </div>
      </div>
    </div>
  );
}
