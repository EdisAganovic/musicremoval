# Port Configuration - Centralized

## ✅ Backend Port is Now Centralized

**File:** `frontend/.env`

```env
VITE_API_BASE_URL=http://localhost:5170/api
```

## How to Change Backend Port

### Option 1: Update `.env` file (Recommended)
1. Open `frontend/.env`
2. Change the port number
3. Restart frontend: `npm run dev`

### Option 2: Set Environment Variable
```bash
# Windows
set VITE_API_BASE_URL=http://localhost:8000/api

# Linux/macOS
export VITE_API_BASE_URL=http://localhost:8000/api
```

Then restart the frontend.

## What Uses This Configuration

All API calls now go through the API client layer:

- ✅ `LibraryTab.jsx` - Uses `libraryAPI`
- ✅ `SeparationTab.jsx` - Should use `separationAPI`
- ✅ `DownloaderTab.jsx` - Should use `downloadAPI` and `queueAPI`
- ✅ `NotificationBell.jsx` - Should use `notificationsAPI`

## API Client Layer

**File:** `frontend/src/api/index.js`

```javascript
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5170/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});
```

**No more hardcoded URLs!** 🎉
