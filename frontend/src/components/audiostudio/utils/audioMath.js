// -------------------------------------------------------------
// AUDIO STUDIO MATH & TIMELINE UTILITIES
// -------------------------------------------------------------

export function formatTime(seconds) {
  if (isNaN(seconds) || seconds < 0) return "00:00.00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
}

export function formatTimeCode(seconds) {
  if (isNaN(seconds) || seconds < 0) return "00:00:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}:${String(ms).padStart(2, '0')}`;
}

export function roundTo(val, dec = 2) {
  if (isNaN(val)) return 0;
  const factor = Math.pow(10, dec);
  return Math.round(val * factor) / factor;
}

export function snapToGrid(time, snapSec) {
  if (!snapSec || snapSec <= 0) return time;
  return Math.round(time / snapSec) * snapSec;
}

export function makeHannCurve(isFadeOut) {
  const n = 64;
  const curve = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1);
    curve[i] = isFadeOut
      ? 0.5 * (1.0 + Math.cos(Math.PI * t))
      : 0.5 * (1.0 - Math.cos(Math.PI * t));
  }
  return curve;
}

export function calcVuLevel(pcm) {
  if (!pcm || pcm.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < pcm.length; i++) {
    sum += pcm[i] * pcm[i];
  }
  const rms = Math.sqrt(sum / pcm.length);
  const db = 20 * Math.log10(rms + 1e-9);
  return Math.round(Math.min(100, Math.max(0, ((db + 60) / 60) * 100)));
}

export function generatePeaks(audioBuffer, targetLength = 1000) {
  if (!audioBuffer) return { min: new Float32Array(0), max: new Float32Array(0) };
  const rawData = audioBuffer.getChannelData(0);
  const sampleCount = rawData.length;
  const blockSize = Math.floor(sampleCount / targetLength) || 1;
  const minPeaks = new Float32Array(targetLength);
  const maxPeaks = new Float32Array(targetLength);

  for (let i = 0; i < targetLength; i++) {
    const start = i * blockSize;
    let min = 0.0;
    let max = 0.0;
    const end = Math.min(start + blockSize, sampleCount);
    for (let j = start; j < end; j++) {
      const val = rawData[j];
      if (val > max) max = val;
      if (val < min) min = val;
    }
    minPeaks[i] = min;
    maxPeaks[i] = max;
  }
  return { min: minPeaks, max: maxPeaks };
}
