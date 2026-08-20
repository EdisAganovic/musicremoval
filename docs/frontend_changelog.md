# Frontend Changelog

## [0.0.18] - 2026-08-20 ⚡

### [Added]
- **Remove Silence (1s Padding) Toggle**: Added toggle switch to the Separation tab to automatically trim silence gaps from separated vocals while preserving a 1.0s margin before and after vocal phrases for smooth, natural listening flow. Supported in single-file upload, library file selection, and batch folder queues.

---

## [0.0.17] - 2026-07-10 🛠️

### [Added]
- **Instrumental/Karaoke toggle**: New "Also Export Instrumental" switch in the Separation tab. When the backend finishes, a "Play instrumental" button appears alongside the existing Play/Open Folder actions if a karaoke track was produced.
- **Quick Preview mode**: New toggle + seconds input (single-file mode only) lets you process just the first N seconds of a file to A/B Spleeter vs Demucs vs Both before committing to the full run.
- **Bulk "Separate Selected"**: Library tab multi-select now has a "Separate N" button next to bulk delete. It builds a batch via the new `/api/folder/scan-files` + `/api/folder-queue/process` endpoints and hands the running batch off to the Separation tab for progress tracking.
- **Library pagination**: New page-size selector (25/50/100/250) with prev/next controls under the file table, so large libraries don't render every row at once.

### [Fixed]
- **Duplicate API method**: Removed a dead duplicate `libraryAPI.delete` definition in `api/index.js` that silently shadowed the real one.
- **Fragile global `event` reference**: The "Copy as Markdown" button in the System Info modal read the deprecated global `event` object instead of its own handler argument.
- **Cancelled downloads showing as failed**: Queue items now render a distinct "CANCELLED" badge/icon instead of falling into the "FAILED" state.
- **Idle polling overhead**: `DownloaderTab`'s three always-on polling intervals (200ms/1s/2s for download status, active downloads, and queue) now skip their network call while the tab/document is hidden, matching the pattern already used for notifications and console logs.

---

## [0.1.4] - 2026-05-07 🎯

### [Added]
- **Resume Badge**: Folder scan results now show "(ALREADY PROCESSED)" for files that already have output in `nomusic/`. These files are auto-deselected.
- **Random Delay Toggle**: New toggle switch in the downloader tab to enable/disable anti-bot random delays between queue downloads.

### [Fixed]
- **Subfolder State**: Fixed `playlistSubfolder` vs `subfolder` state variable — custom subfolder input is no longer bypassed when downloading from playlists.

---

## [0.0.13] - 2026-03-07 🚀

### [Added]
- **Emerald Green Theme**: Complete visual theme overhaul. All primary accents, gradients, search highlights, and component borders transitioned to emerald green.
- **Interactive State Refinement**: Added better tooltips and hover effects to the Library list items.

### [Fixed]
- **Theme Consistency**: Applied the emerald green theme to the search focus bar and active pagination indicators.

---

## [0.0.12] - 2026-03-07 🚀

### [Fixed]
- **Version Display**: App header now correctly displays `v0.0.12`, synced across the entire stack.
- **UI Responsiveness**: Improved interface stability during long-running background synchronization tasks.

---


### [Added]
- **Diagnostics Panel**: New modal accessible via System Info → Diagnostics button. Shows CUDA, packages, FFmpeg, disk, model files, and live Demucs test.
- **TIMEOUT Badge**: Orange status badge for sections that timed out during diagnostics.
- **Copy Report**: One-click copy of full diagnostic report as markdown for sharing.
- **Loading Hints**: "CUDA and Demucs checks may take up to 20 seconds" shown during diagnostics loading.

### [Fixed]
- **Diagnostics Timeout**: Increased axios timeout from 30s → 60s to accommodate slow machines where torch import takes 20s.
- **Timed Out Sections**: CUDA and Demucs sections now show orange timeout banner with recovery advice instead of failing silently.
- **Spinner Squashing**: Added `flex-shrink-0` to all loading spinners in the downloader tab. Prevents icons from shrinking when displayed alongside long status text like "Analyzing...".

---
## [0.0.11] - 2026-03-03 🎨

### [Added]
- **Cancel All Button**: New button in Active Downloads to halt current tasks and clear queue.
- **Force Cancellation UI**: Handles cancelling of stuck tasks even after server restarts.

### [Fixed]
- **Subfolder Support**: Fixed "Download Now" bypassing the custom subfolder field.
- **Playlist Progress Persistence**: Fixed polling state where playlist index (e.g. 1/41) would disappear.
- **Duplicate Handlers**: Cleaned up duplicate `handleCancelDownload` and `handleCancelAll` definitions.

---
## [0.0.10] - 2026-03-03 🔧
- **System Info Footer**: FDK_AAC installation status rendered inline.
- **Separation Icon**: Swapped visual elements to `AudioLines`.
