"""
Pydantic Models for the backend API.
"""
from pydantic import BaseModel
from typing import List, Dict, Optional


class QueueItem(BaseModel):
    queue_id: str
    url: str
    format_type: str
    format_id: str = None
    subtitles: str = None
    auto_separate: bool = False
    status: str = "pending"  # pending, downloading, completed, failed
    task_id: str = None
    added_at: float = None


class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: float
    current_step: str
    result_files: List[str] = []
    metadata: dict = {}
    download_info: dict = {}
    url: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    processing_time: Optional[float] = None


class DownloadRequest(BaseModel):
    url: str
    format: str = "audio"
    format_id: Optional[str] = None
    subtitles: Optional[str] = None
    auto_separate: bool = False
    subfolder: Optional[str] = None


class DownloadCancelRequest(BaseModel):
    task_id: str


class QueueAddRequest(BaseModel):
    url: str
    format: str = "audio"
    format_id: Optional[str] = None
    subtitles: Optional[str] = None
    auto_separate: bool = False
    subfolder: Optional[str] = None
    title: Optional[str] = None


class QueueBatchRequest(BaseModel):
    videos: List[Dict[str, str]]
    format: str = "audio"
    format_id: Optional[str] = None
    subtitles: Optional[str] = None
    auto_separate: bool = False
    subfolder: Optional[str] = None


class QueueActionRequest(BaseModel):
    queue_id: Optional[str] = None


class FileActionRequest(BaseModel):
    file_path: Optional[str] = None
    path: Optional[str] = None


class SeparateRequest(BaseModel):
    file_path: str
    model: str = "both"


class FolderScanRequest(BaseModel):
    folder_path: str


class FolderQueueUpdateRequest(BaseModel):
    queue_id: str
    file_id: str
    selected: bool


class FolderQueueRemoveRequest(BaseModel):
    queue_id: str
    file_id: str


class FolderQueueProcessRequest(BaseModel):
    queue_id: str
    model: str = "both"
    selected_files: Optional[List[str]] = None
    duration: Optional[int] = None


class DeleteFileRequest(BaseModel):
    task_id: str
    file_path: Optional[str] = None


class NotificationRequest(BaseModel):
    id: Optional[str] = None


class URLFormatRequest(BaseModel):
    url: str
    check_playlist: bool = False


class LibraryActionRequest(BaseModel):
    task_id: str
    path: Optional[str] = None
    folder: Optional[str] = None
