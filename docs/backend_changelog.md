# Backend Changelog

## [0.0.11] - 2026-03-03 ⚙️

### [Fixed]
- **Video Extension Bug**: Fixed issue where video downloads failed at 99% due to incorrect merged file extension detection.
- **Robust File Detection**: Implemented 3-stage fallback (Exact -> Extension Try -> Time modified) to find merged media files.
- **Private/Deleted Video Filtering**: Playlist analysis now automatically skips unavailable videos.
- **Cleaner Filenames**: Stripped `.part` suffixes in `progress_hook` for better UI display.
- **Rate Limiting**: Reduced inter-download delay from 30-50s to 3-7s.
- **Sticky Status**: Fixed 404 error when cancelling tasks from a previous session.

### [Added]
- **Queue Control API**: Implemented `POST /api/queue/stop` to clear pending items.
- **Force Cancel**: Added logic to mark orphaned/stuck tasks as cancelled.

---
## [0.0.10] - 2026-03-03 🐛
- **Stuck N/A Metadata**: Fixed relative vs absolute path in `metadata_cache.json`.
- **Library Scan**: Fixed exclusion logic to show completed files.
