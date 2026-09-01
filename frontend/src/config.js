/**
 * Application Configuration
 *
 * Central place for app-wide constants.
 * Version should match pyproject.toml version.
 */
export const APP_VERSION = "0.0.19";

export const APP_NAME = "Audio Splitter Pro";

// Dynamically target port 5170 on current host (e.g. localhost, 192.168.0.111)
// Direct port 5170 streaming bypasses Vite proxy buffering for fast, reliable media playback over LAN.
const computeBackendUrl = () => {
  if (import.meta.env.VITE_BACKEND_URL !== undefined && import.meta.env.VITE_BACKEND_URL !== '') {
    return import.meta.env.VITE_BACKEND_URL;
  }
  if (typeof window !== 'undefined' && window.location && window.location.hostname) {
    const protocol = window.location.protocol || 'http:';
    const hostname = window.location.hostname;
    return `${protocol}//${hostname}:5170`;
  }
  return 'http://localhost:5170';
};

export const BACKEND_URL = computeBackendUrl();
