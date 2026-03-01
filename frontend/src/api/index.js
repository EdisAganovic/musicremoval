/**
 * API Client Layer
 * Centralized API communication for the application
 */
import axios from 'axios';

// Get base URL from environment or default to localhost
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5170/api';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000, // 30 second timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging/debugging
api.interceptors.request.use(
  (config) => {
    console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('[API] Request error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ECONNABORTED') {
      console.error('[API] Request timeout');
    } else if (error.response) {
      console.error(`[API] Error ${error.response.status}:`, error.response.data);
    } else {
      console.error('[API] Network error:', error.message);
    }
    return Promise.reject(error);
  }
);

// Separation API endpoints
export const separationAPI = {
  upload: (file, model) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model', model);
    return api.post('/separate', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  separateFile: (filePath, model) =>
    api.post('/separate-file', { file_path: filePath, model }),
  status: (taskId) => api.get(`/status/${taskId}`),
  scanFolder: (folderPath) => api.post('/folder/scan', { folder_path: folderPath }),
  processBatch: (queueId, model) =>
    api.post('/folder-queue/process', { queue_id: queueId, model }),
  removeFromQueue: (queueId, fileId) =>
    api.post('/folder-queue/remove', { queue_id: queueId, file_id: fileId }),
  batchStatus: (batchId) => api.get(`/batch-status/${batchId}`),
};

// Download API endpoints
export const downloadAPI = {
  start: (url, format, formatId, subtitles) =>
    api.post('/download', { url, format, format_id: formatId, subtitles }),
  cancel: (taskId) => api.post('/download/cancel', { task_id: taskId }),
  formats: (url, checkPlaylist) =>
    api.post('/yt-formats', { url, check_playlist: checkPlaylist }),
  status: (taskId) => api.get(`/status/${taskId}`),
};

// Queue API endpoints
export const queueAPI = {
  add: (url, format, formatId, subtitles, autoSeparate) =>
    api.post('/queue/add', { url, format, format_id: formatId, subtitles, auto_separate: autoSeparate }),
  addBatch: (videos, format, formatId, subtitles, autoSeparate) =>
    api.post('/queue/add-batch', { videos, format, format_id: formatId, subtitles, auto_separate: autoSeparate }),
  remove: (queueId) => api.post('/queue/remove', { queue_id: queueId }),
  clear: () => api.post('/queue/clear'),
  start: () => api.post('/queue/start'),
  stop: () => api.post('/queue/stop'),
  get: () => api.get('/queue'),
};

// Library API endpoints
export const libraryAPI = {
  get: () => api.get('/library'),
  delete: (taskId) => api.post('/delete-file', { task_id: taskId }),
  openFile: (path) => api.post('/open-file', { path }),
  openFolder: (folderName) => {
    // Convert folder name to full path
    const folderPaths = {
      'download': 'download',
      'nomusic': 'nomusic'
    };
    const folderPath = folderPaths[folderName] || folderName;
    return api.post('/open-folder', { path: folderPath });
  },
};

// Notifications API endpoints
export const notificationsAPI = {
  get: () => api.get('/notifications'),
  markRead: () => api.post('/notifications/mark-read'),
  markSingleRead: (id) => api.post('/notifications/mark-single-read', { id }),
  clear: () => api.post('/notifications/clear'),
  test: () => api.post('/notifications/test'),
};

export default api;
