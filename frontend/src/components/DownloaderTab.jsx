import { useState, useEffect } from 'react';
import axios from 'axios';
import { Download, Youtube, CheckCircle, AlertCircle, Video, Music, Loader2, Link, Search, Subtitles, List, Trash2, Play, Pause, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const DownloaderTab = () => {
    const [url, setUrl] = useState('');
    const [taskId, setTaskId] = useState(null);
    const [status, setStatus] = useState(null);
    const [progress, setProgress] = useState(0);
    const [currentStep, setCurrentStep] = useState('');
    const [error, setError] = useState(null);
    const [format, setFormat] = useState('video');

    // New states for format selection
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [videoInfo, setVideoInfo] = useState(null);
    const [availableFormats, setAvailableFormats] = useState([]);
    const [selectedFormatId, setSelectedFormatId] = useState('');
    const [subtitles, setSubtitles] = useState('none');

    // Queue states
    const [queue, setQueue] = useState([]);
    const [queueProcessing, setQueueProcessing] = useState(false);
    const [autoSeparate, setAutoSeparate] = useState(false);
    const [showQueue, setShowQueue] = useState(true);
    const [currentTaskId, setCurrentTaskId] = useState(null);

    // Dynamic languages based on video info
    const availableSubtitleOptions = [
        { code: 'none', label: 'No Subtitles' },
        ...(videoInfo?.subtitles || []),
        { code: 'all', label: 'All Available' }
    ];

    // Fetch queue
    const fetchQueue = async () => {
        try {
            const response = await axios.get('http://localhost:8000/api/queue');
            setQueue(response.data.queue || []);
            setQueueProcessing(response.data.processing || false);
        } catch (err) {
            console.error("Failed to fetch queue", err);
        }
    };

    // Polling effect
    useEffect(() => {
        let interval;
        if (taskId && (status === 'processing')) {
            interval = setInterval(async () => {
                try {
                    const response = await axios.get(`http://localhost:8000/api/status/${taskId}`);
                    const data = response.data;

                    setProgress(data.progress || 0);
                    setCurrentStep(data.currentStep || data.current_step);
                    setStatus(data.status);

                    if (data.status === 'completed') {
                        clearInterval(interval);
                    } else if (data.status === 'failed' || data.status === 'error') {
                        setError('Download failed.');
                        clearInterval(interval);
                    }
                } catch (err) {
                    console.error("Polling error", err);
                }
            }, 1000);
        }
        return () => clearInterval(interval);
    }, [taskId, status]);

    // Queue polling effect
    useEffect(() => {
        const queueInterval = setInterval(fetchQueue, 2000);
        return () => clearInterval(queueInterval);
    }, []);

    const handleAddToQueue = async () => {
        if (!url) return;

        try {
            const response = await axios.post('http://localhost:8000/api/queue/add', {
                url,
                format,
                format_id: selectedFormatId,
                subtitles,
                auto_separate: autoSeparate
            });
            
            // Clear URL and refresh queue
            setUrl('');
            fetchQueue();
        } catch (err) {
            console.error(err);
            setError('Failed to add to queue.');
        }
    };

    const handleRemoveFromQueue = async (queueId) => {
        try {
            await axios.post('http://localhost:8000/api/queue/remove', { queue_id: queueId });
            fetchQueue();
        } catch (err) {
            console.error("Failed to remove from queue", err);
        }
    };

    const handleClearQueue = async () => {
        try {
            await axios.post('http://localhost:8000/api/queue/clear');
            fetchQueue();
        } catch (err) {
            console.error("Failed to clear queue", err);
        }
    };

    const handleStartQueue = async () => {
        try {
            await axios.post('http://localhost:8000/api/queue/start');
            fetchQueue();
        } catch (err) {
            console.error("Failed to start queue", err);
        }
    };

    const handleStopQueue = async () => {
        try {
            await axios.post('http://localhost:8000/api/queue/stop');
            fetchQueue();
        } catch (err) {
            console.error("Failed to stop queue", err);
        }
    };

    const handleAnalyze = async () => {
        if (!url) return;
        setIsAnalyzing(true);
        setError(null);
        setVideoInfo(null);
        setAvailableFormats([]);
        
        try {
            const response = await axios.post('http://localhost:8000/api/yt-formats', { url });
            setVideoInfo(response.data);
            
            // Filter formats based on current 'format' selection (audio or video)
            const filtered = response.data.formats.filter(f => {
                if (format === 'audio') return f.vcodec === 'none';
                return f.vcodec !== 'none';
            });
            
            setAvailableFormats(filtered);
            if (filtered.length > 0) {
                // Select best by default (usually last in list)
                setSelectedFormatId(filtered[filtered.length - 1].format_id);
            }
        } catch (err) {
            console.error(err);
            setError('Failed to analyze link. Check if URL is valid.');
        } finally {
            setIsAnalyzing(false);
        }
    };

    // Update filtered formats when tab changes
    useEffect(() => {
        if (videoInfo) {
            const filtered = videoInfo.formats.filter(f => {
                if (format === 'audio') return f.vcodec === 'none';
                return f.vcodec !== 'none';
            });
            setAvailableFormats(filtered);
            if (filtered.length > 0) {
                setSelectedFormatId(filtered[filtered.length - 1].format_id);
            }
        }
    }, [format, videoInfo]);

    const handleDownload = async () => {
        if (!url) return;

        setStatus('processing');
        setCurrentStep('Starting download...');
        setProgress(0);
        setError(null);

        try {
            const response = await axios.post('http://localhost:8000/api/download', {
                url,
                format,
                format_id: selectedFormatId,
                subtitles: subtitles
            });
            setTaskId(response.data.task_id);
            setCurrentTaskId(response.data.task_id);
        } catch (err) {
            console.error(err);
            setError('Failed to start download.');
            setStatus('error');
        }
    };

    const handleCancelDownload = async () => {
        if (!currentTaskId) return;
        
        try {
            const response = await axios.post('http://localhost:8000/api/download/cancel', {
                task_id: currentTaskId
            });
            
            if (response.data.status === 'cancelled') {
                setStatus('error');
                setCurrentStep('Download cancelled by user');
                setError('Download was stopped');
            }
        } catch (err) {
            if (err.response?.data?.status === 'already_finished') {
                // Already finished, just update UI
                setStatus('completed');
            } else {
                console.error("Failed to cancel download", err);
            }
        }
    };

    return (
        <div className="space-y-8 max-w-3xl mx-auto pb-10">
            {/* Header */}
            <motion.div 
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="text-center relative py-4"
            >
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-24 h-24 bg-red-600/20 blur-3xl rounded-full"></div>
                <div className="relative inline-block mb-4 p-4 rounded-3xl bg-dark-800/80 border border-white/5 shadow-2xl backdrop-blur-sm">
                    <Youtube className="w-10 h-10 text-red-500 drop-shadow-[0_0_15px_rgba(239,68,68,0.5)]" />
                </div>
                <h2 className="text-3xl font-black text-white tracking-tight">YouTube Downloader</h2>
                <p className="text-gray-400 mt-1 font-medium italic">Advanced Format Selection Control</p>
            </motion.div>

            {/* Input & Form */}
            <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
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
                            className={`mr-3 px-6 py-2.5 rounded-lg flex items-center space-x-2 font-bold text-sm transition-all ${
                                !url || isAnalyzing 
                                ? 'bg-dark-800 text-gray-600' 
                                : 'bg-white/5 hover:bg-white/10 text-white border border-white/10'
                            }`}
                        >
                            {isAnalyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                            <span>{isAnalyzing ? 'Analyzing...' : 'Analyze'}</span>
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
                            <div className="flex p-4 space-x-4">
                                <div className="w-32 h-20 bg-dark-900 rounded-lg overflow-hidden flex-shrink-0 border border-white/5">
                                    <img src={videoInfo.thumbnail} alt="Thumbnail" className="w-full h-full object-cover" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <h4 className="text-white font-bold truncate leading-tight">{videoInfo.title}</h4>
                                    
                                    {/* Format Selection Dropdown */}
                                    <div className="mt-3 space-y-2">
                                        <label className="text-[10px] uppercase tracking-widest text-gray-500 font-black">Choose Resolution / Quality</label>
                                        <select 
                                            value={selectedFormatId}
                                            onChange={(e) => setSelectedFormatId(e.target.value)}
                                            className="w-full bg-dark-900 text-white text-xs border border-white/10 rounded-lg px-3 py-2 outline-none focus:border-red-500/50 transition-colors"
                                        >
                                            {availableFormats.map(f => (
                                                <option key={f.format_id} value={f.format_id}>
                                                    {f.label}
                                                </option>
                                            ))}
                                        </select>
                                    </div>

                                    {/* Subtitle Selection Dropdown */}
                                    <div className="mt-3 space-y-2">
                                        <label className="text-[10px] uppercase tracking-widest text-gray-500 font-black flex items-center gap-1">
                                            <Subtitles className="w-3 h-3" /> Subtitles / Captions
                                        </label>
                                        <select 
                                            value={subtitles}
                                            onChange={(e) => setSubtitles(e.target.value)}
                                            className="w-full bg-dark-900 text-white text-xs border border-white/10 rounded-lg px-3 py-2 outline-none focus:border-red-500/50 transition-colors"
                                        >
                                            {availableSubtitleOptions.map(lang => (
                                                <option key={lang.code} value={lang.code}>
                                                    {lang.label}
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Format Selector - Toggle Style */}
                <div className="flex justify-center p-1 bg-dark-900/50 rounded-xl w-fit mx-auto border border-white/5 backdrop-blur-sm">
                    {['audio', 'video'].map((f) => (
                        <button
                            key={f}
                            onClick={() => setFormat(f)}
                            className={`flex items-center space-x-2 px-8 py-3 rounded-lg text-sm font-bold transition-all duration-300 relative ${
                                format === f 
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

            {/* Status Card */}
            <AnimatePresence>
                {(status === 'processing' || status === 'completed') && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="bg-dark-900/80 backdrop-blur-xl p-8 rounded-3xl border border-white/10 space-y-6 shadow-2xl relative overflow-hidden"
                    >
                        <div className="flex justify-between items-end relative z-10">
                            <div className="space-y-1 flex-1">
                                <span className="text-xs font-bold uppercase tracking-widest text-gray-500">Status</span>
                                <div className="flex items-center space-x-3">
                                    {status === 'processing' && <Loader2 className="w-4 h-4 text-primary-400 animate-spin" />}
                                    <span className={`font-bold text-lg ${status === 'completed' ? 'text-emerald-400' : 'text-white'} truncate`}>
                                        {status === 'completed' ? 'Success' : (currentStep || 'Initializing...')}
                                    </span>
                                </div>
                            </div>
                            <div className="flex items-center space-x-3">
                                {status === 'processing' && (
                                    <button
                                        onClick={handleCancelDownload}
                                        className="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 hover:text-red-300 rounded-lg text-xs font-bold transition-all flex items-center space-x-2 border border-red-500/20"
                                    >
                                        <X className="w-4 h-4" />
                                        <span>STOP</span>
                                    </button>
                                )}
                                <span className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-br from-white to-gray-600">
                                    {Math.round(progress)}%
                                </span>
                            </div>
                        </div>

                        <div className="h-4 bg-dark-800 rounded-full overflow-hidden p-1 border border-white/5 relative z-10 shadow-inner">
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${progress}%` }}
                                className={`h-full rounded-full shadow-lg relative overflow-hidden ${
                                    status === 'completed'
                                    ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                                    : 'bg-gradient-to-r from-red-600 to-primary-600'
                                    }`}
                            />
                        </div>

                        {status === 'completed' && (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="flex justify-center pt-2"
                            >
                                <div className="bg-emerald-500/20 text-emerald-300 px-6 py-2 rounded-full text-sm font-bold flex items-center space-x-2 border border-emerald-500/20 shadow-lg shadow-emerald-500/10">
                                    <CheckCircle className="w-4 h-4" />
                                    <span>Download Finished! Check Library.</span>
                                </div>
                            </motion.div>
                        )}
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
                                                    key={item.queue_id}
                                                    className="p-3 flex items-center justify-between hover:bg-white/5 transition-colors"
                                                >
                                                    <div className="flex items-center space-x-3 flex-1 min-w-0">
                                                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                                                            item.status === 'downloading' ? 'bg-red-600/20' :
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
                                                            <p className="text-white text-sm font-medium truncate">{item.url}</p>
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
                                                        <span className={`text-xs font-bold px-2 py-1 rounded ${
                                                            item.status === 'downloading' ? 'bg-red-600/20 text-red-400' :
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
