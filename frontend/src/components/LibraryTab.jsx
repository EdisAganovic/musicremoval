import { useState, useEffect, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { libraryAPI, separationAPI } from '../api/index.js';
import { BACKEND_URL } from '../config';
import { useAudioPlayer } from '../contexts/AudioPlayerContext';
import { 
    Video, Music, FolderOpen, Folder, Trash2, AudioLines, Search, CheckSquare, 
    Square, PlayCircle, Download, RefreshCw, Loader2, AlertCircle, Edit3, 
    ChevronLeft, ChevronRight, ChevronDown, Play, ExternalLink,
    PanelLeftClose, PanelLeftOpen, Layers, Film, Music2, HardDrive,
    GripVertical, FolderPlus, Plus, Move
} from 'lucide-react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { motion, AnimatePresence } from 'framer-motion';

const LibraryTab = ({ onSeparate, onBulkSeparate, isActive }) => {
    const [items, setItems] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedItems, setSelectedItems] = useState([]);
    const [sortBy, setSortBy] = useState('date');
    const [selectedFolder, setSelectedFolder] = useState({ category: 'all', subfolder: null });
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [expandedFolders, setExpandedFolders] = useState({ download: true, nomusic: true });
    const [folderSizes, setFolderSizes] = useState({ download: '0 MB', nomusic: '0 MB' });
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    // Drag and Drop state
    const [draggedItem, setDraggedItem] = useState(null);
    const [dragOverFolder, setDragOverFolder] = useState(null); // format: `${category}:${subfolder}`
    const [showNewFolderModal, setShowNewFolderModal] = useState(false);
    const [newFolderName, setNewFolderName] = useState('');
    const [newFolderCategory, setNewFolderCategory] = useState('download');
    const [diskFolders, setDiskFolders] = useState({ download: [], nomusic: [] });

    // Helper to extract folder category and subfolder name from file path
    const getFolderInfo = (item) => {
        const filePath = item.result_files?.[0] || '';
        const normalized = filePath.replace(/\\/g, '/');
        const lower = normalized.toLowerCase();
        
        const downloadIdx = lower.indexOf('/download/');
        const nomusicIdx = lower.indexOf('/nomusic/');
        
        if (downloadIdx !== -1) {
            const rest = normalized.slice(downloadIdx + '/download/'.length);
            const parts = rest.split('/');
            const sub = parts.length > 1 ? parts[0] : '(Direct Files)';
            return { category: 'download', subfolder: sub };
        }
        if (nomusicIdx !== -1) {
            const rest = normalized.slice(nomusicIdx + '/nomusic/'.length);
            const parts = rest.split('/');
            const sub = parts.length > 1 ? parts[0] : '(Direct Files)';
            return { category: 'nomusic', subfolder: sub };
        }
        return { category: 'other', subfolder: '(Direct Files)' };
    };

    // Calculate dynamic folder hierarchy and counts (including empty disk folders)
    const folderTree = useMemo(() => {
        const downloadMap = {};
        const nomusicMap = {};
        let totalDownload = 0;
        let totalNomusic = 0;

        // Initialize with all discovered disk folders so even empty folders are visible
        (diskFolders.download || []).forEach(name => {
            downloadMap[name] = 0;
        });
        (diskFolders.nomusic || []).forEach(name => {
            nomusicMap[name] = 0;
        });

        items.forEach(item => {
            const { category, subfolder } = getFolderInfo(item);
            if (category === 'download') {
                totalDownload++;
                downloadMap[subfolder] = (downloadMap[subfolder] || 0) + 1;
            } else if (category === 'nomusic') {
                totalNomusic++;
                nomusicMap[subfolder] = (nomusicMap[subfolder] || 0) + 1;
            }
        });

        return {
            all: items.length,
            download: {
                total: totalDownload,
                directCount: downloadMap['(Direct Files)'] || 0,
                subfolders: Object.entries(downloadMap).sort(([a], [b]) => a[0].localeCompare(b[0]))
            },
            nomusic: {
                total: totalNomusic,
                directCount: nomusicMap['(Direct Files)'] || 0,
                subfolders: Object.entries(nomusicMap).sort(([a], [b]) => a[0].localeCompare(b[0]))
            }
        };
    }, [items, diskFolders]);

    // Subfolder cards visible when at root level
    const visibleSubfolders = useMemo(() => {
        if (selectedFolder.subfolder !== null) return []; // Currently inside a folder
        
        if (selectedFolder.category === 'download') {
            return folderTree.download.subfolders
                .filter(([name]) => name !== '(Direct Files)')
                .map(([name, count]) => ({ category: 'download', name, count }));
        }
        if (selectedFolder.category === 'nomusic') {
            return folderTree.nomusic.subfolders
                .filter(([name]) => name !== '(Direct Files)')
                .map(([name, count]) => ({ category: 'nomusic', name, count }));
        }
        
        // 'all' category: list all subfolders from both download and nomusic
        const allSubs = [];
        folderTree.download.subfolders.forEach(([name, count]) => {
            if (name !== '(Direct Files)') allSubs.push({ category: 'download', name, count });
        });
        folderTree.nomusic.subfolders.forEach(([name, count]) => {
            if (name !== '(Direct Files)') allSubs.push({ category: 'nomusic', name, count });
        });
        return allSubs;
    }, [selectedFolder, folderTree]);

    // Filter and sort items: show ONLY root files when at root level, or specific folder items when inside
    const filteredItems = useMemo(() => {
        return items.filter(item => {
            const filePath = (item.result_files?.[0] || '').toLowerCase();
            const normalizedPath = filePath.replace(/\\/g, '/');
            const query = searchQuery.toLowerCase();

            // Folder & Subfolder Filter (Show only root files when at root level)
            const { category, subfolder } = getFolderInfo(item);
            if (selectedFolder.category !== 'all') {
                if (category !== selectedFolder.category) return false;
            }

            if (selectedFolder.subfolder === null) {
                // Root only: only show files directly in root
                if (subfolder !== '(Direct Files)') return false;
            } else {
                // Inside specific subfolder
                if (subfolder !== selectedFolder.subfolder) return false;
            }

            return normalizedPath.includes(query) || (item.title || '').toLowerCase().includes(query) || (item.filename || '').toLowerCase().includes(query);
        }).sort((a, b) => {
            if (sortBy === 'date') {
                const timeA = a.created_at || 0;
                const timeB = b.created_at || 0;
                return timeB - timeA;
            } else if (sortBy === 'duration') {
                const parseDuration = (dur) => {
                    if (!dur || dur === 'N/A') return 0;
                    const parts = dur.split(':').map(Number);
                    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
                    if (parts.length === 2) return parts[0] * 60 + parts[1];
                    return parseFloat(dur) || 0;
                };
                return parseDuration(b.metadata?.duration) - parseDuration(a.metadata?.duration);
            }
            return 0;
        });
    }, [items, selectedFolder, searchQuery, sortBy]);

    // Pagination
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(50);

    // Modal state for delete confirmations
    const [deleteConfirm, setDeleteConfirm] = useState(null); // { type: 'single' | 'bulk', id?: string, path?: string, count?: number }

    // Context menu state
    const [contextMenu, setContextMenu] = useState(null); // { x, y, item }

    // Rename state
    const [renameConfirm, setRenameConfirm] = useState(null); // { item, newName }

    // Refs for cleanup
    const abortControllerRef = useRef(null);
    const sizeAbortRef = useRef(null);
    const searchInputRef = useRef(null);

    // In-browser Audio Player
    const { playTrack, currentTrack, isPlaying } = useAudioPlayer();

    const handlePlayInBrowser = (item) => {
        const filePath = item?.result_files?.[0];
        if (!filePath) {
            toast.error("File path not available");
            return;
        }

        const fileName = item.filename || item.title || filePath.split(/[\\/]/).pop();
        const ext = filePath.split('.').pop()?.toLowerCase() || 'mp3';
        const isVocal = filePath.toLowerCase().includes('vocal');
        const isInstrumental = filePath.toLowerCase().includes('instrumental') || filePath.toLowerCase().includes('karaoke');

        playTrack({
            url: `${BACKEND_URL}/api/media/stream?path=${encodeURIComponent(filePath)}`,
            title: fileName,
            path: filePath,
            type: isVocal ? 'vocal' : isInstrumental ? 'instrumental' : 'audio',
            badge: ext.toUpperCase()
        });
        toast.success(`Playing in browser: ${fileName}`);
    };

    const fetchLibrary = async (isInitial = false) => {
        setIsRefreshing(true);
        if (isInitial || items.length === 0) {
            setIsLoading(true);
        }
        // Cancel previous request if still pending
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        try {
            const [libRes, foldRes] = await Promise.allSettled([
                libraryAPI.get({ signal: abortControllerRef.current.signal }),
                libraryAPI.getFolders()
            ]);

            if (libRes.status === 'fulfilled') {
                setItems(libRes.value?.data || []);
            }
            if (foldRes.status === 'fulfilled' && foldRes.value?.data) {
                setDiskFolders(foldRes.value.data);
            }
        } catch (err) {
            // Silently ignore abort errors (expected when switching tabs)
            if (err.name === 'AbortError' || err.name === 'CanceledError') {
                return;
            }
            console.error("Failed to fetch library", err);
        } finally {
            setIsLoading(false);
            setIsRefreshing(false);
        }
    };

    const silentRefresh = async () => {
        try {
            const [libRes, foldRes] = await Promise.allSettled([
                libraryAPI.get(),
                libraryAPI.getFolders()
            ]);
            if (libRes.status === 'fulfilled') {
                setItems(libRes.value?.data || []);
            }
            if (foldRes.status === 'fulfilled' && foldRes.value?.data) {
                setDiskFolders(foldRes.value.data);
            }
        } catch (_) {}
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
        const handleClickOutside = (_e) => {
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
            // Optimistically remove from UI immediately
            setItems(prev => prev.filter(item => item.task_id !== taskId && item.result_files?.[0] !== filePath));

            await libraryAPI.delete(taskId, filePath);

            // Show success toast with undo
            const fileName = filePath?.split(/[\\/]/).pop() || 'File';
            toast.success(`Deleted "${fileName}"`);
            await silentRefresh();
        } catch (err) {
            console.error("Failed to delete file", err);
            toast.error("Failed to delete file");
            // Reload library to restore correct state if delete failed
            await silentRefresh();
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

            // Show success toast
            toast.success(`Deleted ${deletedItems.length} file${deletedItems.length !== 1 ? 's' : ''}`);

            // If current filter has no files left, switch to "All Files"
            if (filteredItems.length === selectedItems.length) {
                setSelectedFolder({ category: 'all', subfolder: null });
            }
            await silentRefresh();
        } catch (err) {
            console.error("Failed to bulk delete", err);
            toast.error("Failed to delete files");
            // Reload library to restore correct state if delete failed
            await silentRefresh();
        }
    };

    const handleBulkDelete = () => {
        if (selectedItems.length === 0) return;
        setDeleteConfirm({ type: 'bulk', count: selectedItems.length });
    };

    const [isBulkSeparating, setIsBulkSeparating] = useState(false);

    const handleBulkSeparate = async () => {
        if (selectedItems.length === 0 || isBulkSeparating) return;

        const filePaths = items
            .filter(item => selectedItems.includes(item.task_id))
            .map(item => item.result_files?.[0])
            .filter(path => path && !path.toLowerCase().includes('nomusic'));

        if (filePaths.length === 0) {
            toast.error("No eligible files in selection (already-separated files are skipped)");
            return;
        }

        setIsBulkSeparating(true);
        const loadingToast = toast.loading(`Queuing ${filePaths.length} file${filePaths.length !== 1 ? 's' : ''} for separation...`);
        try {
            const scanResponse = await separationAPI.scanFileList(filePaths);
            const { queue_id } = scanResponse.data;

            const batchResponse = await separationAPI.processBatch(queue_id, "both");
            const { batch_id } = batchResponse.data;

            toast.success(`Started separating ${filePaths.length} file${filePaths.length !== 1 ? 's' : ''}`, { id: loadingToast });
            setSelectedItems([]);
            onBulkSeparate?.(batch_id);
        } catch (err) {
            console.error("Failed to start bulk separation", err);
            toast.error(err.response?.data?.detail || "Failed to start bulk separation", { id: loadingToast });
        } finally {
            setIsBulkSeparating(false);
        }
    };

    const handleRename = (item) => {
        const currentName = item.result_files?.[0]?.split(/[\\/]/).pop() || '';
        const nameWithoutExt = currentName.substring(0, currentName.lastIndexOf('.')) || currentName;
        setRenameConfirm({ item, newName: nameWithoutExt });
    };

    const executeRename = async () => {
        if (!renameConfirm || !renameConfirm.newName) return;

        const loadingToast = toast.loading("Renaming file...");
        try {
            const { item, newName } = renameConfirm;
            await libraryAPI.rename(item.task_id, newName);
            toast.success(`Renamed file`, { id: loadingToast });
            setRenameConfirm(null);
            await silentRefresh();
        } catch (err) {
            console.error("Failed to rename file", err);
            toast.error(err.response?.data?.detail || "Failed to rename file", { id: loadingToast });
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
            toast.error(`Cannot open ${folderName} folder.`);
        }
    };

    // Drag & Drop handlers (Optimistic & No Screen Refresh)
    const handleDragOverFolder = (category, subfolder, e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const folderKey = `${category}:${subfolder || 'root'}`;
        if (dragOverFolder !== folderKey) {
            setDragOverFolder(folderKey);
        }
    };

    const handleDragLeaveFolder = (e) => {
        e.preventDefault();
        setDragOverFolder(null);
    };

    const handleDropOnFolder = async (category, subfolder, e) => {
        e.preventDefault();
        setDragOverFolder(null);

        let taskIds = [];
        let filePaths = [];

        try {
            const dataStr = e.dataTransfer.getData('application/json');
            if (dataStr) {
                const parsed = JSON.parse(dataStr);
                taskIds = parsed.task_ids || [];
                filePaths = parsed.file_paths || [];
            }
        } catch (_) {}

        if (taskIds.length === 0 && filePaths.length === 0 && draggedItem) {
            taskIds = draggedItem.items.map(i => i.task_id);
            filePaths = draggedItem.items.map(i => i.result_files?.[0]).filter(Boolean);
        }

        if (taskIds.length === 0 && filePaths.length === 0) return;

        const targetSub = subfolder === '(Direct Files)' ? '' : (subfolder || '');
        const targetCat = category === 'all' ? 'download' : category;
        const targetLabel = targetSub ? targetSub : `${targetCat} (Root)`;
        const count = taskIds.length || filePaths.length;

        // 1. Instant Optimistic UI Update (Zero delay, Zero spinner)
        const previousItems = [...items];
        setItems(prev => prev.map(item => {
            const isMatch = taskIds.includes(item.task_id) || 
                (item.result_files?.[0] && filePaths.includes(item.result_files[0]));
            if (!isMatch) return item;

            const oldPath = item.result_files?.[0] || '';
            const fileName = oldPath.split(/[/\\]/).pop();
            const simulatedPath = targetSub 
                ? `${targetCat}/${targetSub}/${fileName}` 
                : `${targetCat}/${fileName}`;

            return {
                ...item,
                result_files: [simulatedPath]
            };
        }));
        setSelectedItems([]);
        setDraggedItem(null);

        // 2. Background Server Sync
        try {
            await libraryAPI.move({
                task_ids: taskIds,
                file_paths: filePaths,
                target_category: targetCat,
                target_subfolder: targetSub
            });
            toast.success(`Moved ${count} file${count !== 1 ? 's' : ''} to "${targetLabel}"`);
            await silentRefresh();
        } catch (err) {
            console.error("Failed to move files", err);
            toast.error(err.response?.data?.detail || "Failed to move files");
            // Rollback optimistic change on error
            setItems(previousItems);
        }
    };

    const handleCreateFolderSubmit = async (e) => {
        e?.preventDefault();
        const trimmed = newFolderName.trim();
        if (!trimmed) {
            toast.error("Please enter a folder name");
            return;
        }

        // Instant optimistic folder add
        setDiskFolders(prev => ({
            ...prev,
            [newFolderCategory]: Array.from(new Set([...(prev[newFolderCategory] || []), trimmed]))
        }));
        setSelectedFolder({ category: newFolderCategory, subfolder: trimmed });
        setExpandedFolders(prev => ({ ...prev, [newFolderCategory]: true }));
        setShowNewFolderModal(false);
        setNewFolderName('');

        try {
            await libraryAPI.createFolder({
                category: newFolderCategory,
                folder_name: trimmed
            });
            toast.success(`Created folder "${trimmed}"`);
            await silentRefresh();
        } catch (err) {
            console.error("Failed to create folder", err);
            toast.error(err.response?.data?.detail || "Failed to create folder");
            await silentRefresh();
        }
    };

    const totalPages = Math.max(1, Math.ceil(filteredItems.length / pageSize));
    const paginatedItems = filteredItems.slice((currentPage - 1) * pageSize, currentPage * pageSize);

    // Reset to page 1 whenever the filtered set changes shape
    useEffect(() => {
        setCurrentPage(1);
    }, [searchQuery, selectedFolder, sortBy, pageSize]);

    // Clamp current page if items were deleted and it now overshoots the page count
    useEffect(() => {
        if (currentPage > totalPages) {
            setCurrentPage(totalPages);
        }
    }, [totalPages, currentPage]);

    // Re-fetch when tab becomes active
    useEffect(() => {
        if (isActive) {
            handleRefresh();
        }

        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
            if (sizeAbortRef.current) {
                sizeAbortRef.current.abort();
            }
        };
        // `handleRefresh` is recreated every render; including it would refetch
        // on every render instead of only when the tab becomes active.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isActive]);

    // Keyboard Shortcuts
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (deleteConfirm || showNewFolderModal) return;

            if (e.key === 'Escape') {
                if (selectedItems.length > 0) {
                    setSelectedItems([]);
                }
                if (contextMenu) {
                    setContextMenu(null);
                }
                if (showNewFolderModal) {
                    setShowNewFolderModal(false);
                }
            }

            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                searchInputRef.current?.focus();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [selectedItems, contextMenu, deleteConfirm, showNewFolderModal]);

    const toggleFolderExpand = (category, e) => {
        e.stopPropagation();
        setExpandedFolders(prev => ({
            ...prev,
            [category]: !prev[category]
        }));
    };

    return (
        <div className="flex gap-4 items-start w-full">
            {/* Collapsible Folder Sidebar */}
            <AnimatePresence initial={false}>
                {sidebarOpen && (
                    <motion.aside
                        initial={{ width: 0, opacity: 0 }}
                        animate={{ width: 280, opacity: 1 }}
                        exit={{ width: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden flex-shrink-0"
                    >
                        <div className="bg-dark-900/80 backdrop-blur-xl border border-white/10 rounded-2xl p-3 space-y-3 shadow-xl">
                            {/* Sidebar Header */}
                            <div className="flex items-center justify-between px-2 pb-2 border-b border-white/5">
                                <div className="flex items-center space-x-2">
                                    <Folder className="w-4 h-4 text-primary-400" />
                                    <span className="text-xs font-bold uppercase tracking-wider text-gray-300">Folders</span>
                                </div>
                                <div className="flex items-center space-x-1">
                                    <button
                                        onClick={() => setShowNewFolderModal(true)}
                                        className="p-1 text-gray-400 hover:text-amber-400 hover:bg-white/5 rounded-lg transition-colors"
                                        title="Create New Folder"
                                    >
                                        <FolderPlus className="w-4 h-4" />
                                    </button>
                                    <button
                                        onClick={() => setSidebarOpen(false)}
                                        className="p-1 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                                        title="Collapse Folders"
                                    >
                                        <PanelLeftClose className="w-4 h-4" />
                                    </button>
                                </div>
                            </div>

                            {/* Folder List */}
                            <div className="space-y-1 max-h-[70vh] overflow-y-auto pr-1">
                                {/* All Files */}
                                <button
                                    onClick={() => setSelectedFolder({ category: 'all', subfolder: null })}
                                    onDragOver={(e) => handleDragOverFolder('all', null, e)}
                                    onDragLeave={handleDragLeaveFolder}
                                    onDrop={(e) => handleDropOnFolder('all', null, e)}
                                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                                        dragOverFolder === 'all:root'
                                            ? 'bg-primary-500/30 border-2 border-primary-400 ring-2 ring-primary-500/40 text-white scale-[1.02]'
                                            : selectedFolder.category === 'all'
                                            ? 'bg-gradient-to-r from-primary-600/30 to-primary-500/20 text-white border border-primary-500/40 shadow-sm'
                                            : 'text-gray-400 hover:text-white hover:bg-white/5 border border-transparent'
                                    }`}
                                >
                                    <div className="flex items-center space-x-2">
                                        <Layers className="w-4 h-4 text-blue-400" />
                                        <span>All Files</span>
                                    </div>
                                    <span className="px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-dark-800 text-gray-400 border border-white/5">
                                        {folderTree.all}
                                    </span>
                                </button>

                                {/* Download Folder Section */}
                                <div className="pt-2">
                                    <div
                                        onClick={() => setSelectedFolder({ category: 'download', subfolder: null })}
                                        onDragOver={(e) => handleDragOverFolder('download', null, e)}
                                        onDragLeave={handleDragLeaveFolder}
                                        onDrop={(e) => handleDropOnFolder('download', null, e)}
                                        className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold cursor-pointer transition-all ${
                                            dragOverFolder === 'download:root'
                                                ? 'bg-red-500/30 border-2 border-red-400 ring-2 ring-red-500/40 text-white scale-[1.02]'
                                                : selectedFolder.category === 'download' && selectedFolder.subfolder === null
                                                ? 'bg-red-600/20 text-red-300 border border-red-500/40 shadow-sm'
                                                : 'text-gray-300 hover:text-white hover:bg-white/5 border border-transparent'
                                        }`}
                                    >
                                        <div className="flex items-center space-x-2">
                                            <button
                                                onClick={(e) => toggleFolderExpand('download', e)}
                                                className="p-0.5 text-gray-500 hover:text-white transition-colors"
                                            >
                                                {expandedFolders.download ? (
                                                    <ChevronDown className="w-3.5 h-3.5" />
                                                ) : (
                                                    <ChevronRight className="w-3.5 h-3.5" />
                                                )}
                                            </button>
                                            <Download className="w-4 h-4 text-red-400" />
                                            <span className="font-bold">Download</span>
                                        </div>
                                        <span className="px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-red-950/40 text-red-400 border border-red-500/20">
                                            {folderTree.download.total}
                                        </span>
                                    </div>

                                    {/* Download Subfolders */}
                                    {expandedFolders.download && (
                                        <div className="pl-6 pr-1 py-1 space-y-0.5">
                                            {folderTree.download.subfolders.map(([subName, count]) => {
                                                const isSelected = selectedFolder.category === 'download' && selectedFolder.subfolder === subName;
                                                const isDragOver = dragOverFolder === `download:${subName}`;
                                                return (
                                                    <button
                                                        key={`dl-sub-${subName}`}
                                                        onClick={() => setSelectedFolder({ category: 'download', subfolder: subName })}
                                                        onDragOver={(e) => handleDragOverFolder('download', subName, e)}
                                                        onDragLeave={handleDragLeaveFolder}
                                                        onDrop={(e) => handleDropOnFolder('download', subName, e)}
                                                        className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition-all text-left ${
                                                            isDragOver
                                                                ? 'bg-amber-500/30 border-2 border-amber-400 ring-2 ring-amber-500/40 text-white font-bold scale-[1.02]'
                                                                : isSelected
                                                                ? 'bg-red-500/20 text-white font-bold border border-red-500/30'
                                                                : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent'
                                                        }`}
                                                        title={subName}
                                                    >
                                                        <div className="flex items-center space-x-2 truncate">
                                                            <Folder className={`w-3.5 h-3.5 flex-shrink-0 ${isDragOver ? 'text-amber-300' : isSelected ? 'text-red-400' : 'text-gray-500'}`} />
                                                            <span className="truncate">{subName}</span>
                                                        </div>
                                                        <span className="text-[10px] text-gray-500 font-mono flex-shrink-0 ml-1">
                                                            {count}
                                                        </span>
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>

                                {/* NoMusic Folder Section */}
                                <div className="pt-2">
                                    <div
                                        onClick={() => setSelectedFolder({ category: 'nomusic', subfolder: null })}
                                        onDragOver={(e) => handleDragOverFolder('nomusic', null, e)}
                                        onDragLeave={handleDragLeaveFolder}
                                        onDrop={(e) => handleDropOnFolder('nomusic', null, e)}
                                        className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold cursor-pointer transition-all ${
                                            dragOverFolder === 'nomusic:root'
                                                ? 'bg-emerald-500/30 border-2 border-emerald-400 ring-2 ring-emerald-500/40 text-white scale-[1.02]'
                                                : selectedFolder.category === 'nomusic' && selectedFolder.subfolder === null
                                                ? 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                                                : 'text-gray-300 hover:text-white hover:bg-white/5 border border-transparent'
                                        }`}
                                    >
                                        <div className="flex items-center space-x-2">
                                            <button
                                                onClick={(e) => toggleFolderExpand('nomusic', e)}
                                                className="p-0.5 text-gray-500 hover:text-white transition-colors"
                                            >
                                                {expandedFolders.nomusic ? (
                                                    <ChevronDown className="w-3.5 h-3.5" />
                                                ) : (
                                                    <ChevronRight className="w-3.5 h-3.5" />
                                                )}
                                            </button>
                                            <Music2 className="w-4 h-4 text-emerald-400" />
                                            <span className="font-bold">NoMusic</span>
                                        </div>
                                        <span className="px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-emerald-950/40 text-emerald-400 border border-emerald-500/20">
                                            {folderTree.nomusic.total}
                                        </span>
                                    </div>

                                    {/* NoMusic Subfolders */}
                                    {expandedFolders.nomusic && (
                                        <div className="pl-6 pr-1 py-1 space-y-0.5">
                                            {folderTree.nomusic.subfolders.map(([subName, count]) => {
                                                const isSelected = selectedFolder.category === 'nomusic' && selectedFolder.subfolder === subName;
                                                const isDragOver = dragOverFolder === `nomusic:${subName}`;
                                                return (
                                                    <button
                                                        key={`nomusic-sub-${subName}`}
                                                        onClick={() => setSelectedFolder({ category: 'nomusic', subfolder: subName })}
                                                        onDragOver={(e) => handleDragOverFolder('nomusic', subName, e)}
                                                        onDragLeave={handleDragLeaveFolder}
                                                        onDrop={(e) => handleDropOnFolder('nomusic', subName, e)}
                                                        className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition-all text-left ${
                                                            isDragOver
                                                                ? 'bg-amber-500/30 border-2 border-amber-400 ring-2 ring-amber-500/40 text-white font-bold scale-[1.02]'
                                                                : isSelected
                                                                ? 'bg-emerald-500/20 text-white font-bold border border-emerald-500/30'
                                                                : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent'
                                                        }`}
                                                        title={subName}
                                                    >
                                                        <div className="flex items-center space-x-2 truncate">
                                                            <Folder className={`w-3.5 h-3.5 flex-shrink-0 ${isDragOver ? 'text-amber-300' : isSelected ? 'text-emerald-400' : 'text-gray-500'}`} />
                                                            <span className="truncate">{subName}</span>
                                                        </div>
                                                        <span className="text-[10px] text-gray-500 font-mono flex-shrink-0 ml-1">
                                                            {count}
                                                        </span>
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </motion.aside>
                )}
            </AnimatePresence>

            {/* Main Content Area */}
            <div className="flex-1 min-w-0 space-y-4">
                {/* Top Control Bar & Breadcrumbs */}
                <div className="bg-dark-900/80 backdrop-blur-xl border border-white/10 rounded-2xl p-3 flex flex-wrap items-center justify-between gap-3 shadow-lg">
                    {/* Left: Sidebar Toggle + Current Folder Breadcrumb */}
                    <div className="flex items-center space-x-2 sm:space-x-3 flex-wrap gap-y-2">
                        {!sidebarOpen && (
                            <button
                                onClick={() => setSidebarOpen(true)}
                                className="px-3 py-1.5 bg-dark-800 hover:bg-dark-700 text-gray-300 hover:text-white rounded-xl border border-white/10 text-xs font-bold transition-all flex items-center gap-1.5 shadow-sm"
                                title="Show Folders Sidebar"
                            >
                                <PanelLeftOpen className="w-4 h-4 text-primary-400" />
                                <span>Folders</span>
                            </button>
                        )}

                        {selectedFolder.subfolder !== null && (
                            <button
                                onClick={() => setSelectedFolder(prev => ({ ...prev, subfolder: null }))}
                                className="px-2.5 py-1.5 bg-primary-600/20 hover:bg-primary-600/30 text-primary-300 rounded-xl text-xs font-bold transition-all flex items-center gap-1 border border-primary-500/30 shadow-sm"
                                title="Back to root folders"
                            >
                                <ChevronLeft className="w-3.5 h-3.5" />
                                <span>Back to Folders</span>
                            </button>
                        )}

                        {/* Breadcrumbs */}
                        <div className="flex items-center space-x-1.5 text-xs">
                            <button 
                                onClick={() => setSelectedFolder({ category: 'all', subfolder: null })}
                                className="text-gray-400 hover:text-white font-medium transition-colors"
                            >
                                Library
                            </button>
                            <ChevronRight className="w-3.5 h-3.5 text-gray-600" />
                            {selectedFolder.category === 'all' && selectedFolder.subfolder === null ? (
                                <span className="px-2 py-0.5 bg-primary-500/10 text-primary-300 rounded-md font-bold border border-primary-500/20">
                                    Root Files
                                </span>
                            ) : (
                                <>
                                    <button
                                        onClick={() => setSelectedFolder({ category: selectedFolder.category, subfolder: null })}
                                        className={`hover:underline font-bold ${
                                            selectedFolder.category === 'download' ? 'text-red-400' : 'text-emerald-400'
                                        }`}
                                    >
                                        {selectedFolder.category === 'download' ? 'Download' : 'NoMusic'}
                                    </button>
                                    {selectedFolder.subfolder && (
                                        <>
                                            <ChevronRight className="w-3.5 h-3.5 text-gray-600" />
                                            <span className="px-2 py-0.5 bg-amber-500/15 text-amber-300 rounded-md font-bold border border-amber-500/30 truncate max-w-[200px]" title={selectedFolder.subfolder}>
                                                {selectedFolder.subfolder}
                                            </span>
                                        </>
                                    )}
                                </>
                            )}
                            <span className="text-gray-500 ml-1">({filteredItems.length} files)</span>
                        </div>
                    </div>

                    {/* Right: Quick Action Buttons */}
                    <div className="flex items-center space-x-2">
                        {/* Refresh Button */}
                        <button
                            onClick={handleRefresh}
                            disabled={isRefreshing}
                            className={`p-2 rounded-xl transition-all border ${isRefreshing
                                ? 'bg-blue-600/20 text-blue-400 border-blue-500/50 cursor-not-allowed'
                                : 'bg-blue-600/10 hover:bg-blue-600/20 text-blue-400 hover:text-blue-300 border-blue-500/30'
                                }`}
                            title="Refresh library"
                        >
                            <RefreshCw
                                className="w-3.5 h-3.5"
                                style={isRefreshing ? { animation: 'spin 1s linear infinite' } : {}}
                            />
                        </button>

                        {/* Open in Explorer */}
                        <button
                            onClick={() => {
                                const target = selectedFolder.category === 'nomusic' ? 'nomusic' : 'download';
                                openFolder(target);
                            }}
                            className="px-3 py-1.5 bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white text-xs font-bold rounded-xl transition-all border border-white/10 flex items-center gap-1.5"
                            title="Open current folder in file explorer"
                        >
                            <FolderOpen className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Open in Explorer</span>
                        </button>
                    </div>
                </div>

                {/* Filter and Search Bar */}
                <div className="flex gap-3 flex-wrap items-center">
                    {/* Search Input */}
                    <div className="flex-1 min-w-64 relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                        <input
                            ref={searchInputRef}
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Search in current folder (Ctrl+F)"
                            className="w-full bg-dark-800/90 text-white text-sm border border-white/10 rounded-xl pl-10 pr-4 py-2 outline-none focus:border-primary-500/50 transition-colors"
                        />
                    </div>

                    {/* Sort Dropdown */}
                    <select
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value)}
                        className="bg-dark-800 text-white text-sm border border-white/10 rounded-xl px-3 py-2 outline-none focus:border-primary-500/50 transition-colors cursor-pointer"
                    >
                        <option value="date">Date</option>
                        <option value="duration">Duration</option>
                    </select>

                    {/* Select All */}
                    <button
                        onClick={selectAll}
                        className="px-3 py-2 bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white text-sm font-bold rounded-xl transition-all border border-white/10 flex items-center gap-2"
                        title="Select All"
                    >
                        {selectedItems.length === filteredItems.length && filteredItems.length > 0 ? (
                            <CheckSquare className="w-4 h-4 text-primary-400" />
                        ) : (
                            <Square className="w-4 h-4" />
                        )}
                    </button>

                    {/* Bulk Separate */}
                    {selectedItems.length > 0 && (
                        <button
                            onClick={handleBulkSeparate}
                            disabled={isBulkSeparating}
                            className="px-3 py-2 bg-emerald-600/10 hover:bg-emerald-600/20 disabled:opacity-50 disabled:cursor-not-allowed text-emerald-400 hover:text-emerald-300 text-sm font-bold rounded-xl transition-all border border-emerald-500/20 flex items-center gap-2"
                            title="Separate vocals for all selected files"
                        >
                            {isBulkSeparating ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                                <AudioLines className="w-4 h-4" />
                            )}
                            <span>Separate {selectedItems.length}</span>
                        </button>
                    )}

                    {/* Bulk Delete */}
                    {selectedItems.length > 0 && (
                        <button
                            onClick={handleBulkDelete}
                            className="px-3 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 hover:text-red-300 text-sm font-bold rounded-xl transition-all border border-red-500/20 flex items-center gap-2"
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
                    {selectedFolder.subfolder !== null ? (
                        <>
                            <FolderOpen className="w-16 h-16 mx-auto text-amber-500/40 mb-4" />
                            <p className="text-gray-300 font-medium text-lg">Folder "{selectedFolder.subfolder}" is empty</p>
                            <p className="text-gray-500 text-sm mt-2">
                                Drag & drop files from the root files list onto <span className="text-amber-400 font-semibold">{selectedFolder.subfolder}</span> in the sidebar to move them here.
                            </p>
                        </>
                    ) : selectedFolder.category === 'nomusic' ? (
                        <>
                            <Music className="w-16 h-16 mx-auto text-gray-600 mb-4" />
                            <p className="text-gray-400 font-medium text-lg">No files in NoMusic folder</p>
                            <p className="text-gray-600 text-sm mt-2">Files processed with vocal separation will appear here.</p>
                        </>
                    ) : selectedFolder.category === 'download' ? (
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
                    <table className="w-full table-fixed">
                        <thead className="bg-dark-900/80 border-b border-white/10">
                            <tr className="text-xs font-bold uppercase tracking-wider text-gray-400">
                                <th className="px-4 py-2.5 text-left w-12">
                                    <input
                                        type="checkbox"
                                        checked={selectedItems.length === filteredItems.length && filteredItems.length > 0}
                                        onChange={selectAll}
                                        className="w-4 h-4 rounded border-gray-600 bg-dark-700 text-primary-500 focus:ring-primary-500 cursor-pointer"
                                    />
                                </th>
                                <th className="px-4 py-2.5 text-left">File</th>
                                <th className="px-4 py-2.5 text-left w-20 sm:w-24">Dur.</th>
                                <th className="px-4 py-2.5 text-left w-24 hidden md:table-cell">Quality</th>
                                <th className="px-4 py-2.5 text-right w-[140px] sm:w-44">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                            {paginatedItems.map((item) => {
                                const isCurrentTrack = currentTrack?.path === item.result_files?.[0];
                                const isSelected = selectedItems.includes(item.task_id);
                                return (
                                <tr
                                    key={item.task_id}
                                    draggable={true}
                                    onDragStart={(e) => {
                                        const itemsToMove = isSelected && selectedItems.length > 1
                                            ? items.filter(i => selectedItems.includes(i.task_id))
                                            : [item];
                                        setDraggedItem({ items: itemsToMove });
                                        e.dataTransfer.effectAllowed = 'move';
                                        e.dataTransfer.setData('application/json', JSON.stringify({
                                            task_ids: itemsToMove.map(i => i.task_id),
                                            file_paths: itemsToMove.map(i => i.result_files?.[0]).filter(Boolean)
                                        }));
                                    }}
                                    onDragEnd={() => {
                                        setDraggedItem(null);
                                        setDragOverFolder(null);
                                    }}
                                    className={`transition-all cursor-pointer group ${isCurrentTrack
                                        ? 'bg-emerald-500/10 border-l-2 border-emerald-500'
                                        : isSelected
                                        ? 'bg-primary-500/10'
                                        : 'bg-dark-800/40 hover:bg-dark-800/60'
                                        }`}
                                    onDoubleClick={() => handlePlayInBrowser(item)}
                                    onContextMenu={(e) => handleContextMenu(e, item)}
                                >
                                    <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                                        <div className="flex items-center space-x-1.5">
                                            <GripVertical className="w-3.5 h-3.5 text-gray-600 group-hover:text-gray-400 cursor-grab active:cursor-grabbing flex-shrink-0" />
                                            <input
                                                type="checkbox"
                                                checked={isSelected}
                                                onChange={() => toggleSelect(item.task_id)}
                                                className="w-4 h-4 rounded border-gray-600 bg-dark-700 text-primary-500 focus:ring-primary-500 cursor-pointer"
                                            />
                                        </div>
                                    </td>
                                    <td className="px-4 py-2">
                                        <div className="flex items-center space-x-3">
                                            <div
                                                className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 cursor-pointer shadow-lg transition-transform hover:scale-105 ${isCurrentTrack && isPlaying
                                                    ? 'bg-gradient-to-tr from-emerald-500 to-teal-400 shadow-emerald-500/40 ring-2 ring-emerald-400'
                                                    : item.model === 'spleeter'
                                                    ? 'bg-gradient-to-tr from-blue-600 to-blue-400 shadow-blue-500/20'
                                                    : item.model === 'demucs'
                                                        ? 'bg-gradient-to-tr from-orange-600 to-orange-400 shadow-orange-500/20'
                                                        : item.model === 'both'
                                                            ? 'bg-gradient-to-tr from-emerald-600 to-emerald-400 shadow-emerald-500/20'
                                                            : 'bg-gradient-to-tr from-indigo-600 to-primary-500 shadow-primary-500/20'
                                                    }`}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handlePlayInBrowser(item);
                                                }}
                                                title="Play in browser"
                                            >
                                                {isCurrentTrack && isPlaying ? (
                                                    <span className="flex space-x-0.5 items-end h-4">
                                                        <span className="w-1 bg-white h-3 animate-pulse rounded-full"></span>
                                                        <span className="w-1 bg-white h-4 animate-pulse rounded-full" style={{ animationDelay: '150ms' }}></span>
                                                        <span className="w-1 bg-white h-2 animate-pulse rounded-full" style={{ animationDelay: '300ms' }}></span>
                                                    </span>
                                                ) : item.metadata?.is_video ? (
                                                    <Video className="w-4 h-4 text-white" />
                                                ) : (
                                                    <Music className="w-4 h-4 text-white" />
                                                )}
                                            </div>
                                            <div className="flex flex-col min-w-0">
                                                <span
                                                    className={`text-sm font-medium truncate max-w-full ${isCurrentTrack ? 'text-emerald-400 font-bold' : 'text-white'}`}
                                                    title={item.result_files?.[0]?.split(/[\\/]/).pop() || 'Untitled'}
                                                >
                                                    {item.result_files?.[0]?.split(/[\\/]/).pop() || 'Untitled'}
                                                </span>
                                                {item.model && (
                                                    <span className={`text-[10px] uppercase tracking-wider font-bold ${item.model === 'spleeter' ? 'text-blue-400' :
                                                        item.model === 'demucs' ? 'text-orange-400' :
                                                            'text-emerald-400'
                                                        }`}>
                                                        {item.model}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-4 py-2">
                                        <span className="text-xs text-gray-400">{item.metadata?.duration || 'N/A'}</span>
                                    </td>
                                    <td className="px-4 py-2 hidden md:table-cell">
                                        <div className="flex items-center space-x-1 truncate">
                                            {item.metadata?.resolution && item.metadata.resolution !== 'N/A' && (
                                                <span className="bg-dark-700 px-1.5 py-0.5 rounded text-[10px] text-gray-400">{item.metadata.resolution}</span>
                                            )}
                                            <span className="bg-dark-700 px-1.5 py-0.5 rounded text-[10px] text-gray-400">{item.metadata?.audio_codec || 'N/A'}</span>
                                        </div>
                                    </td>
                                    <td className="px-4 py-2">
                                        <div className="flex items-center justify-end space-x-1">
                                            <button
                                                className={`p-1.5 rounded transition-all ${
                                                    isCurrentTrack && isPlaying
                                                        ? 'bg-emerald-500 text-dark-950 font-bold shadow-md shadow-emerald-500/30'
                                                        : 'bg-primary-600/10 hover:bg-primary-600 text-primary-400 hover:text-white'
                                                }`}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handlePlayInBrowser(item);
                                                }}
                                                title={isCurrentTrack && isPlaying ? "Playing in browser" : "Play in browser"}
                                            >
                                                <PlayCircle className="w-3.5 h-3.5" />
                                            </button>
                                            {/* Show Separate button only for files from download folder */}
                                            {!item.result_files?.[0].toLowerCase().includes('nomusic') && (
                                                <button
                                                    className="p-1.5 bg-emerald-600/5 hover:bg-emerald-600/20 text-emerald-400 rounded-lg transition-all border border-emerald-500/20 hover:border-emerald-500/40"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        onSeparate?.(item.result_files?.[0]);
                                                    }}
                                                    title="Separate vocals"
                                                >
                                                    <AudioLines className="w-4 h-4" />
                                                </button>
                                            )}
                                            <button
                                                className="p-1.5 bg-dark-700 hover:bg-dark-600 text-gray-400 hover:text-white rounded transition-all"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    libraryAPI.openFolder(item.result_files?.[0]).catch(() => toast.error("Cannot open folder."));
                                                }}
                                                title="Folder"
                                            >
                                                <FolderOpen className="w-3.5 h-3.5" />
                                            </button>
                                            <button
                                                className="p-1.5 bg-red-500/10 hover:bg-red-500 text-red-400 hover:text-white rounded transition-all"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDelete(item.task_id, item.result_files?.[0]);
                                                }}
                                                title="Delete"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            );
                            })}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Pagination Controls */}
            {filteredItems.length > 0 && (
                <div className="flex items-center justify-between flex-wrap gap-3">
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                        <span>Page</span>
                        <span className="text-white font-bold">{currentPage}</span>
                        <span>of {totalPages}</span>
                        <select
                            value={pageSize}
                            onChange={(e) => setPageSize(Number(e.target.value))}
                            className="ml-3 bg-dark-800 text-white text-xs border border-white/10 rounded-lg px-2 py-1 outline-none focus:border-primary-500/50 transition-colors cursor-pointer"
                        >
                            <option value={25}>25 / page</option>
                            <option value={50}>50 / page</option>
                            <option value={100}>100 / page</option>
                            <option value={250}>250 / page</option>
                        </select>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                            disabled={currentPage <= 1}
                            className="p-2 bg-dark-800 hover:bg-dark-700 disabled:opacity-40 disabled:cursor-not-allowed text-gray-400 hover:text-white rounded-lg transition-all border border-white/10"
                            title="Previous page"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                            disabled={currentPage >= totalPages}
                            className="p-2 bg-dark-800 hover:bg-dark-700 disabled:opacity-40 disabled:cursor-not-allowed text-gray-400 hover:text-white rounded-lg transition-all border border-white/10"
                            title="Next page"
                        >
                            <ChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}
            </div>

            {/* Delete Confirmation Modal - Portaled to Body */}
            {deleteConfirm && createPortal(
                <AnimatePresence>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
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
                                <br /><br />
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
                </AnimatePresence>,
                document.body
            )}

            {/* Rename Modal - Portaled to Body */}
            {renameConfirm && createPortal(
                <AnimatePresence>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
                        onClick={() => setRenameConfirm(null)}
                    >
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.95, opacity: 0 }}
                            onClick={(e) => e.stopPropagation()}
                            className="bg-dark-900 border border-white/10 rounded-2xl p-6 max-w-md w-full shadow-2xl"
                        >
                            <div className="flex items-center space-x-3 mb-4">
                                <div className="p-3 bg-primary-600/20 rounded-full">
                                    <Edit3 className="w-6 h-6 text-primary-500" />
                                </div>
                                <h3 className="text-xl font-bold text-white">Rename File</h3>
                            </div>

                            <div className="space-y-4 mb-6">
                                <p className="text-xs text-gray-400">
                                    Enter a new name for the file. The extension will be preserved.
                                </p>
                                <input
                                    autoFocus
                                    type="text"
                                    value={renameConfirm.newName}
                                    onChange={(e) => setRenameConfirm({ ...renameConfirm, newName: e.target.value })}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') executeRename();
                                        if (e.key === 'Escape') setRenameConfirm(null);
                                    }}
                                    className="w-full bg-dark-800 text-white text-sm border border-white/10 rounded-lg px-4 py-3 outline-none focus:border-primary-500/50 transition-colors"
                                    placeholder="Enter new filename"
                                />
                            </div>

                            <div className="flex gap-3">
                                <button
                                    onClick={() => setRenameConfirm(null)}
                                    className="flex-1 px-4 py-3 bg-dark-800 hover:bg-dark-700 text-gray-300 hover:text-white rounded-xl font-bold transition-all border border-white/10"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={executeRename}
                                    disabled={!renameConfirm.newName || !renameConfirm.newName.trim()}
                                    className="flex-1 px-4 py-3 bg-gradient-to-r from-primary-600 to-indigo-600 hover:from-primary-500 hover:to-indigo-500 text-white rounded-xl font-bold transition-all shadow-lg shadow-primary-600/30 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    Rename
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                </AnimatePresence>,
                document.body
            )}

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
                            handlePlayInBrowser(contextMenu.item);
                            setContextMenu(null);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300 flex items-center gap-2 font-medium"
                    >
                        <Play className="w-4 h-4 fill-current" />
                        Play in Browser
                    </button>
                    <button
                        onClick={() => {
                            libraryAPI.openFile(contextMenu.item?.result_files?.[0]).catch(() => { });
                            setContextMenu(null);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-white/5 hover:text-white flex items-center gap-2"
                    >
                        <ExternalLink className="w-4 h-4" />
                        Open in Desktop Player
                    </button>
                    <button
                        onClick={() => {
                            handleRename(contextMenu.item);
                            setContextMenu(null);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-white/5 hover:text-white flex items-center gap-2"
                    >
                        <Edit3 className="w-4 h-4" />
                        Rename
                    </button>
                    <button
                        onClick={() => {
                            libraryAPI.openFolder(contextMenu.item?.result_files?.[0]).catch(() => { });
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
                            className="w-full px-3 py-2 text-left text-sm text-emerald-400 hover:bg-emerald-600/10 flex items-center gap-2"
                        >
                            <AudioLines className="w-4 h-4" />
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

            {/* Create New Folder Modal - Portaled to Body */}
            {showNewFolderModal && createPortal(
                <AnimatePresence>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
                        onClick={() => setShowNewFolderModal(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.95, opacity: 0 }}
                            onClick={(e) => e.stopPropagation()}
                            className="bg-dark-900 border border-white/10 rounded-2xl p-6 max-w-md w-full shadow-2xl"
                        >
                            <div className="flex items-center space-x-3 mb-4">
                                <div className="p-3 bg-amber-500/20 rounded-full">
                                    <FolderPlus className="w-6 h-6 text-amber-400" />
                                </div>
                                <div>
                                    <h3 className="text-xl font-bold text-white">Create New Folder</h3>
                                    <p className="text-xs text-gray-400">Add a subfolder to organize your audio files</p>
                                </div>
                            </div>

                            <form onSubmit={handleCreateFolderSubmit} className="space-y-4">
                                <div>
                                    <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                                        Folder Location
                                    </label>
                                    <div className="grid grid-cols-2 gap-2">
                                        <button
                                            type="button"
                                            onClick={() => setNewFolderCategory('download')}
                                            className={`p-3 rounded-xl border text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                                                newFolderCategory === 'download'
                                                    ? 'bg-red-600/20 border-red-500/50 text-red-300 shadow-sm'
                                                    : 'bg-dark-800 border-white/10 text-gray-400 hover:text-white'
                                            }`}
                                        >
                                            <Download className="w-4 h-4 text-red-400" />
                                            <span>Download</span>
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => setNewFolderCategory('nomusic')}
                                            className={`p-3 rounded-xl border text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                                                newFolderCategory === 'nomusic'
                                                    ? 'bg-emerald-600/20 border-emerald-500/50 text-emerald-300 shadow-sm'
                                                    : 'bg-dark-800 border-white/10 text-gray-400 hover:text-white'
                                            }`}
                                        >
                                            <Music2 className="w-4 h-4 text-emerald-400" />
                                            <span>NoMusic</span>
                                        </button>
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                                        Folder Name
                                    </label>
                                    <input
                                        type="text"
                                        autoFocus
                                        value={newFolderName}
                                        onChange={(e) => setNewFolderName(e.target.value)}
                                        placeholder="e.g. Cartoon Season 1, Podcasts..."
                                        className="w-full bg-dark-800 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-amber-500/50 transition-colors"
                                    />
                                </div>

                                <div className="flex gap-3 pt-2">
                                    <button
                                        type="button"
                                        onClick={() => setShowNewFolderModal(false)}
                                        className="flex-1 px-4 py-2.5 bg-dark-800 hover:bg-dark-700 text-gray-300 hover:text-white rounded-xl font-bold transition-all border border-white/10 text-sm"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        disabled={!newFolderName.trim()}
                                        className="flex-1 px-4 py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 text-white rounded-xl font-bold transition-all shadow-lg shadow-amber-500/30 text-sm flex items-center justify-center gap-2"
                                    >
                                        <FolderPlus className="w-4 h-4" />
                                        <span>Create Folder</span>
                                    </button>
                                </div>
                            </form>
                        </motion.div>
                    </motion.div>
                </AnimatePresence>,
                document.body
            )}
        </div>
    );
};

export default LibraryTab;
