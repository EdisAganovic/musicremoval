import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { UploadCloud, CheckCircle, AlertCircle, PlayCircle, FolderOpen, Loader2, Copy, RefreshCw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const SeparationTab = () => {
    const [file, setFile] = useState(null);
    const [dragging, setDragging] = useState(false);
    const [taskId, setTaskId] = useState(null);
    const [status, setStatus] = useState(null); // 'idle', 'uploading', 'processing', 'completed', 'error'
    const [progress, setProgress] = useState(0);
    const [currentStep, setCurrentStep] = useState('');
    const [error, setError] = useState(null);
    const [resultFiles, setResultFiles] = useState([]);
    const [model, setModel] = useState('both');
    const [metadata, setMetadata] = useState(null);

    const fileInputRef = useRef(null);

    const handleReset = () => {
        setFile(null);
        setTaskId(null);
        setStatus(null);
        setProgress(0);
        setCurrentStep('');
        setError(null);
        setResultFiles([]);
        setMetadata(null);
    };

    // Polling effect
    useEffect(() => {
        let interval;
        if (taskId && (status === 'processing')) {
            interval = setInterval(async () => {
                try {
                    const response = await axios.get(`http://localhost:8000/api/status/${taskId}`);
                    const data = response.data;
                    
                    setProgress(data.progress);
                    setCurrentStep(data.currentStep || data.current_step);
                    setStatus(data.status);
                    
                    if (data.metadata) {
                        setMetadata(data.metadata);
                    }
                    
                    if (data.status === 'completed') {
                        setResultFiles(data.result_files || data.resultFiles || []);
                        clearInterval(interval);
                    } else if (data.status === 'failed' || data.status === 'error') {
                        setError('Process failed: Check backend logs.');
                        clearInterval(interval);
                        setStatus('error');
                    }
                } catch (err) {
                    console.error("Polling error", err);
                }
            }, 1000);
        }
        return () => clearInterval(interval);
    }, [taskId, status]);

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setError(null);
            setStatus('idle');
            setProgress(0);
            setResultFiles([]);
        }
    };

    const handleUpload = async () => {
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);
        formData.append('model', model);

        setStatus('uploading');
        setCurrentStep('Transferring file...');
        setProgress(0);

        try {
            const response = await axios.post('http://localhost:8000/api/separate', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
                onUploadProgress: (progressEvent) => {
                    const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
                    if (percentCompleted < 100) {
                        setProgress(percentCompleted);
                    } else {
                        setCurrentStep('Upload complete. Queuing task...');
                    }
                }
            });
            
            setTaskId(response.data.task_id);
            if (response.data.metadata) {
                setMetadata(response.data.metadata);
            }
            setStatus('processing');
        } catch (err) {
            console.error(err);
            setError('Failed to contact server. Is backend running?');
            setStatus('error');
        }
    };

    const handleDragOver = (e) => { e.preventDefault(); setDragging(true); };
    const handleDragLeave = (e) => { e.preventDefault(); setDragging(false); };
    const handleDrop = (e) => {
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            setFile(e.dataTransfer.files[0]);
            setError(null);
            setStatus('idle');
        }
    };

    return (
        <div className="space-y-8 max-w-3xl mx-auto">
            
            {/* Model Selection */}
            <div className="flex justify-center space-x-4 mb-6">
                {['spleeter', 'demucs', 'both'].map((m) => (
                    <button
                        key={m}
                        onClick={() => setModel(m)}
                        className={`px-5 py-2 rounded-lg text-sm font-medium transition-all duration-200 border border-transparent ${
                            model === m 
                            ? 'bg-primary-600/20 text-primary-400 border-primary-500/50 shadow-lg shadow-primary-500/10' 
                            : 'bg-dark-800 text-gray-400 hover:text-white hover:bg-dark-700'
                        }`}
                    >
                        <span className="capitalize">{m}</span> {(m === 'both') && '(Recommended)'}
                    </button>
                ))}
            </div>

            {/* Drop Zone */}
            <motion.div 
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
                className={`relative group rounded-2xl border-2 border-dashed p-10 transition-all duration-300 cursor-pointer overflow-hidden
                    ${dragging 
                        ? 'border-primary-500 bg-primary-500/10' 
                        : 'border-white/10 hover:border-primary-400/50 hover:bg-white/5'
                    } ${file ? 'bg-gradient-to-br from-dark-800 to-dark-900 border-primary-500/30' : ''}`}
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
                                    <h3 className="text-xl font-bold text-white tracking-tight">{file.name}</h3>
                                    <p className="text-sm text-primary-400 font-mono mt-1">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                                </div>
                                {status === 'idle' && (
                                    <button 
                                        onClick={(e) => { e.stopPropagation(); setFile(null); }}
                                        className="text-xs text-red-400 hover:text-red-300 underline underline-offset-4 decoration-red-400/30 hover:decoration-red-300"
                                    >
                                        Remove File
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
                                    Supports MP3, WAV, FLAC, MP4, MKV. Max file size: 500MB recommended.
                                </p>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
                
                {/* Background Glow Effect */}
                <div className={`absolute inset-0 bg-primary-500/5 rounded-2xl transition-opacity duration-500 pointer-events-none ${dragging ? 'opacity-100' : 'opacity-0'}`} />
            </motion.div>

            {/* File Info / Metadata Card */}
            <AnimatePresence>
                {metadata && (
                    <motion.div
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="grid grid-cols-2 md:grid-cols-4 gap-4"
                    >
                        {[
                            { label: 'Duration', value: metadata.duration, icon: '🕒' },
                            { label: 'Resolution', value: metadata.resolution, icon: '📺', hidden: !metadata.is_video },
                            { label: 'Audio Codec', value: metadata.audio_codec, icon: '🎵' },
                            { label: 'Video Codec', value: metadata.video_codec, icon: '🎞️', hidden: !metadata.is_video },
                        ].map((item, idx) => !item.hidden && (
                            <div key={idx} className="bg-dark-800/50 border border-white/5 p-4 rounded-xl backdrop-blur-sm shadow-lg">
                                <div className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-1 flex items-center space-x-2">
                                    <span>{item.icon}</span>
                                    <span>{item.label}</span>
                                </div>
                                <div className="text-sm font-black text-white truncate">{item.value || 'Unknown'}</div>
                            </div>
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Error Message */}
            <AnimatePresence>
                {error && (
                    <motion.div 
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="bg-red-500/10 border border-red-500/20 text-red-200 p-4 rounded-xl flex items-center space-x-3 backdrop-blur-sm"
                    >
                        <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
                        <span className="font-medium text-sm">{error}</span>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Start Button */}
            <div className="flex justify-center">
                <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={handleUpload}
                    disabled={!file || status === 'uploading' || status === 'processing'}
                    className={`
                        relative overflow-hidden px-10 py-4 rounded-full font-bold text-lg shadow-2xl transition-all duration-300 group
                        ${!file || status === 'uploading' || status === 'processing'
                            ? 'bg-dark-700 text-gray-500 cursor-not-allowed opacity-50'
                            : 'bg-gradient-to-r from-primary-600 to-accent-600 text-white shadow-primary-500/25 hover:shadow-primary-500/40'
                        }
                    `}
                >
                    <span className="relative z-10 flex items-center space-x-3">
                        {status === 'processing' || status === 'uploading' ? (
                            <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (
                            <PlayCircle className="w-5 h-5" />
                        )}
                        <span>{status === 'processing' ? 'Processing...' : 'Start Separation'}</span>
                    </span>
                    {/* Button Shine Effect */}
                    <div className="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-1000 bg-gradient-to-r from-transparent via-white/20 to-transparent skew-x-12" />
                </motion.button>
            </div>

            {/* Progress Bar - Only visible when active */}
            <AnimatePresence>
                {(status === 'uploading' || status === 'processing' || status === 'completed') && (
                    <motion.div 
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 20 }}
                        className="bg-dark-900/50 backdrop-blur rounded-2xl p-6 border border-white/5 space-y-4 shadow-xl"
                    >
                        <div className="flex justify-between items-end">
                            <div className="flex flex-col">
                                <span className="text-xs uppercase tracking-wider text-gray-500 font-bold mb-1">Status</span>
                                <span className="text-gray-200 font-medium flex items-center space-x-2">
                                    {status === 'completed' 
                                        ? <span className="text-emerald-400 flex items-center"><CheckCircle className="w-4 h-4 mr-1"/> Finished</span> 
                                        : <span className="animate-pulse text-primary-400">{currentStep || 'Initializing...'}</span>}
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
                                transition={{ type: 'spring', stiffness: 50, damping: 20 }}
                                className={`h-full rounded-full relative overflow-hidden transition-colors duration-500 ${
                                    status === 'completed' ? 'bg-emerald-500' : 'bg-gradient-to-r from-primary-500 to-accent-500'
                                }`}
                            >
                                <div className="absolute inset-0 bg-white/20 animate-[shimmer_2s_infinite]" style={{ backgroundImage: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent)' }}></div>
                            </motion.div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Success Message */}
            <AnimatePresence>
                {status === 'completed' && (
                    <motion.div 
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-6 text-center space-y-4 backdrop-blur-md"
                    >
                        <div className="w-12 h-12 bg-emerald-500 rounded-full flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/30">
                            <CheckCircle className="w-6 h-6 text-white" />
                        </div>
                        <div>
                            <h4 className="text-xl font-bold text-white">Separation Successful!</h4>
                            <p className="text-emerald-200/80 text-sm mt-1">Your files are ready in the output directory.</p>
                        </div>
                        <div className="flex flex-col items-center space-y-4 pt-2">
                             <div className="flex justify-center space-x-3">
                                 <button 
                                     onClick={async () => {
                                         try {
                                             await axios.post('http://localhost:8000/api/open-file', { path: resultFiles[0] });
                                         } catch (err) {
                                             alert("Ne mogu otvoriti fajl.");
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
                                             await axios.post('http://localhost:8000/api/open-folder', { path: resultFiles[0] });
                                         } catch (err) {
                                             alert("Ne mogu otvoriti folder.");
                                         }
                                     }}
                                     className="px-6 py-3 bg-dark-800 hover:bg-dark-700 text-white rounded-xl text-sm font-bold transition-all border border-white/5 active:scale-95 flex items-center space-x-2"
                                 >
                                     <FolderOpen className="w-4 h-4" />
                                     <span>OTVORI FOLDER</span>
                                 </button>
                             </div>
                             
                             <button 
                                onClick={handleReset}
                                className="flex items-center space-x-2 text-xs font-bold text-gray-500 hover:text-primary-400 transition-colors uppercase tracking-widest pt-2 group"
                             >
                                <RefreshCw className="w-3 h-3 group-hover:rotate-180 transition-transform duration-500" />
                                <span>Odaberi novi fajl / Restart</span>
                             </button>
                         </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default SeparationTab;
