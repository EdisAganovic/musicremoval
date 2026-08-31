import { useState, useRef, useCallback, useEffect } from "react";
import axios from "axios";
import { BACKEND_URL } from "../../../config";
import { makeHannCurve, calcVuLevel, generatePeaks } from "../utils/audioMath";

export function useAudioEngine({ videoRef, isLoopingRef, getProjectDuration }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(30);
  const [masterVolume, setMasterVolume] = useState(1.0);

  // Web Audio Refs
  const audioCtxRef = useRef(null);
  const trackAudioBuffers = useRef({}); // { [trackId]: AudioBuffer }
  const trackPeakData = useRef({}); // { [trackId]: { min: Float32Array, max: Float32Array } }
  const trackSourceNodes = useRef({}); // { [trackId]: AudioBufferSourceNode }
  const trackGainNodes = useRef({}); // { [trackId]: GainNode }
  const trackPanNodes = useRef({}); // { [trackId]: StereoPannerNode }
  const masterGainNode = useRef(null);
  const analyserL = useRef(null);
  const analyserR = useRef(null);
  const vuLevelsRef = useRef({ l: 0, r: 0 });

  const startTimeRef = useRef(0);
  const pauseOffsetRef = useRef(0);
  const isPlayingRef = useRef(false);
  const animationFrameRef = useRef(null);
  const updatePlayheadRef = useRef(null);

  // Initialize Web Audio Context & Master Chain
  const initAudioEngine = useCallback(() => {
    if (!audioCtxRef.current) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioCtx();
      audioCtxRef.current = ctx;

      const master = ctx.createGain();
      master.gain.value = masterVolume;
      masterGainNode.current = master;

      const anL = ctx.createAnalyser();
      anL.fftSize = 256;
      analyserL.current = anL;

      const anR = ctx.createAnalyser();
      anR.fftSize = 256;
      analyserR.current = anR;

      const splitter = ctx.createChannelSplitter(2);
      master.connect(splitter);
      splitter.connect(anL, 0);
      splitter.connect(anR, 1);
      master.connect(ctx.destination);
    }
    return audioCtxRef.current;
  }, [masterVolume]);

  // Master Volume update
  useEffect(() => {
    if (masterGainNode.current && audioCtxRef.current) {
      masterGainNode.current.gain.setValueAtTime(masterVolume, audioCtxRef.current.currentTime);
    }
  }, [masterVolume]);

  // Apply cuts automation envelope to a track GainNode
  const applyCutsAutomationToGainNode = useCallback((gainNode, track, offset, ctx, isMuted) => {
    if (!gainNode || !ctx) return;
    const now = ctx.currentTime;
    try {
      gainNode.gain.cancelScheduledValues(now);
    } catch (_e) {}

    if (isMuted) {
      gainNode.gain.setValueAtTime(0.0, now);
      return;
    }

    const baseVol = track.volume ?? 1.0;

    // Normalize + sort cuts so scheduling is deterministic
    const cuts = (track.cuts || [])
      .map(c => {
        const s = Math.max(0, Math.min(c.start, c.end));
        const e = Math.max(0, Math.max(c.start, c.end));
        const dur = Math.max(0.01, e - s);
        return {
          start: s,
          end: e,
          fadeOut: Math.min(dur * 0.48, Math.max(0.01, (c.fade_out_ms || 100) / 1000.0)),
          fadeIn: Math.min(dur * 0.48, Math.max(0.01, (c.fade_in_ms || 100) / 1000.0)),
        };
      })
      .sort((a, b) => a.start - b.start);

    if (cuts.length === 0) {
      gainNode.gain.setValueAtTime(baseVol, now);
      return;
    }

    const hannOut = makeHannCurve(true); // 1.0 -> 0.0 (fade-out)
    const hannIn = makeHannCurve(false); // 0.0 -> 1.0 (fade-in)
    const scaledHannOut = new Float32Array(hannOut.length);
    const scaledHannIn = new Float32Array(hannIn.length);
    for (let j = 0; j < hannOut.length; j++) {
      scaledHannOut[j] = hannOut[j] * baseVol;
      scaledHannIn[j] = hannIn[j] * baseVol;
    }

    const tCtx = (absSec) => Math.max(now, now + (absSec - offset));

    // Gain at current offset — prevents clicks when seeking mid-cut
    let initial = baseVol;
    for (const c of cuts) {
      if (offset >= c.start && offset < c.start + c.fadeOut) {
        const t = (offset - c.start) / c.fadeOut;
        initial = baseVol * 0.5 * (1.0 + Math.cos(Math.PI * t));
        break;
      } else if (offset >= c.start + c.fadeOut && offset <= c.end - c.fadeIn) {
        initial = 0.0;
        break;
      } else if (offset > c.end - c.fadeIn && offset <= c.end) {
        const t = (offset - (c.end - c.fadeIn)) / c.fadeIn;
        initial = baseVol * 0.5 * (1.0 - Math.cos(Math.PI * t));
        break;
      }
    }
    gainNode.gain.setValueAtTime(initial, now);

    cuts.forEach((cut) => {
      const cutStart = cut.start;
      const cutEnd = cut.end;
      const fadeOutEnd = cut.start + cut.fadeOut;
      const fadeInStart = cut.end - cut.fadeIn;

      // 1. Fade OUT (from cutStart to cutStart + fadeOut)
      if (cutStart > offset) {
        gainNode.gain.setValueAtTime(baseVol, tCtx(cutStart));
        gainNode.gain.setValueCurveAtTime(scaledHannOut, tCtx(cutStart), Math.max(0.0001, cut.fadeOut));
      } else if (offset >= cutStart && offset < fadeOutEnd) {
        gainNode.gain.linearRampToValueAtTime(0.0, tCtx(fadeOutEnd));
      }

      // 2. Pure Silence between (cutStart + fadeOut) and (cutEnd - fadeIn)
      if (fadeOutEnd > offset) {
        gainNode.gain.setValueAtTime(0.0, tCtx(fadeOutEnd));
      }

      // 3. Fade IN (from cutEnd - fadeIn to cutEnd)
      if (fadeInStart > offset) {
        gainNode.gain.setValueAtTime(0.0, tCtx(fadeInStart));
        gainNode.gain.setValueCurveAtTime(scaledHannIn, tCtx(fadeInStart), Math.max(0.0001, cut.fadeIn));
      } else if (offset >= fadeInStart && offset < cutEnd) {
        gainNode.gain.linearRampToValueAtTime(baseVol, tCtx(cutEnd));
      }
    });

    // Ensure past the last cut it returns to baseVol
    const last = cuts[cuts.length - 1];
    if (offset >= last.end) {
      gainNode.gain.setValueAtTime(baseVol, now);
    }
  }, []);

  // Sync gains across all active tracks
  const syncWebAudioGains = useCallback((tracks) => {
    if (!audioCtxRef.current || !tracks) return;
    const ctx = audioCtxRef.current;
    const hasSolo = tracks.some(t => t.solo);
    const currentOffset = pauseOffsetRef.current || 0;

    tracks.forEach(track => {
      const gainNode = trackGainNodes.current[track.id];
      if (gainNode) {
        const isMuted = hasSolo ? !track.solo : track.muted;
        applyCutsAutomationToGainNode(gainNode, track, currentOffset, ctx, isMuted);
      }
    });
  }, [applyCutsAutomationToGainNode]);

  // Preload and populate peak arrays from project data
  const populateTrackPeaks = useCallback((tracks) => {
    if (!tracks || !Array.isArray(tracks)) return;
    tracks.forEach(track => {
      if (track.peaks && track.peaks.min && track.peaks.min.length > 0) {
        trackPeakData.current[track.id] = {
          min: new Float32Array(track.peaks.min),
          max: new Float32Array(track.peaks.max)
        };
      }
    });
  }, []);

  // Load an audio buffer for a track
  const loadTrackAudio = useCallback(async (track) => {
    if (!track.audio_url) return null;
    const ctx = initAudioEngine();
    const url = `${BACKEND_URL}${track.audio_url}`;

    try {
      const res = await axios.get(url, { responseType: "arraybuffer" });
      const audioBuffer = await ctx.decodeAudioData(res.data.slice(0));
      trackAudioBuffers.current[track.id] = audioBuffer;

      // Only compute client-side peaks if not already precomputed
      if (!trackPeakData.current[track.id] || trackPeakData.current[track.id].min.length === 0) {
        if (track.peaks && track.peaks.min && track.peaks.min.length > 0) {
          trackPeakData.current[track.id] = {
            min: new Float32Array(track.peaks.min),
            max: new Float32Array(track.peaks.max)
          };
        } else {
          trackPeakData.current[track.id] = generatePeaks(audioBuffer, 1200);
        }
      }

      // Create Gain & Pan nodes if needed
      if (!trackGainNodes.current[track.id]) {
        const gNode = ctx.createGain();
        gNode.gain.value = track.volume ?? 1.0;
        trackGainNodes.current[track.id] = gNode;

        let panNode = null;
        if (ctx.createStereoPanner) {
          panNode = ctx.createStereoPanner();
          panNode.pan.value = track.pan ?? 0.0;
          trackPanNodes.current[track.id] = panNode;
          gNode.connect(panNode);
          panNode.connect(masterGainNode.current);
        } else {
          gNode.connect(masterGainNode.current);
        }
      }

      setDuration(prev => Math.max(prev, audioBuffer.duration));
      return audioBuffer;
    } catch (_err) {
      return null;
    }
  }, [initAudioEngine]);

  // Stop All Active Buffer Sources
  const stopAllSources = useCallback(() => {
    Object.values(trackSourceNodes.current).forEach(src => {
      try {
        src.stop();
        src.disconnect();
      } catch (_e) {}
    });
    trackSourceNodes.current = {};
  }, []);

  // Pause Playback
  const pausePlayback = useCallback(() => {
    if (!isPlayingRef.current) return;
    isPlayingRef.current = false;
    setIsPlaying(false);

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    if (audioCtxRef.current) {
      const elapsed = audioCtxRef.current.currentTime - startTimeRef.current;
      pauseOffsetRef.current += elapsed;
      setCurrentTime(pauseOffsetRef.current);
    }

    stopAllSources();

    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = pauseOffsetRef.current;
    }

    vuLevelsRef.current = { l: 0, r: 0 };
  }, [stopAllSources, videoRef]);

  // Stop Playback
  const stopPlayback = useCallback(() => {
    isPlayingRef.current = false;
    setIsPlaying(false);

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    pauseOffsetRef.current = 0;
    setCurrentTime(0);
    stopAllSources();

    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
    }

    vuLevelsRef.current = { l: 0, r: 0 };
  }, [stopAllSources, videoRef]);

  // Update playhead RAF loop
  const updatePlayhead = useCallback(() => {
    if (!isPlayingRef.current || !audioCtxRef.current) return;
    const elapsed = audioCtxRef.current.currentTime - startTimeRef.current;
    const current = pauseOffsetRef.current + elapsed;
    const projDuration = getProjectDuration();

    if (current >= projDuration) {
      if (isLoopingRef && isLoopingRef.current) {
        pauseOffsetRef.current = 0;
        startTimeRef.current = audioCtxRef.current.currentTime;
        setCurrentTime(0);
        if (videoRef.current) videoRef.current.currentTime = 0;
      } else {
        pausePlayback();
        setCurrentTime(projDuration);
        pauseOffsetRef.current = 0;
        return;
      }
    } else {
      setCurrentTime(current);
    }

    // VU Meter calculations
    if (analyserL.current && analyserR.current) {
      const pcmL = new Float32Array(analyserL.current.fftSize);
      const pcmR = new Float32Array(analyserR.current.fftSize);
      analyserL.current.getFloatTimeDomainData(pcmL);
      analyserR.current.getFloatTimeDomainData(pcmR);
      vuLevelsRef.current = {
        l: calcVuLevel(pcmL),
        r: calcVuLevel(pcmR)
      };
    }

    if (updatePlayheadRef.current) {
      animationFrameRef.current = requestAnimationFrame(updatePlayheadRef.current);
    }
  }, [getProjectDuration, isLoopingRef, pausePlayback, videoRef]);

  useEffect(() => {
    updatePlayheadRef.current = updatePlayhead;
  }, [updatePlayhead]);

  // Start Playback
  const startPlayback = useCallback((tracks) => {
    if (!tracks || tracks.length === 0) return;
    const ctx = initAudioEngine();
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }
    stopAllSources();

    const offset = pauseOffsetRef.current;
    startTimeRef.current = ctx.currentTime;
    isPlayingRef.current = true;
    setIsPlaying(true);

    const hasSolo = tracks.some(t => t.solo);

    tracks.forEach(track => {
      const buffer = trackAudioBuffers.current[track.id];
      if (!buffer) return;

      const src = ctx.createBufferSource();
      src.buffer = buffer;

      const gainNode = trackGainNodes.current[track.id];
      if (gainNode) {
        src.connect(gainNode);
        const isMuted = hasSolo ? !track.solo : track.muted;
        applyCutsAutomationToGainNode(gainNode, track, offset, ctx, isMuted);
      }

      const playOffset = Math.min(offset, buffer.duration);
      if (playOffset < buffer.duration) {
        src.start(0, playOffset);
        trackSourceNodes.current[track.id] = src;
      }
    });

    if (videoRef.current) {
      videoRef.current.currentTime = offset;
      videoRef.current.play().catch(() => {});
    }

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    if (updatePlayheadRef.current) {
      animationFrameRef.current = requestAnimationFrame(updatePlayheadRef.current);
    }
  }, [initAudioEngine, stopAllSources, applyCutsAutomationToGainNode, videoRef]);

  // Seek to absolute time
  const seekTo = useCallback((targetTime, tracks) => {
    const projDur = getProjectDuration();
    const clampedTime = Math.max(0, Math.min(projDur, targetTime));
    pauseOffsetRef.current = clampedTime;
    setCurrentTime(clampedTime);

    if (videoRef.current) {
      videoRef.current.currentTime = clampedTime;
    }

    if (isPlayingRef.current && tracks) {
      startPlayback(tracks);
    } else if (tracks) {
      syncWebAudioGains(tracks);
    }
  }, [getProjectDuration, startPlayback, syncWebAudioGains, videoRef]);

  // Set Track Pan
  const setTrackPan = useCallback((trackId, pan) => {
    const pNode = trackPanNodes.current[trackId];
    if (pNode && audioCtxRef.current) {
      pNode.pan.setValueAtTime(pan, audioCtxRef.current.currentTime);
    }
  }, []);

  return {
    isPlaying,
    currentTime,
    duration,
    setDuration,
    masterVolume,
    setMasterVolume,
    audioCtxRef,
    trackAudioBuffers,
    trackPeakData,
    vuLevelsRef,
    pauseOffsetRef,
    isPlayingRef,
    initAudioEngine,
    populateTrackPeaks,
    loadTrackAudio,
    applyCutsAutomationToGainNode,
    syncWebAudioGains,
    startPlayback,
    pausePlayback,
    stopPlayback,
    seekTo,
    setTrackPan
  };
}
