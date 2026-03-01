/**
 * APP.JSX - Main Application Component
 * 
 * ROLE: Root component that manages tab navigation and layout
 * 
 * STRUCTURE:
 *   - Header: Logo, title, notification bell
 *   - Tab Navigation: Pill-style animated tabs (Separation, Downloader, Library)
 *   - Content Area: Animated tab content with framer-motion transitions
 *   - Footer: Status indicators (API ready, Deno active, version)
 * 
 * STATE:
 *   - activeTab: Current tab ('separation' | 'downloader' | 'library')
 *   - libraryFileToSeparate: File path passed from Library tab for separation
 * 
 * FEATURES:
 *   - Glassmorphism design with gradient backgrounds
 *   - Framer Motion animations for tab transitions
 *   - Persistent tab state (components don't unmount on switch)
 *   - Notification bell integration
 *   - Deno status indicator with click-to-check
 * 
 * DEPENDENCIES:
 *   - framer-motion: Animation library
 *   - lucide-react: Icon components
 *   - ./components/*: Tab content components
 *   - ./contexts/NotificationContext: Notification state
 */
import { useState, useEffect, useRef } from 'react';
import SeparationTab from './components/SeparationTab';
import DownloaderTab from './components/DownloaderTab';
import LibraryTab from './components/LibraryTab';
import NotificationBell from './components/NotificationBell';
import { NotificationProvider } from './contexts/NotificationContext';
import { motion, AnimatePresence } from 'framer-motion';
import { Layers, Download, Music, Library, Terminal, X, Trash2, Cpu, Info, AlertCircle } from 'lucide-react';
import axios from 'axios';

