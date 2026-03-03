/**
 * DOWNLOADER.JSX - YouTube Downloader Interface
 * 
 * ROLE: Download videos/audio from YouTube with format selection
 * 
 * FEATURES:
 *   - URL input with analyze button
 *   - Video info preview (thumbnail, title, duration)
 *   - Format selection dropdown (filtered by audio/video)
 *   - Subtitle/caption selection
 *   - Audio/Video toggle switch
 *   - Download queue system
 *   - Queue management (add, remove, start, stop, clear)
 *   - Real-time download progress polling
 *   - Cancel active download
 *   - Auto-separate option for queue items
 * 
 * STATE:
 *   - url: YouTube URL input
 *   - taskId: Current download task ID
 *   - status: 'idle' | 'processing' | 'completed' | 'error'
 *   - progress: 0-100 progress percentage
 *   - format: 'audio' | 'video'
 *   - videoInfo: Analyzed video metadata
 *   - availableFormats: Filtered format list
 *   - selectedFormatId: Selected format ID
 *   - subtitles: Selected subtitle language
 *   - queue: Download queue array
 *   - queueProcessing: Queue processing flag
 *   - autoSeparate: Auto-separate after download
 *   - currentTaskId: Currently active download task
 * 
 * API ENDPOINTS:
 *   - POST /api/yt-formats - Analyze URL and get formats
 *   - POST /api/download - Start download
 *   - POST /api/download/cancel - Cancel active download
 *   - POST /api/queue/add - Add to queue
 *   - POST /api/queue/remove - Remove from queue
 *   - POST /api/queue/clear - Clear entire queue
 *   - POST /api/queue/start - Start queue processing
 *   - POST /api/queue/stop - Stop queue processing
 *   - GET /api/queue - Fetch queue status
 *   - GET /api/status/:taskId - Poll download progress
 * 
 * DEPENDENCIES:
 *   - axios: HTTP client
 *   - framer-motion: Animations
 *   - lucide-react: Icons
 */
