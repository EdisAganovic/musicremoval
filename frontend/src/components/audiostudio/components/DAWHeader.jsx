import React, { useState, useRef, useEffect } from "react";
import {
  FolderOpen,
  Plus,
  Undo2,
  Redo2,
  Sparkles,
  Mic,
  Save,
  Download,
  Video,
  Trash2,
  ChevronDown,
  Layers
} from "lucide-react";

export function DAWHeader({
  projects,
  activeProject,
  handleSelectProject,
  handleDeleteProject,
  setShowCreateModal,
  canUndo,
  canRedo,
  handleUndo,
  handleRedo,
  setShowPassModal,
  setShowImportModal,
  saveProjectManual,
  isRendering,
  renderProgress,
  handleExportMix,
  handleRemuxVideo
}) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false);
      }
    }
    if (dropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [dropdownOpen]);

  return (
    <header className="px-5 py-2.5 bg-[#0a0f1d] border-b border-gray-800 flex flex-wrap items-center justify-between gap-3 select-none">
      {/* Left: Project Selector & Brand */}
      <div className="flex items-center gap-3">
        <div className="relative flex items-center gap-1.5" ref={dropdownRef}>
          {/* Custom Project Dropdown Trigger */}
          <button
            onClick={() => setDropdownOpen(prev => !prev)}
            className="flex items-center gap-2 bg-[#11192e] hover:bg-[#16213c] border border-gray-700/80 hover:border-blue-500/60 rounded-lg px-3 py-1.5 text-xs text-gray-200 font-semibold focus:outline-none transition shadow-sm max-w-[240px]"
            title="Switch or Manage Audio Projects"
          >
            <FolderOpen className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
            <span className="truncate">{activeProject?.name || "Select Project"}</span>
            <ChevronDown className={`w-3.5 h-3.5 text-gray-400 flex-shrink-0 transition-transform duration-150 ${dropdownOpen ? "rotate-180" : ""}`} />
          </button>

          {/* New Project Button */}
          <button
            onClick={() => {
              setDropdownOpen(false);
              setShowCreateModal(true);
            }}
            className="p-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition shadow-sm"
            title="Create New Multi-Pass Audio Project"
          >
            <Plus className="w-4 h-4" />
          </button>

          {/* Delete Active Project Button */}
          {activeProject && (
            <button
              onClick={() => handleDeleteProject(activeProject.id, activeProject.name)}
              className="p-1.5 bg-red-950/40 hover:bg-red-900/60 text-red-400 hover:text-red-300 border border-red-800/40 rounded-lg transition"
              title={`Delete current project "${activeProject.name}"`}
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Dropdown Menu */}
          {dropdownOpen && (
            <div className="absolute left-0 top-full mt-1.5 w-72 bg-[#0e1628] border border-gray-700/90 rounded-xl shadow-2xl z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-100 divide-y divide-gray-800/80">
              <div className="px-3 py-2 bg-[#090e1a] flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400">Audio Projects</span>
                <span className="text-[10px] text-gray-500">{projects.length} available</span>
              </div>

              <div className="max-h-64 overflow-y-auto py-1 space-y-0.5">
                {projects.length === 0 ? (
                  <div className="px-3 py-4 text-center text-xs text-gray-500">
                    No projects found. Create one!
                  </div>
                ) : (
                  projects.map((p) => {
                    const isActive = activeProject?.id === p.id;
                    return (
                      <div
                        key={p.id}
                        className={`group flex items-center justify-between px-3 py-2 text-xs transition cursor-pointer ${
                          isActive
                            ? "bg-blue-600/20 text-blue-300 font-semibold border-l-2 border-blue-500"
                            : "text-gray-300 hover:bg-white/5 hover:text-white"
                        }`}
                        onClick={() => {
                          handleSelectProject(p.id);
                          setDropdownOpen(false);
                        }}
                      >
                        <div className="flex items-center gap-2 min-w-0 flex-1 pr-2">
                          <FolderOpen className={`w-3.5 h-3.5 flex-shrink-0 ${isActive ? "text-blue-400" : "text-gray-400 group-hover:text-gray-300"}`} />
                          <span className="truncate">{p.name}</span>
                        </div>

                        <div className="flex items-center gap-2 flex-shrink-0">
                          {p.track_count !== undefined && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 flex items-center gap-1 font-mono">
                              <Layers className="w-2.5 h-2.5" />
                              {p.track_count}
                            </span>
                          )}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteProject(p.id, p.name);
                            }}
                            className="p-1 text-gray-500 hover:text-red-400 hover:bg-red-950/40 rounded transition"
                            title={`Delete "${p.name}"`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <div className="p-1.5 bg-[#090e1a]">
                <button
                  onClick={() => {
                    setDropdownOpen(false);
                    setShowCreateModal(true);
                  }}
                  className="w-full py-1.5 px-3 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 hover:text-white border border-blue-500/30 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Create New Project</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {activeProject && (
          <div className="hidden sm:flex items-center gap-2 border-l border-gray-800 pl-3">
            <span className="text-xs font-bold text-white tracking-wide truncate max-w-[220px]">
              {activeProject.name}
            </span>
            <span className="px-2 py-0.5 bg-blue-950/60 text-blue-300 border border-blue-800/50 rounded-full text-[10px] font-mono">
              {activeProject.tracks?.length || 0} Stems
            </span>
          </div>
        )}
      </div>

      {/* Right: Actions & History */}
      {activeProject && (
        <div className="flex items-center gap-2">
          {/* Undo / Redo */}
          <div className="flex items-center bg-[#11192e] border border-gray-800 rounded-lg p-0.5">
            <button
              onClick={handleUndo}
              disabled={!canUndo}
              className="p-1 text-gray-400 hover:text-white disabled:opacity-30 rounded hover:bg-white/5 transition"
              title="Undo Last Edit (Ctrl+Z)"
            >
              <Undo2 className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleRedo}
              disabled={!canRedo}
              className="p-1 text-gray-400 hover:text-white disabled:opacity-30 rounded hover:bg-white/5 transition"
              title="Redo (Ctrl+Y / Ctrl+Shift+Z)"
            >
              <Redo2 className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Add Pass */}
          <button
            onClick={() => setShowPassModal(true)}
            className="px-2.5 py-1.5 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shadow-sm"
            title="Run AI Separation Pass (Tiger, Roformer, Demucs, Spleeter)"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Add Pass</span>
          </button>

          {/* Import Voiceover */}
          <button
            onClick={() => setShowImportModal(true)}
            className="px-2.5 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shadow-sm"
            title="Import External Translated Voiceover or Foley Track"
          >
            <Mic className="w-3.5 h-3.5 text-emerald-400" />
            <span>Import Voice</span>
          </button>

          {/* Save Project */}
          <button
            onClick={saveProjectManual}
            className="p-1.5 bg-[#11192e] hover:bg-gray-800 text-gray-300 hover:text-white border border-gray-700/80 rounded-lg transition"
            title="Save Project (Auto-saves on edits)"
          >
            <Save className="w-3.5 h-3.5" />
          </button>

          {/* Export Audio Mix */}
          <button
            onClick={handleExportMix}
            disabled={isRendering}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition shadow-md shadow-blue-500/20"
            title="Render Master WAV & AAC Mixdown"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{isRendering ? renderProgress || "Rendering..." : "Export Mix"}</span>
          </button>

          {/* Remux Video */}
          {activeProject.video_file && (
            <button
              onClick={handleRemuxVideo}
              disabled={isRendering}
              className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition shadow-md shadow-purple-500/20"
              title="Remux Video with Clean Audio Mix"
            >
              <Video className="w-3.5 h-3.5" />
              <span>Remux Video</span>
            </button>
          )}
        </div>
      )}
    </header>
  );
}
