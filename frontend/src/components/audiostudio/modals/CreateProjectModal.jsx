import React from "react";
import { Plus, Video } from "lucide-react";

export function CreateProjectModal({
  show,
  onClose,
  newProjName,
  setNewProjName,
  newProjFile,
  setNewProjFile,
  libraryFiles,
  selectedLibPath,
  setSelectedLibPath,
  createDuration,
  setCreateDuration,
  handleCreateProject,
  loading
}) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-[#0f172a] border border-blue-900/50 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-5 text-gray-200 animate-in fade-in zoom-in duration-200">
        <div className="flex justify-between items-center border-b border-gray-800 pb-3">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Plus className="w-5 h-5 text-blue-400" /> New Multi-Pass Audio Project
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">✕</button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-gray-400 block mb-1">Project Name</label>
            <input
              type="text"
              value={newProjName}
              onChange={(e) => setNewProjName(e.target.value)}
              className="w-full bg-[#1e293b] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              placeholder="e.g. Episode 01 Dialogue Cleanup"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-400 block mb-1">Select from Downloaded Media Library</label>
            <select
              value={selectedLibPath}
              onChange={(e) => {
                setSelectedLibPath(e.target.value);
                if (e.target.value) setNewProjFile(null);
              }}
              className="w-full bg-[#1e293b] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">-- Or Choose from Local Library --</option>
              {libraryFiles.map((f, idx) => {
                const pathVal = f.filepath || (f.result_files && f.result_files[0]) || f.file_path || "";
                const label = f.filename || (pathVal ? pathVal.split(/[/\\]/).pop() : `Media Item ${idx + 1}`);
                const typeBadge = f.type ? ` [${f.type}]` : "";
                return (
                  <option key={f.task_id || idx} value={pathVal}>
                    {label}{typeBadge}
                  </option>
                );
              })}
            </select>
          </div>

          <div className="relative flex py-1 items-center">
            <div className="flex-grow border-t border-gray-700"></div>
            <span className="flex-shrink mx-3 text-xs text-gray-500">OR UPLOAD FILE</span>
            <div className="flex-grow border-t border-gray-700"></div>
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-400 block mb-1">Upload Video or Audio File (.mp4, .mkv, .wav, .mp3)</label>
            <input
              type="file"
              accept="video/*,audio/*"
              onChange={(e) => {
                setNewProjFile(e.target.files[0]);
                if (e.target.files[0]) setSelectedLibPath("");
              }}
              className="w-full text-xs text-gray-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500 cursor-pointer"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-400 block mb-1">Duration Limit (Seconds, Optional)</label>
            <input
              type="number"
              value={createDuration}
              onChange={(e) => setCreateDuration(e.target.value)}
              placeholder="Full File Duration"
              className="w-full bg-[#1e293b] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            />
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
            onClick={handleCreateProject}
            disabled={loading || (!newProjFile && !selectedLibPath)}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded-lg text-sm flex items-center gap-2 shadow-lg shadow-blue-500/20 transition"
          >
            {loading ? "Extracting Audio..." : "Create Project"}
          </button>
        </div>
      </div>
    </div>
  );
}
