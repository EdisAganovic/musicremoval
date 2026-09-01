import React, { useState, useEffect, useRef, useCallback, memo } from "react";
import axios from "axios";
import { BACKEND_URL } from "../config";
import { snapToGrid } from "./audiostudio/utils/audioMath";
import { useProjectHistory } from "./audiostudio/hooks/useProjectHistory";
import { useAudioEngine } from "./audiostudio/hooks/useAudioEngine";

// Sub-components & Modals
import { DAWHeader } from "./audiostudio/components/DAWHeader";
import { DAWTransport } from "./audiostudio/components/DAWTransport";
import { VideoPlayerPanel } from "./audiostudio/components/VideoPlayerPanel";
import { TimelineRuler } from "./audiostudio/components/TimelineRuler";
import { TrackControls } from "./audiostudio/components/TrackControls";
import { TrackWaveform } from "./audiostudio/components/TrackWaveform";
import { MinimapScrollbar } from "./audiostudio/components/MinimapScrollbar";
import { CreateProjectModal } from "./audiostudio/modals/CreateProjectModal";
import { SeparationPassModal } from "./audiostudio/modals/SeparationPassModal";
import { ImportTrackModal } from "./audiostudio/modals/ImportTrackModal";
import { ExportPreviewModal } from "./audiostudio/modals/ExportPreviewModal";

