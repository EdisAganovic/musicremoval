# Frontend Changelog

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
