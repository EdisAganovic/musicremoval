import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { libraryAPI } from '../api/index.js';
import { Video, Music, FolderOpen, Trash2, Layers, Search, CheckSquare, Square, PlayCircle, Download, RefreshCw, Loader2, AlertCircle } from 'lucide-react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { motion, AnimatePresence } from 'framer-motion';

const BACKEND_URL = 'http://127.0.0.1:5170';

const LibraryTab = ({ onSeparate }) => {
    const [items, setItems] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedItems, setSelectedItems] = useState([]);
    const [sortBy, setSortBy] = useState('date');
    const [folderFilter, setFolderFilter] = useState('all'); // 'all', 'download', 'nomusic'
    const [folderSizes, setFolderSizes] = useState({ download: '0 MB', nomusic: '0 MB' });
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    
    // Modal state for delete confirmations
    const [deleteConfirm, setDeleteConfirm] = useState(null); // { type: 'single' | 'bulk', id?: string, path?: string, count?: number }
    
    // Context menu state
    const [contextMenu, setContextMenu] = useState(null); // { x, y, item }

    // Refs for cleanup
    const abortControllerRef = useRef(null);
    const sizeAbortRef = useRef(null);
    const searchInputRef = useRef(null);

    const fetchLibrary = async () => {
        setIsRefreshing(true);
        setIsLoading(true);
        // Cancel previous request if still pending
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        try {
            const response = await libraryAPI.get({ signal: abortControllerRef.current.signal });
            setItems(response.data || []);
            setIsLoading(false);
            setIsRefreshing(false);
        } catch (err) {
            // Silently ignore abort errors (expected when switching tabs)
            if (err.name === 'AbortError' || err.name === 'CanceledError') {
                return;
            }
            console.error("Failed to fetch library", err);
            setIsLoading(false);
            setIsRefreshing(false);
        }
    };

    const fetchFolderSizes = async () => {
        // Cancel previous request if still pending
        if (sizeAbortRef.current) {
            sizeAbortRef.current.abort();
        }
        sizeAbortRef.current = new AbortController();

        try {
            const response = await axios.get(`${BACKEND_URL}/api/system-info`, {
                signal: sizeAbortRef.current.signal
            });
            setFolderSizes({
                download: response.data.storage.download_size,
                nomusic: response.data.storage.output_size
            });
        } catch (err) {
            // Silently ignore abort errors (expected when switching tabs)
            if (err.name === 'AbortError' || err.name === 'CanceledError') {
                return;
            }
            // Only log actual errors
            console.error("Failed to fetch folder sizes", err);
        }
    };

    // Close context menu on outside click
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (contextMenu) {
                setContextMenu(null);
            }
        };
        document.addEventListener('click', handleClickOutside);
        return () => document.removeEventListener('click', handleClickOutside);
    }, [contextMenu]);

    // Handle context menu positioning
    const handleContextMenu = (e, item) => {
        e.preventDefault();
        const menuWidth = 200;
        const menuHeight = 280;
        
        // Use clientX/clientY for viewport-relative position
        let x = e.clientX;
        let y = e.clientY;
        
        // If menu would go off right edge, position it to the left of cursor
        if (x + menuWidth > window.innerWidth) {
            x = x - menuWidth;
        }
        
        // If menu would go off bottom edge, position it above cursor
        if (y + menuHeight > window.innerHeight) {
            y = y - menuHeight;
        }
        
        // Ensure minimum margins
        x = Math.max(10, x);
        y = Math.max(10, y);
        
        setContextMenu({ x, y, item });
    };

    const handleRefresh = async () => {
        await fetchLibrary();
        await fetchFolderSizes();
    };

    const executeDelete = async (taskId, filePath) => {
        try {
            // Find the item being deleted
            const itemToDelete = items.find(item => item.task_id === taskId);
            
            // Optimistically remove from UI immediately
            setItems(prev => prev.filter(item => item.task_id !== taskId && item.result_files?.[0] !== filePath));

            await libraryAPI.delete(taskId, filePath);

            // Show success toast with undo
            const fileName = filePath?.split(/[\\/]/).pop() || 'File';
            toast.success(`Deleted "${fileName}"`);
        } catch (err) {
            console.error("Failed to delete file", err);
            toast.error("Failed to delete file");
            // Reload library to restore correct state if delete failed
            await fetchLibrary();
        }
    };

    const handleDelete = (taskId, filePath) => {
        setDeleteConfirm({ type: 'single', id: taskId, path: filePath });
    };

    const executeBulkDelete = async () => {
        try {
            // Store deleted items for potential undo
            const deletedItems = items.filter(item => selectedItems.includes(item.task_id));
            
            // Optimistically remove from UI immediately
            setItems(prev => prev.filter(item => !selectedItems.includes(item.task_id)));
            setSelectedItems([]);

            // Delete files
            for (const item of items) {
                if (selectedItems.includes(item.task_id)) {
                    const filePath = item.result_files?.[0];
                    await libraryAPI.delete(item.task_id, filePath);
                }
            }

            // Then fetch fresh data to ensure consistency
            await fetchLibrary();

            // Show success toast
            toast.success(`Deleted ${deletedItems.length} file${deletedItems.length !== 1 ? 's' : ''}`);

            // If current filter has no files left, switch to "All Files"
            if (filteredItems.length === selectedItems.length) {
                setFolderFilter('all');
            }
        } catch (err) {
            console.error("Failed to bulk delete", err);
            toast.error("Failed to delete files");
            // Reload library to restore correct state if delete failed
            await fetchLibrary();
        }
    };

    const handleBulkDelete = () => {
        if (selectedItems.length === 0) return;
        setDeleteConfirm({ type: 'bulk', count: selectedItems.length });
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
            toast.error(`Cannot open ${folderName} folder.`);
        }
    };

    // Filter and sort items
    const filteredItems = items.filter(item => {
        const filePath = (item.result_files?.[0] || '').toLowerCase();
        // Normalize path separators for cross-platform compatibility
        const normalizedPath = filePath.replace(/\\/g, '/');
        const query = searchQuery.toLowerCase();

        // Folder filter - check if path contains the folder name (supports both absolute and relative paths)
        if (folderFilter === 'download') {
            const hasDownload = normalizedPath.includes('download/') ||
                               normalizedPath.endsWith('/download') ||
                               normalizedPath.endsWith('download');
            if (!hasDownload) return false;
        }
        if (folderFilter === 'nomusic') {
            const hasNomusic = normalizedPath.includes('nomusic/') ||
                              normalizedPath.endsWith('/nomusic') ||
                              normalizedPath.endsWith('nomusic');
            if (!hasNomusic) return false;
        }

        return normalizedPath.includes(query);
    }).sort((a, b) => {
        if (sortBy === 'date') {
            // Sort by created_at timestamp (newest first)
            const timeA = a.created_at || 0;
            const timeB = b.created_at || 0;
            return timeB - timeA;
        } else if (sortBy === 'duration') {
            // Parse duration in "MM:SS" or "HH:MM:SS" format
            const parseDuration = (dur) => {
                if (!dur || dur === 'N/A') return 0;
                const parts = dur.split(':').map(Number);
                if (parts.length === 3) {
                    return parts[0] * 3600 + parts[1] * 60 + parts[2];
                } else if (parts.length === 2) {
                    return parts[0] * 60 + parts[1];
                }
                return parseFloat(dur) || 0;
            };
            return parseDuration(b.metadata?.duration) - parseDuration(a.metadata?.duration);
        }
        return 0;
    });

    // Initial fetch only - manual refresh via button
    useEffect(() => {
        fetchLibrary();
        fetchFolderSizes();
        
        return () => {
            // Cleanup: abort pending requests on unmount
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
            if (sizeAbortRef.current) {
                sizeAbortRef.current.abort();
            }
        };
    }, []);

    // Keyboard Shortcuts
    useEffect(() => {
        const handleKeyDown = (e) => {
            // Context menu or modal open? Let them handle Esc
            if (deleteConfirm) return;
            
            if (e.key === 'Escape') {
                if (selectedItems.length > 0) {
                    setSelectedItems([]);
                }
                if (contextMenu) {
                    setContextMenu(null);
                }
            }
            
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                searchInputRef.current?.focus();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [selectedItems, deleteConfirm, contextMenu]);

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
                        <span className="text-xs text-emerald-400">({folderSizes.download})</span>
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
                        <span className="text-xs text-emerald-400">({folderSizes.nomusic})</span>
                    </button>
                </div>

                {/* Actions */}
                <div className="flex gap-2 items-center">
                    {/* Refresh Button */}
                    <button
                        onClick={handleRefresh}
                        disabled={isRefreshing}
                        className={`p-2 rounded-lg transition-all border ${
                            isRefreshing
                                ? 'bg-blue-600/20 text-blue-400 border-blue-500/50 cursor-not-allowed'
                                : 'bg-blue-600/10 hover:bg-blue-600/20 text-blue-400 hover:text-blue-300 border-blue-500/30'
                        }`}
                        title="Refresh library"
                    >
                        <RefreshCw 
                            className="w-4 h-4"
                            style={isRefreshing ? { animation: 'spin 1s linear infinite' } : {}}
                        />
                    </button>

                    {/* Open Folder Actions */}
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
                {/* File Count Display */}
                <div className="text-sm text-gray-400">
                    Showing <span className="text-white font-bold">{filteredItems.length}</span> of <span className="text-white font-bold">{items.length}</span> files
                </div>

                {/* Search Input */}
                <div className="flex-1 min-w-64 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <input
                        ref={searchInputRef}
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search files (Ctrl+F)"
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
            </div>

            {/* Table */}
            {isLoading ? (
                <div className="text-center py-20 bg-dark-900/50 rounded-lg border border-white/5">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto text-primary-400 mb-3" />
                    <p className="text-gray-400 font-medium">Loading library...</p>
                    <p className="text-gray-600 text-xs mt-1">Scanning files and extracting metadata</p>
                </div>
            ) : items.length === 0 ? (
                <div className="text-center py-20 bg-dark-900/50 rounded-lg border border-white/5">
                    <FolderOpen className="w-16 h-16 mx-auto text-gray-600 mb-4" />
                    <p className="text-gray-400 font-medium text-lg">No files yet</p>
                    <p className="text-gray-600 text-sm mt-2">Download or process files to see them here.</p>
                </div>
            ) : filteredItems.length === 0 ? (
                <div className="text-center py-20 bg-dark-900/50 rounded-lg border border-white/5">
                    {folderFilter === 'nomusic' ? (
                        <>
                            <Music className="w-16 h-16 mx-auto text-gray-600 mb-4" />
                            <p className="text-gray-400 font-medium text-lg">No files in NoMusic folder</p>
                            <p className="text-gray-600 text-sm mt-2">Files processed with vocal separation will appear here.</p>
                        </>
                    ) : folderFilter === 'download' ? (
                        <>
                            <Download className="w-16 h-16 mx-auto text-gray-600 mb-4" />
                            <p className="text-gray-400 font-medium text-lg">No files in Download folder</p>
                            <p className="text-gray-600 text-sm mt-2">Downloaded videos will appear here.</p>
                        </>
                    ) : (
                        <>
                            <Search className="w-16 h-16 mx-auto text-gray-600 mb-4" />
                            <p className="text-gray-400 font-medium text-lg">No files match your search</p>
                            <p className="text-gray-600 text-sm mt-2">Try a different search term or clear filters.</p>
                        </>
                    )}
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
                                <tr
                                    key={item.task_id}
                                    className={`transition-all ${
                                        selectedItems.includes(item.task_id)
                                            ? 'bg-primary-500/5'
                                            : 'bg-dark-800/40 hover:bg-dark-800/60'
                                    }`}
                                    onContextMenu={(e) => handleContextMenu(e, item)}
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
                                                onClick={() => libraryAPI.openFile(item.result_files?.[0]).catch(() => toast.error("Cannot open file."))}
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
                                                onClick={() => libraryAPI.openFile(item.result_files?.[0]).catch(() => toast.error("Cannot open file."))}
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
                                                onClick={() => libraryAPI.openFolder(item.result_files?.[0]).catch(() => toast.error("Cannot open folder."))}
                                                title="Folder"
                                            >
                                                <FolderOpen className="w-3.5 h-3.5" />
                                            </button>
                                            <button
                                                className="p-1.5 bg-red-500/10 hover:bg-red-500 text-red-400 hover:text-white rounded transition-all"
                                                onClick={() => handleDelete(item.task_id, item.result_files?.[0])}
                                                title="Delete"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Delete Confirmation Modal */}
            <AnimatePresence>
                {deleteConfirm && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
                        onClick={() => setDeleteConfirm(null)}
                    >
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.95, opacity: 0 }}
                            onClick={(e) => e.stopPropagation()}
                            className="bg-dark-900 border border-white/10 rounded-2xl p-6 max-w-md w-full shadow-2xl"
                        >
                            <div className="flex items-center space-x-3 mb-4">
                                <div className="p-3 bg-red-600/20 rounded-full">
                                    <Trash2 className="w-6 h-6 text-red-500" />
                                </div>
                                <h3 className="text-xl font-bold text-white">Confirm Deletion</h3>
                            </div>
                            
                            <p className="text-gray-300 mb-6">
                                {deleteConfirm.type === 'bulk' 
                                    ? `Are you sure you want to delete ${deleteConfirm.count} files from your library and disk?`
                                    : `Are you sure you want to delete this file from your library and disk?`}
                                <br/><br/>
                                <span className="text-red-400 font-medium text-sm">This action cannot be undone.</span>
                            </p>
                            
                            <div className="flex gap-3">
                                <button
                                    onClick={() => setDeleteConfirm(null)}
                                    className="flex-1 px-4 py-3 bg-dark-800 hover:bg-dark-700 text-gray-300 hover:text-white rounded-xl font-bold transition-all border border-white/10"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={() => {
                                        if (deleteConfirm.type === 'bulk') {
                                            executeBulkDelete();
                                        } else {
                                            executeDelete(deleteConfirm.id, deleteConfirm.path);
                                        }
                                        setDeleteConfirm(null);
                                    }}
                                    className="flex-1 px-4 py-3 bg-gradient-to-r from-red-600 to-red-500 hover:from-red-500 hover:to-red-400 text-white rounded-xl font-bold transition-all shadow-lg shadow-red-600/30"
                                >
                                    Yes, Delete
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Context Menu - Portaled to Body for fixed positioning */}
            {contextMenu && createPortal(
                <div
                    className="fixed z-50 bg-dark-900 border border-white/10 rounded-lg shadow-2xl py-2 min-w-[200px] backdrop-blur-sm"
                    style={{
                        top: contextMenu.y,
                        left: contextMenu.x
                    }}
                    onClick={(e) => e.stopPropagation()}
                    onContextMenu={(e) => e.stopPropagation()}
                >
                    <div className="px-3 py-2 border-b border-white/5 mb-1">
                        <p className="text-xs text-gray-500 truncate max-w-[200px]">
                            {contextMenu.item?.result_files?.[0]?.split(/[\\/]/).pop()}
                        </p>
                    </div>
                    <button
                        onClick={() => {
                            libraryAPI.openFile(contextMenu.item?.result_files?.[0]).catch(() => {});
                            setContextMenu(null);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-white/5 hover:text-white flex items-center gap-2"
                    >
                        <PlayCircle className="w-4 h-4" />
                        Play
                    </button>
                    <button
                        onClick={() => {
                            libraryAPI.openFolder(contextMenu.item?.result_files?.[0]).catch(() => {});
                            setContextMenu(null);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-white/5 hover:text-white flex items-center gap-2"
                    >
                        <FolderOpen className="w-4 h-4" />
                        Open Folder
                    </button>
                    {!contextMenu.item?.result_files?.[0]?.toLowerCase().includes('nomusic') && (
                        <button
                            onClick={() => {
                                onSeparate?.(contextMenu.item?.result_files?.[0]);
                                setContextMenu(null);
                            }}
                            className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-white/5 hover:text-white flex items-center gap-2"
                        >
                            <Layers className="w-4 h-4" />
                            Separate Vocals
                        </button>
                    )}
                    <div className="border-t border-white/5 my-1"></div>
                    <button
                        onClick={() => {
                            handleDelete(contextMenu.item?.task_id, contextMenu.item?.result_files?.[0]);
                            setContextMenu(null);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-red-400 hover:bg-red-600/20 hover:text-red-300 flex items-center gap-2"
                    >
                        <Trash2 className="w-4 h-4" />
                        Delete
                    </button>
                </div>,
                document.body
            )}
        </div>
    );
};

export default LibraryTab;
