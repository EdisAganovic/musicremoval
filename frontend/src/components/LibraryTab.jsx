import { useState, useEffect } from 'react';
import { libraryAPI } from '../api/index.js';
import { Video, Music, FolderOpen, Trash2, Layers, Search, CheckSquare, Square, PlayCircle, Download } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const LibraryTab = ({ onSeparate }) => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedItems, setSelectedItems] = useState([]);
    const [sortBy, setSortBy] = useState('date');
    const [folderFilter, setFolderFilter] = useState('all'); // 'all', 'download', 'nomusic'

    const fetchLibrary = async () => {
        setLoading(true);
        try {
            const response = await libraryAPI.get();
            setItems(response.data);
        } catch (err) {
            console.error("Failed to fetch library", err);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (taskId) => {
        if (!window.confirm("Are you sure you want to delete this file from library and disk?")) {
            return;
        }

        try {
            await libraryAPI.delete(taskId);
            fetchLibrary();
        } catch (err) {
            console.error("Failed to delete file", err);
            alert("Error deleting file.");
        }
    };

    const handleBulkDelete = async () => {
        if (selectedItems.length === 0) return;

        if (!window.confirm(`Are you sure you want to delete ${selectedItems.length} file(s)?`)) {
            return;
        }

        try {
            for (const taskId of selectedItems) {
                await libraryAPI.delete(taskId);
            }
            setSelectedItems([]);
            fetchLibrary();
        } catch (err) {
            console.error("Failed to bulk delete", err);
            alert("Error deleting files.");
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

    const openFolder = async (folderName) => {
        try {
            await libraryAPI.openFolder(folderName);
        } catch (err) {
            alert(`Cannot open ${folderName} folder.`);
        }
    };

    // Filter and sort items
    const filteredItems = items.filter(item => {
        const filename = (item.result_files?.[0] || '').toLowerCase();
        const query = searchQuery.toLowerCase();
        
        // Folder filter
        if (folderFilter === 'download' && !filename.includes('download')) return false;
        if (folderFilter === 'nomusic' && !filename.includes('nomusic')) return false;
        
        return filename.includes(query);
    }).sort((a, b) => {
        if (sortBy === 'date') {
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
        const interval = setInterval(() => {
            fetchLibrary();
        }, 10000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="space-y-4 max-w-5xl mx-auto">
            {/* Folder Filter & Actions */}
            <div className="flex gap-2 items-center justify-between flex-wrap">
                {/* Folder Filter Buttons */}
                <div className="flex gap-2">
                    <button
                        onClick={() => setFolderFilter('all')}
                        className={`px-4 py-2 rounded-lg text-sm font-bold transition-all border ${
                            folderFilter === 'all'
                                ? 'bg-primary-600/20 text-primary-400 border-primary-500/50'
                                : 'bg-dark-800 text-gray-400 hover:text-white border-transparent'
                        }`}
                    >
                        All Files
                    </button>
                    <button
                        onClick={() => setFolderFilter('download')}
                        className={`px-4 py-2 rounded-lg text-sm font-bold transition-all border flex items-center gap-2 ${
                            folderFilter === 'download'
                                ? 'bg-red-600/20 text-red-400 border-red-500/50'
                                : 'bg-dark-800 text-gray-400 hover:text-white border-transparent'
                        }`}
                    >
                        <Download className="w-3.5 h-3.5" />
                        Download
                    </button>
                    <button
                        onClick={() => setFolderFilter('nomusic')}
                        className={`px-4 py-2 rounded-lg text-sm font-bold transition-all border flex items-center gap-2 ${
                            folderFilter === 'nomusic'
                                ? 'bg-emerald-600/20 text-emerald-400 border-emerald-500/50'
                                : 'bg-dark-800 text-gray-400 hover:text-white border-transparent'
                        }`}
                    >
                        <FolderOpen className="w-3.5 h-3.5" />
                        NoMusic
                    </button>
                </div>

                {/* Open Folder Actions */}
                <div className="flex gap-2">
                    <button
                        onClick={() => openFolder('download')}
                        className="px-3 py-2 bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white text-xs font-bold rounded-lg transition-all border border-white/10 flex items-center gap-2"
                        title="Open download folder"
                    >
                        <FolderOpen className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Open Download</span>
                    </button>
                    <button
                        onClick={() => openFolder('nomusic')}
                        className="px-3 py-2 bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white text-xs font-bold rounded-lg transition-all border border-white/10 flex items-center gap-2"
                        title="Open nomusic folder"
                    >
                        <FolderOpen className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Open NoMusic</span>
                    </button>
                </div>
            </div>

            {/* Header with Search */}
            <div className="flex gap-3 flex-wrap items-center">
                {/* Search Input */}
                <div className="flex-1 min-w-64 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search files..."
                        className="w-full bg-dark-800 text-white text-sm border border-white/10 rounded-lg pl-10 pr-4 py-2 outline-none focus:border-primary-500/50 transition-colors"
                    />
                </div>

                {/* Sort Dropdown */}
                <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="bg-dark-800 text-white text-sm border border-white/10 rounded-lg px-3 py-2 outline-none focus:border-primary-500/50 transition-colors cursor-pointer"
                >
                    <option value="date">Date</option>
                    <option value="duration">Duration</option>
                </select>

                {/* Select All */}
                <button
                    onClick={selectAll}
                    className="px-3 py-2 bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white text-sm font-bold rounded-lg transition-all border border-white/10 flex items-center gap-2"
                >
                    {selectedItems.length === filteredItems.length && filteredItems.length > 0 ? (
                        <CheckSquare className="w-4 h-4" />
                    ) : (
                        <Square className="w-4 h-4" />
                    )}
                </button>

                {/* Bulk Delete */}
                {selectedItems.length > 0 && (
                    <button
                        onClick={handleBulkDelete}
                        className="px-3 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 hover:text-red-300 text-sm font-bold rounded-lg transition-all border border-red-500/20 flex items-center gap-2"
                    >
                        <Trash2 className="w-4 h-4" />
                        <span>Delete {selectedItems.length}</span>
                    </button>
                )}

                {/* Refresh */}
                <button
                    onClick={fetchLibrary}
                    className="p-2 bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white rounded-lg transition-all border border-white/5"
                >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                    </svg>
                </button>
            </div>

            {/* Table */}
            {loading && items.length === 0 ? (
                <div className="text-center py-10 text-gray-500">Loading...</div>
            ) : items.length === 0 ? (
                <div className="text-center py-20 bg-dark-900/50 rounded-lg border border-white/5">
                    <p className="text-gray-500 text-sm">No files yet</p>
                </div>
            ) : (
                <div className="overflow-hidden rounded-lg border border-white/10 shadow-xl">
                    <table className="w-full">
                        <thead className="bg-dark-900/80 border-b border-white/10">
                            <tr className="text-xs font-bold uppercase tracking-wider text-gray-400">
                                <th className="px-4 py-2.5 text-left w-10">
                                    <input
                                        type="checkbox"
                                        checked={selectedItems.length === filteredItems.length && filteredItems.length > 0}
                                        onChange={selectAll}
                                        className="w-4 h-4 rounded border-gray-600 bg-dark-700 text-primary-500 focus:ring-primary-500 cursor-pointer"
                                    />
                                </th>
                                <th className="px-4 py-2.5 text-left">File</th>
                                <th className="px-4 py-2.5 text-left w-24">Duration</th>
                                <th className="px-4 py-2.5 text-left w-28">Quality</th>
                                <th className="px-4 py-2.5 text-right w-40">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                            {filteredItems.map((item) => (
                                <motion.tr
                                    key={item.task_id}
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className={`transition-all ${
                                        selectedItems.includes(item.task_id)
                                            ? 'bg-primary-500/5'
                                            : 'bg-dark-800/40 hover:bg-dark-800/60'
                                    }`}
                                >
                                    <td className="px-4 py-2">
                                        <input
                                            type="checkbox"
                                            checked={selectedItems.includes(item.task_id)}
                                            onChange={() => toggleSelect(item.task_id)}
                                            className="w-4 h-4 rounded border-gray-600 bg-dark-700 text-primary-500 focus:ring-primary-500 cursor-pointer"
                                        />
                                    </td>
                                    <td className="px-4 py-2">
                                        <div className="flex items-center space-x-3">
                                            <div
                                                className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 cursor-pointer bg-gradient-to-tr from-indigo-600 to-primary-500"
                                                onClick={() => libraryAPI.openFile(item.result_files?.[0]).catch(() => alert("Cannot open file."))}
                                            >
                                                {item.metadata?.is_video ? (
                                                    <Video className="w-4 h-4 text-white" />
                                                ) : (
                                                    <Music className="w-4 h-4 text-white" />
                                                )}
                                            </div>
                                            <span className="text-sm font-medium text-white truncate max-w-md">
                                                {item.result_files?.[0]?.split(/[\\/]/).pop() || 'Untitled'}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-4 py-2">
                                        <span className="text-xs text-gray-400">{item.metadata?.duration || 'N/A'}</span>
                                    </td>
                                    <td className="px-4 py-2">
                                        <div className="flex items-center space-x-1">
                                            {item.metadata?.resolution && item.metadata.resolution !== 'N/A' && (
                                                <span className="bg-dark-700 px-1.5 py-0.5 rounded text-xs text-gray-400">{item.metadata.resolution}</span>
                                            )}
                                            <span className="bg-dark-700 px-1.5 py-0.5 rounded text-xs text-gray-400">{item.metadata?.audio_codec || 'N/A'}</span>
                                        </div>
                                    </td>
                                    <td className="px-4 py-2">
                                        <div className="flex items-center justify-end space-x-1">
                                            <button
                                                className="p-1.5 bg-primary-600/10 hover:bg-primary-600 text-primary-400 hover:text-white rounded transition-all"
                                                onClick={() => libraryAPI.openFile(item.result_files?.[0]).catch(() => alert("Cannot open file."))}
                                                title="Play"
                                            >
                                                <PlayCircle className="w-3.5 h-3.5" />
                                            </button>
                                            {/* Show Separate button only for files from download folder */}
                                            {!item.result_files?.[0].toLowerCase().includes('nomusic') && (
                                                <button
                                                    className="p-1.5 bg-emerald-600/10 hover:bg-emerald-600 text-emerald-400 hover:text-white rounded transition-all"
                                                    onClick={() => onSeparate?.(item.result_files?.[0])}
                                                    title="Separate vocals"
                                                >
                                                    <Layers className="w-3.5 h-3.5" />
                                                </button>
                                            )}
                                            <button
                                                className="p-1.5 bg-dark-700 hover:bg-dark-600 text-gray-400 hover:text-white rounded transition-all"
                                                onClick={() => libraryAPI.openFolder(item.result_files?.[0]).catch(() => alert("Cannot open folder."))}
                                                title="Folder"
                                            >
                                                <FolderOpen className="w-3.5 h-3.5" />
                                            </button>
                                            <button
                                                className="p-1.5 bg-red-500/10 hover:bg-red-500 text-red-400 hover:text-white rounded transition-all"
                                                onClick={() => handleDelete(item.task_id)}
                                                title="Delete"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    </td>
                                </motion.tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default LibraryTab;
