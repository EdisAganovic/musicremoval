import React from "react";
import { Download, ExternalLink, FileAudio, FileVideo, Music } from "lucide-react";
import { BACKEND_URL } from "../../../config";

export function ExportPreviewModal({
  show,
  onClose,
  data
}) {
  if (!show || !data) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-[#0f172a] border border-blue-500/40 rounded-2xl w-full max-w-xl p-6 shadow-2xl space-y-5 text-gray-200">
        <div className="flex justify-between items-center border-b border-gray-800 pb-3">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            {data.type === "video" ? (
              <FileVideo className="w-5 h-5 text-purple-400" />
            ) : (
              <FileAudio className="w-5 h-5 text-blue-400" />
            )}
            {data.title || "Export Result Preview"}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">✕</button>
        </div>

        {/* Media Preview Box */}
        <div className="bg-black/60 border border-gray-800 rounded-xl p-4 flex flex-col items-center justify-center min-h-[160px]">
          {data.type === "video" ? (
            <video
              src={`${BACKEND_URL}${data.url}`}
              controls
              autoPlay
              className="w-full max-h-64 rounded-lg bg-black object-contain shadow-md"
            />
          ) : (
            <div className="w-full space-y-4">
              <div className="flex items-center justify-center gap-3 text-blue-400">
                <Music className="w-8 h-8 animate-pulse" />
                <span className="font-semibold text-sm">Master Mixdown Audio Preview</span>
              </div>
              <audio
                src={`${BACKEND_URL}${data.url}`}
                controls
                autoPlay
                className="w-full h-10 accent-blue-500"
              />
            </div>
          )}
        </div>

        {/* Download Buttons */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
          <div className="text-xs text-gray-400">
            File: <span className="font-mono text-gray-300">{data.filename}</span>
          </div>

          <div className="flex items-center gap-2">
            {data.aacUrl && (
              <a
                href={`${BACKEND_URL}${data.aacUrl}`}
                download
                className="px-3.5 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition"
              >
                <Download className="w-3.5 h-3.5" /> Download AAC
              </a>
            )}

            <a
              href={`${BACKEND_URL}${data.url}`}
              download={data.filename}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg flex items-center gap-1.5 shadow-lg shadow-blue-500/20 transition"
            >
              <Download className="w-4 h-4" /> Download {data.type === "video" ? "Remuxed MP4" : "Master WAV"}
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
