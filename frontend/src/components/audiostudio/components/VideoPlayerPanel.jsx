import React, { useState, useEffect } from "react";
import { Video, Maximize2, Minimize2 } from "lucide-react";
import { BACKEND_URL } from "../../../config";

export function VideoPlayerPanel({
  videoFile,
  videoRef,
  videoExpanded,
  setVideoExpanded,
  videoWidth,
  setVideoWidth,
  isPlayingRef
}) {
  const [isResizing, setIsResizing] = useState(false);

  useEffect(() => {
    if (!isResizing) return;
    const onMouseMove = (e) => {
      const newWidth = Math.max(260, Math.min(600, e.clientX));
      setVideoWidth(newWidth);
    };
    const onMouseUp = () => setIsResizing(false);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [isResizing, setVideoWidth]);

  if (!videoFile) return null;

  return (
    <div
      className={`relative bg-[#060a14] border-r border-gray-800/90 flex flex-col shrink-0 transition-[width] duration-75 select-none ${
        videoExpanded ? "" : "w-10 overflow-hidden"
      }`}
      style={{ width: videoExpanded ? `${videoWidth}px` : "40px" }}
    >
      {/* Header */}
      <div className="px-3 py-2 bg-[#090e1c] border-b border-gray-800 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-bold text-gray-300 truncate">
          <Video className="w-3.5 h-3.5 text-blue-400 shrink-0" />
          {videoExpanded && <span className="truncate">Reference Video</span>}
        </div>
        <button
          onClick={() => setVideoExpanded(!videoExpanded)}
          className="p-1 text-gray-400 hover:text-white rounded hover:bg-white/5 transition"
          title={videoExpanded ? "Collapse Video Panel" : "Expand Video Panel"}
        >
          {videoExpanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Video Content */}
      {videoExpanded ? (
        <div className="flex-1 flex flex-col justify-center items-center p-3 bg-black/80">
          {videoFile ? (
            <>
              <video
                ref={videoRef}
                src={`${BACKEND_URL}/api/project/stream-video?file=${encodeURIComponent(videoFile)}`}
                crossOrigin="anonymous"
                preload="auto"
                muted
                playsInline
                onPlay={() => {
                  if (videoRef.current && !isPlayingRef.current) {
                    videoRef.current.pause();
                  }
                }}
                className="w-full max-h-[260px] object-contain rounded-lg shadow-xl bg-black border border-gray-900"
              />
              <div className="mt-2 text-[10px] text-gray-500 font-mono text-center truncate w-full">
                {videoFile.split(/[/\\]/).pop()}
              </div>
            </>
          ) : (
            <div className="text-center py-8 text-gray-600 text-xs font-mono">
              No video loaded
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center cursor-pointer" onClick={() => setVideoExpanded(true)}>
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest rotate-90 whitespace-nowrap">
            Video Sync
          </span>
        </div>
      )}

      {/* Resize Handle */}
      {videoExpanded && (
        <div
          onMouseDown={() => setIsResizing(true)}
          className="absolute top-0 bottom-0 right-0 w-1.5 cursor-ew-resize hover:bg-blue-500/50 transition-colors z-30"
          title="Drag to resize video preview width"
        />
      )}
    </div>
  );
}
