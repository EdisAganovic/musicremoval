/**
 * Application Configuration
 *
 * Central place for app-wide constants.
 * Version should match pyproject.toml version.
 */
export const APP_VERSION = "0.0.19";

export const APP_NAME = "Audio Splitter Pro";

// Same-origin: all /api and /projects calls are proxied by the Vite dev server
// to the backend (see vite.config.js). This keeps the app working from LAN
// devices without CORS/firewall issues. Override with VITE_BACKEND_URL for
// production builds where no proxy is available.
export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
