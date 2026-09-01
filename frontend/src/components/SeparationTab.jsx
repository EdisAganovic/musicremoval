/**
 * SEPARATIONTAB.JSX - Vocal Separation Interface
 * 
 * ROLE: Main UI for uploading files and processing vocal separation
 * 
 * MODES:
 *   - single: Upload/drag-drop single file for processing
 *   - folder: Batch process entire folder of media files
 * 
 * FEATURES:
 *   - Drag & drop file upload with animation
 *   - Model selection (Spleeter, Demucs, Both)
 *   - Folder path input with batch processing
 *   - File selection/deselection for batch
 *   - Real-time progress polling (1s interval)
 *   - Batch progress polling (2s interval)
 *   - Metadata display (duration, resolution, codec)
 *   - Result file preview with open/play actions
 * 
 * STATE:
 *   - file: Selected file object
 *   - libraryFilePath: Pre-loaded file from Library tab
 *   - folderPath: Folder path for batch processing
 *   - queueId/batchId: Backend queue/batch identifiers
 *   - batchFiles: Array of files in batch with status
 *   - taskId: Current processing task ID
 *   - status: 'idle' | 'uploading' | 'processing' | 'completed' | 'error'
 *   - progress: 0-100 progress percentage
 *   - currentStep: Current processing step description
 *   - model: 'spleeter' | 'demucs' | 'both'
 *   - processingMode: 'single' | 'folder'
 * 
 * API ENDPOINTS:
 *   - POST /api/separate - Upload file for separation
 *   - POST /api/separate-file - Process library file
 *   - POST /api/folder/scan - Scan folder for media files
 *   - POST /api/folder-queue/process - Start batch processing
 *   - POST /api/folder-queue/remove - Remove file from queue
 *   - GET /api/status/:taskId - Poll task progress
 *   - GET /api/batch-status/:batchId - Poll batch progress
 * 
 * PROPS:
 *   - libraryFile: Pre-selected file path from Library tab
 *   - onFileCleared: Callback when file is reset
 * 
 * DEPENDENCIES:
 *   - axios: HTTP client
 *   - framer-motion: Animations
 *   - lucide-react: Icons
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
  RefreshCw,
  FolderInput,
  FileAudio,
  Files,
  Trash2,
  Video,
  AudioLines,
  Scissors,
  Zap,
  Monitor,
  Play,
  Music,
  ExternalLink
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from 'react-hot-toast';

const SeparationTab = ({ libraryFile, initialFilePath, onFileCleared, onClearInitialFile, externalBatchId, initialBatchId, onExternalBatchConsumed, onClearBatchId }) => {
  const activeLibraryFile = libraryFile || initialFilePath;
  const activeBatchId = externalBatchId || initialBatchId;
  const [file, setFile] = useState(null);
  const [libraryFilePath, setLibraryFilePath] = useState(null);
  const [folderPath, setFolderPath] = useState(null);
  const [queueId, setQueueId] = useState(null);
  const [batchFiles, setBatchFiles] = useState([]);
  const [batchId, setBatchId] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState(null);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [error, setError] = useState(null);
  const [resultFiles, setResultFiles] = useState([]);
  const [model, setModel] = useState("both");
  const [roformerModel, setRoformerModel] = useState("mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt");
  const [tigerTarget, setTigerTarget] = useState("dialogue_sfx");
  const [tigerOverlap, setTigerOverlap] = useState(50);
  const [metadata, setMetadata] = useState(null);
  const [processingMode, setProcessingMode] = useState("single");
  const [isScanning, setIsScanning] = useState(false);
  const [processingTime, setProcessingTime] = useState(null);
  const [detailedTimings, setDetailedTimings] = useState(null);
  const [skipVideoEncoding, setSkipVideoEncoding] = useState(false);

  const TIGER_TARGETS = [
    { id: "dialogue_sfx", name: "🎬 Dialogue + SFX (No Music)", desc: "Clean dialogue with 100% cartoon Foley & sound effects" },
    { id: "dialogue", name: "🗣️ Dialogue Only", desc: "Pure speech isolation (ideal for voiceovers / dubbing)" },
    { id: "sfx", name: "💥 SFX / Foley Only", desc: "Pure cartoon sound effects, hits & atmosphere (no speech or music)" },
    { id: "music", name: "🎼 Music Only", desc: "Isolates only the background musical score" }
  ];

  const ROFORMER_MODELS = [
    {
      id: "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt",
      name: "🎬 Mel-Band Roformer Crowd & BGM",
      desc: "Best for Cartoons, Anime & Movies (Preserves Speech, Shouts & Foley)",
      badge: "Recommended"
    },
    {
      id: "mel_band_roformer_kim_ft_unwa.ckpt",
      name: "🎤 Mel-Band Roformer Vocals (Kim)",
      desc: "Standard Song Vocal Extraction (Cleanest isolated vocals in modern music)",
      badge: "Kim FT"
    },
    {
      id: "model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt",
      name: "💎 Mel-Band Roformer Vocals (ViperX)",
      desc: "High-Fidelity Music Vocal Isolation (Minimal artifacts, rich high-end)",
      badge: "SDR 11.43"
    },
    {
      id: "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
      name: "⚡ BS-Roformer Vocals (ViperX)",
      desc: "Bit-Stream Roformer (Top-tier SDR benchmark score for clean vocals)",
      badge: "SDR 12.97"
    },
    {
      id: "melband_roformer_instvoc_duality_v1.ckpt",
      name: "🎥 Mel-Band Roformer InstVoc Duality (Kim)",
      desc: "Specialized Film Model (High SDR for Music vs SFX+Dialogue)",
      badge: "Film SFX HQ"
    },
    {
      id: "MDX23C-8KFFT-InstVoc_HQ.ckpt",
      name: "🎨 MDX23C InstVoc HQ",
      desc: "Gentle Cartoon Mode (Preserves Musical/Synth Sound Effects)",
      badge: "Cartoon SFX"
    },
    {
      id: "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt",
      name: "🎼 Mel-Band Roformer Karaoke",
      desc: "Heavy Score Stripper (Action Movies & Loud Soundtracks)",
      badge: "High SDR"
    },
    {
      id: "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
      name: "🏛️ Mel-Band Roformer De-Reverb",
      desc: "Studio Clean Dialogue (Strips Room Reverb & Hall Echo)",
      badge: "De-Echo"
    },
    {
      id: "denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt",
      name: "✨ Mel-Band Roformer Denoise & Clean",
      desc: "Removes Background Noise & Hiss while keeping Dialogue intact",
      badge: "Denoise"
    },
    {
      id: "mel_band_roformer_bleed_suppressor_v1.ckpt",
      name: "🧹 Mel-Band Roformer Bleed Suppressor",
      desc: "Cleans High-Frequency Bleed from Vintage / Noisy Audio",
      badge: "Clean Bleed"
    }
  ];
  const [superKeyframe, setSuperKeyframe] = useState(false);
  const [resolution, setResolution] = useState("1080p");
  const [previewMode, setPreviewMode] = useState(false);
  const [previewSeconds, setPreviewSeconds] = useState(30);
  const [instrumentalFile, setInstrumentalFile] = useState(null);
  const [exportInstrumental, setExportInstrumental] = useState(false);
  const [removeSilence, setRemoveSilence] = useState(false);

  // In-browser Audio Player
  const { playTrack, currentTrack, isPlaying } = useAudioPlayer();

  const isVideoOutput = Boolean(
    metadata?.is_video ||
    (resultFiles && resultFiles[0] && /\.(mp4|mkv|webm|mov|avi|ts|flv)$/i.test(resultFiles[0]))
  );

  const handlePlayVocalsInBrowser = () => {
    if (!resultFiles || !resultFiles[0]) return;
    const filePath = resultFiles[0];
    const fileName = filePath.split(/[\\/]/).pop();
    const isVideo = isVideoOutput;
    playTrack({
      url: `${BACKEND_URL}/api/media/stream?path=${encodeURIComponent(filePath)}`,
      title: fileName,
      path: filePath,
      type: isVideo ? 'video' : 'vocal',
      badge: isVideo ? 'NO-MUSIC VIDEO' : 'VOCALS'
    });
    toast.success(`Playing ${isVideo ? 'video' : 'vocals'} in browser: ${fileName}`);
  };

  const handlePlayInstrumentalInBrowser = () => {
    if (!instrumentalFile) return;
    const fileName = instrumentalFile.split(/[\\/]/).pop();
    playTrack({
      url: `${BACKEND_URL}/api/media/stream?path=${encodeURIComponent(instrumentalFile)}`,
      title: fileName,
      path: instrumentalFile,
      type: 'instrumental',
      badge: 'INSTRUMENTAL'
    });
    toast.success(`Playing instrumental in browser: ${fileName}`);
  };

  const fileInputRef = useRef(null);
  const batchListRef = useRef(null);


  // Auto-scroll to currently processing file in batch mode
  useEffect(() => {
    if (batchFiles.length > 0 && batchListRef.current && (status === "processing" || status === "pending")) {
      const processingIndex = batchFiles.findIndex(f => f.status === "processing");
      if (processingIndex !== -1) {
        const processingElement = batchListRef.current.children[processingIndex];
        if (processingElement) {
          processingElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    }
  }, [batchFiles, status]);

  // Handle library file pre-load
  useEffect(() => {
    if (activeLibraryFile) {
      setLibraryFilePath(activeLibraryFile);
      setFile({
        name: activeLibraryFile.split(/[\\/]/).pop() || 'Selected File',
        size: 0,
        path: activeLibraryFile
      });
      setStatus("idle");
      setProgress(0);
      setResultFiles([]);
      setError(null);
      onFileCleared?.();
      onClearInitialFile?.();
    }
  }, [activeLibraryFile]);

  // Handle an already-running batch handed off from Library's bulk "Separate Selected"
  // action: jump straight into folder/batch mode and let the existing batch-status
  // polling effect (keyed on batchId + processingMode) pick it up.
  useEffect(() => {
    if (activeBatchId) {
      setProcessingMode("folder");
      setQueueId(null);
      setBatchFiles([]);
      setError(null);
      setProgress(0);
      setStatus("processing");
      setBatchId(activeBatchId);
      onExternalBatchConsumed?.();
      onClearBatchId?.();
    }
    // `onExternalBatchConsumed`/`onClearBatchId` are inline callbacks that clear the
    // hand-off batch; they're consumed once when the batch arrives, so they're
    // intentionally excluded to avoid re-firing as parent re-renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeBatchId]);

  const handleReset = () => {
    setFile(null);
    setLibraryFilePath(null);
    if (onFileCleared) {
      onFileCleared();
    }
    setTaskId(null);
    setStatus(null);
    setProgress(0);
    setCurrentStep("");
    setError(null);
    setResultFiles([]);
    setMetadata(null);
    setSkipVideoEncoding(false);
    setInstrumentalFile(null);
    setRemoveSilence(false);
  };

  const handleCancelQueue = async () => {
    try {
      await axios.post(`${BACKEND_URL}/api/separation-queue/clear`);
      toast.success("Separation queue cleared");
    } catch (_) { }
    handleReset();
  };

  // Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Esc to clear inputs
      if (e.key === 'Escape' && status !== 'processing' && status !== 'pending') {
        handleReset();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
    // `handleReset` is recreated each render; including it would re-register the
    // keydown listener on every render. The handler only depends on `status`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  // Polling effect
  useEffect(() => {
    let interval;
    let consecutiveErrors = 0;
    const MAX_CONSECUTIVE_ERRORS = 10;

    if (taskId && (status === "processing" || status === "pending" || status === "uploading")) {
      interval = setInterval(async () => {
        try {
          const response = await axios.get(
            `${BACKEND_URL}/api/status/${taskId}`,
            { timeout: 300000 } // 5 minute timeout for long FFmpeg operations
          );
          const data = response.data;

          // Reset error counter on successful response
          consecutiveErrors = 0;

          setProgress(data.progress);
          setCurrentStep(data.currentStep || data.current_step);
          setStatus(data.status);

          if (data.metadata) {
            setMetadata(data.metadata);
          }

          if (data.status === "completed") {
            setResultFiles(data.result_files || data.resultFiles || []);
            setProcessingTime(data.processing_time || data.processingTime);
            setDetailedTimings(data.timings);
            setInstrumentalFile(data.instrumental_file || null);
            clearInterval(interval);
          } else if (data.status === "failed" || data.status === "error") {
            setError("Process failed: Check backend logs.");
            clearInterval(interval);
            setStatus("error");
          }
        } catch (err) {
          consecutiveErrors++;

          // Treat 404 as task completion only after several retries
          // (prevents race conditions during server reloads)
          if (err.response?.status === 404) {
            if (consecutiveErrors > 15) {
              setStatus("completed");
              setTaskId(null);
              clearInterval(interval);
            }
            return;
          }

          // Show error after 30 consecutive failures
          if (consecutiveErrors >= 30) {
            setError("Connection lost to backend. Refresh page to reconnect.");
            setStatus("error");
            clearInterval(interval);
          }
        }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [taskId, status]);

  // Batch polling effect
  useEffect(() => {
    let interval;
    let consecutiveErrors = 0;
    const MAX_CONSECUTIVE_ERRORS = 10;

    if (batchId && processingMode === "folder") {
      interval = setInterval(async () => {
        try {
          const response = await axios.get(
            `${BACKEND_URL}/api/batch-status/${batchId}`,
            { timeout: 300000 } // 5 minute timeout for long FFmpeg operations
          );
          const batch = response.data;

          // Reset error counter on successful response
          consecutiveErrors = 0;

          // Update batch files with latest status
          setBatchFiles(batch.files || []);
          const totalFiles = batch.total_files || 0;
          const processed = batch.processed || 0;
          setProgress(totalFiles > 0 ? Math.round((processed / totalFiles) * 100) : 0);

          // Update current step with progress
          const processingCount = batch.files.filter(f => f.status === "processing").length;
          const completedCount = batch.files.filter(f => f.status === "completed").length;
          const failedCount = batch.files.filter(f => f.status === "failed").length;

          if (processingCount > 0) {
            setCurrentStep(`Processing: ${completedCount + failedCount + 1} / ${batch.total_files} files...`);
          }

          if (batch.processed >= batch.total_files) {
            clearInterval(interval);
            if (batch.success > 0) {
              setStatus("completed");
              setCurrentStep(`Batch complete: ${batch.success} succeeded, ${batch.failed} failed`);
            } else {
              setStatus("error");
              setError("All files in batch failed to process");
            }
          }
        } catch (err) {
          consecutiveErrors++;

          // Show error after 3 consecutive failures
          if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
            setError("Connection lost to backend. Refresh page to reconnect.");
            setStatus("error");
            clearInterval(interval);
          }
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [batchId, processingMode]);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setLibraryFilePath(null);
      setError(null);
      setStatus("idle");
      setProgress(0);
      setResultFiles([]);
    }
  };

  const handleFolderScan = async () => {
    if (!folderPath) return;

    setProcessingMode("folder");
    setError(null);
    setBatchFiles([]);
    setQueueId(null);
    setStatus(null); // Reset status
    setBatchId(null); // Reset batch ID
    setIsScanning(true);

    // Scan folder using Python backend
    try {
      setIsScanning(true);
      const response = await axios.post(`${BACKEND_URL}/api/folder/scan`, {
        folder_path: folderPath
      });

      setQueueId(response.data.queue_id);
      setBatchFiles(response.data.files || []);

      if (response.data.files && response.data.files.length > 0) {
        // Files found
        if (batchListRef.current) {
          batchListRef.current.scrollTop = 0;
        }
      }
    } catch (err) {
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Failed to scan folder. Make sure it contains media files.");
      }
      setBatchFiles([]);
    } finally {
      setIsScanning(false);
    }
  };

  const handleRemoveFile = async (fileId) => {
    if (!queueId) return;

    try {
      const response = await axios.post(`${BACKEND_URL}/api/folder-queue/remove`, {
        queue_id: queueId,
        file_id: fileId
      });

      setBatchFiles(response.data.files || []);
    } catch (err) {
      // Silent fail
    }
  };

  const handleToggleFile = (fileId) => {
    setBatchFiles(prev => prev.map(f =>
      f.id === fileId ? { ...f, selected: !f.selected } : f
    ));
  };

  const handleStartBatchProcessing = async () => {
    if (!queueId) {
      setError("No queue ID - please scan folder first");
      return;
    }

    try {
      const selectedFiles = batchFiles.filter(f => f.selected).map(f => f.file_path);
      if (selectedFiles.length === 0) {
        // Assuming toast is available, otherwise use setError
        // toast.error("Please select at least one file");
        setError("Please select at least one file");
        return;
      }

      setStatus("processing");
      setProgress(0);
      const response = await axios.post(`${BACKEND_URL}/api/folder-queue/process`, {
        queue_id: queueId,
        selected_files: selectedFiles,
        model,
        roformer_model: roformerModel,
        tiger_target: tigerTarget,
        tiger_overlap: tigerOverlap,
        skip_video_encoding: skipVideoEncoding,
        super_keyframe: superKeyframe,
        resolution: resolution,
        export_instrumental: exportInstrumental,
        remove_silence: removeSilence
      });

      setBatchId(response.data.batch_id);
      setBatchFiles(response.data.files || []);
    } catch (err) {
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Failed to start batch processing");
      }
      setStatus("error");
    }
  };

  const handleUpload = async () => {
    if (!file && !libraryFilePath) return;

    try {
      if (libraryFilePath) {
        // Library file processing
        setCurrentStep("Starting separation...");
        setProgress(0);

        const response = await axios.post(`${BACKEND_URL}/api/separate-file`, {
          file_path: libraryFilePath,
          model,
          roformer_model: roformerModel,
          tiger_target: tigerTarget,
          tiger_overlap: tigerOverlap,
          skip_video_encoding: skipVideoEncoding,
          super_keyframe: superKeyframe,
          resolution: resolution,
          duration: previewMode ? previewSeconds : null,
          export_instrumental: exportInstrumental,
          remove_silence: removeSilence
        });
        setTaskId(response.data.task_id);
        setStatus("processing");
      } else {
        // Direct upload processing
        const formData = new FormData();
        formData.append("file", file);
        formData.append("model", model);
        formData.append("roformer_model", roformerModel);
        formData.append("tiger_target", tigerTarget);
        formData.append("tiger_overlap", tigerOverlap);
        formData.append("skip_video_encoding", skipVideoEncoding);
        formData.append("super_keyframe", superKeyframe);
        formData.append("resolution", resolution);
        formData.append("export_instrumental", exportInstrumental);
        formData.append("remove_silence", removeSilence);
        if (previewMode) {
          formData.append("duration", previewSeconds);
        }

        setStatus("uploading");
        setCurrentStep("Transferring file...");
        setProgress(0);

        const response = await axios.post(`${BACKEND_URL}/api/separate`, formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
          onUploadProgress: (progressEvent) => {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total,
            );
            if (percentCompleted < 100) {
              setProgress(percentCompleted);
            } else {
              setCurrentStep("Upload complete. Queuing task...");
            }
          },
        });
        setTaskId(response.data.task_id);
      }

      setStatus("processing");
    } catch (err) {
      console.error("Separation failed:", err);
      const errMsg = err.response?.data?.detail || "Failed to start processing. Check backend connection.";
      setError(errMsg);
      toast.error(errMsg);
      setStatus("error");
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
      setStatus("idle");
      setProgress(0);
      setResultFiles([]);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      {/* Processing Mode Selection */}
      <div className="flex justify-center space-x-4 mb-6">
        <button
          onClick={() => { setProcessingMode("single"); setBatchFiles([]); setBatchId(null); }}
          className={`px-6 py-3 rounded-xl text-sm font-bold transition-all duration-200 border flex items-center space-x-2 ${processingMode === "single"
            ? "bg-primary-600/20 text-primary-400 border-primary-500/50 shadow-lg shadow-primary-500/10"
            : "bg-dark-800 text-gray-400 hover:text-white hover:bg-dark-700 border-transparent"
            }`}
        >
          <UploadCloud className="w-4 h-4" />
          <span>Single File</span>
        </button>
        <button
          onClick={() => { setProcessingMode("folder"); setFile(null); }}
          className={`px-6 py-3 rounded-xl text-sm font-bold transition-all duration-200 border flex items-center space-x-2 ${processingMode === "folder"
            ? "bg-primary-600/20 text-primary-400 border-primary-500/50 shadow-lg shadow-primary-500/10"
            : "bg-dark-800 text-gray-400 hover:text-white hover:bg-dark-700 border-transparent"
            }`}
        >
          <FolderInput className="w-4 h-4" />
          <span>Process Folder</span>
        </button>
      </div>

      {/* Model Selection */}
      <div className="flex flex-wrap justify-center gap-2.5 mb-6">
        {[
          { id: "both", label: "Spleeter+Demucs" },
          { id: "roformer", label: "🎬 Roformer BGM" },
          { id: "tiger", label: "🐯 TIGER-DnR (3-Stem)" },
          { id: "demucs", label: "Demucs" },
          { id: "spleeter", label: "Spleeter" },
        ].map(({ id, label }) => (
          <button
            key={`model-${id}`}
            onClick={() => setModel(id)}
            className={`px-3.5 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all duration-200 border ${model === id
              ? "bg-primary-600/20 text-primary-400 border-primary-500/50 shadow-lg shadow-primary-500/10 scale-105"
              : "bg-dark-800 text-gray-400 hover:text-white hover:bg-dark-700 border-transparent"
              }`}
          >
            <span>{label}</span>
          </button>
        ))}
      </div>

      {/* Roformer Architecture Dropdown */}
      {model === "roformer" && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-gradient-to-r from-primary-950/40 via-dark-900 to-primary-950/40 p-4 rounded-xl border border-primary-500/30 shadow-lg mb-6 max-w-2xl mx-auto"
        >
          <div className="flex flex-col space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-primary-300 uppercase tracking-wider flex items-center gap-1.5">
                <Music className="w-3.5 h-3.5" />
                <span>Roformer BGM Neural Checkpoint</span>
              </label>
              <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                NVIDIA CUDA Accelerated
              </span>
            </div>

            <div className="relative">
              <select
                value={roformerModel}
                onChange={(e) => setRoformerModel(e.target.value)}
                style={{ backgroundColor: '#0f172a', color: '#f8fafc' }}
                className="w-full bg-[#0f172a] border border-primary-500/40 rounded-xl px-4 py-2.5 text-xs sm:text-sm font-medium text-white shadow-inner focus:outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 cursor-pointer appearance-none pr-10"
              >
                {ROFORMER_MODELS.map((item) => (
                  <option key={item.id} value={item.id} style={{ backgroundColor: '#0f172a', color: '#f8fafc' }} className="bg-[#0f172a] text-gray-100 py-2">
                    {item.name} [{item.badge}]
                  </option>
                ))}
              </select>
              <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-primary-400">
                <svg className="w-4 h-4 fill-current" viewBox="0 0 20 20">
                  <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
                </svg>
              </div>
            </div>

            <p className="text-xs text-gray-400 italic pt-1">
              💡 {ROFORMER_MODELS.find(m => m.id === roformerModel)?.desc}
            </p>
          </div>
        </motion.div>
      )}

      {/* TIGER-DnR Options Panel */}
      {model === "tiger" && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-gradient-to-r from-amber-950/40 via-dark-900 to-amber-950/40 p-4 rounded-xl border border-amber-500/30 shadow-lg mb-6 max-w-2xl mx-auto"
        >
          <div className="flex flex-col space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-1.5">
                <span>🐯 TIGER-DnR 3-Stem Extraction Engine</span>
              </label>
              <span className="text-[10px] font-semibold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                PyTorch CUDA Tensor Cores (FP16)
              </span>
            </div>

            {/* Target Stem Selector */}
            <div className="space-y-1">
              <span className="text-[11px] font-semibold text-gray-300 uppercase">Target Extraction Track:</span>
              <div className="relative">
                <select
                  value={tigerTarget}
                  onChange={(e) => setTigerTarget(e.target.value)}
                  style={{ backgroundColor: '#0f172a', color: '#f8fafc' }}
                  className="w-full bg-[#0f172a] border border-amber-500/40 rounded-xl px-4 py-2.5 text-xs sm:text-sm font-medium text-white shadow-inner focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400 cursor-pointer appearance-none pr-10"
                >
                  {TIGER_TARGETS.map((t) => (
                    <option key={t.id} value={t.id} style={{ backgroundColor: '#0f172a', color: '#f8fafc' }} className="bg-[#0f172a] text-gray-100 py-2">
                      {t.name}
                    </option>
                  ))}
                </select>
                <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none text-amber-400">
                  <svg className="w-4 h-4 fill-current" viewBox="0 0 20 20">
                    <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
                  </svg>
                </div>
              </div>
              <p className="text-xs text-gray-400 italic pt-0.5">
                💡 {TIGER_TARGETS.find(t => t.id === tigerTarget)?.desc}
              </p>
            </div>

            {/* Overlap & Quality Selector */}
            <div className="flex items-center justify-between pt-2 border-t border-white/5">
              <div className="flex flex-col">
                <span className="text-xs font-bold text-gray-200">Overlap Precision (Hann Window)</span>
                <span className="text-[10px] text-gray-400">
                  {tigerOverlap >= 75 ? "4-pass smooth crossfade (Best for classical & complex scores)" : "Standard 2-pass crossfade (Fast - 4.8x realtime)"}
                </span>
              </div>
              <div className="flex items-center gap-2 bg-dark-950 p-1 rounded-lg border border-white/5">
                <button
                  type="button"
                  onClick={() => setTigerOverlap(50)}
                  className={`px-2.5 py-1 rounded text-xs font-bold transition-colors ${tigerOverlap === 50 ? 'bg-amber-600 text-white' : 'text-gray-400 hover:text-white'}`}
                >
                  50% (Fast)
                </button>
                <button
                  type="button"
                  onClick={() => setTigerOverlap(75)}
                  className={`px-2.5 py-1 rounded text-xs font-bold transition-colors ${tigerOverlap === 75 ? 'bg-amber-600 text-white' : 'text-gray-400 hover:text-white'}`}
                >
                  75% (Ultra-HQ)
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* Options Grid (2 Columns) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl mx-auto mb-6 bg-dark-900/60 p-4 rounded-xl border border-white/5 shadow-inner">
        {/* Left Column */}
        <div className="space-y-4">
          {/* Skip Video Encoding Toggle */}
          <label className="flex items-center space-x-3 cursor-pointer group">
            <div className={`relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0 ${skipVideoEncoding ? 'bg-emerald-600' : 'bg-dark-700'}`}>
              <input
                type="checkbox"
                className="sr-only"
                checked={skipVideoEncoding}
                onChange={() => setSkipVideoEncoding(!skipVideoEncoding)}
              />
              <div className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform duration-300 ${skipVideoEncoding ? 'translate-x-5' : ''}`} />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold text-gray-200 group-hover:text-white transition-colors flex items-center gap-2">
                <Video className="w-4 h-4 text-emerald-400" />
                Skip Video Encoding
              </span>
              <span className="text-[10px] text-gray-500">Fast mode: uses original video stream</span>
            </div>
          </label>

          {/* Remove Silence Toggle */}
          <label className="flex items-center space-x-3 cursor-pointer group">
            <div className={`relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0 ${removeSilence ? 'bg-cyan-600' : 'bg-dark-700'}`}>
              <input
                type="checkbox"
                className="sr-only"
                checked={removeSilence}
                onChange={() => setRemoveSilence(!removeSilence)}
              />
              <div className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform duration-300 ${removeSilence ? 'translate-x-5' : ''}`} />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold text-gray-200 group-hover:text-white transition-colors flex items-center gap-2">
                <Scissors className="w-4 h-4 text-cyan-400" />
                Remove Silence (1s Padding)
              </span>
              <span className="text-[10px] text-gray-500">Cuts silence gaps with 1s padding</span>
            </div>
          </label>

        </div>

        {/* Right Column */}
        <div className="space-y-4">
          {/* Super Keyframe Toggle */}
          <label className="flex items-center space-x-3 cursor-pointer group">
            <div className={`relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0 ${superKeyframe ? 'bg-amber-500 shadow-lg shadow-amber-500/20' : 'bg-dark-700'}`}>
              <input
                type="checkbox"
                className="sr-only"
                checked={superKeyframe}
                onChange={() => setSuperKeyframe(!superKeyframe)}
              />
              <div className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform duration-300 ${superKeyframe ? 'translate-x-5' : ''}`} />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold text-gray-200 group-hover:text-white transition-colors flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-400" />
                Super keyframe
              </span>
              <span className="text-[10px] text-gray-500">Parallel dual-NVENC chunked encode</span>
            </div>
          </label>


          {/* Resolution Selector */}
          {!skipVideoEncoding && (
            <div className="flex items-center justify-between pt-0.5">
              <div className="flex flex-col">
                <span className="text-sm font-bold text-gray-200 flex items-center gap-2">
                  <Monitor className="w-4 h-4 text-blue-400" />
                  Resolution
                </span>
                <span className="text-[10px] text-gray-500">Output video scale</span>
              </div>
              <div className="flex items-center bg-dark-800 rounded-lg p-0.5 border border-white/10 text-xs">
                {[
                  { label: "4K", value: "4k" },
                  { label: "1080p", value: "1080p" },
                  { label: "720p", value: "720p" },
                  { label: "Original", value: "original" },
                ].map((r) => (
                  <button
                    key={r.value}
                    type="button"
                    onClick={() => setResolution(r.value)}
                    className={`px-2 py-0.5 rounded-md transition-all text-xs font-semibold ${resolution === r.value
                      ? "bg-blue-600 text-white shadow-sm shadow-blue-500/30"
                      : "text-gray-400 hover:text-white"
                      }`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {processingMode === "folder" && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <div className="relative group">
            <div className="absolute -inset-1 bg-gradient-to-r from-primary-600 to-accent-600 rounded-xl blur opacity-25 group-hover:opacity-60 transition duration-500"></div>
            <div className="relative bg-dark-900 rounded-xl border border-white/10 shadow-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className="p-3 bg-primary-600/20 rounded-lg">
                    <FolderInput className="w-6 h-6 text-primary-400" />
                  </div>
                  <div>
                    <h3 className="text-white font-bold text-lg">Select Folder</h3>
                    <p className="text-xs text-gray-500">Process all media files in folder</p>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                {/* Folder Path Input */}
                <div className="flex items-center space-x-2">
                  <input
                    type="text"
                    disabled={isScanning}
                    value={folderPath || ''}
                    onChange={(e) => setFolderPath(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleFolderScan()}
                    placeholder="C:\Users\YourName\Videos"
                    className="flex-1 bg-dark-800 text-white text-sm border border-white/10 rounded-lg px-3 py-3 outline-none focus:border-primary-500/50 transition-colors font-mono"
                  />
                  <button
                    onClick={handleFolderScan}
                    disabled={!folderPath || isScanning}
                    title={!folderPath ? "Please enter a folder path first" : "Scan folder for media files"}
                    className="px-6 py-3 bg-gradient-to-r from-primary-600 to-accent-600 hover:from-primary-500 hover:to-accent-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-bold rounded-lg transition-all flex items-center space-x-2 min-w-[120px] justify-center"
                  >
                    {isScanning ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Scanning...</span>
                      </>
                    ) : (
                      <>
                        <FolderInput className="w-4 h-4" />
                        <span>Scan</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="flex items-start space-x-2 p-3 bg-dark-800/50 rounded-lg border border-white/5">
                  <span className="text-lg">💡</span>
                  <div className="text-xs text-gray-400 space-y-1">
                    <p><strong className="text-gray-300">How to get folder path:</strong></p>
                    <ol className="list-decimal list-inside space-y-0.5 ml-1">
                      <li>Open folder in Windows Explorer</li>
                      <li>Click on address bar at top</li>
                      <li>Copy path (Ctrl+C)</li>
                      <li>Paste above (Ctrl+V) and click Scan</li>
                    </ol>
                  </div>
                </div>
              </div>
              {batchFiles.length > 0 && (
                <div className="mt-4">
                  {/* Queue Mode - Before Processing */}
                  {status !== "processing" && (
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-2 text-xs text-gray-500">
                        <Files className="w-3 h-3" />
                        <span>{batchFiles.filter(f => f.selected).length} / {batchFiles.length} files selected</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => setBatchFiles(prev => prev.map(f => ({ ...f, selected: true })))}
                          className="px-3 py-1.5 text-xs font-bold text-gray-400 hover:text-white bg-dark-800 hover:bg-dark-700 rounded-lg transition-all"
                        >
                          All
                        </button>
                        <button
                          onClick={() => setBatchFiles(prev => prev.map(f => ({ ...f, selected: false })))}
                          className="px-3 py-1.5 text-xs font-bold text-gray-400 hover:text-white bg-dark-800 hover:bg-dark-700 rounded-lg transition-all"
                        >
                          None
                        </button>
                        <button
                          onClick={() => setBatchFiles(prev => prev.map(f => ({ ...f, selected: !f.selected })))}
                          className="px-3 py-1.5 text-xs font-bold text-gray-400 hover:text-white bg-dark-800 hover:bg-dark-700 rounded-lg transition-all"
                        >
                          Invert
                        </button>
                      </div>
                    </div>
                  )}
                  {status === "processing" && (
                    <div className="flex items-center justify-between mb-3 bg-primary-950/40 p-3 rounded-xl border border-primary-500/30 shadow-inner">
                      <div className="flex items-center space-x-2.5 text-xs">
                        <Loader2 className="w-4 h-4 animate-spin text-primary-400 flex-shrink-0" />
                        <div className="min-w-0">
                          <span className="text-gray-400">Current Action: </span>
                          <span className="text-white font-bold tracking-tight">{currentStep || "Processing..."}</span>
                        </div>
                      </div>
                      <div className="text-xs font-mono font-black text-primary-400 bg-primary-500/20 px-2.5 py-1 rounded-lg border border-primary-500/30 flex-shrink-0">
                        {Math.round(progress)}% Total
                      </div>
                    </div>
                  )}

                  <div className="max-h-80 overflow-y-auto space-y-2 pr-2" ref={batchListRef}>
                    {batchFiles.map((fileInfo, idx) => {
                      const isItemProcessing = fileInfo.status === "processing";
                      const isItemCompleted = fileInfo.status === "completed";
                      const isItemFailed = fileInfo.status === "failed";

                      return (
                        <div
                          key={`batch-file-${fileInfo.task_id || fileInfo.id || idx}-${idx}`}
                          className={`flex items-center justify-between p-3 rounded-xl border transition-all duration-300 ${status === "processing"
                            ? (isItemCompleted ? "bg-emerald-600/10 border-emerald-500/30" :
                              isItemFailed ? "bg-red-600/10 border-red-500/30" :
                                isItemProcessing ? "bg-primary-950/60 border-primary-500/60 shadow-lg shadow-primary-500/20 ring-1 ring-primary-500/40" :
                                  "bg-dark-800/80 border-white/5 opacity-60")
                            : (fileInfo.selected ? "bg-dark-800/80 border-white/10" : "bg-dark-900/50 border-white/5 opacity-60")
                            }`}
                        >
                          <div className="flex items-center space-x-3 flex-1 min-w-0 mr-3">
                            {status === "processing" ? (
                              /* Show status icon during processing */
                              <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${isItemCompleted ? "bg-emerald-600/20 text-emerald-400" :
                                isItemFailed ? "bg-red-600/20 text-red-400" :
                                  isItemProcessing ? "bg-primary-500/20 text-primary-400" :
                                    "bg-dark-700 text-gray-500"
                                }`}>
                                {isItemCompleted ? (
                                  <CheckCircle className="w-5 h-5" />
                                ) : isItemFailed ? (
                                  <AlertCircle className="w-5 h-5" />
                                ) : isItemProcessing ? (
                                  <Loader2 className="w-5 h-5 animate-spin" />
                                ) : (
                                  <FileAudio className="w-5 h-5" />
                                )}
                              </div>
                            ) : (
                              /* Show checkbox before processing */
                              <input
                                type="checkbox"
                                checked={fileInfo.selected}
                                onChange={() => handleToggleFile(fileInfo.id)}
                                className="w-4 h-4 rounded border-gray-600 bg-dark-700 text-primary-500 focus:ring-primary-500 focus:ring-2 cursor-pointer flex-shrink-0"
                              />
                            )}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center space-x-2">
                                <p className={`text-sm font-medium truncate ${isItemProcessing ? "text-white font-bold" : "text-gray-200"}`} title={fileInfo.file_path || fileInfo.file}>
                                  {fileInfo.filename || (fileInfo.file || '').split(/[\\/]/).pop()}
                                </p>
                                {isItemProcessing && (
                                  <span className="px-1.5 py-0.5 rounded bg-primary-500/30 text-primary-300 text-[10px] font-black uppercase tracking-wider border border-primary-500/40 animate-pulse flex-shrink-0">
                                    Active
                                  </span>
                                )}
                                {fileInfo.already_processed && status !== "processing" && (
                                  <span className="px-1.5 py-0.5 rounded-md bg-emerald-500/20 text-emerald-400 text-[10px] font-black uppercase tracking-tighter border border-emerald-500/30 flex items-center gap-1 flex-shrink-0">
                                    <CheckCircle className="w-2.5 h-2.5" />
                                    Already Processed
                                  </span>
                                )}
                              </div>

                              {status !== "processing" && fileInfo.metadata?.duration && (
                                <div className="flex items-center space-x-2 text-xs text-gray-500 mt-0.5">
                                  <span>{fileInfo.metadata.duration}</span>
                                  {fileInfo.already_processed && (
                                    <span className="text-emerald-600/70 font-medium ml-1">Output exists in /nomusic/</span>
                                  )}
                                  {fileInfo.metadata?.resolution && (
                                    <>
                                      <span>•</span>
                                      <span>{fileInfo.metadata.resolution}</span>
                                    </>
                                  )}
                                </div>
                              )}

                              {status === "processing" && (
                                <p className={`text-xs mt-0.5 truncate ${isItemCompleted ? "text-emerald-400 font-semibold" :
                                  isItemFailed ? "text-red-400 font-semibold" :
                                    isItemProcessing ? "text-primary-300 font-bold" :
                                      "text-gray-500"
                                  }`}>
                                  {fileInfo.current_step || (isItemProcessing ? "Processing..." : isItemCompleted ? "Completed" : "Queued in line")}
                                </p>
                              )}
                            </div>
                          </div>

                          {status === "processing" ? (
                            /* Show progress bar and percentage during processing */
                            <div className="w-28 flex-shrink-0 text-right">
                              {isItemProcessing ? (
                                <div>
                                  <div className="text-xs font-mono font-bold text-primary-400 mb-1">
                                    {Math.round(fileInfo.progress || 0)}%
                                  </div>
                                  <div className="h-2 bg-dark-700 rounded-full overflow-hidden border border-white/5">
                                    <div
                                      className="h-full bg-gradient-to-r from-primary-500 to-accent-500 transition-all duration-300 rounded-full"
                                      style={{ width: `${Math.max(5, fileInfo.progress || 0)}%` }}
                                    />
                                  </div>
                                </div>
                              ) : isItemCompleted ? (
                                <span className="text-xs font-bold text-emerald-400">100%</span>
                              ) : isItemFailed ? (
                                <span className="text-xs font-bold text-red-400">Failed</span>
                              ) : (
                                <span className="text-xs text-gray-500">Waiting</span>
                              )}
                            </div>
                          ) : (
                            /* Show remove button before processing */
                            <button
                              onClick={() => handleRemoveFile(fileInfo.id)}
                              className="p-2 hover:bg-red-600/20 text-gray-500 hover:text-red-400 rounded-lg transition-all"
                              title="Remove from queue"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}

      {/* Single File Drop Zone - Only show in single mode */}
      {processingMode === "single" && (
        <motion.div
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          className={`relative group rounded-2xl border-2 border-dashed p-6 transition-all duration-300 cursor-pointer overflow-hidden
                    ${dragging
              ? "border-primary-500 bg-primary-500/10"
              : "border-white/10 hover:border-primary-400/50 hover:bg-white/5"
            } ${file ? "bg-gradient-to-br from-dark-800 to-dark-900 border-primary-500/30" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !status && fileInputRef.current.click()}
        >
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            onChange={handleFileChange}
            accept="audio/*,video/*"
          />

          <div className="flex flex-col items-center justify-center text-center relative z-10">
            <AnimatePresence mode="wait">
              {file ? (
                <motion.div
                  key="file-selected"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="space-y-4"
                >
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-primary-500 to-accent-500 flex items-center justify-center shadow-lg shadow-primary-500/30 mx-auto transform group-hover:rotate-3 transition-transform duration-300">
                    <PlayCircle className="w-7 h-7 text-white" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white tracking-tight truncate max-w-[250px] sm:max-w-md mx-auto" title={file.name}>
                      {file.name}
                    </h3>
                    {libraryFilePath ? (
                      <p className="text-sm text-emerald-400 font-mono mt-1 flex items-center justify-center gap-2">
                        <CheckCircle className="w-3 h-3" />
                        From Library - Ready for Separation
                      </p>
                    ) : (
                      <p className="text-sm text-primary-400 font-mono mt-1">
                        {(file.size / (1024 * 1024)).toFixed(2)} MB
                      </p>
                    )}
                  </div>
                  {status !== "uploading" && status !== "processing" && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleReset();
                      }}
                      className="flex items-center justify-center mx-auto space-x-2 px-4 py-2 mt-4 text-xs font-bold text-white bg-dark-700 hover:bg-dark-600 border border-white/10 hover:border-white/20 rounded-xl transition-all shadow-lg group"
                    >
                      <RefreshCw className="w-4 h-4 text-primary-400 group-hover:rotate-180 transition-transform duration-500" />
                      <span className="tracking-wide">Select new file</span>
                    </button>
                  )}
                </motion.div>
              ) : (
                <motion.div
                  key="upload-prompt"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <div className="w-12 h-12 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mb-3 mx-auto group-hover:bg-primary-500/20 group-hover:border-primary-500/50 transition-colors duration-300">
                    <UploadCloud className="w-6 h-6 text-gray-400 group-hover:text-primary-400 transition-colors" />
                  </div>
                  <h3 className="text-base font-semibold text-gray-200 group-hover:text-white transition-colors">
                    Click or Drag File Here
                  </h3>
                  <p className="text-gray-500 text-sm mt-2 max-w-xs mx-auto">
                    Supports MP3, WAV, FLAC, MP4, MKV...
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Background Glow Effect */}
          <div
            className={`absolute inset-0 bg-primary-500/5 rounded-2xl transition-opacity duration-500 pointer-events-none ${dragging ? "opacity-100" : "opacity-0"}`}
          />
        </motion.div>
      )}

      {/* File Info / Metadata Card */}
      <AnimatePresence>
        {metadata && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-3"
          >
            {[
              { label: "Duration", value: metadata.duration, icon: "🕒" },
              {
                label: "Resolution",
                value: metadata.resolution,
                icon: "📺",
                hidden: !metadata.is_video,
              },
              { label: "Audio Codec", value: metadata.audio_codec, icon: "🎵" },
              {
                label: "Video Codec",
                value: metadata.video_codec,
                icon: "🎞️",
                hidden: !metadata.is_video,
              },
            ].map(
              (item, idx) =>
                !item.hidden && (
                  <div
                    key={idx}
                    className="bg-dark-800/50 border border-white/5 p-3 rounded-xl backdrop-blur-sm shadow-lg"
                  >
                    <div className="text-[9px] uppercase tracking-widest text-gray-500 font-bold mb-1 flex items-center space-x-2">
                      <span>{item.icon}</span>
                      <span>{item.label}</span>
                    </div>
                    <div className="text-xs font-black text-white truncate">
                      {item.value || "Unknown"}
                    </div>
                  </div>
                ),
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error Message */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="bg-red-500/10 border border-red-500/20 text-red-200 p-4 rounded-xl flex items-center space-x-3 backdrop-blur-sm"
          >
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
            <span className="font-medium text-sm">{error}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Start Button - Folder Mode */}
      {processingMode === "folder" && batchFiles.length > 0 && (
        <div className="flex justify-center">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleStartBatchProcessing}
            disabled={status === "processing" || !batchFiles.some(f => f.selected)}
            title={
              status === "processing" ? "Processing in progress..." :
                !batchFiles.some(f => f.selected) ? "Select at least one file" :
                  "Start batch processing"
            }
            className={`
              relative overflow-hidden px-8 py-3 rounded-full font-bold text-base shadow-2xl transition-all duration-300 group
              ${status === "processing" || !batchFiles.some(f => f.selected)
                ? "bg-dark-700 text-gray-500 cursor-not-allowed opacity-50"
                : "bg-gradient-to-r from-primary-600 to-accent-600 text-white shadow-primary-500/25 hover:shadow-primary-500/40"
              }
            `}
          >
            <span className="relative z-10 flex items-center space-x-3">
              {status === "processing" ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <PlayCircle className="w-5 h-5" />
              )}
              <span>
                {status === "processing" ? "Processing..." : `Start Batch (${batchFiles.filter(f => f.selected).length} files)`}
              </span>
            </span>
          </motion.button>
        </div>
      )}

      {/* Start Button - Single File Mode */}
      {processingMode === "single" && (
        <div className="flex justify-center">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleUpload}
            disabled={!file || status === "uploading" || status === "processing" || status === "pending"}
            title={
              !file ? "Please select a file first" :
                status === "uploading" ? "Upload in progress..." :
                  status === "processing" || status === "pending" ? "Processing in progress..." :
                    "Start separation"
            }
            className={`
              relative overflow-hidden px-8 py-3 rounded-full font-bold text-base shadow-2xl transition-all duration-300 group
              ${!file ||
                status === "uploading" ||
                status === "processing"
                ? "bg-dark-700 text-gray-500 cursor-not-allowed opacity-50"
                : "bg-gradient-to-r from-primary-600 to-accent-600 text-white shadow-primary-500/25 hover:shadow-primary-500/40"
              }
            `}
          >
            <span className="relative z-10 flex items-center space-x-3">
              {status === "processing" || status === "pending" || status === "uploading" ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <PlayCircle className="w-5 h-5" />
              )}
              <span>
                {status === "processing" || status === "pending" ? "Processing..." : "Start Separation"}
              </span>
            </span>
          </motion.button>
        </div>
      )}

      {/* Progress Bar - Only visible when active */}
      <AnimatePresence>
        {(status === "uploading" ||
          status === "processing" ||
          status === "pending" ||
          status === "completed") && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              className="bg-dark-900/50 backdrop-blur rounded-2xl p-6 border border-white/5 space-y-4 shadow-xl"
            >
              <div className="flex justify-between items-end">
                <div className="flex flex-col">
                  <span className="text-xs uppercase tracking-wider text-gray-500 font-bold mb-1">
                    Status
                  </span>
                  <span className="text-gray-200 font-medium flex items-center space-x-2">
                    {status === "completed" ? (
                      <span className="text-emerald-400 flex items-center">
                        <CheckCircle className="w-4 h-4 mr-1" /> Finished
                      </span>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="animate-pulse text-primary-400 font-semibold">
                          {currentStep || "Initializing..."}
                        </span>
                        {(status === "pending" || status === "processing" || status === "uploading") && (
                          <button
                            type="button"
                            onClick={handleCancelQueue}
                            className="px-2 py-0.5 text-[11px] font-bold text-red-400 hover:text-white bg-red-500/10 hover:bg-red-500/30 border border-red-500/20 rounded-md transition-colors"
                          >
                            Cancel / Clear
                          </button>
                        )}
                      </div>
                    )}
                  </span>
                </div>
                <span className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-br from-white to-gray-500">
                  {Math.round(progress)}%
                </span>
              </div>

              {/* Custom Progress Bar */}
              <div className="h-4 bg-dark-700/50 rounded-full overflow-hidden p-1 border border-white/5 backdrop-blur-sm">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ type: "spring", stiffness: 50, damping: 20 }}
                  className={`h-full rounded-full relative overflow-hidden transition-colors duration-500 ${status === "completed"
                    ? "bg-emerald-500"
                    : "bg-gradient-to-r from-primary-500 to-accent-500"
                    }`}
                >
                  <div
                    className="absolute inset-0 bg-white/20 animate-[shimmer_2s_infinite]"
                    style={{
                      backgroundImage:
                        "linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent)",
                    }}
                  ></div>
                </motion.div>
              </div>
            </motion.div>
          )}
      </AnimatePresence>

      {/* Success Message */}
      <AnimatePresence>
        {status === "completed" && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-6 text-center space-y-4 backdrop-blur-md"
          >
            <div className="w-12 h-12 bg-emerald-500 rounded-full flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/30">
              <CheckCircle className="w-6 h-6 text-white" />
            </div>
            <div>
              <h4 className="text-xl font-bold text-white">
                Separation Successful!
              </h4>
              <p className="text-emerald-200/80 text-sm mt-1">
                Your files are ready in the output directory.
              </p>
              {processingTime && (
                <div className="mt-2 space-y-1">
                  <div className="text-[10px] uppercase tracking-widest text-emerald-400 font-mono font-bold">
                    Total process time: {processingTime < 60
                      ? `${processingTime.toFixed(1)}s`
                      : `${Math.floor(processingTime / 60)}m ${Math.round(processingTime % 60)}s`}
                  </div>

                  {detailedTimings && (
                    <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 mt-3 px-4 py-3 bg-black/20 rounded-xl border border-white/5">
                      {detailedTimings.extract && (
                        <div className="text-[9px] text-gray-400 font-mono">
                          <span className="text-gray-300 font-bold">1. EXTRACT:</span> {detailedTimings.extract.toFixed(1)}s
                        </div>
                      )}
                      {detailedTimings.spleeter && (
                        <div className="text-[9px] text-gray-400 font-mono">
                          <span className="text-blue-400 font-bold">2. SPLEETER:</span> {detailedTimings.spleeter.toFixed(1)}s
                        </div>
                      )}
                      {detailedTimings.demucs && (
                        <div className="text-[9px] text-gray-400 font-mono">
                          <span className="text-orange-400 font-bold">3. DEMUCS:</span> {detailedTimings.demucs.toFixed(1)}s
                        </div>
                      )}
                      {detailedTimings.mixing && (
                        <div className="text-[9px] text-gray-400 font-mono">
                          <span className="text-emerald-400 font-bold">4. MIX/ALIGN:</span> {detailedTimings.mixing.toFixed(1)}s
                        </div>
                      )}
                      {detailedTimings.sync && (
                        <div className="text-[9px] text-gray-400 font-mono">
                          <span className="text-purple-400 font-bold">5. SYNC:</span> {detailedTimings.sync.toFixed(1)}s
                        </div>
                      )}
                      {detailedTimings.output && (
                        <div className="text-[9px] text-gray-400 font-mono">
                          <span className="text-pink-400 font-bold">6. OUTPUT:</span> {detailedTimings.output.toFixed(1)}s
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="flex flex-col items-center space-y-4 pt-2">
              <div className="flex flex-wrap justify-center gap-3">
                {/* Play in Browser (Video / Vocals) */}
                <button
                  onClick={handlePlayVocalsInBrowser}
                  className="px-6 py-3 bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-dark-950 rounded-xl text-sm sm:text-base font-black transition-all shadow-xl shadow-emerald-500/25 active:scale-95 flex items-center space-x-2.5 group"
                  title={isVideoOutput ? "Play video in browser" : "Play vocal track in browser"}
                >
                  {isVideoOutput ? (
                    <Video className="w-5 h-5 group-hover:scale-110 transition-transform" />
                  ) : (
                    <Play className="w-5 h-5 fill-current group-hover:scale-110 transition-transform" />
                  )}
                  <span>{isVideoOutput ? "Play Video in Browser" : "Play Vocals in Browser"}</span>
                </button>

                {/* Play Instrumental in Browser (if exists) */}
                {instrumentalFile && (
                  <button
                    onClick={handlePlayInstrumentalInBrowser}
                    className="px-6 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-xl text-sm sm:text-base font-bold transition-all shadow-xl shadow-purple-500/25 active:scale-95 flex items-center space-x-2.5 group"
                    title="Play instrumental/karaoke track in browser"
                  >
                    <AudioLines className="w-5 h-5 group-hover:scale-110 transition-transform" />
                    <span>Play Instrumental</span>
                  </button>
                )}

                {/* Open in Desktop App */}
                <button
                  onClick={async () => {
                    try {
                      await axios.post(`${BACKEND_URL}/api/open-file`, {
                        path: resultFiles[0],
                      });
                    } catch (err) {
                      toast.error("Cannot open file in desktop player.");
                    }
                  }}
                  className="px-5 py-3 bg-dark-800 hover:bg-dark-700 text-gray-300 hover:text-white rounded-xl text-sm font-bold transition-all border border-white/10 active:scale-95 flex items-center space-x-2"
                  title="Open file in external media player"
                >
                  <ExternalLink className="w-4 h-4" />
                  <span>Desktop App</span>
                </button>

                {/* Open Folder */}
                <button
                  onClick={async () => {
                    try {
                      await axios.post(
                        `${BACKEND_URL}/api/open-folder`,
                        { path: resultFiles[0] },
                      );
                    } catch (err) {
                      toast.error("Cannot open folder.");
                    }
                  }}
                  className="px-5 py-3 bg-dark-800 hover:bg-dark-700 text-gray-300 hover:text-white rounded-xl text-sm font-bold transition-all border border-white/10 active:scale-95 flex items-center space-x-2"
                  title="Open folder containing result files"
                >
                  <FolderOpen className="w-4 h-4" />
                  <span>Folder</span>
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default SeparationTab;
