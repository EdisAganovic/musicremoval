import React from "react";
import { Sparkles, Layers, Sliders, Music, Mic } from "lucide-react";

export function SeparationPassModal({
  show,
  onClose,
  passName,
  setPassName,
  passModel,
  setPassModel,
  passRoformerModel,
  setPassRoformerModel,
  passTigerTarget,
  setPassTigerTarget,
  passTigerOverlap,
  setPassTigerOverlap,
  passDemucsStems,
  setPassDemucsStems,
  passSpleeterStems,
  setPassSpleeterStems,
  handleRunPass,
  passRunning
}) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-[#0f172a] border border-amber-500/40 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-5 text-gray-200 animate-in fade-in zoom-in duration-200">
        <div className="flex justify-between items-center border-b border-gray-800 pb-3">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-400" /> Run AI Stem Separation Pass
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">✕</button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-gray-400 block mb-1">Pass Name / Label</label>
            <input
              type="text"
              value={passName}
              onChange={(e) => setPassName(e.target.value)}
              className="w-full bg-[#1e293b] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-400 block mb-1">AI Separation Model</label>
            <select
              value={passModel}
              onChange={(e) => setPassModel(e.target.value)}
              className="w-full bg-[#1e293b] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
            >
              <option value="tiger">⚡ TIGER AI (3-Stem: Dialogue/Foley/Score - Fastest & Best for TV/Cartoons)</option>
              <option value="roformer">👑 Mel-Band Roformer (State-of-the-Art Music/Vocal Bleed Removal)</option>
              <option value="demucs">🎸 Demucs v4 HT (High Fidelity 4-Stem/6-Stem Multi-Band)</option>
              <option value="spleeter">⚡ Spleeter Classic (Fast 2/4/5 Stems)</option>
            </select>
          </div>

          {passModel === "tiger" && (
            <div className="p-3 bg-amber-950/20 border border-amber-900/40 rounded-xl space-y-3">
              <div className="text-xs font-semibold text-amber-300">TIGER Model Options</div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">Target Mode</label>
                <select
                  value={passTigerTarget}
                  onChange={(e) => setPassTigerTarget(e.target.value)}
                  className="w-full bg-[#1e293b] border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white"
                >
                  <option value="dialogue_sfx">Dialogue + SFX Separation (Preserve Foley, Isolate Score)</option>
                  <option value="all">Full 3-Way Stem Split (Dialogue, Foley Effects, Music Score)</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">Window Overlap ({passTigerOverlap}%)</label>
                <input
                  type="range"
                  min="25"
                  max="75"
                  step="5"
                  value={passTigerOverlap}
                  onChange={(e) => setPassTigerOverlap(Number(e.target.value))}
                  className="w-full accent-amber-500"
                />
              </div>
            </div>
          )}

          {passModel === "roformer" && (
            <div className="p-3 bg-cyan-950/20 border border-cyan-900/40 rounded-xl space-y-3">
              <div className="text-xs font-semibold text-cyan-300">Mel-Band Roformer Checkpoint</div>
              <select
                value={passRoformerModel}
                onChange={(e) => setPassRoformerModel(e.target.value)}
                className="w-full bg-[#1e293b] border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white"
              >
                <option value="mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt">Mel-Band Roformer Crowd & Vocal SDR 8.71 (ViperX)</option>
                <option value="mel_band_roformer_vocals.ckpt">Standard Vocal Roformer</option>
              </select>
            </div>
          )}

          {passModel === "demucs" && (
            <div className="p-3 bg-indigo-950/20 border border-indigo-900/40 rounded-xl space-y-3">
              <div className="text-xs font-semibold text-indigo-300">Demucs Stem Count</div>
              <select
                value={passDemucsStems}
                onChange={(e) => setPassDemucsStems(Number(e.target.value))}
                className="w-full bg-[#1e293b] border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white"
              >
                <option value={4}>4 Stems (Vocals, Drums, Bass, Other)</option>
                <option value={6}>6 Stems (Vocals, Drums, Bass, Other, Guitar, Piano)</option>
              </select>
            </div>
          )}

          {passModel === "spleeter" && (
            <div className="p-3 bg-purple-950/20 border border-purple-900/40 rounded-xl space-y-3">
              <div className="text-xs font-semibold text-purple-300">Spleeter Stems</div>
              <select
                value={passSpleeterStems}
                onChange={(e) => setPassSpleeterStems(Number(e.target.value))}
                className="w-full bg-[#1e293b] border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white"
              >
                <option value={2}>2 Stems (Vocals + Accompaniment)</option>
                <option value={4}>4 Stems (Vocals, Drums, Bass, Other)</option>
                <option value={5}>5 Stems (Vocals, Drums, Bass, Piano, Other)</option>
              </select>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition"
          >
            Cancel
          </button>
          <button
            onClick={handleRunPass}
            disabled={passRunning}
            className="px-5 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-medium rounded-lg text-sm flex items-center gap-2 shadow-lg shadow-amber-600/20 transition"
          >
            {passRunning ? "Processing Separation..." : "Start Separation Pass"}
          </button>
        </div>
      </div>
    </div>
  );
}
