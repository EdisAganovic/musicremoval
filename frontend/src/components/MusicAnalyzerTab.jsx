/**
 * MUSICANALYZERTAB.JSX - Antigravity AI Audio & Speech Sharia Compliance Analyzer
 * 
 * ROLE: Analyzes audio/video files for background music detection, Sharia speech compliance,
 *       target keyword watchlists, and custom speech auditing using Antigravity Multimodal Audio intelligence.
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
  ShieldCheck,
  AlertTriangle,
  Scale,
  MessageSquareQuote,
  Edit3,
  RotateCcw,
  Tag,
  Hash
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from 'react-hot-toast';

const SHARIA_PRESET_PROMPT = `Analyze the spoken audio carefully against Islamic rulings (Sharia guidelines on speech) and ethical standards.
Identify and locate every spoken phrase, dialogue, or statement that falls into the following violation categories:
1. Profanity, Cursing & Vulgarity (Fahishah / Sabb): Curse words, swear words, obscene slang, sexually explicit speech, crude insults.
2. Blasphemy & Sacred Transgressions (Kufr / Shirk / Istihza'): Mocking God, prophets, sacred scriptures, religion, or endorsing idolatry/sorcery.
3. Slander, Defamation & Malicious Gossip (Qadhf / Gheebah / Nameemah): Backbiting, false moral accusations, spreading rumors to damage honor.
4. Vice & Forbidden Promotion (Haram / Fasād): Promoting, justifying, or glamorizing intoxicants/drugs/alcohol, gambling (Maysir), interest/usury (Riba), or illicit relations (Zina).
5. Deception, Perjury & Falsehood (Kidhb / Shahadat al-Zoor): Promoting scams, lying, or encouraging deceit.
6. Violence & Injustice: Inciting unlawful aggression or cruelty.`;

const PROFANITY_PRESET_PROMPT = `Analyze the spoken audio to detect all swear words, profanity, crude insults, sexual innuendo, and vulgar expressions.`;

const DEFAULT_SHARIA_KEYWORDS = "Jesus, Christ, Lord, swear, bet, casino, wine, alcohol, beer";

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
  const [analysisMode, setAnalysisMode] = useState("sharia_compliance"); // "sharia_compliance" | "music" | "custom_speech"
  const [customPrompt, setCustomPrompt] = useState(SHARIA_PRESET_PROMPT);
  const [keywords, setKeywords] = useState(DEFAULT_SHARIA_KEYWORDS);
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const [activeView, setActiveView] = useState("cues"); // "cues" | "srt"
  const fileInputRef = useRef(null);

  const { playTrack } = useAudioPlayer();

  // Switch default prompt on mode change
  const handleModeChange = (mode) => {
    setAnalysisMode(mode);
    if (mode === "sharia_compliance") {
      setCustomPrompt(SHARIA_PRESET_PROMPT);
      setKeywords(DEFAULT_SHARIA_KEYWORDS);
    } else if (mode === "custom_speech") {
      setCustomPrompt(PROFANITY_PRESET_PROMPT);
      setKeywords("");
    } else {
      setCustomPrompt("");
      setKeywords("");
    }
  };

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
            toast.success("Analysis complete!");
          } else if (data.status === "failed" || data.status === "error") {
            setError(data.error || "Analysis failed. Check logs.");
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
      const formData = new FormData();
      if (file) {
        formData.append("file", file);
      } else {
        formData.append("file_path", libraryFilePath);
      }
      formData.append("chunk_duration", chunkDuration);
      formData.append("analysis_mode", analysisMode);
      if (customPrompt && customPrompt.trim()) {
        formData.append("custom_prompt", customPrompt.trim());
      }
      if (keywords && keywords.trim()) {
        formData.append("keywords", keywords.trim());
      }

      response = await axios.post(`${BACKEND_URL}/api/music-analyzer/analyze`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });

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
      title: `${cue.category || cue.description} (${cue.start_srt})`,
      path: targetPath,
      type: 'cue',
      badge: analysisMode === 'sharia_compliance' ? 'SHARIA FLAG' : 'AUDIO CUE'
    });
    toast.success(`Playing from ${cue.start_srt}`);
  };

  const formatSecs = (sec) => {
    if (!sec && sec !== 0) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const getSeverityBadge = (severity) => {
    const s = (severity || "").toLowerCase();
    if (s === "critical") return "bg-red-500/20 text-red-400 border-red-500/40";
    if (s === "high") return "bg-orange-500/20 text-orange-400 border-orange-500/40";
    if (s === "medium") return "bg-amber-500/20 text-amber-300 border-amber-500/40";
    return "bg-blue-500/20 text-blue-300 border-blue-500/40";
  };

  // Keyword chip pills
  const parsedKeywordList = keywords
    ? keywords.split(',').map(k => k.trim()).filter(Boolean)
    : [];

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-emerald-950/40 via-dark-900 to-purple-950/40 p-6 rounded-2xl border border-emerald-500/20 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-4">
            <div className="p-3.5 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl shadow-lg shadow-emerald-500/20">
              <Scale className="w-7 h-7 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-wide">Antigravity AI Audio & Speech Analyzer</h2>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  Multimodal Sharia & Speech Auditing
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                AI speech analysis for Sharia rulings, specific keyword watchlists, or background music with SRT subtitle export.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 bg-dark-950/80 px-4 py-2.5 rounded-xl border border-white/5">
            <Clock className="w-4 h-4 text-emerald-400" />
            <div className="flex flex-col">
              <span className="text-[11px] font-bold text-gray-200">Segment Limit</span>
              <span className="text-[10px] text-gray-400">30 Min Precision Windows</span>
            </div>
          </div>
        </div>
      </div>

      {/* Analysis Mode Selector */}
      <div className="flex flex-wrap items-center justify-center gap-3 bg-dark-900/60 p-2.5 rounded-2xl border border-white/5 shadow-inner">
        {[
          { id: "sharia_compliance", label: "⚖️ Sharia Speech Compliance", desc: "Audits for cursing, blasphemy, slander, vice & forbidden speech" },
          { id: "music", label: "🎵 Music & BGM Detection", desc: "Pinpoints background music intervals and themes" },
          { id: "custom_speech", label: "✍️ Custom Speech Audit", desc: "Custom user guidelines or general profanity filtering" }
        ].map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => handleModeChange(m.id)}
            className={`px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all duration-200 border flex flex-col items-center ${
              analysisMode === m.id
                ? "bg-emerald-600/20 text-emerald-300 border-emerald-500/50 shadow-lg shadow-emerald-500/10 scale-105"
                : "bg-dark-800 text-gray-400 hover:text-white hover:bg-dark-700 border-transparent"
            }`}
          >
            <span>{m.label}</span>
          </button>
        ))}
      </div>

      {/* Specific Target Keywords Watchlist Input */}
      <div className="bg-dark-900/70 p-4 rounded-xl border border-white/10 shadow-md space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold text-emerald-300 uppercase tracking-wider flex items-center gap-1.5">
            <Tag className="w-3.5 h-3.5" />
            <span>Target Keywords Watchlist (Separated by commas)</span>
          </label>
          <span className="text-[10px] text-gray-400">
            {parsedKeywordList.length} keywords active
          </span>
        </div>

        <input
          type="text"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder="e.g. Jesus, Christ, swear, bet, casino, wine, beer..."
          className="w-full bg-dark-950 text-white text-xs font-mono px-3.5 py-2.5 rounded-xl border border-white/10 focus:border-emerald-500/50 outline-none transition-colors"
        />

        {parsedKeywordList.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {parsedKeywordList.map((kw, i) => (
              <span
                key={i}
                className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 flex items-center gap-1"
              >
                <Hash className="w-2.5 h-2.5 text-emerald-400" />
                {kw}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Custom Prompt & Rulebook Accordion */}
      <div className="bg-dark-900/70 p-4 rounded-xl border border-white/10 shadow-md">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Edit3 className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-bold text-white uppercase tracking-wider">
              {analysisMode === "sharia_compliance" ? "Sharia Ruling Criteria & Speech Guidelines" : "Custom Speech Prompt & Rules"}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setShowPromptEditor(!showPromptEditor)}
            className="text-xs text-emerald-400 hover:text-emerald-300 font-semibold underline"
          >
            {showPromptEditor ? "Hide Rule Editor" : "Customize Prompt & Criteria"}
          </button>
        </div>

        {showPromptEditor && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="mt-3 space-y-3"
          >
            <textarea
              rows={6}
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              placeholder="Enter your custom speech analysis criteria, prohibited words, Islamic rulings, or guidelines..."
              className="w-full bg-dark-950 text-gray-200 text-xs font-mono p-3 rounded-xl border border-white/10 focus:border-emerald-500/50 outline-none transition-colors"
            />
            <div className="flex items-center justify-between text-[11px] text-gray-400">
              <span>💡 You can add specific terms, slang, or specialized rulings to inspect.</span>
              <button
                type="button"
                onClick={() => setCustomPrompt(analysisMode === "sharia_compliance" ? SHARIA_PRESET_PROMPT : PROFANITY_PRESET_PROMPT)}
                className="flex items-center gap-1 text-gray-400 hover:text-white transition-colors"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Reset to Preset</span>
              </button>
            </div>
          </motion.div>
        )}
      </div>

      {/* Upload & Dropzone Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-300 ${
          dragging
            ? 'border-emerald-500 bg-emerald-500/10 scale-[1.01]'
            : 'border-white/10 hover:border-emerald-500/40 bg-dark-900/40'
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
          <div className="p-4 bg-emerald-600/20 rounded-full text-emerald-400">
            <UploadCloud className="w-8 h-8" />
          </div>
          <div>
            <p className="text-base font-bold text-white">
              {file ? file.name : libraryFilePath ? libraryFilePath.split(/[\\/]/).pop() : "Drop audio/video file here, or click to browse"}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Supports MP3, WAV, MP4, MKV, FLAC, AAC, M4A & all media files
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
                  chunkDuration === s ? 'bg-emerald-600 text-white' : 'text-gray-400 hover:text-white'
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
          className="w-full sm:w-auto px-6 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-bold rounded-xl transition-all shadow-lg shadow-emerald-500/20 flex items-center justify-center space-x-2"
        >
          {status === "processing" || status === "uploading" ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Analyzing Speech & Audio...</span>
            </>
          ) : (
            <>
              <ShieldCheck className="w-4 h-4" />
              <span>{analysisMode === "sharia_compliance" ? "Run Sharia Compliance Audit" : "Analyze Audio & Generate SRT"}</span>
            </>
          )}
        </button>
      </div>

      {/* Progress Card */}
      {(status === "processing" || status === "uploading") && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-dark-900/90 p-6 rounded-2xl border border-emerald-500/30 shadow-xl space-y-4"
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-bold text-white flex items-center gap-2">
              <Radio className="w-4 h-4 text-emerald-400 animate-pulse" />
              {currentStep || "Processing..."}
            </span>
            <span className="text-sm font-mono font-bold text-emerald-400">{progress}%</span>
          </div>

          <div className="w-full bg-dark-950 h-3 rounded-full overflow-hidden border border-white/5">
            <motion.div
              className="h-full bg-gradient-to-r from-emerald-600 to-teal-500"
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
              <span className="text-[11px] font-bold text-gray-400 uppercase">
                {analysisMode === "sharia_compliance" ? "Flagged Violations" : "Total Cues"}
              </span>
              <span className="text-2xl font-bold text-white mt-1">
                {analysisResult.summary?.segment_count || analysisResult.events?.length || 0}
              </span>
            </div>
            <div className="bg-dark-900/80 p-4 rounded-xl border border-white/5 flex flex-col">
              <span className="text-[11px] font-bold text-gray-400 uppercase">Flagged Duration</span>
              <span className="text-2xl font-bold text-emerald-400 mt-1">
                {formatSecs(analysisResult.summary?.total_flagged_seconds || analysisResult.summary?.total_music_seconds)}
              </span>
            </div>
            <div className="bg-dark-900/80 p-4 rounded-xl border border-white/5 flex flex-col">
              <span className="text-[11px] font-bold text-gray-400 uppercase">Violation Percentage</span>
              <span className="text-2xl font-bold text-amber-400 mt-1">
                {analysisResult.summary?.flagged_percentage || analysisResult.summary?.music_percentage || 0}%
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
                    ? "bg-emerald-600 text-white shadow-md shadow-emerald-500/20"
                    : "text-gray-400 hover:text-white bg-dark-900"
                }`}
              >
                {analysisMode === "sharia_compliance" ? "Sharia Audit Report" : "Interactive Cue Sheet"} ({analysisResult.events?.length || 0})
              </button>
              <button
                onClick={() => setActiveView("srt")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                  activeView === "srt"
                    ? "bg-emerald-600 text-white shadow-md shadow-emerald-500/20"
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
                <Copy className="w-3.5 h-3.5 text-emerald-400" />
                <span>Copy SRT</span>
              </button>
              <button
                onClick={handleDownloadSRT}
                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 shadow-md shadow-emerald-500/20"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download .srt</span>
              </button>
            </div>
          </div>

          {/* Interactive Cue & Audit List */}
          {activeView === "cues" && (
            <div className="space-y-3">
              {(!analysisResult.events || analysisResult.events.length === 0) ? (
                <div className="text-center py-12 text-gray-500 bg-dark-900/40 rounded-xl border border-white/5">
                  <CheckCircle className="w-9 h-9 mx-auto mb-2 text-emerald-400" />
                  <p className="text-sm font-semibold text-gray-200">
                    {analysisMode === "sharia_compliance" ? "Clean Audio - 100% Sharia Compliant" : "No flagged events detected"}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    No speech violations or non-compliant content were detected in this audio.
                  </p>
                </div>
              ) : (
                analysisResult.events.map((cue, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: -5 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.02 }}
                    className="p-4 bg-dark-900/80 hover:bg-dark-800/80 rounded-xl border border-white/5 transition-colors space-y-2"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center space-x-3">
                        <span className="w-7 h-7 rounded-lg bg-emerald-600/20 text-emerald-400 font-mono font-bold text-xs flex items-center justify-center border border-emerald-500/20">
                          #{idx + 1}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-white">
                            {cue.category || cue.description}
                          </span>
                          {cue.severity && (
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getSeverityBadge(cue.severity)}`}>
                              {cue.severity}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-semibold text-emerald-400 bg-emerald-950/60 px-2.5 py-1 rounded-lg border border-emerald-800/40">
                          {cue.start_srt} ➔ {cue.end_srt} ({cue.duration_seconds}s)
                        </span>
                        <button
                          onClick={() => handlePlayCue(cue)}
                          className="px-3 py-1 bg-emerald-600/20 hover:bg-emerald-600 text-emerald-300 hover:text-white rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 border border-emerald-500/30"
                        >
                          <PlayCircle className="w-4 h-4" />
                          <span>Play</span>
                        </button>
                      </div>
                    </div>

                    {cue.quote && (
                      <div className="bg-dark-950/60 p-2.5 rounded-lg border border-white/5 text-xs text-gray-300 flex items-start space-x-2">
                        <MessageSquareQuote className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                        <span className="italic">"{cue.quote}"</span>
                      </div>
                    )}

                    {cue.description && cue.description !== cue.category && (
                      <p className="text-xs text-gray-400 pl-1">
                        <strong className="text-gray-300">Ruling Note:</strong> {cue.description}
                      </p>
                    )}
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
