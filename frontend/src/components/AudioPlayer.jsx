import React, { useState } from 'react';
import { useAudioPlayer } from '../contexts/AudioPlayerContext';
import { libraryAPI } from '../api/index.js';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  RotateCcw,
  RotateCw,
  Repeat,
  X,
  Music,
  ExternalLink,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { toast } from 'react-hot-toast';

const formatTime = (seconds) => {
  if (isNaN(seconds) || seconds < 0) return "00:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

const AudioPlayer = () => {
  const {
    currentTrack,
    isPlaying,
    currentTime,
    duration,
    volume,
    isMuted,
    playbackRate,
    isLooping,
    isLoading,
    togglePlay,
    seek,
    setVolume,
    toggleMute,
    setPlaybackRate,
    toggleLoop,
    skipSeconds,
    closePlayer,
  } = useAudioPlayer();

  const [showSpeedMenu, setShowSpeedMenu] = useState(false);

  if (!currentTrack) return null;

  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  const handleSeekChange = (e) => {
    const newPercent = parseFloat(e.target.value);
    const newTime = (newPercent / 100) * duration;
    seek(newTime);
  };

  const handleOpenExternal = async () => {
    if (currentTrack.path) {
      try {
        await libraryAPI.openFile(currentTrack.path);
        toast.success("Opening in desktop player...");
      } catch (err) {
        toast.error("Could not open file externally.");
      }
    }
  };

  const rates = [0.75, 1.0, 1.25, 1.5, 2.0];

  return (
    <AnimatePresence>
      <div className="fixed bottom-5 inset-x-0 z-50 flex justify-center px-4 pointer-events-none">
        <motion.div
          initial={{ y: 80, opacity: 0, scale: 0.95 }}
          animate={{ y: 0, opacity: 1, scale: 1 }}
          exit={{ y: 80, opacity: 0, scale: 0.95 }}
          transition={{ type: "spring", stiffness: 320, damping: 30 }}
          className="w-full max-w-3xl pointer-events-auto"
        >
          <div className="relative bg-dark-900/95 backdrop-blur-2xl border border-white/15 shadow-2xl rounded-2xl p-3.5 sm:p-4 text-white overflow-hidden ring-1 ring-primary-500/20">
          {/* Subtle animated background glow */}
          <div className="absolute -top-24 -left-24 w-48 h-48 bg-primary-500/15 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-24 -right-24 w-48 h-48 bg-emerald-500/15 rounded-full blur-3xl pointer-events-none" />

          {/* Progress Bar Header */}
          <div className="space-y-1 mb-2">
            <div className="flex items-center justify-between text-xs text-gray-400 font-mono px-0.5">
              <span>{formatTime(currentTime)}</span>
              <span className="text-gray-500">{formatTime(duration)}</span>
            </div>

            <div className="relative group cursor-pointer h-2 flex items-center">
              <input
                type="range"
                min="0"
                max="100"
                step="0.1"
                value={progressPercent || 0}
                onChange={handleSeekChange}
                className="absolute inset-0 w-full h-full opacity-0 z-20 cursor-pointer"
                title="Seek"
              />
              {/* Custom Track */}
              <div className="w-full h-1.5 bg-dark-700/80 rounded-full overflow-hidden relative">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 via-primary-500 to-emerald-400 rounded-full transition-all duration-75"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              {/* Scrubber Knob */}
              <div
                className="absolute h-3.5 w-3.5 bg-white rounded-full shadow-md shadow-black/50 border border-primary-400 pointer-events-none -ml-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ left: `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Main Controls Row */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            {/* Left: Track Info & Waveform */}
            <div className="flex items-center space-x-3 min-w-0 w-full sm:w-auto flex-1">
              <div className="relative flex-shrink-0 w-11 h-11 rounded-xl bg-gradient-to-tr from-primary-600 to-emerald-500 p-0.5 shadow-lg shadow-primary-500/20">
                <div className="w-full h-full bg-dark-900 rounded-[10px] flex items-center justify-center">
                  <Music className={`w-5 h-5 ${isPlaying ? 'text-emerald-400' : 'text-primary-400'}`} />
                </div>
                {isPlaying && (
                  <span className="absolute -top-1 -right-1 flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                  </span>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center space-x-2">
                  <h4 className="text-sm font-bold text-white truncate max-w-[200px] sm:max-w-xs" title={currentTrack.title}>
                    {currentTrack.title}
                  </h4>
                  {currentTrack.type && (
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase ${
                      currentTrack.type === 'vocal'
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        : currentTrack.type === 'instrumental'
                        ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                        : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    }`}>
                      {currentTrack.badge || currentTrack.type}
                    </span>
                  )}
                </div>

                {/* Animated Waveform indicator */}
                <div className="flex items-center space-x-1 mt-1">
                  {[...Array(6)].map((_, i) => (
                    <div
                      key={i}
                      className={`w-0.5 rounded-full bg-emerald-400/70 transition-all ${
                        isPlaying ? 'animate-pulse' : 'h-1'
                      }`}
                      style={{
                        height: isPlaying ? `${Math.max(4, ((i * 3 + 5) % 12) + 2)}px` : '4px',
                        animationDelay: `${i * 120}ms`
                      }}
                    />
                  ))}
                  <span className="text-[11px] text-gray-400 font-mono ml-2">In-Browser Player</span>
                </div>
              </div>
            </div>

            {/* Center: Playback Buttons */}
            <div className="flex items-center space-x-2 sm:space-x-3">
              {/* Skip Back 5s */}
              <button
                onClick={() => skipSeconds(-5)}
                className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 active:scale-95 transition-all"
                title="Rewind 5s"
              >
                <RotateCcw className="w-4 h-4" />
              </button>

              {/* Main Play/Pause */}
              <button
                onClick={togglePlay}
                disabled={isLoading}
                className="w-12 h-12 rounded-full bg-gradient-to-r from-primary-500 to-emerald-400 hover:from-primary-400 hover:to-emerald-300 text-dark-950 font-bold flex items-center justify-center shadow-lg shadow-emerald-500/25 active:scale-95 transition-all"
                title={isPlaying ? "Pause (Space)" : "Play (Space)"}
              >
                {isLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin text-dark-950" />
                ) : isPlaying ? (
                  <Pause className="w-5 h-5 fill-current" />
                ) : (
                  <Play className="w-5 h-5 fill-current ml-0.5" />
                )}
              </button>

              {/* Skip Forward 5s */}
              <button
                onClick={() => skipSeconds(5)}
                className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 active:scale-95 transition-all"
                title="Forward 5s"
              >
                <RotateCw className="w-4 h-4" />
              </button>

              {/* Loop Toggle */}
              <button
                onClick={toggleLoop}
                className={`p-2 rounded-lg transition-all ${
                  isLooping
                    ? 'text-emerald-400 bg-emerald-500/20 border border-emerald-500/30'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}
                title={isLooping ? "Looping Enabled" : "Enable Loop"}
              >
                <Repeat className="w-4 h-4" />
              </button>
            </div>

            {/* Right: Volume & Extra Controls */}
            <div className="flex items-center space-x-2 w-full sm:w-auto justify-end">
              {/* Playback Speed */}
              <div className="relative">
                <button
                  onClick={() => setShowSpeedMenu(!showSpeedMenu)}
                  className="px-2 py-1 bg-dark-800 hover:bg-dark-700 text-gray-300 rounded text-xs font-mono font-bold border border-white/10 hover:text-white transition-all"
                  title="Playback Speed"
                >
                  {playbackRate}x
                </button>
                {showSpeedMenu && (
                  <div className="absolute bottom-full right-0 mb-2 bg-dark-800 border border-white/15 rounded-xl shadow-xl py-1 z-30 min-w-[70px]">
                    {rates.map(rate => (
                      <button
                        key={rate}
                        onClick={() => {
                          setPlaybackRate(rate);
                          setShowSpeedMenu(false);
                        }}
                        className={`w-full text-left px-3 py-1 text-xs font-mono hover:bg-primary-500/20 hover:text-primary-300 transition-colors ${
                          playbackRate === rate ? 'text-emerald-400 font-bold bg-emerald-500/10' : 'text-gray-300'
                        }`}
                      >
                        {rate}x
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Volume Slider */}
              <div className="flex items-center space-x-1 bg-dark-800/80 px-2 py-1 rounded-xl border border-white/10">
                <button
                  onClick={toggleMute}
                  className="p-1 text-gray-400 hover:text-white transition-colors"
                  title={isMuted ? "Unmute" : "Mute"}
                >
                  {isMuted || volume === 0 ? (
                    <VolumeX className="w-4 h-4 text-red-400" />
                  ) : (
                    <Volume2 className="w-4 h-4 text-gray-300" />
                  )}
                </button>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={isMuted ? 0 : (volume ?? 1)}
                  onChange={(e) => setVolume(parseFloat(e.target.value))}
                  className="w-16 h-1 bg-dark-600 rounded-lg appearance-none cursor-pointer accent-emerald-400"
                  title={`Volume: ${Math.round((isMuted ? 0 : volume) * 100)}%`}
                />
              </div>

              {/* Open in Desktop Player */}
              {currentTrack.path && (
                <button
                  onClick={handleOpenExternal}
                  className="p-2 text-gray-400 hover:text-primary-400 rounded-lg hover:bg-white/5 active:scale-95 transition-all"
                  title="Open in Desktop Media Player"
                >
                  <ExternalLink className="w-4 h-4" />
                </button>
              )}

              {/* Close Button */}
              <button
                onClick={closePlayer}
                className="p-2 text-gray-400 hover:text-red-400 rounded-lg hover:bg-red-500/10 active:scale-95 transition-all"
                title="Close Player"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  </AnimatePresence>
  );
};

export default AudioPlayer;
