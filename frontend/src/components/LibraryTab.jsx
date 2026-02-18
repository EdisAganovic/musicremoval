import { useState, useEffect } from 'react';
import axios from 'axios';
import { LayoutGrid, Music, Video, FolderOpen, RefreshCw, Clock, HardDrive, FileAudio, Copy, PlayCircle, Trash2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const LibraryTab = () => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchLibrary = async () => {
        setLoading(true);
        try {
            const response = await axios.get('http://localhost:8000/api/library');
            setItems(response.data);
        } catch (err) {
            console.error("Failed to fetch library", err);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (taskId) => {
        if (!window.confirm("Jeste li sigurni da želite obrisati ovaj fajl iz biblioteke i sa diska?")) {
            return;
        }

        try {
            await axios.post('http://localhost:8000/api/delete-file', { task_id: taskId });
            // Refresh list after deletion
            fetchLibrary();
        } catch (err) {
            console.error("Failed to delete file", err);
            alert("Greška pri brisanju fajla.");
        }
    };

    useEffect(() => {
        fetchLibrary();
        
        // Auto-refresh every 10 seconds to catch new completions
        const interval = setInterval(() => {
            fetchLibrary();
        }, 10000);
        
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="space-y-8 max-w-4xl mx-auto pb-10">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-black text-white tracking-tight">Your Library</h2>
                    <p className="text-gray-500 text-sm font-medium">History of processed files</p>
                </div>
                <button 
                    onClick={fetchLibrary}
                    className="p-2 bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white rounded-xl transition-all border border-white/5 active:scale-95"
                >
                    <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
                </button>
            </div>

            {loading && items.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 space-y-4">
                    <Loader2 className="w-10 h-10 text-primary-500 animate-spin" />
                    <p className="text-gray-500 font-bold animate-pulse">Loading finished files...</p>
                </div>
            ) : items.length === 0 ? (
                <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex flex-col items-center justify-center py-32 bg-dark-900/50 rounded-3xl border border-white/5 border-dashed"
                >
                    <div className="p-5 rounded-full bg-white/5 mb-4">
                        <HardDrive className="w-8 h-8 text-gray-600" />
                    </div>
                    <p className="text-gray-500 font-bold">No finished files yet.</p>
                    <p className="text-gray-600 text-sm">Upload something to get started!</p>
                </motion.div>
            ) : (
                <div className="grid grid-cols-1 gap-4">
                    <AnimatePresence>
                        {items.map((item, idx) => (
                            <motion.div
                                key={item.task_id}
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, scale: 0.95 }}
                                transition={{ delay: idx * 0.05 }}
                                className="group relative bg-dark-800/80 backdrop-blur-xl border border-white/5 p-5 rounded-2xl flex items-center justify-between hover:border-primary-500/30 transition-all hover:shadow-2xl hover:shadow-primary-600/10"
                            >
                                <div className="flex items-center space-x-5">
                                    <div 
                                        className="w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg transition-transform group-hover:scale-110 duration-300 cursor-pointer overflow-hidden relative"
                                        onClick={async () => {
                                            try { await axios.post('http://localhost:8000/api/open-file', { path: item.result_files?.[0] }); }
                                            catch (err) { alert("Ne mogu otvoriti fajl."); }
                                        }}
                                    >
                                        <div className={`absolute inset-0 ${
                                            item.metadata?.is_video 
                                            ? 'bg-gradient-to-tr from-indigo-600 to-primary-500' 
                                            : 'bg-gradient-to-tr from-emerald-600 to-teal-500'
                                        }`} />
                                        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 bg-black/40 transition-opacity">
                                            <PlayCircle className="w-8 h-8 text-white fill-white/20" />
                                        </div>
                                        {item.metadata?.is_video ? (
                                            <Video className="w-7 h-7 text-white relative z-10" />
                                        ) : (
                                            <Music className="w-7 h-7 text-white relative z-10" />
                                        )}
                                    </div>
                                    <div className="space-y-1 group/text">
                                        <h3 
                                            className="text-white font-bold text-lg hover:text-primary-400 transition-colors truncate max-w-sm cursor-pointer"
                                            onClick={async () => {
                                                try { await axios.post('http://localhost:8000/api/open-file', { path: item.result_files?.[0] }); }
                                                catch (err) { alert("Ne mogu otvoriti fajl."); }
                                            }}
                                            title="Click to play"
                                        >
                                            {item.result_files?.[0]?.split(/[\\/]/).pop() || 'Untitled Job'}
                                        </h3>
                                        <div className="flex flex-col space-y-1">
                                            <div className="flex items-center space-x-4 text-xs font-bold uppercase tracking-wider text-gray-500">
                                                <span className="flex items-center space-x-1">
                                                    <Clock className="w-3 h-3" />
                                                    <span>{item.metadata?.duration || 'N/A'}</span>
                                                </span>
                                                {item.metadata?.resolution && item.metadata.resolution !== 'N/A' && (
                                                    <span className="flex items-center space-x-1">
                                                        <LayoutGrid className="w-3 h-3" />
                                                        <span>{item.metadata.resolution}</span>
                                                    </span>
                                                )}
                                                <span className="bg-white/5 px-2 py-0.5 rounded text-[10px] text-gray-400">
                                                    {item.metadata?.audio_codec || 'N/A'}
                                                    {item.metadata?.is_video && item.metadata?.video_codec && item.metadata.video_codec !== 'N/A' && ` / ${item.metadata.video_codec}`}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-center space-x-3">
                                    <button 
                                        className="p-3 bg-primary-600/10 hover:bg-primary-600 text-primary-400 hover:text-white rounded-xl transition-all border border-primary-500/20 shadow-lg shadow-primary-500/5 group/play active:scale-95"
                                        onClick={async () => {
                                            try { await axios.post('http://localhost:8000/api/open-file', { path: item.result_files?.[0] }); }
                                            catch (err) { alert("Ne mogu otvoriti fajl."); }
                                        }}
                                        title="Pokreni fajl"
                                    >
                                        <PlayCircle className="w-5 h-5 transition-transform group-hover/play:scale-125" />
                                    </button>
                                    <button 
                                        className="p-3 bg-dark-900/80 hover:bg-dark-700 text-gray-400 hover:text-white rounded-xl transition-all border border-white/5 shadow-inner flex items-center space-x-2 font-bold text-sm group/folder active:scale-95"
                                        onClick={async () => {
                                            try {
                                                await axios.post('http://localhost:8000/api/open-folder', { path: item.result_files?.[0] });
                                            } catch (err) {
                                                alert("Ne mogu otvoriti folder.");
                                            }
                                        }}
                                        title="Otvori u folderu"
                                    >
                                        <FolderOpen className="w-4 h-4 transition-transform group-hover/folder:scale-110" />
                                        <span className="hidden md:inline">Folder</span>
                                    </button>
                                    <button 
                                        className="p-3 bg-red-500/10 hover:bg-red-500 text-red-500/70 hover:text-white rounded-xl transition-all border border-red-500/20 active:scale-90 group/delete"
                                        onClick={() => handleDelete(item.task_id)}
                                        title="Obriši fajl"
                                    >
                                        <Trash2 className="w-4 h-4 transition-transform group-hover/delete:scale-110" />
                                    </button>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                </div>
            )}
        </div>
    );
};

const Loader2 = ({ className }) => (
    <motion.svg 
        className={className} 
        viewBox="0 0 24 24" 
        fill="none" 
        stroke="currentColor" 
        strokeWidth="2" 
        strokeLinecap="round" 
        strokeLinejoin="round"
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
    >
        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </motion.svg>
);

export default LibraryTab;
