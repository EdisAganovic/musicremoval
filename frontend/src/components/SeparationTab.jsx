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
  Video
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const SeparationTab = ({ libraryFile, onFileCleared }) => {
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
  const [metadata, setMetadata] = useState(null);
  const [processingMode, setProcessingMode] = useState("single");

  const fileInputRef = useRef(null);
  const batchListRef = useRef(null);

  // Auto-scroll batch list when files are loaded
  useEffect(() => {
    if (batchFiles.length > 5 && batchListRef.current) {
      batchListRef.current.scrollTop = batchListRef.current.scrollHeight / 2;
    }
  }, [batchFiles]);

  // Handle library file pre-load
  useEffect(() => {
    if (libraryFile) {
      setLibraryFilePath(libraryFile);
      setFile({
        name: libraryFile.split(/[\\/]/).pop() || 'Selected File',
        size: 0,
        path: libraryFile
      });
      setStatus("idle");
      setProgress(0);
      setResultFiles([]);
      setError(null);
    }
  }, [libraryFile]);

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
  };

  // Polling effect
  useEffect(() => {
    let interval;
    let consecutiveErrors = 0;
    const MAX_CONSECUTIVE_ERRORS = 3;
    
    if (taskId && status === "processing") {
      interval = setInterval(async () => {
        try {
          const response = await axios.get(
            `http://localhost:5170/api/status/${taskId}`,
            { timeout: 10000 } // 10 second timeout
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
            clearInterval(interval);
          } else if (data.status === "failed" || data.status === "error") {
            setError("Process failed: Check backend logs.");
            clearInterval(interval);
            setStatus("error");
          }
        } catch (err) {
          console.error("Polling error", err);
          consecutiveErrors++;
          
          // Show error after 3 consecutive failures
          if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
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
    const MAX_CONSECUTIVE_ERRORS = 3;
    
    if (batchId && processingMode === "folder") {
      interval = setInterval(async () => {
        try {
          const response = await axios.get(
            `http://localhost:5170/api/batch-status/${batchId}`,
            { timeout: 10000 } // 10 second timeout
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
          console.error("Batch polling error", err);
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
    
    console.log("Scanning folder:", folderPath);
    
    // Scan folder using Python backend
    try {
      const response = await axios.post('http://localhost:5170/api/folder/scan', {
        folder_path: folderPath
      });
      
      console.log("Scan response:", response.data);
      setQueueId(response.data.queue_id);
      setBatchFiles(response.data.files || []);
      
      if (response.data.files && response.data.files.length > 0) {
        console.log(`Found ${response.data.files.length} files`);
      }
    } catch (err) {
      console.error("Folder scan error:", err);
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Failed to scan folder. Make sure it contains media files.");
      }
      setBatchFiles([]);
    }
  };

  const handleRemoveFile = async (fileId) => {
    if (!queueId) return;
    
    try {
      const response = await axios.post('http://localhost:5170/api/folder-queue/remove', {
        queue_id: queueId,
        file_id: fileId
      });
      
      setBatchFiles(response.data.files || []);
    } catch (err) {
      console.error("Failed to remove file", err);
    }
  };

  const handleToggleFile = (fileId) => {
    setBatchFiles(prev => prev.map(f => 
      f.id === fileId ? { ...f, selected: !f.selected } : f
    ));
  };

  const handleStartBatchProcessing = async () => {
    if (!queueId) {
      console.error("No queue ID");
      setError("No queue ID - please scan folder first");
      return;
    }
    
    const selectedCount = batchFiles.filter(f => f.selected).length;
    if (selectedCount === 0) {
      setError("No files selected for processing");
      return;
    }

    console.log(`Starting batch processing for ${selectedCount} files...`);
    setStatus("processing");
    setCurrentStep(`Starting batch processing (${selectedCount} files)...`);
    setProgress(0);

    try {
      console.log("Sending process request with queue_id:", queueId);
      const response = await axios.post('http://localhost:5170/api/folder-queue/process', {
        queue_id: queueId,
        model: model
      });
      
      console.log("Process response:", response.data);
      setBatchId(response.data.batch_id);
      setBatchFiles(response.data.files || []);
    } catch (err) {
      console.error("Batch process error:", err);
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Failed to start batch processing");
      }
      setStatus("error");
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    // If it's a library file, use a different endpoint
    if (libraryFilePath) {
      setStatus("processing");
      setCurrentStep("Starting separation...");
      setProgress(0);

      try {
        const response = await axios.post(
          "http://localhost:5170/api/separate-file",
          { file_path: libraryFilePath, model },
        );

        setTaskId(response.data.task_id);
        if (response.data.metadata) {
          setMetadata(response.data.metadata);
        }
        setStatus("processing");
      } catch (err) {
        console.error(err);
        setError("Failed to contact server. Is backend running?");
        setStatus("error");
      }
      return;
    }

    // Regular file upload flow
    const formData = new FormData();
    formData.append("file", file);
    formData.append("model", model);

    setStatus("uploading");
    setCurrentStep("Transferring file...");
    setProgress(0);

    try {
      const response = await axios.post(
        "http://localhost:5170/api/separate",
        formData,
        {
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
        },
      );

      setTaskId(response.data.task_id);
      if (response.data.metadata) {
        setMetadata(response.data.metadata);
      }
      setStatus("processing");
    } catch (err) {
      console.error(err);
      setError("Failed to contact server. Is backend running?");
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
      setError(null);
      setStatus("idle");
    }
  };

  return (
    <div className="space-y-8 max-w-3xl mx-auto">
      {/* Processing Mode Selection */}
      <div className="flex justify-center space-x-4 mb-6">
        <button
          onClick={() => { setProcessingMode("single"); setBatchFiles([]); setBatchId(null); }}
          className={`px-6 py-3 rounded-xl text-sm font-bold transition-all duration-200 border flex items-center space-x-2 ${
            processingMode === "single"
              ? "bg-primary-600/20 text-primary-400 border-primary-500/50 shadow-lg shadow-primary-500/10"
              : "bg-dark-800 text-gray-400 hover:text-white hover:bg-dark-700 border-transparent"
          }`}
        >
          <UploadCloud className="w-4 h-4" />
          <span>Single File</span>
        </button>
        <button
          onClick={() => { setProcessingMode("folder"); setFile(null); }}
          className={`px-6 py-3 rounded-xl text-sm font-bold transition-all duration-200 border flex items-center space-x-2 ${
            processingMode === "folder"
              ? "bg-primary-600/20 text-primary-400 border-primary-500/50 shadow-lg shadow-primary-500/10"
              : "bg-dark-800 text-gray-400 hover:text-white hover:bg-dark-700 border-transparent"
          }`}
        >
          <FolderInput className="w-4 h-4" />
          <span>Process Folder</span>
        </button>
      </div>

      {/* Model Selection */}
      <div className="flex justify-center space-x-4 mb-6">
        {["spleeter", "demucs", "both"].map((m) => (
          <button
            key={m}
            onClick={() => setModel(m)}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-all duration-200 border border-transparent ${
              model === m
                ? "bg-primary-600/20 text-primary-400 border-primary-500/50 shadow-lg shadow-primary-500/10"
                : "bg-dark-800 text-gray-400 hover:text-white hover:bg-dark-700"
            }`}
          >
            <span className="capitalize">{m}</span>{" "}
            {m === "both" && "(Recommended)"}
          </button>
        ))}
      </div>

      {/* Folder Selection - Only show in folder mode */}
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
                    value={folderPath || ''}
                    onChange={(e) => setFolderPath(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleFolderScan()}
                    placeholder="C:\Users\YourName\Videos"
                    className="flex-1 bg-dark-800 text-white text-sm border border-white/10 rounded-lg px-3 py-3 outline-none focus:border-primary-500/50 transition-colors font-mono"
                  />
                  <button
                    onClick={handleFolderScan}
                    disabled={!folderPath}
                    title={!folderPath ? "Please enter a folder path first" : "Scan folder for media files"}
                    className="px-6 py-3 bg-gradient-to-r from-primary-600 to-accent-600 hover:from-primary-500 hover:to-accent-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-bold rounded-lg transition-all flex items-center space-x-2"
                  >
                    <FolderInput className="w-4 h-4" />
                    <span>Scan</span>
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

                  {/* Processing Mode - Show Progress */}
                  {status === "processing" && (
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-2 text-xs text-gray-500">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        <span>Processing files...</span>
                      </div>
                      <div className="text-xs font-bold text-primary-400">
                        {Math.round(progress)}% Complete
                      </div>
                    </div>
                  )}

                  <div className="max-h-80 overflow-y-auto space-y-2 pr-2" ref={batchListRef}>
                    {batchFiles.map((fileInfo, idx) => (
                      <div
                        key={fileInfo.task_id || fileInfo.id}
                        className={`flex items-center justify-between p-3 rounded-lg border transition-all ${
                          status === "processing"
                            ? (fileInfo.status === "completed" ? "bg-emerald-600/10 border-emerald-500/30" :
                               fileInfo.status === "failed" ? "bg-red-600/10 border-red-500/30" :
                               fileInfo.status === "processing" ? "bg-primary-600/10 border-primary-500/30" :
                               "bg-dark-800/80 border-white/10")
                            : (fileInfo.selected ? "bg-dark-800/80 border-white/10" : "bg-dark-900/50 border-white/5 opacity-60")
                        }`}
                      >
                        <div className="flex items-center space-x-3 flex-1 min-w-0">
                          {status === "processing" ? (
                            /* Show status icon during processing */
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                              fileInfo.status === "completed" ? "bg-emerald-600/20" :
                              fileInfo.status === "failed" ? "bg-red-600/20" :
                              fileInfo.status === "processing" ? "bg-primary-600/20" :
                              "bg-dark-700"
                            }`}>
                              {fileInfo.status === "completed" ? (
                                <CheckCircle className="w-4 h-4 text-emerald-400" />
                              ) : fileInfo.status === "failed" ? (
                                <AlertCircle className="w-4 h-4 text-red-400" />
                              ) : fileInfo.status === "processing" ? (
                                <Loader2 className="w-4 h-4 text-primary-400 animate-spin" />
                              ) : (
                                <FileAudio className="w-4 h-4 text-gray-500" />
                              )}
                            </div>
                          ) : (
                            /* Show checkbox before processing */
                            <input
                              type="checkbox"
                              checked={fileInfo.selected}
                              onChange={() => handleToggleFile(fileInfo.id)}
                              className="w-4 h-4 rounded border-gray-600 bg-dark-700 text-primary-500 focus:ring-primary-500 focus:ring-2 cursor-pointer"
                            />
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="text-white text-sm font-medium truncate" title={fileInfo.file_path || fileInfo.file}>
                              {fileInfo.filename || (fileInfo.file || '').split(/[\\/]/).pop()}
                            </p>
                            {status !== "processing" && fileInfo.metadata?.duration && (
                              <div className="flex items-center space-x-2 text-xs text-gray-500 mt-0.5">
                                <span>{fileInfo.metadata.duration}</span>
                                {fileInfo.metadata?.resolution && (
                                  <>
                                    <span>•</span>
                                    <span>{fileInfo.metadata.resolution}</span>
                                  </>
                                )}
                              </div>
                            )}
                            {status === "processing" && (
                              <p className="text-xs capitalize font-bold" style={{
                                color: fileInfo.status === "completed" ? "#34d399" :
                                       fileInfo.status === "failed" ? "#f87171" :
                                       fileInfo.status === "processing" ? "#60a5fa" :
                                       "#9ca3af"
                              }}>
                                {fileInfo.status || "queued"}
                              </p>
                            )}
                          </div>
                        </div>
                        {status === "processing" ? (
                          /* Show progress bar during processing */
                          fileInfo.progress !== undefined && (
                            <div className="w-24">
                              <div className="text-xs text-gray-500 text-right mb-1">{fileInfo.progress}%</div>
                              <div className="h-1.5 bg-dark-700 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-gradient-to-r from-primary-500 to-accent-500 transition-all"
                                  style={{ width: `${fileInfo.progress}%` }}
                                />
                              </div>
                            </div>
                          )
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
                    ))}
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
        className={`relative group rounded-2xl border-2 border-dashed p-10 transition-all duration-300 cursor-pointer overflow-hidden
                    ${
                      dragging
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
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-primary-500 to-accent-500 flex items-center justify-center shadow-lg shadow-primary-500/30 mx-auto transform group-hover:rotate-3 transition-transform duration-300">
                  <PlayCircle className="w-10 h-10 text-white" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white tracking-tight">
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
                    className="flex items-center justify-center mx-auto space-x-2 px-5 py-2.5 mt-4 text-sm font-bold text-white bg-dark-700 hover:bg-dark-600 border border-white/10 hover:border-white/20 rounded-xl transition-all shadow-lg group"
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
                <div className="w-16 h-16 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mb-4 mx-auto group-hover:bg-primary-500/20 group-hover:border-primary-500/50 transition-colors duration-300">
                  <UploadCloud className="w-8 h-8 text-gray-400 group-hover:text-primary-400 transition-colors" />
                </div>
                <h3 className="text-lg font-semibold text-gray-200 group-hover:text-white transition-colors">
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
            className="grid grid-cols-2 md:grid-cols-4 gap-4"
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
                    className="bg-dark-800/50 border border-white/5 p-4 rounded-xl backdrop-blur-sm shadow-lg"
                  >
                    <div className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-1 flex items-center space-x-2">
                      <span>{item.icon}</span>
                      <span>{item.label}</span>
                    </div>
                    <div className="text-sm font-black text-white truncate">
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
              relative overflow-hidden px-10 py-4 rounded-full font-bold text-lg shadow-2xl transition-all duration-300 group
              ${
                status === "processing" || !batchFiles.some(f => f.selected)
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
            disabled={!file || status === "uploading" || status === "processing"}
            title={
              !file ? "Please select a file first" :
              status === "uploading" ? "Upload in progress..." :
              status === "processing" ? "Processing in progress..." :
              "Start separation"
            }
            className={`
              relative overflow-hidden px-10 py-4 rounded-full font-bold text-lg shadow-2xl transition-all duration-300 group
              ${
                !file ||
                status === "uploading" ||
                status === "processing"
                  ? "bg-dark-700 text-gray-500 cursor-not-allowed opacity-50"
                  : "bg-gradient-to-r from-primary-600 to-accent-600 text-white shadow-primary-500/25 hover:shadow-primary-500/40"
              }
            `}
          >
            <span className="relative z-10 flex items-center space-x-3">
              {status === "processing" || status === "uploading" ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <PlayCircle className="w-5 h-5" />
              )}
              <span>
                {status === "processing" ? "Processing..." : "Start Separation"}
              </span>
            </span>
          </motion.button>
        </div>
      )}

      {/* Progress Bar - Only visible when active */}
      <AnimatePresence>
        {(status === "uploading" ||
          status === "processing" ||
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
                    <span className="animate-pulse text-primary-400">
                      {currentStep || "Initializing..."}
                    </span>
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
                className={`h-full rounded-full relative overflow-hidden transition-colors duration-500 ${
                  status === "completed"
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
            </div>
            <div className="flex flex-col items-center space-y-4 pt-2">
              <div className="flex justify-center space-x-3">
                <button
                  onClick={async () => {
                    try {
                      await axios.post("http://localhost:5170/api/open-file", {
                        path: resultFiles[0],
                      });
                    } catch (err) {
                      alert("Cannot open file.");
                    }
                  }}
                  className="px-8 py-3 bg-gradient-to-r from-primary-600 to-accent-600 hover:from-primary-500 hover:to-accent-500 text-white rounded-xl text-lg font-black transition-all shadow-xl shadow-primary-500/25 active:scale-95 flex items-center space-x-3 group"
                >
                  <PlayCircle className="w-6 h-6 group-hover:scale-110 transition-transform" />
                  <span>POKRENI FAJL</span>
                </button>
                <button
                  onClick={async () => {
                    try {
                      await axios.post(
                        "http://localhost:5170/api/open-folder",
                        { path: resultFiles[0] },
                      );
                    } catch (err) {
                      alert("Cannot open folder.");
                    }
                  }}
                  className="px-6 py-3 bg-dark-800 hover:bg-dark-700 text-white rounded-xl text-sm font-bold transition-all border border-white/5 active:scale-95 flex items-center space-x-2"
                >
                  <FolderOpen className="w-4 h-4" />
                  <span>OTVORI FOLDER</span>
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
