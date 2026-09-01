import React, { createContext, useContext, useState, useRef, useEffect } from 'react';
import { BACKEND_URL } from '../config';
import { toast } from 'react-hot-toast';

const AudioPlayerContext = createContext(null);

export const AudioPlayerProvider = ({ children }) => {
  const [currentTrack, setCurrentTrack] = useState(null); // { url, title, path, type, badge }
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolumeState] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [playbackRate, setPlaybackRateState] = useState(1);
  const [isLooping, setIsLooping] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Lazy-initialize a persistent Audio element
  const audioRef = useRef(null);
  if (!audioRef.current && typeof window !== 'undefined') {
    const a = new Audio();
    a.preload = "auto";
    audioRef.current = a;
  }

  // Set up event listeners on the audio element
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
    };

    const handleLoadedMetadata = () => {
      console.log(`[AudioPlayer] Metadata loaded, duration: ${audio.duration}s`);
      setDuration(audio.duration || 0);
      setIsLoading(false);
    };

    const handleWaiting = () => {
      setIsLoading(true);
    };

    const handleCanPlay = () => {
      setIsLoading(false);
    };

    const handlePlaying = () => {
      setIsPlaying(true);
      setIsLoading(false);
    };

    const handlePause = () => {
      setIsPlaying(false);
    };

    const handleEnded = () => {
      if (!audio.loop) {
        setIsPlaying(false);
        setCurrentTime(0);
      }
    };

    const handleError = () => {
      // Ignore harmless error events when audio is cleared/closed
      const rawSrc = audio.getAttribute('src');
      if (!rawSrc || !audio.src || audio.src === window.location.href) {
        setIsLoading(false);
        setIsPlaying(false);
        return;
      }

      const mediaErr = audio.error;
      let errMsg = "Media playback error";
      if (mediaErr) {
        switch (mediaErr.code) {
          case 1: errMsg = "Playback aborted by client (Code 1)"; break;
          case 2: errMsg = "Network error downloading audio (Code 2)"; break;
          case 3: errMsg = "Audio decoding error (Code 3)"; break;
          case 4: errMsg = "Audio format not supported or file not found (Code 4)"; break;
          default: errMsg = `Error Code ${mediaErr.code}: ${mediaErr.message || ''}`; break;
        }
      }
      console.error("[AudioPlayer] Error event:", errMsg, audio.error, "Current src:", audio.src);
      setIsLoading(false);
      setIsPlaying(false);
      toast.error(`Audio error: ${errMsg}`);
    };

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('waiting', handleWaiting);
    audio.addEventListener('canplay', handleCanPlay);
    audio.addEventListener('playing', handlePlaying);
    audio.addEventListener('pause', handlePause);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('error', handleError);

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('waiting', handleWaiting);
      audio.removeEventListener('canplay', handleCanPlay);
      audio.removeEventListener('playing', handlePlaying);
      audio.removeEventListener('pause', handlePause);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('error', handleError);
    };
  }, []);

  // Play a track
  const playTrack = (track) => {
    const audio = audioRef.current;
    if (!audio || !track) {
      console.warn("[AudioPlayer] playTrack called with empty audio or track", track);
      return;
    }

    // Resolve URL cleanly
    let streamUrl = track.url;
    if (!streamUrl && track.path) {
      const cleanP = track.path.replace(/^file:\/\/\/?/, '');
      streamUrl = `${BACKEND_URL}/api/media/stream?path=${encodeURIComponent(cleanP)}`;
    }

    console.log("[AudioPlayer] playTrack requested:", { title: track.title, streamUrl, path: track.path });

    const fullTrack = {
      ...track,
      url: streamUrl,
    };

    // If same track, toggle play/pause
    if (currentTrack && (currentTrack.url === streamUrl || (currentTrack.path && currentTrack.path === track.path))) {
      if (isPlaying) {
        audio.pause();
        setIsPlaying(false);
      } else {
        audio.play()
          .then(() => setIsPlaying(true))
          .catch((err) => {
            console.warn("[AudioPlayer] Playback resume blocked:", err);
            toast.error("Tap play button in bottom bar to start audio");
          });
      }
      return;
    }

    // New track
    setCurrentTrack(fullTrack);
    setIsLoading(true);
    setCurrentTime(0);

    try {
      audio.pause();
      audio.src = streamUrl;
      audio.playbackRate = playbackRate;
      audio.loop = isLooping;
      audio.muted = isMuted;
      audio.volume = isMuted ? 0 : (volume ?? 1);
      audio.load();

      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            console.log("[AudioPlayer] Playback started successfully:", streamUrl);
            setIsPlaying(true);
            setIsLoading(false);
          })
          .catch((err) => {
            console.warn("[AudioPlayer] Auto-play was blocked or failed:", err);
            setIsLoading(false);
            setIsPlaying(false);
            if (err.name === 'NotAllowedError') {
              toast.error("Browser blocked autoplay. Tap play in the bottom bar to listen.");
            } else {
              toast.error(`Playback issue: ${err.message || 'Stream not ready'}`);
            }
          });
      }
    } catch (e) {
      console.error("[AudioPlayer] Exception during playTrack:", e);
      setIsLoading(false);
      setIsPlaying(false);
      toast.error(`Could not start playback: ${e.message}`);
    }
  };

  const pauseTrack = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  };

  const resumeTrack = () => {
    if (audioRef.current && currentTrack) {
      audioRef.current.play()
        .then(() => setIsPlaying(true))
        .catch((err) => {
          console.error("[AudioPlayer] Resume error:", err);
          toast.error("Tap play button in player bar");
        });
    }
  };

  const togglePlay = () => {
    if (isPlaying) {
      pauseTrack();
    } else {
      resumeTrack();
    }
  };

  const seek = (seconds) => {
    if (audioRef.current) {
      const targetTime = Math.max(0, Math.min(seconds, duration || 0));
      audioRef.current.currentTime = targetTime;
      setCurrentTime(targetTime);
    }
  };

  const setVolume = (val) => {
    const clamped = Math.max(0, Math.min(val, 1));
    setVolumeState(clamped);
    if (audioRef.current) {
      audioRef.current.volume = clamped;
      if (clamped > 0 && isMuted) {
        setIsMuted(false);
        audioRef.current.muted = false;
      }
    }
  };

  const toggleMute = () => {
    if (audioRef.current) {
      const newMuted = !isMuted;
      setIsMuted(newMuted);
      audioRef.current.muted = newMuted;
      audioRef.current.volume = newMuted ? 0 : volume;
    }
  };

  const setPlaybackRate = (rate) => {
    setPlaybackRateState(rate);
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
    }
  };

  const toggleLoop = () => {
    const newLoop = !isLooping;
    setIsLooping(newLoop);
    if (audioRef.current) {
      audioRef.current.loop = newLoop;
    }
  };

  const skipSeconds = (seconds) => {
    if (audioRef.current) {
      seek(audioRef.current.currentTime + seconds);
    }
  };

  const closePlayer = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.removeAttribute('src');
      audioRef.current.load();
    }
    setCurrentTrack(null);
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
  };

  return (
    <AudioPlayerContext.Provider
      value={{
        currentTrack,
        isPlaying,
        currentTime,
        duration,
        volume,
        isMuted,
        playbackRate,
        isLooping,
        isLoading,
        playTrack,
        pauseTrack,
        resumeTrack,
        togglePlay,
        seek,
        setVolume,
        toggleMute,
        setPlaybackRate,
        toggleLoop,
        skipSeconds,
        closePlayer,
      }}
    >
      {children}
    </AudioPlayerContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components -- context + hook co-location is intentional
export const useAudioPlayer = () => {
  const context = useContext(AudioPlayerContext);
  if (!context) {
    throw new Error("useAudioPlayer must be used within an AudioPlayerProvider");
  }
  return context;
};
