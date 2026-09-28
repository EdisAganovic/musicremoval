/**
 * MUSICANALYZERTAB.JSX - Antigravity AI Music Analyzer & SRT Generator
 * 
 * ROLE: Analyzes audio/video files to locate background music timestamps
 *       using Antigravity Multimodal Audio intelligence, outputting standard SRT files.
 */

import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { BACKEND_URL } from '../config';
import { useAudioPlayer } from '../contexts/AudioPlayerContext';
import {
  UploadCloud,
  CheckCircle,
  AlertCircle,
  PlayCircle,
  FolderOpen,
  Loader2,
  Copy,
  Download,
  Music,
  Clock,
  Sparkles,
  FileText,
  Radio,
  Sliders,
  Share2,
  ExternalLink,
  Scissors
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from 'react-hot-toast';

const MusicAnalyzerTab = ({ isActive = true, onSendToStudio }) => {
  const [file, setFile] = useState(null);
  const [libraryFilePath, setLibraryFilePath] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState(null);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [error, setError] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [chunkDuration, setChunkDuration] = useState(1800); // 30 minutes
  const [activeView, setActiveView] = useState("cues"); // "cues" | "srt"
  const fileInputRef = useRef(null);

  const { playTrack } = useAudioPlayer();

  // Polling effect for active analysis
  useEffect(() => {
    let interval;
    if (taskId && (status === "processing" || status === "pending" || status === "uploading")) {
      interval = setInterval(async () => {
        try {
          const response = await axios.get(`${BACKEND_URL}/api/music-analyzer/status/${taskId}`);
          const data = response.data;
          setProgress(data.progress || 0);
          setCurrentStep(data.current_step || "");
          setStatus(data.status);

          if (data.status === "completed") {
            setAnalysisResult(data.result || data);
            clearInterval(interval);
            toast.success("Music analysis complete!");
          } else if (data.status === "failed" || data.status === "error") {
            setError(data.error || "Music analysis failed. Check logs.");
            setStatus("error");
            clearInterval(interval);
          }
        } catch (err) {
          // Keep retrying unless persistent error
        }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [taskId, status]);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setLibraryFilePath(null);
      setError(null);
      setAnalysisResult(null);
      setStatus(null);
      setProgress(0);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setLibraryFilePath(null);
      setError(null);
      setAnalysisResult(null);
      setStatus(null);
      setProgress(0);
    }
  };

  const handleStartAnalysis = async () => {
    if (!file && !libraryFilePath) {
      toast.error("Please select an audio or video file first");
      return;
    }

    setError(null);
    setStatus("uploading");
    setProgress(5);
    setCurrentStep("Preparing file for Antigravity AI...");

    try {
      let response;
      if (file) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("chunk_duration", chunkDuration);
        response = await axios.post(`${BACKEND_URL}/api/music-analyzer/analyze`, formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });
      } else {
        const formData = new FormData();
        formData.append("file_path", libraryFilePath);
        formData.append("chunk_duration", chunkDuration);
        response = await axios.post(`${BACKEND_URL}/api/music-analyzer/analyze`, formData);
      }

      setTaskId(response.data.task_id);
      setStatus("processing");
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to start analysis");
      setStatus("error");
    }
  };

  const handleCopySRT = () => {
    if (!analysisResult?.srt_content) return;
    navigator.clipboard.writeText(analysisResult.srt_content);
    toast.success("SRT subtitle copied to clipboard!");
  };

  const handleDownloadSRT = () => {
    if (!taskId) return;
    window.open(`${BACKEND_URL}/api/music-analyzer/download-srt/${taskId}`, '_blank');
  };

  const handlePlayCue = (cue) => {
    const targetPath = file?.path || libraryFilePath || analysisResult?.summary?.file_name;
    if (!targetPath) return;
    
    playTrack({
      url: `${BACKEND_URL}/api/media/stream?path=${encodeURIComponent(targetPath)}`,
      title: `${cue.description} (${cue.start_srt})`,
      path: targetPath,
      type: 'music-cue',
      badge: 'MUSIC CUE'
    });
    toast.success(`Playing from ${cue.start_srt}`);
  };

  const formatSecs = (sec) => {
    if (!sec && sec !== 0) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-purple-900/40 via-dark-900 to-primary-900/40 p-6 rounded-2xl border border-purple-500/20 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-4">
            <div className="p-3.5 bg-gradient-to-br from-purple-600 to-primary-600 rounded-xl shadow-lg shadow-purple-500/20">
              <Sparkles className="w-7 h-7 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-wide">Antigravity Music Analyzer</h2>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                  Multimodal AI
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                Pinpoints where background music and soundtrack themes appear, and exports standard SRT subtitle cue sheets.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 bg-dark-950/80 px-4 py-2.5 rounded-xl border border-white/5">
            <Clock className="w-4 h-4 text-purple-400" />
            <div className="flex flex-col">
              <span className="text-[11px] font-bold text-gray-200">Segment Limit</span>
              <span className="text-[10px] text-gray-400">30 Min Optimum Precision</span>
            </div>
          </div>
        </div>
      </div>

      {/* Upload & Dropzone Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-300 ${
          dragging
            ? 'border-purple-500 bg-purple-500/10 scale-[1.01]'
            : 'border-white/10 hover:border-purple-500/40 bg-dark-900/40'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*,video/*"
          onChange={handleFileChange}
          className="hidden"
        />

        <div className="flex flex-col items-center justify-center space-y-3">
          <div className="p-4 bg-purple-600/20 rounded-full text-purple-400">
            <UploadCloud className="w-8 h-8" />
          </div>
          <div>
            <p className="text-base font-bold text-white">
              {file ? file.name : libraryFilePath ? libraryFilePath.split(/[\\/]/).pop() : "Drop audio/video file here, or click to browse"}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Supports MP3, WAV, MP4, MKV, FLAC, AAC, M4A & all media formats
            </p>
          </div>
        </div>
      </div>

      {/* Action Button & Configuration */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-dark-900/60 p-4 rounded-xl border border-white/5">
        <div className="flex items-center space-x-3 text-xs text-gray-300">
          <span className="font-semibold text-gray-400">Chunk Split Window:</span>
          <div className="flex items-center gap-1.5 bg-dark-950 p-1 rounded-lg border border-white/5">
            {[900, 1800].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setChunkDuration(s)}
                className={`px-2.5 py-1 rounded text-xs font-bold transition-all ${
                  chunkDuration === s ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                {s === 1800 ? "30 min (Optimal)" : "15 min (Micro)"}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={handleStartAnalysis}
          disabled={(!file && !libraryFilePath) || status === "processing" || status === "uploading"}
          className="w-full sm:w-auto px-6 py-3 bg-gradient-to-r from-purple-600 to-primary-600 hover:from-purple-500 hover:to-primary-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-bold rounded-xl transition-all shadow-lg shadow-purple-500/20 flex items-center justify-center space-x-2"
        >
          {status === "processing" || status === "uploading" ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Analyzing Music...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>Analyze Music & Generate SRT</span>
            </>
          )}
        </button>
      </div>

      {/* Progress Card */}
      {(status === "processing" || status === "uploading") && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-dark-900/90 p-6 rounded-2xl border border-purple-500/30 shadow-xl space-y-4"
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-bold text-white flex items-center gap-2">
              <Radio className="w-4 h-4 text-purple-400 animate-pulse" />
              {currentStep || "Processing..."}
            </span>
            <span className="text-sm font-mono font-bold text-purple-400">{progress}%</span>
          </div>

          <div className="w-full bg-dark-950 h-3 rounded-full overflow-hidden border border-white/5">
            <motion.div
              className="h-full bg-gradient-to-r from-purple-600 to-primary-500"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </motion.div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-red-950/40 border border-red-500/40 rounded-xl text-red-200 text-xs flex items-center space-x-2">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Results Dashboard */}
      {analysisResult && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-dark-900/80 p-4 rounded-xl border border-white/5 flex flex-col">
              <span className="text-[11px] font-bold text-gray-400 uppercase">Music Segments</span>
              <span className="text-2xl font-bold text-white mt-1">
                {analysisResult.summary?.segment_count || analysisResult.events?.length || 0}
              </span>
            </div>
            <div className="bg-dark-900/80 p-4 rounded-xl border border-white/5 flex flex-col">
              <span className="text-[11px] font-bold text-gray-400 uppercase">Total Music Duration</span>
              <span className="text-2xl font-bold text-purple-400 mt-1">
                {formatSecs(analysisResult.summary?.total_music_seconds)}
              </span>
            </div>
            <div className="bg-dark-900/80 p-4 rounded-xl border border-white/5 flex flex-col">
              <span className="text-[11px] font-bold text-gray-400 uppercase">Music Percentage</span>
              <span className="text-2xl font-bold text-emerald-400 mt-1">
                {analysisResult.summary?.music_percentage || 0}%
              </span>
            </div>
            <div className="bg-dark-900/80 p-4 rounded-xl border border-white/5 flex flex-col">
              <span className="text-[11px] font-bold text-gray-400 uppercase">File Duration</span>
              <span className="text-2xl font-bold text-gray-200 mt-1">
                {formatSecs(analysisResult.summary?.total_duration_seconds)}
              </span>
            </div>
          </div>

          {/* View Mode Tabs & Actions */}
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setActiveView("cues")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                  activeView === "cues"
                    ? "bg-purple-600 text-white shadow-md shadow-purple-500/20"
                    : "text-gray-400 hover:text-white bg-dark-900"
                }`}
              >
                Interactive Cue Sheet ({analysisResult.events?.length || 0})
              </button>
              <button
                onClick={() => setActiveView("srt")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                  activeView === "srt"
                    ? "bg-purple-600 text-white shadow-md shadow-purple-500/20"
                    : "text-gray-400 hover:text-white bg-dark-900"
                }`}
              >
                Raw SRT Subtitles
              </button>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={handleCopySRT}
                className="px-3 py-1.5 bg-dark-800 hover:bg-dark-700 text-gray-200 rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 border border-white/10"
              >
                <Copy className="w-3.5 h-3.5 text-purple-400" />
                <span>Copy SRT</span>
              </button>
              <button
                onClick={handleDownloadSRT}
                className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 shadow-md shadow-purple-500/20"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download .srt</span>
              </button>
            </div>
          </div>

          {/* Interactive Cue List */}
          {activeView === "cues" && (
            <div className="space-y-2.5">
              {(!analysisResult.events || analysisResult.events.length === 0) ? (
                <div className="text-center py-12 text-gray-500 bg-dark-900/40 rounded-xl border border-white/5">
                  <Music className="w-8 h-8 mx-auto mb-2 opacity-40 text-purple-400" />
                  <p className="text-sm font-semibold text-gray-300">No background music detected</p>
                  <p className="text-xs text-gray-500 mt-1">This file appears to contain clean speech or ambient sound effects.</p>
                </div>
              ) : (
                analysisResult.events.map((cue, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: -5 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.03 }}
                    className="flex items-center justify-between p-3.5 bg-dark-900/80 hover:bg-dark-800/80 rounded-xl border border-white/5 transition-colors group"
                  >
                    <div className="flex items-center space-x-3.5">
                      <span className="w-7 h-7 rounded-lg bg-purple-600/20 text-purple-400 font-mono font-bold text-xs flex items-center justify-center border border-purple-500/20">
                        #{idx + 1}
                      </span>
                      <div className="flex flex-col">
                        <span className="text-sm font-bold text-gray-100 group-hover:text-purple-300 transition-colors">
                          {cue.description}
                        </span>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[11px] font-mono font-semibold text-purple-400 bg-purple-950/60 px-2 py-0.5 rounded border border-purple-800/40">
                            {cue.start_srt} ➔ {cue.end_srt}
                          </span>
                          <span className="text-[10px] text-gray-500">
                            ({cue.duration_seconds}s)
                          </span>
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => handlePlayCue(cue)}
                      className="px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600 text-purple-300 hover:text-white rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 border border-purple-500/30"
                    >
                      <PlayCircle className="w-4 h-4" />
                      <span>Play Cue</span>
                    </button>
                  </motion.div>
                ))
              )}
            </div>
          )}

          {/* Raw SRT View */}
          {activeView === "srt" && (
            <div className="bg-dark-950 p-4 rounded-xl border border-white/10 font-mono text-xs text-gray-300 overflow-x-auto max-h-96">
              <pre className="whitespace-pre-wrap">{analysisResult.srt_content || "No SRT generated."}</pre>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
};

export default MusicAnalyzerTab;
