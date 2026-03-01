import { useState, useEffect } from 'react';
import axios from 'axios';
import { LayoutGrid, Music, Video, FolderOpen, RefreshCw, Clock, HardDrive, FileAudio, Copy, PlayCircle, Trash2, Layers, Search, CheckSquare, Square } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const LibraryTab = ({ onSeparate }) => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedItems, setSelectedItems] = useState([]);
    const [sortBy, setSortBy] = useState('date'); // date, size, duration

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

    const handleBulkDelete = async () => {
        if (selectedItems.length === 0) return;
        
        if (!window.confirm(`Jeste li sigurni da želite obrisati ${selectedItems.length} fajl(ova)?`)) {
            return;
        }

        try {
            for (const taskId of selectedItems) {
                await axios.post('http://localhost:8000/api/delete-file', { task_id: taskId });
            }
            setSelectedItems([]);
            fetchLibrary();
        } catch (err) {
            console.error("Failed to bulk delete", err);
            alert("Greška pri brisanju fajlova.");
        }
    };

    const toggleSelect = (taskId) => {
        setSelectedItems(prev => 
            prev.includes(taskId) 
                ? prev.filter(id => id !== taskId)
                : [...prev, taskId]
        );
    };

    const selectAll = () => {
        if (selectedItems.length === filteredItems.length) {
            setSelectedItems([]);
        } else {
            setSelectedItems(filteredItems.map(item => item.task_id));
        }
    };

    // Filter and sort items
    const filteredItems = items.filter(item => {
        const filename = (item.result_files?.[0] || '').toLowerCase();
        const query = searchQuery.toLowerCase();
        return filename.includes(query) || 
               (item.metadata?.duration || '').toLowerCase().includes(query);
    }).sort((a, b) => {
        if (sortBy === 'date') {
            // Sort by task_id (contains timestamp)
            return b.task_id.localeCompare(a.task_id);
        } else if (sortBy === 'duration') {
            const durA = parseFloat(a.metadata?.duration) || 0;
            const durB = parseFloat(b.metadata?.duration) || 0;
            return durB - durA;
        }
        return 0;
    });

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
            {/* Header with Search */}
            <div className="space-y-4">
                <div className="flex justify-between items-center">
                    <div>
                        <h2 className="text-2xl font-black text-white tracking-tight">Your Library</h2>
                        <p className="text-gray-500 text-sm font-medium">
                            {filteredItems.length} files {selectedItems.length > 0 && `• ${selectedItems.length} selected`}
                        </p>
                    </div>
                    <button
                        onClick={fetchLibrary}
                        className="p-2 bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white rounded-xl transition-all border border-white/5 active:scale-95"
                    >
                        <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>

                {/* Search and Controls */}
                <div className="flex gap-3 flex-wrap">
                    {/* Search Input */}
                    <div className="flex-1 min-w-64 relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Search files..."
                            className="w-full bg-dark-800 text-white text-sm border border-white/10 rounded-xl pl-10 pr-4 py-2.5 outline-none focus:border-primary-500/50 transition-colors"
                        />
                    </div>

                    {/* Sort Dropdown */}
                    <select
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value)}
                        className="bg-dark-800 text-white text-sm border border-white/10 rounded-xl px-4 py-2.5 outline-none focus:border-primary-500/50 transition-colors cursor-pointer"
                    >
                        <option value="date">Sort by Date</option>
                        <option value="duration">Sort by Duration</option>
                    </select>

                    {/* Select All */}
                    <button
                        onClick={selectAll}
                        className="px-4 py-2.5 bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white text-sm font-bold rounded-xl transition-all border border-white/10 flex items-center gap-2"
                    >
                        {selectedItems.length === filteredItems.length && filteredItems.length > 0 ? (
                            <>
                                <CheckSquare className="w-4 h-4" />
                                <span>Deselect All</span>
                            </>
                        ) : (
                            <>
                                <Square className="w-4 h-4" />
                                <span>Select All</span>
                            </>
                        )}
                    </button>

                    {/* Bulk Delete */}
                    {selectedItems.length > 0 && (
                        <button
                            onClick={handleBulkDelete}
                            className="px-4 py-2.5 bg-red-600/20 hover:bg-red-600/30 text-red-400 hover:text-red-300 text-sm font-bold rounded-xl transition-all border border-red-500/20 flex items-center gap-2"
                        >
                            <Trash2 className="w-4 h-4" />
                            <span>Delete {selectedItems.length}</span>
                        </button>
                    )}
                </div>
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
                        {filteredItems.map((item, idx) => (
                            <motion.div
                                key={item.task_id}
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, scale: 0.95 }}
                                transition={{ delay: idx * 0.05 }}
                                className={`group relative bg-dark-800/80 backdrop-blur-xl border p-5 rounded-2xl flex items-center justify-between transition-all hover:shadow-2xl ${
                                    selectedItems.includes(item.task_id)
                                        ? 'border-primary-500/50 bg-primary-500/5 shadow-primary-600/10'
                                        : 'border-white/5 hover:border-primary-500/30'
                                }`}
                            >
                                {/* Checkbox */}
                                <div className="absolute left-4 top-1/2 -translate-y-1/2">
                                    <input
                                        type="checkbox"
                                        checked={selectedItems.includes(item.task_id)}
                                        onChange={() => toggleSelect(item.task_id)}
                                        className="w-5 h-5 rounded border-gray-600 bg-dark-700 text-primary-500 focus:ring-primary-500 focus:ring-2 cursor-pointer"
                                    />
                                </div>
                                
                                <div className="flex items-center space-x-5 pl-10">
                                    <div
                                        className="w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg transition-transform group-hover:scale-110 duration-300 cursor-pointer overflow-hidden relative bg-gradient-to-tr from-indigo-600 to-primary-500"
                                        onClick={async () => {
                                            try { await axios.post('http://localhost:8000/api/open-file', { path: item.result_files?.[0] }); }
                                            catch (err) { alert("Ne mogu otvoriti fajl."); }
                                        }}
                                    >
                                        {item.metadata?.is_video ? (
                                            <Video className="w-7 h-7 text-white" />
                                        ) : (
                                            <Music className="w-7 h-7 text-white" />
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
                                        className="p-3 bg-emerald-600/10 hover:bg-emerald-600 text-emerald-400 hover:text-white rounded-xl transition-all border border-emerald-500/20 shadow-lg shadow-emerald-500/5 group/separate active:scale-95"
                                        onClick={() => {
                                            if (onSeparate) {
                                                onSeparate(item.result_files?.[0]);
                                            }
                                        }}
                                        title="Separiraj vokale"
                                    >
                                        <Layers className="w-5 h-5 transition-transform group-hover/separate:scale-110" />
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
