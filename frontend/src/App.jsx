import { useState } from 'react';
import SeparationTab from './components/SeparationTab';
import DownloaderTab from './components/DownloaderTab';
import LibraryTab from './components/LibraryTab';
import NotificationBell from './components/NotificationBell';
import { NotificationProvider } from './contexts/NotificationContext';
import { motion, AnimatePresence } from 'framer-motion';
import { Layers, Download, Music, Library } from 'lucide-react';

function AppContent() {
  const [activeTab, setActiveTab] = useState('separation');
  const [libraryFileToSeparate, setLibraryFileToSeparate] = useState(null);

  const tabVariants = {
    hidden: { opacity: 0, y: 10 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
    exit: { opacity: 0, y: -10, transition: { duration: 0.2 } }
  };

  return (
    <div className="min-h-screen text-gray-200 font-sans p-6 md:p-12 selection:bg-primary-500/30">
      <div className="max-w-5xl mx-auto space-y-8">
        
        {/* Header - Glassmorphism */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between mb-10"
        >
          <div className="flex items-center space-x-6">
            <div className="relative group">
              <div className="absolute -inset-1 bg-gradient-to-r from-primary-600 to-accent-500 rounded-full blur opacity-25 group-hover:opacity-75 transition duration-1000 group-hover:duration-200"></div>
              <div className="relative p-4 bg-dark-800 rounded-full ring-1 ring-white/10 shadow-2xl">
                <Music className="w-8 h-8 text-primary-400 group-hover:text-white transition-colors" />
              </div>
            </div>
            <div>
              <h1 className="text-4xl font-extrabold tracking-tight text-white drop-shadow-lg">
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400">
                  Audio Splitter
                </span>{' '}
                <span className="text-gray-500 font-light">Pro</span>
              </h1>
              <p className="text-gray-400 mt-1 font-medium tracking-wide">Next-Gen AI Separation & Downloader</p>
            </div>
          </div>
          
          {/* Notification Bell */}
          <NotificationBell />
        </motion.div>

        {/* Tab Navigation - Pill Style */}
        <div className="flex justify-center mb-8">
          <div className="bg-dark-900/50 backdrop-blur-md p-1.5 rounded-full inline-flex border border-white/5 shadow-xl relative">
            {['separation', 'downloader', 'library'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`relative px-8 py-3 rounded-full text-sm font-semibold transition-all duration-300 z-10 flex items-center space-x-2 outline-none focus:outline-none ${
                  activeTab === tab ? 'text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                {activeTab === tab && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute inset-0 bg-gradient-to-r from-primary-600 to-primary-500 rounded-full shadow-lg shadow-primary-500/30"
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
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

        {/* Content Area - Persistent Tabs (Preserves State) */}
        <div className="relative min-h-[500px]">
          {/* Separation Tab Wrapper */}
          <motion.div
            initial={false}
            animate={{
              opacity: activeTab === 'separation' ? 1 : 0,
              scale: activeTab === 'separation' ? 1 : 0.98,
              y: activeTab === 'separation' ? 0 : 10,
              display: activeTab === 'separation' ? 'block' : 'none'
            }}
            transition={{ duration: 0.3 }}
            className="glass-card p-8 md:p-10 min-h-[500px] border border-white/5 bg-gradient-to-b from-dark-800/80 to-dark-900/80 shadow-[0_0_50px_-12px_rgba(0,0,0,0.5)]"
          >
            <SeparationTab libraryFile={libraryFileToSeparate} onFileCleared={() => setLibraryFileToSeparate(null)} />
          </motion.div>

          {/* Downloader Tab Wrapper */}
          <motion.div
            initial={false}
            animate={{ 
              opacity: activeTab === 'downloader' ? 1 : 0,
              scale: activeTab === 'downloader' ? 1 : 0.98,
              y: activeTab === 'downloader' ? 0 : 10,
              display: activeTab === 'downloader' ? 'block' : 'none'
            }}
            transition={{ duration: 0.3 }}
            className="glass-card p-8 md:p-10 min-h-[500px] border border-white/5 bg-gradient-to-b from-dark-800/80 to-dark-900/80 shadow-[0_0_50px_-12px_rgba(0,0,0,0.5)]"
          >
            <DownloaderTab />
          </motion.div>

          {/* Library Tab Wrapper */}
          <motion.div
            initial={false}
            animate={{
              opacity: activeTab === 'library' ? 1 : 0,
              scale: activeTab === 'library' ? 1 : 0.98,
              y: activeTab === 'library' ? 0 : 10,
              display: activeTab === 'library' ? 'block' : 'none'
            }}
            transition={{ duration: 0.3 }}
            className="glass-card p-8 md:p-10 min-h-[500px] border border-white/5 bg-gradient-to-b from-dark-800/80 to-dark-900/80 shadow-[0_0_50px_-12px_rgba(0,0,0,0.5)]"
          >
            <LibraryTab onSeparate={(filePath) => {
              setLibraryFileToSeparate(filePath);
              setActiveTab('separation');
            }} />
          </motion.div>
        </div>

        {/* Footer Status */}
        <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="flex flex-col items-center space-y-2 mt-12"
        >
            <div className="flex justify-center items-center space-x-6 text-[10px] text-gray-500 bg-dark-900/40 py-2.5 px-6 rounded-full border border-white/5 backdrop-blur-md shadow-2xl">
                <div className="flex items-center space-x-2">
                    <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_8px_#10b981]"></div>
                    <span className="font-mono tracking-widest uppercase">API READY</span>
                </div>
                
                <div className="w-px h-3 bg-white/10"></div>
                
                <div 
                    className="flex items-center space-x-2 cursor-help group"
                    onClick={async () => {
                        try {
                            const res = await fetch('http://localhost:8000/api/deno-info');
                            const data = await res.json();
                            alert(`Deno Status:\n${JSON.stringify(data.output ? JSON.parse(data.output) : data, null, 2)}`);
                        } catch (err) {
                            alert("Deno info check failed.");
                        }
                    }}
                >
                    <span className="text-primary-400 group-hover:text-primary-300 transition-colors">🦖</span>
                    <span className="font-mono tracking-widest uppercase group-hover:text-gray-300">DENO ACTIVE</span>
                </div>

                <div className="w-px h-3 bg-white/10"></div>

                <span className="font-mono tracking-widest opacity-60">v1.2.0-BETA</span>
            </div>
            <p className="text-[9px] text-gray-600 uppercase tracking-[0.2em] font-bold">2025 DeepMind Advanced Audio Ecosystem</p>
        </motion.div>
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
