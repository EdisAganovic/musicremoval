/**
 * Application Configuration
 *
 * Central place for app-wide constants.
 * Version should match pyproject.toml version.
 */
export const APP_VERSION = "0.0.19";

export const APP_NAME = "Audio Splitter Pro";

// Use dynamic hostname if running in browser, so devices on the same LAN connect to the right backend
const defaultBackendHost = typeof window !== 'undefined' && window.location.hostname
    ? `http://${window.location.hostname}:5170`
    : 'http://localhost:5170';

export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || defaultBackendHost;
