# Frontend Changelog

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
