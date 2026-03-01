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

          {/* Notification Bell */}
          <NotificationBell />
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
            <DownloaderTab />
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