function AudioStudioTab({ isActive = true }) {
  // -------------------------------------------------------------
  // STATE MANAGEMENT
  // -------------------------------------------------------------
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [loading, setLoading] = useState(false);
  const [_error, setError] = useState(null);
  const [notificationMsg, setNotificationMsg] = useState(null);

  // Modals State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProjName, setNewProjName] = useState("New Cartoon Audio Project");
  const [newProjFile, setNewProjFile] = useState(null);
  const [libraryFiles, setLibraryFiles] = useState([]);
  const [selectedLibPath, setSelectedLibPath] = useState("");
  const [createDuration, setCreateDuration] = useState("");

  const [showPassModal, setShowPassModal] = useState(false);
  const [passName, setPassName] = useState("TIGER SFX & Dialogue Focus");
  const [passModel, setPassModel] = useState("tiger");
  const [passRoformerModel, setPassRoformerModel] = useState("mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt");
  const [passTigerTarget, setPassTigerTarget] = useState("dialogue_sfx");
  const [passTigerOverlap, setPassTigerOverlap] = useState(50);
  const [passDemucsStems, setPassDemucsStems] = useState(4);
  const [passSpleeterStems, setPassSpleeterStems] = useState(2);
  const [passRunning, setPassRunning] = useState(false);

  const [showImportModal, setShowImportModal] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importTrackName, setImportTrackName] = useState("🎙️ Translated Voiceover / Dub");

  const [isRendering, setIsRendering] = useState(false);
  const [renderProgress, setRenderProgress] = useState("");
  const [showExportPreviewModal, setShowExportPreviewModal] = useState(false);
  const [exportPreviewData, setExportPreviewData] = useState(null);

  // DAW Tools, Zoom, Video Panel State
  const [activeTool, setActiveTool] = useState("select");
  const [hoverTime, setHoverTime] = useState(null);
  const [selectedCut, setSelectedCut] = useState(null);
  const [snapGrid, setSnapGrid] = useState(0);
  const [dragSelection, setDragSelection] = useState(null);
  const [fadeInDurationMs, setFadeInDurationMs] = useState(100);
  const [fadeOutDurationMs, setFadeOutDurationMs] = useState(100);
  const [zoomLevel, setZoomLevel] = useState(1.0);
  const [isLooping, setIsLooping] = useState(false);
  const [videoExpanded, setVideoExpanded] = useState(true);
  const [videoWidth, setVideoWidth] = useState(380);

  // Inline Track Editing
  const [editingTrackId, setEditingTrackId] = useState(null);
  const [editingName, setEditingName] = useState("");

  // Refs
  const videoRef = useRef(null);
  const timelineContainerRef = useRef(null);
  const timelineRulerRef = useRef(null);
  const isLoopingRef = useRef(isLooping);
  isLoopingRef.current = isLooping;

  const notifyTimerRef = useRef(null);
  const pendingSaveRef = useRef(null);
  const saveTimerRef = useRef(null);
  const saveSeqRef = useRef(0);
  const onApplyHistoryRef = useRef(null);
  const historyHookRef = useRef(null);

  const showNotification = useCallback((msg) => {
    setNotificationMsg(msg);
    if (notifyTimerRef.current) clearTimeout(notifyTimerRef.current);
    notifyTimerRef.current = setTimeout(() => setNotificationMsg(null), 3000);
  }, []);

  const getProjectDuration = useCallback(() => {
    return activeProject?.duration || 30;
  }, [activeProject]);

  // -------------------------------------------------------------
  // AUDIO ENGINE & HISTORY HOOKS (Strict Top-Level Declaration)
  // -------------------------------------------------------------
  const {
    isPlaying,
    currentTime,
    duration,
    masterVolume,
    setMasterVolume,
    trackPeakData,
    vuLevelsRef,
    pauseOffsetRef,
    isPlayingRef,
    populateTrackPeaks,
    loadTrackAudio,
    syncWebAudioGains,
    startPlayback,
    pausePlayback,
    stopPlayback,
    seekTo,
    setTrackPan
  } = useAudioEngine({ videoRef, isLoopingRef, getProjectDuration });

  const historyHook = useProjectHistory({
    onApplyHistory: (tracks) => onApplyHistoryRef.current?.(tracks),
    onNotify: showNotification
  });
  historyHookRef.current = historyHook;

  // Update tracks with auto-save & history dispatch
  const updateProjectTracks = useCallback((newTracks, options = {}) => {
    setActiveProject(prev => {
      if (!prev) return prev;
      const updated = { ...prev, tracks: newTracks };

      // Push history unless from history undo/redo
      if (!options.fromHistory && historyHookRef.current) {
        historyHookRef.current.pushHistory(newTracks);
      }

      // Debounce auto-save
      pendingSaveRef.current = newTracks;
      saveSeqRef.current += 1;
      const seq = saveSeqRef.current;
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);

      saveTimerRef.current = setTimeout(async () => {
        if (seq !== saveSeqRef.current) return;
        try {
          await axios.put(`${BACKEND_URL}/api/project/${prev.id}/tracks`, {
            tracks: pendingSaveRef.current
          });
        } catch (_err) {}
      }, options.immediate ? 0 : 400);

      return updated;
    });
  }, []);

  useEffect(() => {
    onApplyHistoryRef.current = (targetTracks) => {
      updateProjectTracks(targetTracks, { fromHistory: true, immediate: true });
      syncWebAudioGains(targetTracks);
    };
  }, [updateProjectTracks, syncWebAudioGains]);

  // -------------------------------------------------------------
  // FETCH PROJECTS & MEDIA LIBRARY
  // -------------------------------------------------------------
  const handleSelectProject = useCallback(async (projId) => {
    stopPlayback();
    setLoading(true);
    try {
      const res = await axios.get(`${BACKEND_URL}/api/project/${projId}`);
      const proj = res.data.project;
      setActiveProject(proj);
      historyHook.resetHistory(proj.tracks || []);

      if (proj.tracks && proj.tracks.length > 0) {
        // Instantly populate waveform peaks for 0ms rendering
        populateTrackPeaks(proj.tracks);

        // Preload Web Audio buffers for playback in background
        for (const t of proj.tracks) {
          await loadTrackAudio(t);
        }
      }
      showNotification(`📁 Opened project: ${proj.name}`);
    } catch (_err) {
      setError("Failed to load project details");
    } finally {
      setLoading(false);
    }
  }, [stopPlayback, historyHook, populateTrackPeaks, loadTrackAudio, showNotification]);

  const fetchProjects = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/project`);
      const list = res.data.projects || [];
      setProjects(list);
      if (list.length > 0 && !activeProject) {
        handleSelectProject(list[0].id);
      }
    } catch (_err) {
      setError("Failed to fetch audio studio projects");
    }
  }, [activeProject, handleSelectProject]);

  const fetchLibrary = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/library`);
      const raw = Array.isArray(res.data) ? res.data : (res.data?.files || res.data?.library || []);
      const normalized = raw.map(item => {
        const primaryPath = (item.result_files && item.result_files.length > 0) ? item.result_files[0] : (item.file_path || item.filepath || "");
        const name = item.filename || item.title || (primaryPath ? primaryPath.split(/[/\\]/).pop() : "Media File");
        const ext = name.split('.').pop()?.toLowerCase() || '';
        const isVid = ['mp4', 'mkv', 'webm', 'mov', 'avi'].includes(ext);
        return {
          ...item,
          filepath: primaryPath,
          filename: name,
          type: isVid ? "Video" : "Audio",
          duration: item.metadata?.duration || item.duration || ""
        };
      }).filter(item => Boolean(item.filepath));
      setLibraryFiles(normalized);
    } catch (_err) {}
  }, []);

  useEffect(() => {
    fetchProjects();
    fetchLibrary();
  }, [fetchProjects, fetchLibrary]);

  // -------------------------------------------------------------
  // GLOBAL KEYBOARD SHORTCUTS
  // -------------------------------------------------------------
  useEffect(() => {
    const handleKeyDown = (e) => {
      const activeTag = document.activeElement?.tagName?.toLowerCase();
      if (activeTag === "input" || activeTag === "textarea" || activeTag === "select") return;

      // Spacebar: Play / Pause
      if (e.code === "Space" || e.key === " ") {
        e.preventDefault();
        if (isPlayingRef.current) {
          pausePlayback();
        } else {
          startPlayback(activeProject?.tracks || []);
        }
        return;
      }

      // Undo / Redo
      if ((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "Z")) {
        e.preventDefault();
        if (e.shiftKey) historyHook.handleRedo();
        else historyHook.handleUndo();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === "y" || e.key === "Y")) {
        e.preventDefault();
        historyHook.handleRedo();
        return;
      }

      // Tools
      if (e.key === "v" || e.key === "V") { e.preventDefault(); setActiveTool("select"); }
      if (e.key === "c" || e.key === "C") { e.preventDefault(); setActiveTool("cut"); }
      if (e.key === "z" || e.key === "Z") {
        if (!e.ctrlKey && !e.metaKey) { e.preventDefault(); applySilenceCut(); }
      }

      // Delete Cut or Selection (Del, Backspace, X)
      if (e.key === "Delete" || e.key === "Backspace" || e.key === "x" || e.key === "X") {
        if (dragSelection) {
          e.preventDefault();
          const selStart = Math.min(dragSelection.start, dragSelection.end);
          const selEnd = Math.max(dragSelection.start, dragSelection.end);
          applyDeleteCut(dragSelection.trackId, selStart, selEnd);
        } else if (selectedCut) {
          e.preventDefault();
          removeCut(selectedCut.trackId, selectedCut.cutId);
        }
      }

      // Escape
      if (e.key === "Escape") {
        setDragSelection(null);
        setSelectedCut(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  // -------------------------------------------------------------
  // CUT & SELECTION ACTIONS
  // -------------------------------------------------------------
  const applySilenceCut = useCallback(() => {
    if (!dragSelection || !activeProject) return;
    const start = Math.min(dragSelection.start, dragSelection.end);
    const end = Math.max(dragSelection.start, dragSelection.end);
    if (end - start < 0.05) { setDragSelection(null); return; }

    const newCut = {
      id: `cut_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      start,
      end,
      fade_in_ms: fadeInDurationMs,
      fade_out_ms: fadeOutDurationMs,
      cut_type: "silence",
      deleted: false
    };

    const updatedTracks = activeProject.tracks.map(t => {
      if (t.id !== dragSelection.trackId) return t;
      return { ...t, cuts: [...(t.cuts || []), newCut] };
    });

    updateProjectTracks(updatedTracks);
    syncWebAudioGains(updatedTracks);
    showNotification(`🔇 Applied Silence Cut (${(end - start).toFixed(2)}s)`);
    setDragSelection(null);
  }, [dragSelection, activeProject, fadeInDurationMs, fadeOutDurationMs, updateProjectTracks, syncWebAudioGains, showNotification]);

  const applyDeleteCut = useCallback((trackId, start, end) => {
    if (!activeProject || end - start < 0.05) return;
    const newCut = {
      id: `cut_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      start,
      end,
      fade_in_ms: fadeInDurationMs,
      fade_out_ms: fadeOutDurationMs,
      cut_type: "delete",
      deleted: true
    };

    const updatedTracks = activeProject.tracks.map(t => {
      if (t.id !== trackId) return t;
      return { ...t, cuts: [...(t.cuts || []), newCut] };
    });

    updateProjectTracks(updatedTracks);
    syncWebAudioGains(updatedTracks);
    showNotification(`✂️ Deleted Audio Segment (${(end - start).toFixed(2)}s)`);
    setDragSelection(null);
  }, [activeProject, fadeInDurationMs, fadeOutDurationMs, updateProjectTracks, syncWebAudioGains, showNotification]);

  const removeCut = useCallback((trackId, cutId) => {
    if (!activeProject) return;
    const updatedTracks = activeProject.tracks.map(t => {
      if (t.id !== trackId) return t;
      return { ...t, cuts: (t.cuts || []).filter(c => c.id !== cutId) };
    });

    updateProjectTracks(updatedTracks);
    syncWebAudioGains(updatedTracks);
    if (selectedCut?.cutId === cutId) setSelectedCut(null);
    showNotification("🗑️ Restored audio region");
  }, [activeProject, selectedCut, updateProjectTracks, syncWebAudioGains, showNotification]);

  // Handle Drag Selection on Track Waveform
  const handleTrackMouseDown = useCallback((e, trackId) => {
    if (e.target.closest('.group\\/cut') || e.target.closest('button') || e.target.closest('input')) return;
    const trackLane = e.currentTarget;
    const rect = trackLane.getBoundingClientRect();
    const projDur = getProjectDuration();
    const clickX = e.clientX - rect.left;
    const startTime = snapToGrid((clickX / rect.width) * projDur, snapGrid);

    if (activeTool === "cut") {
      seekTo(startTime, activeProject?.tracks);
      return;
    }

    setDragSelection({ trackId, start: startTime, end: startTime });

    const onMouseMove = (moveEvent) => {
      const currentX = moveEvent.clientX - rect.left;
      const curTime = snapToGrid(Math.max(0, Math.min(projDur, (currentX / rect.width) * projDur)), snapGrid);
      setDragSelection(prev => (prev ? { ...prev, end: curTime } : null));
    };

    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      setDragSelection(prev => {
        if (!prev) return null;
        if (Math.abs(prev.end - prev.start) < 0.05) {
          seekTo(prev.start, activeProject?.tracks);
          return null;
        }
        return prev;
      });
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, [activeTool, snapGrid, getProjectDuration, seekTo, activeProject]);

  // Drag Handles for Selection Box
  const handleSelectionFadeHandleMouseDown = useCallback((e, fadeType) => {
    e.stopPropagation();
    e.preventDefault();
    if (!dragSelection) return;
    const trackLane = e.currentTarget.closest('.waveform-lane');
    if (!trackLane) return;
    const rect = trackLane.getBoundingClientRect();
    const projDur = getProjectDuration();
    const selStart = Math.min(dragSelection.start, dragSelection.end);
    const selEnd = Math.max(dragSelection.start, dragSelection.end);
    const selDur = Math.max(0.1, selEnd - selStart);

    const onMouseMove = (moveEvent) => {
      const mouseX = moveEvent.clientX - rect.left;
      const mouseTime = Math.max(0, Math.min(projDur, (mouseX / rect.width) * projDur));
      if (fadeType === 'fade_out') {
        const deltaSec = Math.max(0.01, Math.min(selDur * 0.48, mouseTime - selStart));
        setFadeOutDurationMs(Math.round(deltaSec * 1000));
      } else {
        const deltaSec = Math.max(0.01, Math.min(selDur * 0.48, selEnd - mouseTime));
        setFadeInDurationMs(Math.round(deltaSec * 1000));
      }
    };

    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, [dragSelection, getProjectDuration]);

  const handleSelectionEdgeMouseDown = useCallback((e, edgeType) => {
    e.stopPropagation();
    e.preventDefault();
    if (!dragSelection) return;
    const trackLane = e.currentTarget.closest('.waveform-lane');
    if (!trackLane) return;
    const rect = trackLane.getBoundingClientRect();
    const projDur = getProjectDuration();

    const onMouseMove = (moveEvent) => {
      const mouseX = moveEvent.clientX - rect.left;
      const mouseTime = snapToGrid(Math.max(0, Math.min(projDur, (mouseX / rect.width) * projDur)), snapGrid);
      setDragSelection(prev => {
        if (!prev) return null;
        return edgeType === 'start' ? { ...prev, start: mouseTime } : { ...prev, end: mouseTime };
      });
    };

    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, [dragSelection, getProjectDuration, snapGrid]);

  // Drag Handles for Applied Cuts
  const handleFadeHandleMouseDown = useCallback((e, trackId, cutId, fadeType) => {
    e.stopPropagation();
    e.preventDefault();
    const track = activeProject?.tracks?.find(t => t.id === trackId);
    const cut = track?.cuts?.find(c => c.id === cutId);
    if (!cut) return;

    setSelectedCut({ trackId, cutId });
    const trackLane = e.currentTarget.closest('.waveform-lane');
    if (!trackLane) return;
    const rect = trackLane.getBoundingClientRect();
    const projDur = getProjectDuration();

    const onMouseMove = (moveEvent) => {
      const mouseX = moveEvent.clientX - rect.left;
      const mouseTime = Math.max(0, Math.min(projDur, (mouseX / rect.width) * projDur));
      const cutDur = Math.max(0.1, cut.end - cut.start);

      let newFadeMs;
      if (fadeType === 'fade_out') {
        const deltaSec = Math.max(0.01, Math.min(cutDur * 0.48, mouseTime - cut.start));
        newFadeMs = Math.round(deltaSec * 1000);
      } else {
        const deltaSec = Math.max(0.01, Math.min(cutDur * 0.48, cut.end - mouseTime));
        newFadeMs = Math.round(deltaSec * 1000);
      }

      setActiveProject(prev => {
        if (!prev) return prev;
        const updated = prev.tracks.map(t => {
          if (t.id !== trackId) return t;
          const newCuts = (t.cuts || []).map(c => {
            if (c.id !== cutId) return c;
            return { ...c, [fadeType === 'fade_out' ? 'fade_out_ms' : 'fade_in_ms']: newFadeMs };
          });
          return { ...t, cuts: newCuts };
        });
        return { ...prev, tracks: updated };
      });
    };

    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      setActiveProject(latest => {
        if (latest) {
          updateProjectTracks(latest.tracks);
          syncWebAudioGains(latest.tracks);
        }
        return latest;
      });
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, [activeProject, getProjectDuration, updateProjectTracks, syncWebAudioGains]);

  const handleCutResizeMouseDown = useCallback((e, trackId, cutId, handleType) => {
    e.stopPropagation();
    e.preventDefault();
    const track = activeProject?.tracks?.find(t => t.id === trackId);
    const cut = track?.cuts?.find(c => c.id === cutId);
    if (!cut) return;

    setSelectedCut({ trackId, cutId });
    const trackLane = e.currentTarget.closest('.waveform-lane');
    if (!trackLane) return;
    const rect = trackLane.getBoundingClientRect();
    const projDur = getProjectDuration();

    const onMouseMove = (moveEvent) => {
      const mouseX = moveEvent.clientX - rect.left;
      const mouseTime = snapToGrid(Math.max(0, Math.min(projDur, (mouseX / rect.width) * projDur)), snapGrid);

      setActiveProject(prev => {
        if (!prev) return prev;
        const updated = prev.tracks.map(t => {
          if (t.id !== trackId) return t;
          const newCuts = (t.cuts || []).map(c => {
            if (c.id !== cutId) return c;
            let newStart = c.start;
            let newEnd = c.end;
            if (handleType === 'start') newStart = Math.min(mouseTime, c.end - 0.05);
            else newEnd = Math.max(mouseTime, c.start + 0.05);
            return { ...c, start: newStart, end: newEnd };
          });
          return { ...t, cuts: newCuts };
        });
        return { ...prev, tracks: updated };
      });
    };

    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      setActiveProject(latest => {
        if (latest) {
          updateProjectTracks(latest.tracks);
          syncWebAudioGains(latest.tracks);
        }
        return latest;
      });
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, [activeProject, getProjectDuration, snapGrid, updateProjectTracks, syncWebAudioGains]);

  // -------------------------------------------------------------
  // TRACK CONTROLS ACTIONS (Mute, Solo, Volume, Pan, Normalize, Bleed)
  // -------------------------------------------------------------
  const toggleMute = useCallback((trackId) => {
    if (!activeProject) return;
    const updated = activeProject.tracks.map(t => t.id === trackId ? { ...t, muted: !t.muted } : t);
    updateProjectTracks(updated);
    syncWebAudioGains(updated);
  }, [activeProject, updateProjectTracks, syncWebAudioGains]);

  const toggleSolo = useCallback((trackId) => {
    if (!activeProject) return;
    const updated = activeProject.tracks.map(t => t.id === trackId ? { ...t, solo: !t.solo } : t);
    updateProjectTracks(updated);
    syncWebAudioGains(updated);
  }, [activeProject, updateProjectTracks, syncWebAudioGains]);

  const setTrackVolume = useCallback((trackId, volume) => {
    if (!activeProject) return;
    const updated = activeProject.tracks.map(t => t.id === trackId ? { ...t, volume } : t);
    updateProjectTracks(updated);
    syncWebAudioGains(updated);
  }, [activeProject, updateProjectTracks, syncWebAudioGains]);

  const handleNormalizeTrack = useCallback(async (trackId) => {
    if (!activeProject) return;
    try {
      showNotification("🎛️ Normalizing track to EBU R128 (-1.0 dB True-Peak)...");
      const res = await axios.post(`${BACKEND_URL}/api/project/${activeProject.id}/normalize-track`, { track_id: trackId });
      const updated = activeProject.tracks.map(t => t.id === trackId ? { ...t, file_path: res.data.file_path, audio_url: res.data.audio_url } : t);
      updateProjectTracks(updated);
      await loadTrackAudio(updated.find(t => t.id === trackId));
      showNotification("✅ Track volume normalized");
    } catch (_err) {
      showNotification("❌ Failed to normalize track");
    }
  }, [activeProject, showNotification, updateProjectTracks, loadTrackAudio]);

  const handleScanBleed = useCallback(async (trackId) => {
    if (!activeProject) return;
    try {
      showNotification("🔍 AI scanning residual music bleed in dialogue...");
      const res = await axios.post(`${BACKEND_URL}/api/project/${activeProject.id}/scan-bleed`, {
        track_id: trackId,
        min_confidence: 0.45
      });
      const regions = res.data.bleed_regions || [];
      const updated = activeProject.tracks.map(t => t.id === trackId ? { ...t, bleed_regions: regions } : t);
      updateProjectTracks(updated);
      showNotification(`✨ Found ${regions.length} music bleed regions`);
    } catch (_err) {
      showNotification("❌ Failed to scan bleed");
    }
  }, [activeProject, showNotification, updateProjectTracks]);

  const handleDeleteTrack = useCallback((trackId) => {
    if (!activeProject) return;
    const updated = activeProject.tracks.filter(t => t.id !== trackId);
    updateProjectTracks(updated);
    syncWebAudioGains(updated);
    showNotification("🗑️ Track deleted from project");
  }, [activeProject, updateProjectTracks, syncWebAudioGains, showNotification]);

  const handleRenameTrack = useCallback((trackId) => {
    if (!activeProject || !editingName.trim()) return;
    const updated = activeProject.tracks.map(t => t.id === trackId ? { ...t, name: editingName.trim() } : t);
    updateProjectTracks(updated);
    setEditingTrackId(null);
    setEditingName("");
  }, [activeProject, editingName, updateProjectTracks]);

  // -------------------------------------------------------------
  // PROJECT & PASS CREATION ACTIONS
  // -------------------------------------------------------------
  const handleDeleteProject = useCallback(async (projId, projName) => {
    if (!projId) return;
    const confirmName = projName || "this project";
    if (!window.confirm(`Are you sure you want to delete "${confirmName}"?\nAll audio stems and cuts in this project will be permanently removed.`)) {
      return;
    }
    setLoading(true);
    try {
      await axios.delete(`${BACKEND_URL}/api/project/${projId}`);
      showNotification(`🗑️ Deleted project "${confirmName}"`);

      const wasActive = activeProject?.id === projId;
      if (wasActive) {
        stopPlayback();
        setActiveProject(null);
      }

      // Re-fetch project list
      const res = await axios.get(`${BACKEND_URL}/api/project`);
      const list = res.data.projects || [];
      setProjects(list);
      if (list.length > 0) {
        if (wasActive || !activeProject) {
          handleSelectProject(list[0].id);
        }
      } else {
        setActiveProject(null);
      }
    } catch (_err) {
      setError("Failed to delete project");
    } finally {
      setLoading(false);
    }
  }, [activeProject, stopPlayback, handleSelectProject, showNotification]);

  const handleCreateProject = useCallback(async () => {
    if (!newProjFile && !selectedLibPath) return;
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("name", newProjName);
      if (newProjFile) formData.append("file", newProjFile);
      if (selectedLibPath) formData.append("library_path", selectedLibPath);
      if (createDuration) formData.append("duration", createDuration);

      const res = await axios.post(`${BACKEND_URL}/api/project/create`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      const newP = res.data.project;
      setShowCreateModal(false);
      await fetchProjects();
      await handleSelectProject(newP.id);
      showNotification("🎉 Created multi-pass audio project!");
    } catch (_err) {
      setError("Failed to create project");
    } finally {
      setLoading(false);
    }
  }, [newProjFile, selectedLibPath, newProjName, createDuration, fetchProjects, handleSelectProject, showNotification]);

  const handleRunPass = useCallback(async () => {
    if (!activeProject) return;
    setPassRunning(true);
    try {
      showNotification(`🚀 Launching AI Separation pass (${passModel.toUpperCase()})...`);
      const payload = {
        pass_name: passName,
        model: passModel,
        roformer_model: passRoformerModel,
        tiger_target: passTigerTarget,
        tiger_overlap: passTigerOverlap,
        demucs_stems: passDemucsStems,
        spleeter_stems: passSpleeterStems
      };
      const res = await axios.post(`${BACKEND_URL}/api/project/${activeProject.id}/run-pass`, payload);
      const newTracks = res.data.new_tracks || [];
      const updated = [...activeProject.tracks, ...newTracks];
      updateProjectTracks(updated);
      for (const t of newTracks) {
        await loadTrackAudio(t);
      }
      setShowPassModal(false);
      showNotification(`✅ Added ${newTracks.length} stems from ${passModel.toUpperCase()} pass!`);
    } catch (_err) {
      showNotification("❌ Failed to process separation pass");
    } finally {
      setPassRunning(false);
    }
  }, [activeProject, passName, passModel, passRoformerModel, passTigerTarget, passTigerOverlap, passDemucsStems, passSpleeterStems, showNotification, updateProjectTracks, loadTrackAudio]);

  const handleImportTrack = useCallback(async () => {
    if (!activeProject || !importFile) return;
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", importFile);
      formData.append("track_name", importTrackName);
      const res = await axios.post(`${BACKEND_URL}/api/project/${activeProject.id}/import-track`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      const newTrack = res.data.track;
      const updated = [...activeProject.tracks, newTrack];
      updateProjectTracks(updated);
      await loadTrackAudio(newTrack);
      setShowImportModal(false);
      setImportFile(null);
      showNotification("✅ Voiceover track imported!");
    } catch (_err) {
      showNotification("❌ Failed to import track");
    } finally {
      setLoading(false);
    }
  }, [activeProject, importFile, importTrackName, updateProjectTracks, loadTrackAudio, showNotification]);

  const handleExportMix = useCallback(async () => {
    if (!activeProject) return;
    setIsRendering(true);
    setRenderProgress("Rendering master mixdown WAV & AAC...");
    try {
      const res = await axios.post(`${BACKEND_URL}/api/project/${activeProject.id}/render-mix`);
      setExportPreviewData({
        type: "audio",
        title: "Master Audio Mixdown",
        url: res.data.mixdown_wav,
        aacUrl: res.data.mixdown_aac,
        filename: "master_mixdown.wav"
      });
      setShowExportPreviewModal(true);
      showNotification("🎧 Master Mixdown Rendered Successfully!");
    } catch (_err) {
      showNotification("❌ Mixdown render failed");
    } finally {
      setIsRendering(false);
      setRenderProgress("");
    }
  }, [activeProject, showNotification]);

  const handleRemuxVideo = useCallback(async () => {
    if (!activeProject) return;
    setIsRendering(true);
    setRenderProgress("Remuxing high-definition video with clean audio...");
    try {
      const res = await axios.post(`${BACKEND_URL}/api/project/${activeProject.id}/remux-video`);
      setExportPreviewData({
        type: "video",
        title: "Remuxed HD Video (Clean Audio)",
        url: res.data.video_url,
        filename: res.data.filename
      });
      setShowExportPreviewModal(true);
      showNotification("🎬 Video Remuxed Successfully!");
    } catch (_err) {
      showNotification("❌ Video remux failed");
    } finally {
      setIsRendering(false);
      setRenderProgress("");
    }
  }, [activeProject, showNotification]);

  const saveProjectManual = useCallback(async () => {
    if (!activeProject) return;
    try {
      await axios.put(`${BACKEND_URL}/api/project/${activeProject.id}/tracks`, {
        tracks: activeProject.tracks
      });
      showNotification("💾 Project saved successfully");
    } catch (_err) {
      showNotification("❌ Save failed");
    }
  }, [activeProject, showNotification]);

  // -------------------------------------------------------------
  // RENDER MAIN WORKSPACE
  // -------------------------------------------------------------
  return (
    <div className="flex flex-col h-full bg-[#050811] text-gray-100 overflow-hidden font-sans select-none">
      {/* Notifications Banner */}
      {notificationMsg && (
        <div className="absolute top-12 left-1/2 -translate-x-1/2 z-50 bg-[#0c162d]/95 border border-blue-500/80 text-blue-200 px-4 py-2 rounded-xl text-xs font-semibold shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-top-2 duration-150">
          {notificationMsg}
        </div>
      )}

      {/* Top DAW Header */}
      <DAWHeader
        projects={projects}
        activeProject={activeProject}
        handleSelectProject={handleSelectProject}
        handleDeleteProject={handleDeleteProject}
        setShowCreateModal={setShowCreateModal}
        canUndo={historyHook.canUndo}
        canRedo={historyHook.canRedo}
        handleUndo={historyHook.handleUndo}
        handleRedo={historyHook.handleRedo}
        setShowPassModal={setShowPassModal}
        setShowImportModal={setShowImportModal}
        saveProjectManual={saveProjectManual}
        isRendering={isRendering}
        renderProgress={renderProgress}
        handleExportMix={handleExportMix}
        handleRemuxVideo={handleRemuxVideo}
      />

      {/* Transport Controls Bar */}
      <DAWTransport
        isPlaying={isPlaying}
        startPlayback={startPlayback}
        pausePlayback={pausePlayback}
        stopPlayback={stopPlayback}
        currentTime={currentTime}
        duration={duration}
        isLooping={isLooping}
        setIsLooping={setIsLooping}
        zoomLevel={zoomLevel}
        setZoomLevel={setZoomLevel}
        snapGrid={snapGrid}
        setSnapGrid={setSnapGrid}
        activeTool={activeTool}
        setActiveTool={setActiveTool}
        masterVolume={masterVolume}
        setMasterVolume={setMasterVolume}
        vuLevelsRef={vuLevelsRef}
        activeTracks={activeProject?.tracks || []}
      />

      {/* Center Studio Workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Synchronized Video Player Panel */}
        <VideoPlayerPanel
          videoFile={activeProject?.video_file}
          videoRef={videoRef}
          videoExpanded={videoExpanded}
          setVideoExpanded={setVideoExpanded}
          videoWidth={videoWidth}
          setVideoWidth={setVideoWidth}
          isPlayingRef={isPlayingRef}
        />

        {/* Multi-Track Timeline */}
        <div ref={timelineContainerRef} className="flex-1 flex flex-col overflow-x-auto overflow-y-auto bg-[#040714]">
          {activeProject && (
            <div
              className="flex flex-col min-w-full"
              style={{ width: `${Math.max(100, zoomLevel * 100)}%` }}
            >
              {/* Timeline Header Row with Ruler */}
              <div className="flex border-b border-gray-800 shrink-0 sticky top-0 z-30 bg-[#080d1a]">
                <div className="w-56 bg-[#080d1a] border-r border-gray-800 px-3 py-1.5 flex items-center justify-between text-xs font-bold text-gray-400 shrink-0">
                  <span>STEM TRACKS ({activeProject.tracks?.length || 0})</span>
                </div>
                <div className="flex-1 overflow-hidden">
                  <TimelineRuler
                    duration={duration}
                    currentTime={currentTime}
                    zoomLevel={zoomLevel}
                    snapGrid={snapGrid}
                    hoverTime={hoverTime}
                    setHoverTime={setHoverTime}
                    seekTo={seekTo}
                    activeTracks={activeProject.tracks || []}
                    timelineRulerRef={timelineRulerRef}
                  />
                </div>
              </div>

              {/* Stem Track Lanes */}
              {activeProject.tracks && activeProject.tracks.length > 0 ? (
                activeProject.tracks.map((track) => (
                  <div key={track.id} className="flex border-b border-gray-800/80 min-h-[112px]">
                    {/* Left Track Controls */}
                    <TrackControls
                      track={track}
                      editingTrackId={editingTrackId}
                      setEditingTrackId={setEditingTrackId}
                      editingName={editingName}
                      setEditingName={setEditingName}
                      handleRenameTrack={handleRenameTrack}
                      toggleMute={toggleMute}
                      toggleSolo={toggleSolo}
                      setTrackVolume={setTrackVolume}
                      setTrackPan={setTrackPan}
                      handleNormalizeTrack={handleNormalizeTrack}
                      handleScanBleed={handleScanBleed}
                      handleDeleteTrack={handleDeleteTrack}
                    />

                    {/* Right Waveform Lane */}
                    <TrackWaveform
                      track={track}
                      duration={duration}
                      currentTime={currentTime}
                      peakData={trackPeakData.current[track.id]}
                      selectedCut={selectedCut}
                      setSelectedCut={setSelectedCut}
                      dragSelection={dragSelection}
                      setDragSelection={setDragSelection}
                      fadeOutDurationMs={fadeOutDurationMs}
                      fadeInDurationMs={fadeInDurationMs}
                      handleTrackMouseDown={handleTrackMouseDown}
                      handleSelectionFadeHandleMouseDown={handleSelectionFadeHandleMouseDown}
                      handleSelectionEdgeMouseDown={handleSelectionEdgeMouseDown}
                      handleFadeHandleMouseDown={handleFadeHandleMouseDown}
                      handleCutResizeMouseDown={handleCutResizeMouseDown}
                      removeCut={removeCut}
                      applyDeleteCut={applyDeleteCut}
                      applySilenceCut={applySilenceCut}
                    />
                  </div>
                ))
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center p-12 text-gray-500 space-y-3">
                  <p className="text-sm">No audio stem tracks in this project yet.</p>
                  <button
                    onClick={() => setShowPassModal(true)}
                    className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold rounded-xl shadow-lg transition"
                  >
                    🚀 Run First AI Separation Pass
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Bottom Minimap Scrollbar */}
      <MinimapScrollbar
        zoomLevel={zoomLevel}
        timelineContainerRef={timelineContainerRef}
      />

      {/* Modals */}
      <CreateProjectModal
        show={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        newProjName={newProjName}
        setNewProjName={setNewProjName}
        newProjFile={newProjFile}
        setNewProjFile={setNewProjFile}
        libraryFiles={libraryFiles}
        selectedLibPath={selectedLibPath}
        setSelectedLibPath={setSelectedLibPath}
        createDuration={createDuration}
        setCreateDuration={setCreateDuration}
        handleCreateProject={handleCreateProject}
        loading={loading}
      />

      <SeparationPassModal
        show={showPassModal}
        onClose={() => setShowPassModal(false)}
        passName={passName}
        setPassName={setPassName}
        passModel={passModel}
        setPassModel={setPassModel}
        passRoformerModel={passRoformerModel}
        setPassRoformerModel={setPassRoformerModel}
        passTigerTarget={passTigerTarget}
        setPassTigerTarget={setPassTigerTarget}
        passTigerOverlap={passTigerOverlap}
        setPassTigerOverlap={setPassTigerOverlap}
        passDemucsStems={passDemucsStems}
        setPassDemucsStems={setPassDemucsStems}
        passSpleeterStems={passSpleeterStems}
        setPassSpleeterStems={setPassSpleeterStems}
        handleRunPass={handleRunPass}
        passRunning={passRunning}
      />

      <ImportTrackModal
        show={showImportModal}
        onClose={() => setShowImportModal(false)}
        importFile={importFile}
        setImportFile={setImportFile}
        importTrackName={importTrackName}
        setImportTrackName={setImportTrackName}
        handleImportTrack={handleImportTrack}
        loading={loading}
      />

      <ExportPreviewModal
        show={showExportPreviewModal}
        onClose={() => setShowExportPreviewModal(false)}
        data={exportPreviewData}
      />
    </div>
  );
}

export default memo(AudioStudioTab);