function AppContent() {
  const [activeTab, setActiveTab] = useState('separation');
  const [libraryFileToSeparate, setLibraryFileToSeparate] = useState(null);
  const [showConsole, setShowConsole] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [consoleLogs, setConsoleLogs] = useState([]);
  const [systemInfo, setSystemInfo] = useState(null);
  const [analyzingProgress, setAnalyzingProgress] = useState({ current: 0, total: 0 });
  const consoleEndRef = useRef(null);

  // Parse console logs for playlist progress
  useEffect(() => {
    if (consoleLogs.length > 0) {
      // Look for "Found X entries in playlist" message
      const lastLog = consoleLogs[consoleLogs.length - 1];
      if (lastLog && lastLog.message.includes('Found') && lastLog.message.includes('entries')) {
        const match = lastLog.message.match(/Found (\d+) entries/);
        if (match) {
          setAnalyzingProgress({ current: parseInt(match[1]), total: parseInt(match[1]) });
        }
      }
      // Look for "Downloading item X of Y" messages
      const downloadMatch = lastLog?.message.match(/Downloading item (\d+) of (\d+)/);
      if (downloadMatch) {
        setAnalyzingProgress({ 
          current: parseInt(downloadMatch[1]), 
          total: parseInt(downloadMatch[2]) 
        });
      }
    }
  }, [consoleLogs]);

  const fetchConsoleLogs = async () => {
    try {
      const response = await axios.get('http://localhost:5170/api/console-logs');
      setConsoleLogs(response.data.logs || []);
    } catch (err) {
      console.error("Failed to fetch console logs", err);
    }
  };

  const fetchSystemInfo = async () => {
    try {
      const response = await axios.get('http://localhost:5170/api/system-info');
      setSystemInfo(response.data);
    } catch (err) {
      console.error("Failed to fetch system info", err);
    }
  };

  const clearConsoleLogs = async () => {
    try {
      await axios.post('http://localhost:5170/api/console-logs/clear');
      setConsoleLogs([]);
    } catch (err) {
      console.error("Failed to clear console logs", err);
    }
  };

  // Auto-fetch logs when console is opened
  useEffect(() => {
    if (showConsole) {
      fetchConsoleLogs();
      const interval = setInterval(fetchConsoleLogs, 2000);
      return () => clearInterval(interval);
    }
  }, [showConsole]);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (showConsole && consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [consoleLogs, showConsole]);

  const tabVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { duration: 0.15 } },
    exit: { opacity: 0, transition: { duration: 0.1 } }
  };

  return (
    <div className="min-h-screen text-gray-200 font-sans p-4 md:p-6 selection:bg-primary-500/30">
      <div className="max-w-5xl mx-auto space-y-4">

        {/* Header - Compact */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center justify-between"
        >
          <div className="flex items-center space-x-3">
            <div className="relative group">
              <div className="absolute -inset-1 bg-gradient-to-r from-primary-600 to-accent-500 rounded-full blur opacity-25 group-hover:opacity-75 transition duration-1000 group-hover:duration-200"></div>
              <div className="relative p-2 bg-dark-800 rounded-full ring-1 ring-white/10 shadow-2xl">
                <Music className="w-5 h-5 text-primary-400 group-hover:text-white transition-colors" />
              </div>
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400">
                  Audio Splitter
                </span>{' '}
                <span className="text-gray-500 font-light">Pro</span>
              </h1>
              <p className="text-xs text-gray-500 font-medium">v0.0.3</p>
            </div>
          </div>

          {/* Header Actions */}
          <div className="flex items-center space-x-2">
            {/* GPU/Settings Button */}
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => {
                setShowSettings(true);
                fetchSystemInfo();
              }}
              className="relative p-2 bg-dark-800/80 hover:bg-dark-700 rounded-lg border border-white/10 transition-all group"
              title="System Info & Settings"
            >
              <Cpu className="w-5 h-5 text-gray-400 group-hover:text-blue-400 transition-colors" />
            </motion.button>

            {/* Console Toggle */}
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => {
                setShowConsole(!showConsole);
                if (!showConsole) fetchConsoleLogs();
              }}
              className="relative p-2 bg-dark-800/80 hover:bg-dark-700 rounded-lg border border-white/10 transition-all group"
              title="View backend console logs"
            >
              <Terminal className={`w-5 h-5 transition-colors ${
                showConsole ? 'text-emerald-400' : 'text-gray-400 group-hover:text-white'
              }`} />
              {consoleLogs.length > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-500 rounded-full text-[9px] font-bold text-white flex items-center justify-center">
                  {consoleLogs.length > 99 ? '99+' : consoleLogs.length}
                </span>
              )}
            </motion.button>

            {/* Notification Bell */}
            <NotificationBell />
          </div>
        </motion.div>

        {/* Tab Navigation - Pill Style */}
        <div className="flex justify-center">
          <div className="bg-dark-900/50 backdrop-blur-md p-1 rounded-full inline-flex border border-white/5 shadow-xl relative">
            {['separation', 'downloader', 'library'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`relative px-6 py-2.5 rounded-full text-sm font-semibold transition-all duration-200 z-10 flex items-center space-x-2 outline-none focus:outline-none ${
                  activeTab === tab ? 'text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                {activeTab === tab && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute inset-0 bg-gradient-to-r from-primary-600 to-primary-500 rounded-full shadow-lg shadow-primary-500/30"
                    transition={{ type: "spring", stiffness: 500, damping: 35 }}
                  />
                )}
                <span className="relative z-10 flex items-center space-x-2">
                  {tab === 'separation' ? <Layers className="w-4 h-4" /> : tab === 'downloader' ? <Download className="w-4 h-4" /> : <Library className="w-4 h-4" />}
                  <span className="capitalize">{tab === 'downloader' ? 'YT Downloader' : tab}</span>
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Content Area - Simple Fade */}
        <div className="relative">
          {/* Separation Tab */}
          <motion.div
            key="separation"
            initial={{ opacity: 0 }}
            animate={{ opacity: activeTab === 'separation' ? 1 : 0 }}
            transition={{ duration: 0.15 }}
            style={{ display: activeTab === 'separation' ? 'block' : 'none' }}
            className="glass-card p-6 md:p-8 border border-white/5 bg-gradient-to-b from-dark-800/80 to-dark-900/80 shadow-xl"
          >
            <SeparationTab libraryFile={libraryFileToSeparate} onFileCleared={() => setLibraryFileToSeparate(null)} />
          </motion.div>

          {/* Downloader Tab */}
          <motion.div
            key="downloader"
            initial={{ opacity: 0 }}
            animate={{ opacity: activeTab === 'downloader' ? 1 : 0 }}
            transition={{ duration: 0.15 }}
            style={{ display: activeTab === 'downloader' ? 'block' : 'none' }}
            className="glass-card p-6 md:p-8 border border-white/5 bg-gradient-to-b from-dark-800/80 to-dark-900/80 shadow-xl"
          >
            <DownloaderTab analyzingProgress={analyzingProgress} />
          </motion.div>

          {/* Library Tab */}
          <motion.div
            key="library"
            initial={{ opacity: 0 }}
            animate={{ opacity: activeTab === 'library' ? 1 : 0 }}
            transition={{ duration: 0.15 }}
            style={{ display: activeTab === 'library' ? 'block' : 'none' }}
            className="glass-card p-6 md:p-8 border border-white/5 bg-gradient-to-b from-dark-800/80 to-dark-900/80 shadow-xl"
          >
            <LibraryTab onSeparate={(filePath) => {
              setLibraryFileToSeparate(filePath);
              setActiveTab('separation');
            }} />
          </motion.div>
        </div>

        {/* Console Logs Modal */}
        <AnimatePresence>
          {showConsole && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              className="fixed bottom-4 right-4 left-4 md:left-auto md:w-[600px] bg-dark-900/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden"
              style={{ maxHeight: '70vh' }}
            >
              {/* Console Header */}
              <div className="flex items-center justify-between p-4 border-b border-white/10 bg-dark-800/50">
                <div className="flex items-center space-x-2">
                  <Terminal className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-white font-bold">Backend Console</h3>
                  <span className="text-xs text-gray-500">({consoleLogs.length} logs)</span>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={clearConsoleLogs}
                    className="p-1.5 hover:bg-red-500/20 text-gray-400 hover:text-red-400 rounded-lg transition-all"
                    title="Clear logs"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setShowConsole(false)}
                    className="p-1.5 hover:bg-white/10 text-gray-400 hover:text-white rounded-lg transition-all"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Console Output */}
              <div className="p-4 overflow-y-auto font-mono text-xs space-y-1" style={{ maxHeight: '50vh' }}>
                {consoleLogs.length === 0 ? (
                  <div className="text-gray-500 text-center py-8">
                    <Terminal className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>No logs yet. Logs will appear here when you use yt-dlp or download features.</p>
                  </div>
                ) : (
                  <>
                    {consoleLogs.map((log, idx) => (
                      <div
                        key={idx}
                        className={`whitespace-pre-wrap break-words ${
                          log.level === 'error' ? 'text-red-400 bg-red-900/20' :
                          log.level === 'warning' ? 'text-yellow-400 bg-yellow-900/20' :
                          log.level === 'success' ? 'text-emerald-400 bg-emerald-900/20' :
                          'text-gray-300'
                        } px-2 py-1 rounded`}
                      >
                        {log.message}
                      </div>
                    ))}
                    <div ref={consoleEndRef} />
                  </>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Settings/System Info Modal */}
        <AnimatePresence>
          {showSettings && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
              onClick={() => setShowSettings(false)}
            >
              <motion.div
                initial={{ y: 20 }}
                animate={{ y: 0 }}
                exit={{ y: 20 }}
                onClick={(e) => e.stopPropagation()}
                className="bg-dark-900/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden"
                style={{ maxHeight: '80vh' }}
              >
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-white/10">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-blue-600/20 rounded-lg">
                      <Cpu className="w-6 h-6 text-blue-400" />
                    </div>
                    <div>
                      <h3 className="text-xl font-bold text-white">System Information</h3>
                      <p className="text-xs text-gray-500">Hardware & Software Details</p>
                    </div>
                  </div>
                  <button
                    onClick={() => setShowSettings(false)}
                    className="p-2 hover:bg-white/10 text-gray-400 hover:text-white rounded-lg transition-all"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto" style={{ maxHeight: '60vh' }}>
                  {!systemInfo ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
                      <span className="ml-3 text-gray-400">Loading system info...</span>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* GPU Section */}
                      <div className="bg-dark-800/50 rounded-xl p-4 border border-white/5">
                        <div className="flex items-center space-x-2 mb-3">
                          <Cpu className="w-5 h-5 text-blue-400" />
                          <h4 className="text-white font-bold">GPU / CUDA</h4>
                        </div>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div>
                            <span className="text-gray-500">Status:</span>
                            <p className={`font-medium ${systemInfo.gpu.available ? 'text-emerald-400' : 'text-red-400'}`}>
                              {systemInfo.gpu.available ? '✓ GPU Available' : '✗ GPU Not Available'}
                            </p>
                          </div>
                          {systemInfo.gpu.available && (
                            <>
                              <div>
                                <span className="text-gray-500">GPU Model:</span>
                                <p className="text-white font-medium">{systemInfo.gpu.name}</p>
                              </div>
                              <div>
                                <span className="text-gray-500">VRAM:</span>
                                <p className="text-white font-medium">{systemInfo.gpu.vram_total}</p>
                              </div>
                              <div>
                                <span className="text-gray-500">CUDA Version:</span>
                                <p className="text-white font-medium">{systemInfo.gpu.cuda_version}</p>
                              </div>
                            </>
                          )}
                          {!systemInfo.gpu.available && (
                            <div className="col-span-2">
                              <div className="flex items-start space-x-2 text-yellow-400 text-xs">
                                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                                <p>GPU acceleration not available. Processing will use CPU (slower).</p>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Memory Section */}
                      <div className="bg-dark-800/50 rounded-xl p-4 border border-white/5">
                        <div className="flex items-center space-x-2 mb-3">
                          <Cpu className="w-5 h-5 text-purple-400" />
                          <h4 className="text-white font-bold">Memory (RAM)</h4>
                        </div>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div>
                            <span className="text-gray-500">Total:</span>
                            <p className="text-white font-medium">{systemInfo.memory.total}</p>
                          </div>
                          <div>
                            <span className="text-gray-500">Available:</span>
                            <p className="text-white font-medium">{systemInfo.memory.available}</p>
                          </div>
                          <div className="col-span-2">
                            <span className="text-gray-500">Demucs Usage:</span>
                            <p className="text-yellow-400 font-medium text-xs">{systemInfo.memory.demucs_usage}</p>
                          </div>
                        </div>
                      </div>

                      {/* Storage Section */}
                      <div className="bg-dark-800/50 rounded-xl p-4 border border-white/5">
                        <div className="flex items-center space-x-2 mb-3">
                          <Download className="w-5 h-5 text-emerald-400" />
                          <h4 className="text-white font-bold">Storage</h4>
                        </div>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div>
                            <span className="text-gray-500">Total Space:</span>
                            <p className="text-white font-medium">{systemInfo.storage.total}</p>
                          </div>
                          <div>
                            <span className="text-gray-500">Free Space:</span>
                            <p className={`font-medium ${
                              parseFloat(systemInfo.storage.free) < 10 ? 'text-red-400' : 'text-white'
                            }`}>{systemInfo.storage.free}</p>
                          </div>
                          <div className="col-span-2">
                            <span className="text-gray-500">Output Folder:</span>
                            <p className="text-gray-400 font-mono text-xs truncate">
                              {systemInfo.storage.output_folder}
                              <span className="text-emerald-400 ml-2">({systemInfo.storage.output_size})</span>
                            </p>
                          </div>
                          <div className="col-span-2">
                            <span className="text-gray-500">Download Folder:</span>
                            <p className="text-gray-400 font-mono text-xs truncate">
                              {systemInfo.storage.download_folder}
                              <span className="text-emerald-400 ml-2">({systemInfo.storage.download_size})</span>
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Processing Section */}
                      <div className="bg-dark-800/50 rounded-xl p-4 border border-white/5">
                        <div className="flex items-center space-x-2 mb-3">
                          <Info className="w-5 h-5 text-orange-400" />
                          <h4 className="text-white font-bold">Processing Config</h4>
                        </div>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div>
                            <span className="text-gray-500">Demucs Workers:</span>
                            <p className="text-white font-medium">{systemInfo.processing.demucs_workers}</p>
                          </div>
                          <div>
                            <span className="text-gray-500">Segment Duration:</span>
                            <p className="text-white font-medium">{systemInfo.processing.segment_duration}</p>
                          </div>
                        </div>
                      </div>

                      {/* Library Stats */}
                      <div className="bg-dark-800/50 rounded-xl p-4 border border-white/5">
                        <div className="flex items-center space-x-2 mb-3">
                          <Library className="w-5 h-5 text-cyan-400" />
                          <h4 className="text-white font-bold">Library Stats</h4>
                        </div>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div>
                            <span className="text-gray-500">Total Files:</span>
                            <p className="text-white font-medium">{systemInfo.library.total_files}</p>
                          </div>
                          <div>
                            <span className="text-gray-500">Total Size:</span>
                            <p className="text-white font-medium">{systemInfo.library.total_size}</p>
                          </div>
                        </div>
                      </div>

                      {/* Packages Section */}
                      <div className="bg-dark-800/50 rounded-xl p-4 border border-white/5">
                        <div className="flex items-center space-x-2 mb-3">
                          <Info className="w-5 h-5 text-emerald-400" />
                          <h4 className="text-white font-bold">Package Versions</h4>
                        </div>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          {Object.entries(systemInfo.packages).map(([pkg, version]) => (
                            <div key={pkg}>
                              <span className="text-gray-500 capitalize">{pkg.replace('-', ' ')}:</span>
                              <p className="text-white font-medium">{version}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function App() {
  return (
    <NotificationProvider>
      <AppContent />
    </NotificationProvider>
  );
}

export default App;
