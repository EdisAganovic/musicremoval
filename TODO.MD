# TODO - Codebase Improvements

> Last Updated: 2026-03-01

---

## ✅ COMPLETED

- [x] Silent polling failures fixed
- [x] yt-dlp errors now visible
- [x] Path traversal security fixed
- [x] Temp file leaks fixed
- [x] FFmpeg errors now visible
- [x] Queue polling errors handled
- [x] Format file size preview
- [x] Invert selection button
- [x] Tooltips on disabled buttons
- [x] Standardized error language (English)
- [x] Auto-scroll batch list
- [x] Environment configuration (.env)
- [x] API client layer created
- [x] Remember format for video (checkbox)
- [x] Video ID display in downloader
- [x] Compact UI (smaller header, smoother transitions)
- [x] Removed YT Downloader header
- [x] Library table layout (compact)
- [x] Folder filter (Download / NoMusic)
- [x] Open folder quick actions
- [x] Hide separate button for nomusic files
- [x] Backend port changed to 5170
- [x] **Centralized port configuration** - No more hardcoded URLs!
- [x] **Playlist/Channel Download Support** - With confirmation modal

---

## 🎯 REMAINING IMPROVEMENTS

### MEDIUM Priority

#### 1. Replace alert() with Toast Notifications
**Files:** `LibraryTab.jsx`, `SeparationTab.jsx`

**Issue:** Using `alert()` for errors (10 instances).

**Improvement:** Add react-hot-toast for better UX.

---

#### 2. Replace window.confirm() with Modal
**File:** `LibraryTab.jsx`

**Issue:** Using `window.confirm()` for delete confirmation (2 instances).

**Improvement:** Create reusable modal component.

---

#### 3. Loading State for Library
**File:** `frontend/src/components/LibraryTab.jsx`

**Issue:** Shows "Loading..." text only.

**Improvement:** Add skeleton table rows or spinner.

---

### LOW Priority

#### 4. Keyboard Shortcuts
**Files:** All components

**Missing:**
- `Ctrl/Cmd + Enter` - Start action
- `Escape` - Cancel/reset
- `Ctrl/Cmd + V` - Auto-paste URL

---

#### 5. Search Improvements
**File:** `frontend/src/components/LibraryTab.jsx`

**Current:** Only searches filename.

**Improvement:** Search by duration, quality, date.

---

#### 6. Batch Operations Status
**File:** `frontend/src/components/SeparationTab.jsx`

**Issue:** No way to see overall batch progress at a glance.

**Improvement:** Add summary bar (X completed, Y failed, Z remaining).

---

#### 7. Error Recovery
**Files:** All components

**Issue:** When backend is down, user sees repeated errors.

**Improvement:** Add "Reconnect" button after connection lost.

---

## 📊 Summary

| Priority | Count | Estimated Time |
|----------|-------|----------------|
| **MEDIUM** | 3 | ~2 hours |
| **LOW** | 4 | ~3 hours |
| **TOTAL** | 7 | ~5 hours |

---

## 🎯 Recommended Next Steps

1. **Toast Notifications** - Replace alerts, major UX improvement
2. **Loading State** - Quick win, improves UX
3. **Confirmation Modal** - Replace window.confirm() for consistency

---

## 🔧 Configuration

**Backend Port:** Defined in `frontend/.env`
```env
VITE_API_BASE_URL=http://localhost:5170/api
```

**To change port:**
1. Edit `frontend/.env`
2. Restart frontend (`npm run dev`)
3. Done! No more manual URL changes.

---

## 🎉 Latest Feature: Playlist/Channel Download

### What Was Added:

**Backend (`backend/main.py`):**
- ✅ Updated `/api/yt-formats` to detect playlist/channel URLs
- ✅ Returns playlist info with video list
- ✅ Added `/api/queue/add-batch` endpoint for bulk adding
- ✅ Added `format_duration()` helper function

**Frontend (`frontend/src/components/DownloaderTab.jsx`):**
- ✅ Detects playlist/channel URLs automatically
- ✅ Shows all videos with thumbnails and duration
- ✅ Select/deselect individual videos
- ✅ Select All / None buttons
- ✅ **Confirmation modal** before adding to queue
- ✅ Shows exact count: "Download X videos"

**API Client (`frontend/src/api/index.js`):**
- ✅ Added `queueAPI.addBatch()` method

### How It Works:

1. **User pastes playlist/channel URL**
2. **Click "Analyze"** → Fetches all videos
3. **Select videos** (or use Select All/None)
4. **Click "Add to Queue"** → Shows confirmation modal
5. **Modal shows:** "Are you sure you want to download 15 videos (out of 20 total)?"
6. **User confirms** → All selected videos added to queue
7. **Queue processes** videos one by one automatically

### Supported URLs:
- ✅ Playlists: `youtube.com/playlist?list=PL...`
- ✅ Channels: `youtube.com/@channel` or `youtube.com/channel/...`
- ✅ Mixes: `youtube.com/watch?v=...&list=RD...`