import { useState, useEffect } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';
import { Download, Youtube, CheckCircle, AlertCircle, Video, Music, Loader2, Link, Search, List, Trash2, Play, Pause, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const DownloaderTab = ({ analyzingProgress }) => {
    const [url, setUrl] = useState('');
    const [taskId, setTaskId] = useState(null);
    const [status, setStatus] = useState(null);
    const [progress, setProgress] = useState(0);
    const [error, setError] = useState(null);
    const [format, setFormat] = useState('video');
    const [currentStep, setCurrentStep] = useState('Preparing download...');
    const [downloadInfo, setDownloadInfo] = useState({ speed: '', eta: '' });

    // New states for format selection
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [videoInfo, setVideoInfo] = useState(null);
    const [availableFormats, setAvailableFormats] = useState([]);
    const [selectedFormatId, setSelectedFormatId] = useState('');

    // Playlist support
    const [isPlaylist, setIsPlaylist] = useState(false);
    const [playlistVideos, setPlaylistVideos] = useState([]);
    const [selectedPlaylistVideos, setSelectedPlaylistVideos] = useState([]);
    const [playlistSubfolder, setPlaylistSubfolder] = useState('');

    // Remember last selected format per video ID
    const [lastVideoId, setLastVideoId] = useState(() => {
        return localStorage.getItem('lastVideoId') || null;
    });
    const [lastSelectedFormat, setLastSelectedFormat] = useState(() => {
        return localStorage.getItem('lastSelectedFormat') || null;
    });
    const [rememberFormat, setRememberFormat] = useState(true);

    // Queue states
    const [queue, setQueue] = useState([]);
    const [queueProcessing, setQueueProcessing] = useState(false);
    const [autoSeparate, setAutoSeparate] = useState(false);
    const [showQueue, setShowQueue] = useState(true);
    const [currentTaskId, setCurrentTaskId] = useState(null);

    // Playlist confirmation modal
    const [showPlaylistConfirm, setShowPlaylistConfirm] = useState(false);
    const [playlistConfirmData, setPlaylistConfirmData] = useState(null);

    // Active downloads tracking
    const [activeDownloads, setActiveDownloads] = useState([]);

    // Fetch queue
    const fetchQueue = async () => {
        try {
            const response = await axios.get(`${BACKEND_URL}/api/queue`);
            setQueue(response.data.queue || []);
            setQueueProcessing(response.data.processing || false);
        } catch (err) {
            // Silent fail for polling
        }
    };


    // Keyboard Shortcuts
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape' && !isAnalyzing && status !== 'processing') {
                setUrl('');
                setVideoInfo(null);
                setAvailableFormats([]);
                setIsPlaylist(false);
                setPlaylistVideos([]);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isAnalyzing, status]);

    // Polling effect
    useEffect(() => {
        let interval;
        let consecutiveErrors = 0;
        const MAX_CONSECUTIVE_ERRORS = 10;
        let currentPollingTaskId = taskId; // Capture taskId at effect start

        if (taskId && (status === 'processing')) {
            interval = setInterval(async () => {
                // Only poll if taskId hasn't changed
                if (currentPollingTaskId !== taskId) {
                    clearInterval(interval);
                    return;
                }

                try {
                    const response = await axios.get(
                        `${BACKEND_URL}/api/status/${taskId}`,
                        { timeout: 300000 } // 5 minute timeout for long operations
                    );
                    const data = response.data;

                    // Reset error counter on successful response
                    consecutiveErrors = 0;

                    setProgress(data.progress || 0);
                    setStatus(data.status);
                    setCurrentStep(data.current_step || 'Downloading...');
                    if (data.download_info) {
                        setDownloadInfo({
                            speed: data.download_info.speed || '',
                            eta: data.download_info.eta || '',
                            filename: data.download_info.filename || '',
                            playlist_index: data.download_info.playlist_index || null,
                            playlist_count: data.download_info.playlist_count || null,
                        });
                    }

                    if (data.status === 'completed' || data.status === 'failed' || data.status === 'error') {
                        setTaskId(null);
                    }
                } catch (err) {
                    consecutiveErrors++;

                    // Treat 404 as task completion only after several retries
                    // (prevents race conditions during server reloads)
                    if (err.response?.status === 404) {
                        if (consecutiveErrors > 10) {
                            setStatus("completed");
                            setTaskId(null);
                            clearInterval(interval);
                        }
                        return;
                    }

                    // Show error after 30 consecutive failures (approx 6-10s at current rate)
                    if (consecutiveErrors >= 30) {
                        setError("Connection lost to backend. Refresh page to reconnect.");
                        setStatus("error");
                        clearInterval(interval);
                    }
                }
            }, 200); // Poll every 200ms for fast downloads
        }
        return () => {
            clearInterval(interval);
        };
    }, [taskId, status]);

    // Queue polling effect
    useEffect(() => {
        let consecutiveErrors = 0;
        const MAX_CONSECUTIVE_ERRORS = 10;

        const queueInterval = setInterval(async () => {
            try {
                await fetchQueue();
                consecutiveErrors = 0; // Reset on success
            } catch (err) {
                consecutiveErrors++;

                // Show error after 3 consecutive failures
                if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
                    setError("Connection lost to backend. Refresh page to reconnect.");
                    clearInterval(queueInterval);
                }
            }
        }, 2000);
        return () => clearInterval(queueInterval);
    }, []);

    // Active downloads polling effect
    const fetchActiveDownloads = async () => {
        try {
            const response = await axios.get(`${BACKEND_URL}/api/downloads`);
            setActiveDownloads(response.data || []);
        } catch (err) {
            // Silent fail for polling
        }
    };

    useEffect(() => {
        let consecutiveErrors = 0;
        const MAX_CONSECUTIVE_ERRORS = 10;

        const downloadsInterval = setInterval(async () => {
            try {
                await fetchActiveDownloads();
                consecutiveErrors = 0;
            } catch (err) {
                consecutiveErrors++;

                if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
                    clearInterval(downloadsInterval);
                }
            }
        }, 1000);
        return () => clearInterval(downloadsInterval);
    }, []);

    const handleAddToQueue = async () => {
        if (!url && !isPlaylist) return;

        // For playlists, show confirmation first
        if (isPlaylist && playlistVideos.length > 0) {
            const selectedCount = selectedPlaylistVideos.length;
            if (selectedCount === 0) {
                setError('Please select at least one video.');
                return;
            }

            // Show confirmation modal
            setPlaylistConfirmData({
                videoCount: selectedCount,
                totalCount: playlistVideos.length
            });
            setShowPlaylistConfirm(true);
            return;
        }

        // Single video - add directly
        try {
            await axios.post(`${BACKEND_URL}/api/queue/add`, {
                url,
                format,
                format_id: selectedFormatId,
                auto_separate: autoSeparate
            });

            setUrl('');
            fetchQueue();
        } catch (err) {
            setError('Failed to add to queue.');
        }
    };

    const handleConfirmPlaylistDownload = async () => {
        // User confirmed - add selected videos to queue
        try {
            const videosToAdd = playlistVideos.filter(v =>
                selectedPlaylistVideos.includes(v.id)
            );

            await axios.post(`${BACKEND_URL}/api/queue/add-batch`, {
                videos: videosToAdd.map(v => ({
                    url: v.url || `https://www.youtube.com/watch?v=${v.id}`,
                    title: v.title
                })),
                format,
                format_id: selectedFormatId,
                auto_separate: autoSeparate,
                subfolder: playlistSubfolder.trim() || null
            });

            setShowPlaylistConfirm(false);
            setPlaylistConfirmData(null);
            setUrl('');
            setPlaylistVideos([]);
            setSelectedPlaylistVideos([]);
            setPlaylistSubfolder('');
            setIsPlaylist(false);
            fetchQueue();
        } catch (err) {
            setError('Failed to add playlist to queue.');
            setShowPlaylistConfirm(false);
        }
    };

    const handleRemoveFromQueue = async (queueId) => {
        try {
            await axios.post(`${BACKEND_URL}/api/queue/remove`, { queue_id: queueId });
            fetchQueue();
        } catch (err) {
            // Silent fail
        }
    };

    const handleClearQueue = async () => {
        try {
            await axios.post(`${BACKEND_URL}/api/queue/clear`);
            fetchQueue();
        } catch (err) {
            // Silent fail
        }
    };

    const handleStartQueue = async () => {
        try {
            await axios.post(`${BACKEND_URL}/api/queue/start`);
            fetchQueue();
        } catch (err) {
            // Silent fail
        }
    };

    const handleStopQueue = async () => {
        try {
            await axios.post(`${BACKEND_URL}/api/queue/stop`);
            fetchQueue();
        } catch (err) {
            // Silent fail
        }
    };

    const handleAnalyze = async () => {
        if (!url) return;
        setIsAnalyzing(true);
        setError(null);
        setVideoInfo(null);
        setAvailableFormats([]);
        setPlaylistVideos([]);
        setSelectedPlaylistVideos([]);
        setIsPlaylist(false);

        try {
            const response = await axios.post(`${BACKEND_URL}/api/yt-formats`, {
                url,
                check_playlist: true
            });
            setVideoInfo(response.data);

            // Check if this is a playlist
            if (response.data.is_playlist) {
                setIsPlaylist(true);
                setPlaylistVideos(response.data.videos || []);
                // Pre-select all videos
                setSelectedPlaylistVideos(response.data.videos?.map(v => v.id) || []);
                // Pre-fill subfolder with sanitized playlist/channel title
                const rawTitle = response.data.title || 'Playlist';
                // Strip invalid filename chars AND leading @ (channel handles)
                const safeTitle = rawTitle.replace(/[\\/:*?"<>|]/g, '_').replace(/^@+/, '').trim();
                setPlaylistSubfolder(safeTitle);
            } else {
                // Single video - filter formats
                const filtered = response.data.formats.filter(f => {
                    if (format === 'audio') return f.vcodec === 'none';
                    return f.vcodec !== 'none';
                });

                setAvailableFormats(filtered);
                if (filtered.length > 0) {
                    // Select best by default (usually last in list)
                    setSelectedFormatId(filtered[filtered.length - 1].format_id);
                }
            }
        } catch (err) {
            // Use backend's specific error message if available (e.g. playlist too large)
            const detail = err?.response?.data?.detail;
            if (detail) {
                setError(detail);
            } else {
                setError('Failed to analyze link. Check if URL is valid.');
            }
        } finally {
            setIsAnalyzing(false);
        }
    };

    // Update filtered formats when tab changes
    useEffect(() => {
        if (videoInfo && !videoInfo.is_playlist && videoInfo.formats) {
            const filtered = videoInfo.formats.filter(f => {
                if (format === 'audio') return f.vcodec === 'none';
                return f.vcodec !== 'none';
            });
            setAvailableFormats(filtered);
            if (filtered.length > 0 && !lastVideoId) {
                setSelectedFormatId(filtered[filtered.length - 1].format_id);
            }
        }
    }, [format, videoInfo]);

    // Save selected format to localStorage when it changes (only if checkbox is checked)
    useEffect(() => {
        if (selectedFormatId && videoInfo && !videoInfo.is_playlist && rememberFormat && url) {
            try {
                const urlParams = new URLSearchParams(new URL(url).search);
                const videoId = urlParams.get('v') || videoInfo.id;
                if (videoId) {
                    setLastVideoId(videoId);
                    setLastSelectedFormat(selectedFormatId);
                    localStorage.setItem('lastVideoId', videoId);
                    localStorage.setItem('lastSelectedFormat', selectedFormatId);
                }
            } catch {
                // Invalid URL, skip
            }
        }
    }, [selectedFormatId, videoInfo, url, rememberFormat]);

    const handleDownload = async () => {
        if (!url) return;

        setStatus('processing');
        setProgress(0);
        setCurrentStep('Starting download...');
        setDownloadInfo({ speed: '', eta: '' });
        setError(null);

        try {
            const response = await axios.post(`${BACKEND_URL}/api/download`, {
                url,
                format,
                format_id: selectedFormatId,
                subfolder: isPlaylist ? playlistSubfolder.trim() || null : null,
                auto_separate: autoSeparate
            });
            setTaskId(response.data.task_id);
            setCurrentTaskId(response.data.task_id);
        } catch (err) {
            console.error('[Downloader] Download failed:', err);
            setError('Failed to start download.');
            setStatus('error');
        }
    };

    const handleCancelDownload = async (idToCancel) => {
        const targetId = idToCancel || currentTaskId || taskId;
        if (!targetId) return;

        try {
            const response = await axios.post(`${BACKEND_URL}/api/download/cancel`, {
                task_id: targetId
            });

            if (response.data.status === 'cancelled' || response.data.status === 'already_finished') {
                if (targetId === taskId) {
                    setTaskId(null);
                    setStatus(null);
                    setProgress(0);
                }
                setError(null);
                fetchActiveDownloads();
            }
        } catch (err) {
            if (err.response?.data?.status === 'already_finished') {
                setStatus('completed');
            }
        }
    };

    // Cancel all active downloads AND stop the queue
    const handleCancelAll = async () => {
        try {
            await axios.post(`${BACKEND_URL}/api/queue/stop`);
            const toCancel = [...activeDownloads];
            for (const dl of toCancel) {
                try { await axios.post(`${BACKEND_URL}/api/download/cancel`, { task_id: dl.task_id }); } catch (_) { }
            }
            if (taskId) {
                try { await axios.post(`${BACKEND_URL}/api/download/cancel`, { task_id: taskId }); } catch (_) { }
            }
            setTaskId(null);
            setStatus(null);
            setProgress(0);
            fetchActiveDownloads();
            fetchQueue();
        } catch (err) { }
    };


    return (
        <div className="space-y-6 max-w-3xl mx-auto">
            {/* Input & Form */}
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
            >
                <div className="relative group">
                    <div className="absolute -inset-1 bg-gradient-to-r from-red-600 to-primary-600 rounded-xl blur opacity-25 group-hover:opacity-60 transition duration-500"></div>
                    <div className="relative flex items-center bg-dark-900 rounded-xl overflow-hidden border border-white/10 shadow-xl">
                        <div className="pl-4 pr-3 text-gray-400">
                            <Link className="w-5 h-5" />
                        </div>
                        <input
                            type="text"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            placeholder="Paste YouTube URL here..."
                            className="w-full bg-transparent text-white py-5 pr-4 border-none focus:ring-0 placeholder-gray-600 text-lg font-medium"
                        />
                        <button
                            onClick={handleAnalyze}
                            disabled={!url || isAnalyzing}
                            title={!url ? "Please enter a URL first" : isAnalyzing ? "Analyzing..." : "Analyze video/playlist"}
                            className={`mr-3 px-6 py-2.5 rounded-lg flex items-center space-x-2 font-bold text-sm transition-all min-w-[140px] ${!url
                                ? 'bg-dark-800 text-gray-600'
                                : isAnalyzing
                                    ? 'bg-blue-900/40 text-blue-400 border border-blue-500/30'
                                    : 'bg-white/5 hover:bg-white/10 text-white border border-white/10'
                                }`}
                        >
                            {isAnalyzing ? (
                                <>
                                    <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
                                    <span>Analyzing...</span>
                                </>
                            ) : (
                                <>
                                    <Search className="w-4 h-4" />
                                    <span>Analyze</span>
                                </>
                            )}
                        </button>
                    </div>
                </div>

                {/* Video Preview Info */}
                <AnimatePresence>
                    {videoInfo && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="bg-dark-800/50 rounded-2xl border border-white/5 overflow-hidden backdrop-blur-sm"
                        >
                            {isPlaylist ? (
                                /* Playlist View */
                                <div className="p-4">
                                    <div className="flex items-center space-x-3 mb-3">
                                        <div className="p-2 bg-red-600/20 rounded-lg">
                                            <List className="w-5 h-5 text-red-400" />
                                        </div>
                                        <div>
                                            <h4 className="text-white font-bold text-lg">{videoInfo.title}</h4>
                                            <p className="text-xs text-gray-500">{playlistVideos.length} videos detected</p>
                                        </div>
                                    </div>

                                    {/* Subfolder input */}
                                    <div className="mb-4 bg-dark-900/60 rounded-xl p-3 border border-white/5">
                                        <label className="text-[10px] uppercase tracking-widest text-gray-500 font-black flex items-center space-x-1 mb-1.5">
                                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" /></svg>
                                            <span>Save to subfolder inside <span className="text-gray-400">download/</span></span>
                                        </label>
                                        <div className="flex items-center space-x-2">
                                            <span className="text-gray-600 text-xs font-mono flex-shrink-0">download /</span>
                                            <input
                                                type="text"
                                                value={playlistSubfolder}
                                                onChange={(e) => setPlaylistSubfolder(e.target.value)}
                                                placeholder="playlist-name  (leave blank for no subfolder)"
                                                className="flex-1 bg-dark-800 text-white text-sm border border-white/10 rounded-lg px-3 py-1.5 outline-none focus:border-blue-500/50 placeholder-gray-600 transition-colors font-mono"
                                            />
                                            {playlistSubfolder && (
                                                <button
                                                    onClick={() => setPlaylistSubfolder('')}
                                                    className="p-1.5 text-gray-500 hover:text-white hover:bg-white/10 rounded-lg transition-all flex-shrink-0"
                                                    title="Clear subfolder (save directly to download/)"
                                                >
                                                    <X className="w-3.5 h-3.5" />
                                                </button>
                                            )}
                                        </div>
                                    </div>

                                    {/* Select All / None */}
                                    <div className="flex items-center justify-between mb-3">
                                        <div className="flex items-center space-x-2 text-xs text-gray-500">
                                            <input
                                                type="checkbox"
                                                checked={selectedPlaylistVideos.length === playlistVideos.length}
                                                onChange={(e) => {
                                                    if (e.target.checked) {
                                                        setSelectedPlaylistVideos(playlistVideos.map(v => v.id));
                                                    } else {
                                                        setSelectedPlaylistVideos([]);
                                                    }
                                                }}
                                                className="rounded border-gray-600 bg-dark-700 text-primary-500 focus:ring-primary-500"
                                            />
                                            <span>{selectedPlaylistVideos.length} / {playlistVideos.length} selected</span>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            <button
                                                onClick={() => setSelectedPlaylistVideos(playlistVideos.map(v => v.id))}
                                                className="px-3 py-1 text-xs font-bold text-gray-400 hover:text-white bg-dark-800 hover:bg-dark-700 rounded"
                                            >
                                                All
                                            </button>
                                            <button
                                                onClick={() => setSelectedPlaylistVideos([])}
                                                className="px-3 py-1 text-xs font-bold text-gray-400 hover:text-white bg-dark-800 hover:bg-dark-700 rounded"
                                            >
                                                None
                                            </button>
                                        </div>
                                    </div>

                                    {/* Video List */}
                                    <div className="max-h-64 overflow-y-auto space-y-2 pr-2">
                                        {playlistVideos.map((video, idx) => (
                                            <div
                                                key={`playlist-video-${video.id || idx}-${idx}`}
                                                className={`flex items-center space-x-3 p-2 rounded-lg border ${selectedPlaylistVideos.includes(video.id)
                                                    ? 'bg-primary-600/10 border-primary-500/30'
                                                    : 'bg-dark-900/50 border-white/5'
                                                    }`}
                                            >
                                                <input
                                                    type="checkbox"
                                                    checked={selectedPlaylistVideos.includes(video.id)}
                                                    onChange={(e) => {
                                                        if (e.target.checked) {
                                                            setSelectedPlaylistVideos([...selectedPlaylistVideos, video.id]);
                                                        } else {
                                                            setSelectedPlaylistVideos(selectedPlaylistVideos.filter(id => id !== video.id));
                                                        }
                                                    }}
                                                    className="rounded border-gray-600 bg-dark-700 text-primary-500 focus:ring-primary-500"
                                                />
                                                {video.thumbnail ? (
                                                    <img
                                                        src={video.thumbnail}
                                                        alt={video.title}
                                                        className="w-16 h-12 rounded object-cover flex-shrink-0"
                                                    />
                                                ) : (
                                                    <div className="w-16 h-12 rounded bg-dark-800 flex items-center justify-center flex-shrink-0">
                                                        <Video className="w-6 h-6 text-gray-600" />
                                                    </div>
                                                )}
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-white text-sm font-medium truncate">{video.title}</p>
                                                    <p className="text-xs text-gray-500">{video.duration || 'N/A'}</p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                /* Single Video View */
                                <div className="flex p-4 space-x-4">
                                    <div className="w-32 h-20 bg-dark-900 rounded-lg overflow-hidden flex-shrink-0 border border-white/5">
                                        {videoInfo.thumbnail ? (
                                            <img src={videoInfo.thumbnail} alt="Thumbnail" className="w-full h-full object-cover" />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center">
                                                <Video className="w-8 h-8 text-gray-600" />
                                            </div>
                                        )}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center space-x-2 mb-1">
                                            {videoInfo.id && (
                                                <span className="text-[10px] font-mono text-primary-400 bg-primary-600/20 px-2 py-0.5 rounded">
                                                    [{videoInfo.id}]
                                                </span>
                                            )}
                                            <h4 className="text-white font-bold truncate leading-tight flex-1">{videoInfo.title}</h4>
                                        </div>

                                        {/* Format Selection Dropdown */}
                                        <div className="mt-3 space-y-2">
                                            <label className="text-[10px] uppercase tracking-widest text-gray-500 font-black">Choose Resolution / Quality</label>
                                            <select
                                                value={selectedFormatId}
                                                onChange={(e) => setSelectedFormatId(e.target.value)}
                                                className="w-full bg-dark-900 text-white text-xs border border-white/10 rounded-lg px-3 py-2 outline-none focus:border-red-500/50 transition-colors"
                                            >
                                                {availableFormats.map((f, idx) => (
                                                    <option key={`format-${f.format_id || idx}-${idx}`} value={f.format_id}>
                                                        {f.label} {f.filesize ? `(${(f.filesize / 1024 / 1024).toFixed(1)} MB)` : ''}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>

                                        {/* Remember Format Checkbox */}
                                        <div className="mt-3 flex items-center space-x-2">
                                            <input
                                                type="checkbox"
                                                id="remember-format"
                                                checked={rememberFormat}
                                                onChange={(e) => setRememberFormat(e.target.checked)}
                                                className="w-4 h-4 rounded border-gray-600 bg-dark-700 text-primary-500 focus:ring-primary-500 focus:ring-2 cursor-pointer"
                                            />
                                            <label
                                                htmlFor="remember-format"
                                                className="text-xs font-medium text-gray-300 cursor-pointer select-none"
                                                title="Save selected format for this video ID"
                                            >
                                                Remember format for this video
                                            </label>
                                            {rememberFormat && (() => {
                                                try {
                                                    const videoId = url ? new URLSearchParams(new URL(url).search).get('v') : null;
                                                    return lastVideoId === (videoId || videoInfo?.id);
                                                } catch {
                                                    return false;
                                                }
                                            })() && (
                                                    <CheckCircle className="w-3 h-3 text-emerald-400" />
                                                )}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Format Selector - Toggle Style */}
                <div className="flex justify-center p-1 bg-dark-900/50 rounded-xl w-fit mx-auto border border-white/5 backdrop-blur-sm">
                    {['audio', 'video'].map((f) => (
                        <button
                            key={f}
                            onClick={() => setFormat(f)}
                            className={`flex items-center space-x-2 px-8 py-3 rounded-lg text-sm font-bold transition-all duration-300 relative ${format === f
                                ? 'text-white shadow-lg'
                                : 'text-gray-500 hover:text-gray-300'
                                }`}
                        >
                            {format === f && (
                                <motion.div
                                    layoutId="format-bg"
                                    className="absolute inset-0 bg-dark-700/80 rounded-lg border border-white/5 shadow-sm"
                                    transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                                />
                            )}
                            <span className="relative z-10 flex items-center space-x-2">
                                {f === 'audio' ? <Music className="w-4 h-4" /> : <Video className="w-4 h-4" />}
                                <span className="capitalize">{f === 'audio' ? 'MP3 Audio' : 'MP4 Video'}</span>
                            </span>
                        </button>
                    ))}
                </div>

                {/* Action Buttons */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={handleAddToQueue}
                        disabled={!url || isAnalyzing}
                        title={!url ? "Please enter a URL first" : isAnalyzing ? "Analyzing..." : "Add to download queue"}
                        className={`py-4 rounded-2xl font-bold text-lg shadow-xl flex items-center justify-center space-x-2 transition-all duration-300 overflow-hidden relative group border border-white/10
                            ${!url || isAnalyzing
                                ? 'bg-dark-800 text-gray-600 cursor-not-allowed'
                                : 'bg-dark-800 hover:bg-dark-700 text-white'
                            }`}
                    >
                        <List className="w-5 h-5 group-hover:rotate-12 transition-transform" />
                        <span>Add to Queue</span>
                    </motion.button>

                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={handleDownload}
                        disabled={!url || status === 'processing' || isAnalyzing}
                        title={
                            !url ? "Please enter a URL first" :
                                status === 'processing' ? "Download in progress..." :
                                    isAnalyzing ? "Analyzing..." :
                                        "Start download"
                        }
                        className={`py-4 rounded-2xl font-bold text-lg shadow-2xl flex items-center justify-center space-x-2 transition-all duration-300 overflow-hidden relative group
                            ${!url || status === 'processing' || isAnalyzing
                                ? 'bg-dark-800 text-gray-600 cursor-not-allowed border border-white/5'
                                : 'bg-gradient-to-tr from-red-600 to-red-500 text-white shadow-red-600/30 hover:shadow-red-600/50 hover:brightness-110'
                            }`}
                    >
                        <div className="relative z-10 flex items-center space-x-2">
                            {status === 'processing' ? (
                                <>
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    <span>Downloading...</span>
                                </>
                            ) : (
                                <>
                                    <Download className="w-5 h-5 group-hover:animate-bounce" />
                                    <span>Download Now</span>
                                </>
                            )}
                        </div>
                    </motion.button>
                </div>
            </motion.div>

            {/* Error Toast */}
            <AnimatePresence>
                {error && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-red-500/10 border border-red-500/20 text-red-200 p-4 rounded-xl flex items-center justify-center space-x-3 backdrop-blur-md"
                    >
                        <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
                        <span className="font-semibold">{error}</span>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Current Download Progress Card */}
            <AnimatePresence>
                {taskId && (
                    <motion.div
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className="bg-gradient-to-r from-red-900/20 to-primary-900/20 border border-red-500/20 rounded-2xl overflow-hidden backdrop-blur-sm"
                    >
                        <div className="p-4 border-b border-red-500/10 flex items-center justify-between">
                            <div className="flex items-center space-x-3">
                                <div className="p-2 bg-red-600/20 rounded-lg">
                                    <Download className="w-5 h-5 text-red-400" />
                                </div>
                                <div>
                                    <h3 className="text-white font-bold leading-tight">
                                        {videoInfo?.title || 'Downloading...'}
                                    </h3>
                                </div>
                            </div>
                            <button
                                onClick={() => handleCancelDownload()}
                                className="p-2 hover:bg-red-500/20 text-gray-500 hover:text-red-400 rounded transition-all"
                                title="Cancel download"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <div className="p-4">
                            {/* Progress Bar */}
                            <div className="h-3 bg-dark-800 rounded-full overflow-hidden border border-white/5 mb-3">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{ width: `${progress}%` }}
                                    className="h-full bg-gradient-to-r from-red-600 to-primary-600 rounded-full"
                                />
                            </div>

                            {/* Progress Info */}
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-br from-white to-gray-400">
                                    {Math.round(progress)}%
                                </span>
                                <div className="flex flex-col items-end max-w-[60%]">
                                    <span className="text-sm text-gray-400 truncate w-full text-right">
                                        {currentStep || 'Preparing download...'}
                                    </span>
                                    {downloadInfo?.filename && (
                                        <span className="text-[10px] text-gray-500 font-mono truncate w-full text-right mt-1" title={downloadInfo.filename}>
                                            {downloadInfo.playlist_index && downloadInfo.playlist_count && (
                                                <strong className="text-primary-400 mr-1 px-1.5 py-0.5 bg-primary-500/10 rounded">
                                                    {downloadInfo.playlist_index}/{downloadInfo.playlist_count}
                                                </strong>
                                            )}
                                            {downloadInfo.filename}
                                        </span>
                                    )}
                                </div>
                            </div>

                            {/* Download Stats */}
                            {(downloadInfo.speed || downloadInfo.eta) && (
                                <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/5">
                                    <div className="flex items-center space-x-4">
                                        {downloadInfo.speed && downloadInfo.speed !== 'N/A' && (
                                            <div className="flex items-center space-x-1">
                                                <span className="text-[10px] text-gray-500 font-bold uppercase tracking-tighter">SPD:</span>
                                                <span className="text-xs text-gray-300 font-mono">{downloadInfo.speed}</span>
                                            </div>
                                        )}
                                        {downloadInfo.eta && downloadInfo.eta !== 'N/A' && (
                                            <div className="flex items-center space-x-1">
                                                <span className="text-[10px] text-gray-500 font-bold uppercase tracking-tighter">ETA:</span>
                                                <span className="text-xs text-gray-300 font-mono">{downloadInfo.eta}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Active Downloads Panel */}
            <AnimatePresence>
                {activeDownloads.filter(d => d.task_id !== taskId).length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className="bg-gradient-to-r from-red-900/20 to-primary-900/20 border border-red-500/20 rounded-2xl overflow-hidden backdrop-blur-sm"
                    >
                        <div className="p-4 border-b border-red-500/10 flex items-center justify-between">
                            <div className="flex items-center space-x-3">
                                <div className="p-2 bg-red-600/20 rounded-lg">
                                    <Download className="w-5 h-5 text-red-400" />
                                </div>
                                <div>
                                    <h3 className="text-white font-bold">Active Downloads</h3>
                                    <p className="text-xs text-gray-500">
                                        {activeDownloads.filter(d => d.task_id !== taskId).length} download{activeDownloads.filter(d => d.task_id !== taskId).length !== 1 ? 's' : ''} in progress
                                    </p>
                                </div>
                            </div>
                            <button
                                onClick={handleCancelAll}
                                className="px-3 py-1.5 text-xs font-bold text-red-400 bg-red-500/10 hover:bg-red-500/20 rounded-lg transition-all flex items-center space-x-1"
                            >
                                <X className="w-3.5 h-3.5" />
                                <span>Cancel All</span>
                            </button>
                        </div>
                        <div className="divide-y divide-red-500/5">
                            {activeDownloads.filter(d => d.task_id !== taskId).map((download, idx) => (
                                <div key={`active-dl-${download.task_id || idx}-${idx}`} className="p-4">
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center space-x-3 flex-1 min-w-0">
                                            <Loader2 className="w-4 h-4 text-red-400 animate-spin flex-shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-white text-sm font-medium truncate flex items-center">
                                                    {download.download_info?.playlist_index && download.download_info?.playlist_count && (
                                                        <strong className="text-primary-400 mr-2 text-[10px] px-1.5 py-0.5 bg-primary-500/10 rounded tracking-widest flex-shrink-0">
                                                            {download.download_info.playlist_index}/{download.download_info.playlist_count}
                                                        </strong>
                                                    )}
                                                    <span className="truncate">
                                                        {download.download_info?.filename || download.current_step?.replace('File:', '').split('|')[0]?.trim() || 'Process in progress...'}
                                                    </span>
                                                </p>
                                                <p className="text-xs text-gray-500 truncate">{download.url || 'Background Task'}</p>
                                            </div>
                                        </div>
                                        <div className="text-right ml-4 flex-shrink-0 flex items-center space-x-3">
                                            <span className="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-br from-white to-gray-400">
                                                {Math.round(download.progress)}%
                                            </span>
                                            <button
                                                onClick={() => {
                                                    handleCancelDownload(download.task_id);
                                                }}
                                                className="p-1 hover:bg-red-500/20 text-gray-500 hover:text-red-400 rounded transition-all"
                                                title="Cancel download"
                                            >
                                                <X className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>

                                    {/* Progress Bar */}
                                    <div className="h-2 bg-dark-800 rounded-full overflow-hidden p-0.5 border border-white/5">
                                        <motion.div
                                            initial={{ width: 0 }}
                                            animate={{ width: `${download.progress}%` }}
                                            className="h-full bg-gradient-to-r from-red-600 to-primary-600 rounded-full"
                                        />
                                    </div>

                                    {/* Download Stats */}
                                    <div className="flex items-center justify-between mt-2 text-[10px] text-gray-500">
                                        <div className="flex items-center space-x-4">
                                            {download.download_info?.speed && (
                                                <span className="flex items-center space-x-1">
                                                    <span className="text-gray-600 font-bold uppercase tracking-tighter">SPD:</span>
                                                    <span className="text-gray-300 font-mono">{download.download_info.speed}</span>
                                                </span>
                                            )}
                                            {download.download_info?.eta && (
                                                <span className="flex items-center space-x-1">
                                                    <span className="text-gray-600 font-bold uppercase tracking-tighter">ETA:</span>
                                                    <span className="text-gray-300 font-mono">{download.download_info.eta}</span>
                                                </span>
                                            )}
                                        </div>
                                        <span className="text-gray-600 font-medium truncate max-w-[50%]">{download.current_step}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Playlist Confirmation Modal */}
            <AnimatePresence>
                {showPlaylistConfirm && playlistConfirmData && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
                        onClick={() => setShowPlaylistConfirm(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            onClick={(e) => e.stopPropagation()}
                            className="bg-dark-900 border border-white/10 rounded-2xl p-6 max-w-md w-full shadow-2xl"
                        >
                            <div className="flex items-center space-x-3 mb-4">
                                <div className="p-3 bg-red-600/20 rounded-full">
                                    <Download className="w-6 h-6 text-red-400" />
                                </div>
                                <h3 className="text-xl font-bold text-white">Confirm Playlist Download</h3>
                            </div>

                            <p className="text-gray-300 mb-6">
                                Are you sure you want to download <strong className="text-white font-bold">{playlistConfirmData.videoCount}</strong> video{playlistConfirmData.videoCount !== 1 ? 's' : ''}
                                {playlistConfirmData.videoCount < playlistConfirmData.totalCount
                                    ? ` (out of ${playlistConfirmData.totalCount} total)`
                                    : ''}
                                to your queue?
                            </p>

                            <div className="bg-dark-800/50 rounded-lg p-4 mb-6">
                                <p className="text-xs text-gray-400 mb-2">This will add all selected videos to the download queue.</p>
                                <p className="text-xs text-gray-500">Processing may take a while depending on the number of videos.</p>
                            </div>

                            <div className="flex gap-3">
                                <button
                                    onClick={() => setShowPlaylistConfirm(false)}
                                    className="flex-1 px-4 py-3 bg-dark-800 hover:bg-dark-700 text-gray-300 hover:text-white rounded-xl font-bold transition-all border border-white/10"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleConfirmPlaylistDownload}
                                    className="flex-1 px-4 py-3 bg-gradient-to-r from-red-600 to-red-500 hover:from-red-500 hover:to-red-400 text-white rounded-xl font-bold transition-all shadow-lg shadow-red-600/30"
                                >
                                    Download {playlistConfirmData.videoCount} Video{playlistConfirmData.videoCount !== 1 ? 's' : ''}
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Status Feedback (Toast style) */}
            <AnimatePresence>
                {status === 'completed' && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.9 }}
                        className="bg-emerald-500/20 text-emerald-300 p-4 rounded-xl flex items-center justify-center space-x-3 backdrop-blur-md border border-emerald-500/20 shadow-lg shadow-emerald-500/10"
                    >
                        <CheckCircle className="w-5 h-5 text-emerald-400" />
                        <span className="font-bold">Download Completed! Check Library.</span>
                        <button
                            onClick={() => setStatus(null)}
                            className="ml-4 p-1 hover:bg-white/10 rounded"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Queue Section */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-8"
            >
                <div className="bg-dark-900/80 backdrop-blur-xl rounded-3xl border border-white/10 overflow-hidden shadow-2xl">
                    {/* Queue Header */}
                    <div className="p-4 border-b border-white/10 flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                            <div className="p-2 bg-red-600/20 rounded-lg">
                                <List className="w-5 h-5 text-red-400" />
                            </div>
                            <div>
                                <h3 className="text-white font-bold">Download Queue</h3>
                                <p className="text-xs text-gray-500">{queue.length} items {queueProcessing ? '• Processing' : '• Paused'}</p>
                            </div>
                        </div>
                        <div className="flex items-center space-x-2">
                            <button
                                onClick={() => setShowQueue(!showQueue)}
                                className="p-2 bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white rounded-lg transition-all"
                            >
                                <X className={`w-4 h-4 transition-transform ${showQueue ? '' : 'rotate-45'}`} />
                            </button>
                        </div>
                    </div>

                    <AnimatePresence>
                        {showQueue && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="overflow-hidden"
                            >
                                {/* Queue Controls */}
                                <div className="p-4 border-b border-white/10 flex items-center justify-between gap-3 flex-wrap">
                                    <div className="flex items-center space-x-2">
                                        <label className="flex items-center space-x-2 cursor-pointer">
                                            <input
                                                type="checkbox"
                                                checked={autoSeparate}
                                                onChange={(e) => setAutoSeparate(e.target.checked)}
                                                className="w-4 h-4 rounded border-gray-600 bg-dark-800 text-red-500 focus:ring-red-500"
                                            />
                                            <span className="text-xs text-gray-400 font-medium">Auto-separate after download</span>
                                        </label>
                                    </div>
                                    <div className="flex items-center space-x-2">
                                        {queueProcessing ? (
                                            <button
                                                onClick={handleStopQueue}
                                                className="px-3 py-1.5 bg-amber-600/20 hover:bg-amber-600/30 text-amber-400 rounded-lg text-xs font-bold transition-all flex items-center space-x-1"
                                            >
                                                <Pause className="w-3 h-3" />
                                                <span>Pause</span>
                                            </button>
                                        ) : (
                                            <button
                                                onClick={handleStartQueue}
                                                disabled={queue.filter(i => i.status === 'pending').length === 0}
                                                className="px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-xs font-bold transition-all flex items-center space-x-1"
                                            >
                                                <Play className="w-3 h-3" />
                                                <span>Start</span>
                                            </button>
                                        )}
                                        <button
                                            onClick={handleClearQueue}
                                            className="px-3 py-1.5 bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white rounded-lg text-xs font-bold transition-all"
                                        >
                                            Clear Done
                                        </button>
                                    </div>
                                </div>

                                {/* Queue Items */}
                                <div className="max-h-64 overflow-y-auto">
                                    {queue.length === 0 ? (
                                        <div className="p-8 text-center text-gray-500 text-sm">
                                            Queue is empty. Add downloads to get started.
                                        </div>
                                    ) : (
                                        <div className="divide-y divide-white/5">
                                            {queue.map((item, idx) => (
                                                <div
                                                    key={`queue-item-${item.queue_id || idx}-${idx}`}
                                                    className="p-3 flex items-center justify-between hover:bg-white/5 transition-colors"
                                                >
                                                    <div className="flex items-center space-x-3 flex-1 min-w-0">
                                                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${item.status === 'downloading' ? 'bg-red-600/20' :
                                                            item.status === 'completed' ? 'bg-emerald-600/20' :
                                                                item.status === 'failed' ? 'bg-red-900/20' :
                                                                    'bg-dark-800'
                                                            }`}>
                                                            {item.status === 'downloading' ? (
                                                                <Loader2 className="w-4 h-4 text-red-400 animate-spin" />
                                                            ) : item.status === 'completed' ? (
                                                                <CheckCircle className="w-4 h-4 text-emerald-400" />
                                                            ) : item.status === 'failed' ? (
                                                                <AlertCircle className="w-4 h-4 text-red-400" />
                                                            ) : (
                                                                <span className="text-xs text-gray-500 font-bold">{idx + 1}</span>
                                                            )}
                                                        </div>
                                                        <div className="flex-1 min-w-0">
                                                            <p className="text-white text-sm font-medium truncate max-w-[200px] sm:max-w-md" title={item.url}>{item.url}</p>
                                                            <div className="flex items-center space-x-2 text-xs text-gray-500 mt-0.5">
                                                                <span className="capitalize">{item.format_type}</span>
                                                                {item.auto_separate && (
                                                                    <span className="px-1.5 py-0.5 bg-red-600/20 text-red-400 rounded text-[10px] font-bold">SEPARATE</span>
                                                                )}
                                                            </div>
                                                            {item.status === 'downloading' && (
                                                                <div className="mt-2 h-1.5 bg-dark-800 rounded-full overflow-hidden">
                                                                    <motion.div
                                                                        initial={{ width: 0 }}
                                                                        animate={{ width: `${item.progress || 0}%` }}
                                                                        className="h-full bg-gradient-to-r from-red-600 to-primary-600"
                                                                    />
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center space-x-2">
                                                        <span className={`text-xs font-bold px-2 py-1 rounded ${item.status === 'downloading' ? 'bg-red-600/20 text-red-400' :
                                                            item.status === 'completed' ? 'bg-emerald-600/20 text-emerald-400' :
                                                                item.status === 'failed' ? 'bg-red-900/20 text-red-400' :
                                                                    'bg-dark-800 text-gray-500'
                                                            }`}>
                                                            {item.status === 'downloading' ? 'DOWNLOADING' :
                                                                item.status === 'completed' ? 'DONE' :
                                                                    item.status === 'failed' ? 'FAILED' : 'PENDING'}
                                                        </span>
                                                        {item.status === 'pending' && (
                                                            <button
                                                                onClick={() => handleRemoveFromQueue(item.queue_id)}
                                                                className="p-1.5 hover:bg-red-600/20 text-gray-500 hover:text-red-400 rounded transition-all"
                                                            >
                                                                <Trash2 className="w-3.5 h-3.5" />
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </motion.div>
        </div>
    );
};

export default DownloaderTab;
